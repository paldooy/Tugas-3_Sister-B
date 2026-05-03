import hashlib
import json
import os
import time
from typing import List, Dict, Any, Optional
import asyncio

from src.utils.config import Config
from src.utils.metrics import metrics_registry
from src.communication.message_passing import NetworkManager

class ConsistentHashing:
    def __init__(self, nodes: List[str], replicas: int = 3):
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []
        for node in nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)

    def add_node(self, node: str):
        for i in range(self.replicas):
            key = self._hash(f"{node}:{i}")
            self.ring[key] = node
            self.sorted_keys.append(key)
        self.sorted_keys.sort()

    def remove_node(self, node: str):
        for i in range(self.replicas):
            key = self._hash(f"{node}:{i}")
            if key in self.ring:
                del self.ring[key]
                self.sorted_keys.remove(key)

    def get_node(self, item: str) -> str:
        if not self.ring:
            return None
        hash_val = self._hash(item)
        for key in self.sorted_keys:
            if hash_val <= key:
                return self.ring[key]
        return self.ring[self.sorted_keys[0]]
    
    def get_replicas(self, item: str, count: int = 2):
        if not self.ring:
            return []

        hash_val = self._hash(item)

        # cari posisi awal
        start_idx = 0
        for i, key in enumerate(self.sorted_keys):
            if hash_val <= key:
                start_idx = i
                break

        nodes = []
        for i in range(count):
            idx = (start_idx + i) % len(self.sorted_keys)
            nodes.append(self.ring[self.sorted_keys[idx]])

        # hapus duplicate
        return list(dict.fromkeys(nodes))

class QueueNode:
    def __init__(self, node_id: str, peers: List[str], network: NetworkManager):
        self.node_id = node_id
        self.peers = peers
        self.network = network
        self.local_address = f"{self.node_id}:{Config.PORT}"
        
        all_nodes = [self.local_address] + peers
        self.hash_ring = ConsistentHashing(all_nodes)
        
        self.queues = {} # topic -> List of messages
        self.unacked = {} # msg_id -> (timestamp, msg) for at-least-once
        self.queue_file = os.path.join(Config.DATA_DIR, "queues.json")
        self._load_queues()
        self._tasks_started = False

    async def start(self):
        if self._tasks_started:
            return
        self._tasks_started = True
        asyncio.create_task(self._recovery_loop())

    def _load_queues(self):
        if os.path.exists(self.queue_file):
            with open(self.queue_file, 'r') as f:
                data = json.load(f)
                self.queues = data.get('queues', {})
                self.unacked = data.get('unacked', {})

    def _save_queues(self):
        with open(self.queue_file, 'w') as f:
            json.dump({'queues': self.queues, 'unacked': self.unacked}, f)

    def _queue_has_msg(self, topic: str, msg_id: str) -> bool:
        return any(m.get('id') == msg_id for m in self.queues.get(topic, []))

    def _store_local(self, topic: str, msg: Dict[str, Any]) -> bool:
        if not self._queue_has_msg(topic, msg['id']):
            self.queues.setdefault(topic, []).append(msg)
            self._save_queues()
            return True
        return False

    async def _recovery_loop(self):
        while True:
            await asyncio.sleep(5)
            now = time.time()
            to_requeue = []
            for msg_id, data in list(self.unacked.items()):
                ts = data['timestamp']
                msg = data['msg']
                # Timeout of 30 seconds for consumer ack
                if now - ts > 30:
                    topic = msg['topic']
                    to_requeue.append((topic, msg))
                    del self.unacked[msg_id]
            
            for topic, msg in to_requeue:
                if not self._queue_has_msg(topic, msg['id']):
                    self.queues.setdefault(topic, []).insert(0, msg)
            
            if to_requeue:
                self._save_queues()

    async def enqueue(self, topic: str, message: Dict[str, Any], replicate: bool = True) -> bool:
        if replicate:
            msg = {
                'id': f"{topic}_{time.time()}_{hash(str(message))}",
                'topic': topic,
                'data': message
            }
        else:
            if isinstance(message, dict) and {'id', 'topic', 'data'}.issubset(message.keys()):
                msg = message
            else:
                msg = {
                    'id': f"{topic}_{time.time()}_{hash(str(message))}",
                    'topic': topic,
                    'data': message
                }

        if not replicate:
            if self._store_local(topic, msg):
                metrics_registry.queue_enqueues += 1
            return True

        nodes = self.hash_ring.get_replicas(topic, 2)
        success = False

        for node in nodes:
            if node == self.local_address:
                if self._store_local(topic, msg):
                    metrics_registry.queue_enqueues += 1
                success = True
            else:
                host, port = node.split(':')
                resp = await self.network.send_message(
                    host,
                    int(port),
                    'queue_enqueue',
                    'queue',
                    {'topic': topic, 'message': msg, 'replicate': False}
                )
                if resp and resp.get('success'):
                    success = True

        return success

    async def dequeue(self, topic: str, allow_replica: bool = False) -> Optional[Dict[str, Any]]:
        nodes = self.hash_ring.get_replicas(topic, 2)

        primary_node = nodes[0]  # node utama
        is_replica = self.local_address in nodes

        # =========================
        # JIKA SAYA PRIMARY (ATAU REPLICA FAILOVER)
        # =========================
        if primary_node == self.local_address or (allow_replica and is_replica):
            if topic in self.queues and self.queues[topic]:
                metrics_registry.queue_dequeues += 1

                msg = self.queues[topic].pop(0)

                self.unacked[msg['id']] = {
                    'timestamp': time.time(),
                    'msg': msg
                }

                self._save_queues()
                return msg

            return None

        # =========================
        # JIKA BUKAN PRIMARY → FORWARD
        # =========================
        host, port = primary_node.split(':')

        resp = await self.network.send_message(
            host,
            int(port),
            'queue_dequeue',
            'queue',
            {'topic': topic, 'allow_replica': False}
        )

        if resp and resp.get('message'):
            return resp['message']

        # =========================
        # FAILOVER → KE REPLICA
        # =========================
        for replica in nodes[1:]:
            host, port = replica.split(':')

            resp = await self.network.send_message(
                host,
                int(port),
                'queue_dequeue',
                'queue',
                {'topic': topic, 'allow_replica': True}
            )

            if resp and resp.get('message'):
                return resp['message']

        return None

    async def ack(self, topic: str, msg_id: str, replicate: bool = True) -> bool:
        if not replicate:
            removed = False
            if msg_id in self.unacked:
                del self.unacked[msg_id]
                removed = True
            if topic in self.queues:
                before = len(self.queues[topic])
                self.queues[topic] = [m for m in self.queues[topic] if m['id'] != msg_id]
                if len(self.queues[topic]) != before:
                    removed = True
            if removed:
                self._save_queues()
            return removed

        nodes = self.hash_ring.get_replicas(topic, 2)
        success = False

        for node in nodes:
            if node == self.local_address:
                if await self.ack(topic, msg_id, replicate=False):
                    success = True
            else:
                host, port = node.split(':')
                resp = await self.network.send_message(
                    host,
                    int(port),
                    'queue_ack',
                    'queue',
                    {'topic': topic, 'msg_id': msg_id, 'replicate': False}
                )
                if resp and resp.get('success'):
                    success = True

        return success
