import asyncio
import uuid
import logging
from aiohttp import web

from src.utils.config import Config
from src.utils.metrics import metrics_registry
from src.communication.message_passing import NetworkManager
from src.consensus.raft import RaftNode
from src.nodes.lock_manager import LockManager
from src.nodes.queue_node import QueueNode
from src.nodes.cache_node import CacheNode

logger = logging.getLogger("FullNode")


class FullNode:
    def __init__(self):
        self.node_id = Config.NODE_ID
        self.peers = Config.PEERS
        self.region = Config.REGION

        self.network = NetworkManager(self.node_id)

        # Core components
        self.raft = RaftNode(self.node_id, self.peers, self.network)
        self.lock_mgr = LockManager(self.node_id, self.raft)
        self.queue_mgr = QueueNode(self.node_id, self.peers, self.network)
        self.cache_mgr = CacheNode(self.node_id, self.peers, self.network, capacity=Config.CACHE_CAPACITY)

        self._register_handlers()
        self._setup_client_api()

    # =========================
    # HANDLERS INTERNAL NODE
    # =========================
    def _register_handlers(self):
        # Raft
        self.network.register_handler('request_vote', self.raft.handle_request_vote)
        self.network.register_handler('append_entries', self.raft.handle_append_entries)

        # Queue
        async def handle_q_enq(p):
            res = await self.queue_mgr.enqueue(
                p['topic'],
                p['message'],
                replicate=p.get('replicate', True)
            )
            return {'success': res}

        async def handle_q_deq(p):
            res = await self.queue_mgr.dequeue(
                p['topic'],
                allow_replica=p.get('allow_replica', False)
            )
            return {'message': res}

        async def handle_q_ack(p):
            res = await self.queue_mgr.ack(
                p['topic'],
                p['msg_id'],
                replicate=p.get('replicate', True)
            )
            return {'success': res}

        self.network.register_handler('queue_enqueue', handle_q_enq)
        self.network.register_handler('queue_dequeue', handle_q_deq)
        self.network.register_handler('queue_ack', handle_q_ack)

        # Cache (MESI)
        async def handle_c_read(p):
            return await self.cache_mgr.handle_mesi_read(p['key'])

        async def handle_c_inv(p):
            return await self.cache_mgr.handle_mesi_invalidate(p['key'])

        self.network.register_handler('mesi_read', handle_c_read)
        self.network.register_handler('mesi_invalidate', handle_c_inv)

    # =========================
    # HTTP API (CLIENT)
    # =========================
    def _setup_client_api(self):
        app = self.network.app

        # Healthcheck (INI YANG KURANG SEBELUMNYA)
        app.router.add_get('/health', self.api_health)

        # Lock API
        app.router.add_post('/api/lock/acquire', self.api_lock_acquire)
        app.router.add_post('/api/lock/release', self.api_lock_release)

        # Queue API
        app.router.add_post('/api/queue/enqueue', self.api_queue_enqueue)
        app.router.add_get('/api/queue/dequeue', self.api_queue_dequeue)
        app.router.add_post('/api/queue/ack', self.api_queue_ack)

        # Cache API
        app.router.add_post('/api/cache/put', self.api_cache_put)
        app.router.add_get('/api/cache/get', self.api_cache_get)

        # Metrics
        app.router.add_get('/api/metrics', self.api_metrics)

    # =========================
    # HEALTH CHECK (FIX UTAMA)
    # =========================
    async def api_health(self, request):
        return web.json_response({
            "status": "ok",
            "node_id": self.node_id,
            "region": self.region
        })

    # =========================
    # LOCK API
    # =========================
    async def api_lock_acquire(self, request):
        data = await request.json()
        owner = data.get('owner', str(uuid.uuid4()))
        lock_type = data.get('type', 'exclusive')

        result = await self.lock_mgr.acquire_lock(
            data['lock_id'],
            owner,
            lock_type
        )

        response = {
            "success": result["success"],
            "lock_id": data['lock_id'],
            "owner": owner,
            "type": lock_type,
            "node_id": self.node_id,
            "region": self.region
        }

        # Tambahkan alasan kalau gagal
        if not result["success"]:
            response["reason"] = result.get("reason", "Lock already held or not granted by leader")

        return web.json_response(response)

    async def api_lock_release(self, request):
        data = await request.json()
        owner = data.get('owner', str(uuid.uuid4()))
        lock_type = data.get('type', 'exclusive')
        result = await self.lock_mgr.release_lock(
            data['lock_id'],
            owner,
            lock_type
        )

        response = {
            "success": result["success"],
            "lock_id": data['lock_id'],
            "owner": owner,
            "type": lock_type,
            "node_id": self.node_id,
            "region": self.region
        }

        if not result["success"]:
            response["reason"] = result.get("reason", "Unknown error")

        return web.json_response(response)

    # =========================
    # QUEUE API
    # =========================
    async def api_queue_enqueue(self, request):
        data = await request.json()
        success = await self.queue_mgr.enqueue(data['topic'], data['message'])
        return web.json_response({"success": success})

    async def api_queue_dequeue(self, request):
        topic = request.query.get('topic')
        msg = await self.queue_mgr.dequeue(topic)
        return web.json_response({"message": msg})

    async def api_queue_ack(self, request):
        data = await request.json()
        success = await self.queue_mgr.ack(data['topic'], data['msg_id'])
        return web.json_response({"success": success})

    # =========================
    # CACHE API
    # =========================
    async def api_cache_put(self, request):
        data = await request.json()
        await self.cache_mgr.put_value(data['key'], data['value'])
        return web.json_response({"success": True})

    async def api_cache_get(self, request):
        key = request.query.get('key')
        val = await self.cache_mgr.get_value(key)
        return web.json_response({"value": val})

    # =========================
    # METRICS
    # =========================
    async def api_metrics(self, request):
        return web.json_response({
            "region": self.region,
            "metrics": {
                "locks": {
                    "req": metrics_registry.lock_requests,
                    "grants": metrics_registry.lock_grants,
                    "denials": metrics_registry.lock_denials,
                    "releases": metrics_registry.lock_releases
                },
                "queue": {
                    "enq": metrics_registry.queue_enqueues,
                    "deq": metrics_registry.queue_dequeues
                },
                "cache": {
                    "hits": metrics_registry.cache_hits,
                    "misses": metrics_registry.cache_misses,
                    "invalidations": metrics_registry.cache_invalidations
                },
                "net": {
                    "sent": metrics_registry.messages_sent,
                    "recv": metrics_registry.messages_received
                }
            }
        })

    # =========================
    # START NODE
    # =========================
    async def start(self):
        logger.info(f"Starting FullNode {self.node_id} in {self.region}")

        await self.network.start_server()
        await self.raft.start()
        await self.queue_mgr.start()

        # keep alive
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    node = FullNode()
    asyncio.run(node.start())