import asyncio
from typing import Dict, Any
from src.consensus.raft import RaftNode, RaftState
from src.utils.metrics import metrics_registry


class LockManager:
    def __init__(self, node_id: str, raft_node: RaftNode):
        self.node_id = node_id
        self.raft = raft_node

        # lock_id -> {'exclusive': str | None, 'shared': set()}
        self.locks: Dict[str, Dict[str, Any]] = {}

        # wait-for graph: owner -> set(owner yang ditunggu)
        self.wait_for_graph: Dict[str, set] = {}

        # register raft apply callback
        self.raft.on_apply = self._apply_lock_command

    # =========================
    # APPLY (STATE MACHINE RAFT)
    # =========================
    async def _apply_lock_command(self, command: Dict[str, Any]):
        action = command.get('action')
        lock_id = command.get('lock_id')
        owner = command.get('owner')
        lock_type = command.get('type')

        if lock_id not in self.locks:
            self.locks[lock_id] = {'exclusive': None, 'shared': set()}

        if action == 'acquire':
            if lock_type == 'exclusive':
                self.locks[lock_id]['exclusive'] = owner
                self.locks[lock_id]['shared'].clear()

            elif lock_type == 'shared':
                self.locks[lock_id]['shared'].add(owner)

        elif action == 'release':
            if lock_type == 'exclusive':
                if self.locks[lock_id]['exclusive'] == owner:
                    self.locks[lock_id]['exclusive'] = None

            elif lock_type == 'shared':
                self.locks[lock_id]['shared'].discard(owner)

            # 🔥 cleanup kalau kosong
            if (
                self.locks[lock_id]['exclusive'] is None and
                len(self.locks[lock_id]['shared']) == 0
            ):
                del self.locks[lock_id]

    # =========================
    # WAIT-FOR GRAPH
    # =========================
    def _add_wait_edge(self, waiter: str, holder: str):
        if waiter == holder:
            return
        self.wait_for_graph.setdefault(waiter, set()).add(holder)

    def _clear_wait_edges(self, owner: str):
        self.wait_for_graph.pop(owner, None)
        for deps in self.wait_for_graph.values():
            deps.discard(owner)

    def _detect_deadlock(self) -> bool:
        visited = set()
        stack = set()

        def dfs(node):
            if node in stack:
                return True
            if node in visited:
                return False

            visited.add(node)
            stack.add(node)

            for neighbor in self.wait_for_graph.get(node, []):
                if dfs(neighbor):
                    return True

            stack.remove(node)
            return False

        for node in self.wait_for_graph:
            if dfs(node):
                return True

        return False

    # =========================
    # ACQUIRE LOCK
    # =========================
    async def acquire_lock(self, lock_id: str, owner: str, lock_type: str = 'exclusive') -> dict:
        metrics_registry.lock_requests += 1

        # hanya leader yang boleh handle
        if self.raft.state != RaftState.LEADER:
            metrics_registry.lock_denials += 1
            return {"success": False, "reason": "Not leader"}

        lock_state = self.locks.get(lock_id, {'exclusive': None, 'shared': set()})

        # =========================
        # CEK KONFLIK
        # =========================

        if lock_type == 'exclusive':
            # konflik dengan exclusive lain
            if lock_state['exclusive'] and lock_state['exclusive'] != owner:
                self._add_wait_edge(owner, lock_state['exclusive'])

                if self._detect_deadlock():
                    metrics_registry.lock_denials += 1
                    return {"success": False, "reason": "Deadlock detected"}

                metrics_registry.lock_denials += 1
                return {"success": False, "reason": "Lock conflict (waiting)"}

            # konflik dengan shared
            if lock_state['shared']:
                for o in lock_state['shared']:
                    if o != owner:
                        self._add_wait_edge(owner, o)

                if self._detect_deadlock():
                    metrics_registry.lock_denials += 1
                    return {"success": False, "reason": "Deadlock detected"}

                metrics_registry.lock_denials += 1
                return {"success": False, "reason": "Lock conflict (shared exists)"}

        elif lock_type == 'shared':
            # konflik dengan exclusive
            if lock_state['exclusive'] and lock_state['exclusive'] != owner:
                self._add_wait_edge(owner, lock_state['exclusive'])

                if self._detect_deadlock():
                    metrics_registry.lock_denials += 1
                    return {"success": False, "reason": "Deadlock detected"}

                metrics_registry.lock_denials += 1
                return {"success": False, "reason": "Lock conflict (exclusive exists)"}

        # =========================
        # REPLICATE VIA RAFT
        # =========================
        success = await self.raft.replicate({
            'action': 'acquire',
            'lock_id': lock_id,
            'owner': owner,
            'type': lock_type
        })

        if success:
            self._clear_wait_edges(owner)
            metrics_registry.lock_grants += 1
            return {"success": True}

        metrics_registry.lock_denials += 1
        return {"success": False, "reason": "Replication failed"}

    # =========================
    # RELEASE LOCK
    # =========================
    async def release_lock(self, lock_id: str, owner: str, lock_type: str = 'exclusive') -> dict:
        if self.raft.state != RaftState.LEADER:
            return {"success": False, "reason": "Not leader"}

        success = await self.raft.replicate({
            'action': 'release',
            'lock_id': lock_id,
            'owner': owner,
            'type': lock_type
        })

        if success:
            self._clear_wait_edges(owner)
            metrics_registry.lock_releases += 1
            return {"success": True}

        return {"success": False, "reason": "Replication failed"}