import asyncio
import time
import random
import logging
from typing import List, Dict, Any, Callable
from collections import defaultdict

from src.utils.config import Config
from src.communication.message_passing import NetworkManager

logger = logging.getLogger("Raft")


class RaftState:
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"


class RaftNode:
    def __init__(self, node_id: str, peers: List[str], network: NetworkManager):
        self.node_id = node_id
        self.peers = peers
        self.network = network

        # =========================
        # PERSISTENT STATE
        # =========================
        self.current_term = 0
        self.voted_for = None
        self.log = []

        # =========================
        # ROLE STATE
        # =========================
        self.state = RaftState.FOLLOWER

        # =========================
        # VOLATILE STATE (FIX)
        # =========================
        self.commit_index = -1      # 🔥 FIX
        self.last_applied = -1      # 🔥 FIX

        # =========================
        # LEADER STATE
        # =========================
        self.next_index = defaultdict(lambda: len(self.log))
        self.match_index = defaultdict(lambda: -1)

        # =========================
        # TIMERS
        # =========================
        self.election_timeout = random.uniform(1.5, 3.0)
        self.last_heartbeat = time.time()
        self.leader_id = None

        # =========================
        # CALLBACK
        # =========================
        self.on_apply = None
        self._tasks_started = False

    async def start(self):
        if self._tasks_started:
            return
        self._tasks_started = True
        asyncio.create_task(self._election_timer())
        asyncio.create_task(self._heartbeat_timer())

    def register_apply_callback(self, callback: Callable):
        self.on_apply = callback

    # =========================
    # ELECTION
    # =========================
    async def _election_timer(self):
        while True:
            await asyncio.sleep(0.1)
            if self.state != RaftState.LEADER and (time.time() - self.last_heartbeat) > self.election_timeout:
                logger.info(f"Node {self.node_id} election timeout, starting election.")
                await self._start_election()

    async def _start_election(self):
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(1.5, 3.0)

        votes = 1

        last_log_index = len(self.log) - 1
        last_log_term = self.log[-1]['term'] if self.log else 0

        tasks = []
        for peer in self.peers:
            host, port = peer.split(':')
            tasks.append(self.network.send_message(
                host, int(port), 'request_vote', 'lock', {
                    'term': self.current_term,
                    'candidate_id': self.node_id,
                    'last_log_index': last_log_index,
                    'last_log_term': last_log_term
                }
            ))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, dict) and resp.get('vote_granted'):
                votes += 1

        if self.state == RaftState.CANDIDATE and votes > (len(self.peers) + 1) // 2:
            logger.info(f"Node {self.node_id} became LEADER in term {self.current_term}")
            self.state = RaftState.LEADER
            self.leader_id = self.node_id

            for peer in self.peers:
                self.next_index[peer] = len(self.log)
                self.match_index[peer] = -1

            await self._send_heartbeats()

    # =========================
    # HEARTBEAT
    # =========================
    async def _heartbeat_timer(self):
        while True:
            await asyncio.sleep(0.5)
            if self.state == RaftState.LEADER:
                await self._send_heartbeats()

    async def _send_heartbeats(self):
        tasks = []

        for peer in self.peers:
            host, port = peer.split(':')

            prev_log_index = self.next_index[peer] - 1
            prev_log_term = self.log[prev_log_index]['term'] if prev_log_index >= 0 else 0

            entries = self.log[self.next_index[peer]:]

            tasks.append(self.network.send_message(
                host, int(port), 'append_entries', 'lock', {
                    'term': self.current_term,
                    'leader_id': self.node_id,
                    'prev_log_index': prev_log_index,
                    'prev_log_term': prev_log_term,
                    'entries': entries,
                    'leader_commit': self.commit_index
                }
            ))

        await asyncio.gather(*tasks, return_exceptions=True)

    # =========================
    # RPC HANDLERS
    # =========================
    async def handle_request_vote(self, payload: Dict) -> Dict:
        term = payload['term']
        candidate_id = payload['candidate_id']

        if term > self.current_term:
            self.current_term = term
            self.state = RaftState.FOLLOWER
            self.voted_for = None

        vote_granted = False

        if term == self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
            self.voted_for = candidate_id
            self.last_heartbeat = time.time()
            vote_granted = True

        return {'term': self.current_term, 'vote_granted': vote_granted}

    async def handle_append_entries(self, payload: Dict) -> Dict:
        term = payload['term']
        leader_id = payload['leader_id']

        if term >= self.current_term:
            self.current_term = term
            self.state = RaftState.FOLLOWER
            self.leader_id = leader_id
            self.last_heartbeat = time.time()

        success = True

        prev_log_index = payload['prev_log_index']

        if prev_log_index >= 0:
            if prev_log_index >= len(self.log) or \
               self.log[prev_log_index]['term'] != payload['prev_log_term']:
                success = False

        if success:
            entries = payload['entries']

            if entries:
                self.log = self.log[:prev_log_index + 1] + entries

            if payload['leader_commit'] > self.commit_index:
                self.commit_index = min(payload['leader_commit'], len(self.log) - 1)
                await self._apply_logs()

        return {'term': self.current_term, 'success': success}

    # =========================
    # APPLY LOG (FIX UTAMA)
    # =========================
    async def _apply_logs(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied]

            if self.on_apply:
                await self.on_apply(entry['command'])

    # =========================
    # CLIENT ENTRY POINT
    # =========================
    async def replicate(self, command: Any) -> bool:
        if self.state != RaftState.LEADER:
            return False

        entry = {
            'term': self.current_term,
            'command': command
        }

        self.log.append(entry)
        index = len(self.log) - 1

        # simplified commit (demo only)
        self.match_index[self.node_id] = index
        self.commit_index = index

        # 🔥 FIX: ensure apply happens
        await self._apply_logs()

        return True