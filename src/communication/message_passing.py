import asyncio
import logging
from aiohttp import web
import aiohttp
from typing import Dict, Any, Callable

from src.utils.config import Config
from src.utils.security import SecurityManager, RBACManager, NodeAuthManager
from src.utils.audit import AuditLogger
from src.utils.metrics import metrics_registry

logger = logging.getLogger("Communication")

class NetworkManager:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.security = SecurityManager()
        self.node_auth = NodeAuthManager.from_config()
        self.audit = AuditLogger(node_id, Config.DATA_DIR)
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.routes = {}
        
        # Default route handler for all inter-node communication
        self.app.router.add_post('/rpc', self.handle_rpc)
        
        # Handlers mapping: type -> Callable
        self.handlers = {}

    def _get_peer_region(self, peer_host: str) -> str:
        # Simple lookup: in practice, could be discovery or registry-based
        if 'node1' in peer_host: return 'us-east'
        if 'node2' in peer_host: return 'eu-west'
        if 'node3' in peer_host: return 'ap-south'
        return Config.REGION

    def _calculate_latency(self, region_a: str, region_b: str) -> float:
        if region_a == region_b:
            return 0.01  # 10ms local
        
        cross_region_latencies = {
            ('us-east', 'eu-west'): 0.09, # 90ms
            ('eu-west', 'us-east'): 0.09,
            ('us-east', 'ap-south'): 0.20, # 200ms
            ('ap-south', 'us-east'): 0.20,
            ('eu-west', 'ap-south'): 0.15, # 150ms
            ('ap-south', 'eu-west'): 0.15
        }
        return cross_region_latencies.get((region_a, region_b), 0.1)

    def register_handler(self, msg_type: str, handler: Callable):
        """Register a handler for a specific message type."""
        self.handlers[msg_type] = handler

    async def handle_rpc(self, request: web.Request) -> web.Response:
        """Handle incoming RPC requests."""
        body = {}
        try:
            body = await request.json()
            metrics_registry.messages_received += 1
            
            # Extract plain metadata
            sender_id = body.get('sender')
            action = body.get('action')
            encrypted_payload = body.get('payload')
            sender_cert = body.get('cert')

            if not self.node_auth.validate(sender_id, sender_cert):
                self.audit.log_event({
                    "direction": "in",
                    "sender": sender_id,
                    "action": action,
                    "status": "denied",
                    "reason": "invalid_cert",
                })
                return web.json_response({"error": "Unauthorized"}, status=403)
            
            # Auth
            if not RBACManager.check_permission(sender_id, action):
                self.audit.log_event({
                    "direction": "in",
                    "sender": sender_id,
                    "action": action,
                    "status": "denied",
                    "reason": "rbac",
                })
                return web.json_response({"error": "Unauthorized"}, status=403)
                
            # Decrypt
            payload = self.security.decrypt_payload(encrypted_payload)
            
            msg_type = payload.get('type')
            handler = self.handlers.get(msg_type)
            
            if handler:
                response_payload = await handler(payload)
                self.audit.log_event({
                    "direction": "in",
                    "sender": sender_id,
                    "action": action,
                    "type": msg_type,
                    "status": "ok",
                })
                # Encrypt response
                enc_response = self.security.encrypt_payload(response_payload) if response_payload else None
                return web.json_response({"status": "success", "payload": enc_response})
            else:
                self.audit.log_event({
                    "direction": "in",
                    "sender": sender_id,
                    "action": action,
                    "type": msg_type,
                    "status": "error",
                    "reason": "no_handler",
                })
                return web.json_response({"error": f"No handler for type: {msg_type}"}, status=400)
                
        except Exception as e:
            logger.error(f"Error handling RPC: {e}")
            self.audit.log_event({
                "direction": "in",
                "sender": body.get('sender') if isinstance(body, dict) else None,
                "action": body.get('action') if isinstance(body, dict) else None,
                "status": "error",
                "reason": "exception",
            })
            return web.json_response({"error": str(e)}, status=500)

    async def start_server(self):
        """Start the HTTP server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, Config.HOST, Config.PORT)
        await self.site.start()
        logger.info(f"Node {self.node_id} listening on {Config.HOST}:{Config.PORT}")

    async def stop_server(self):
        """Stop the HTTP server."""
        if self.runner:
            await self.runner.cleanup()
            
    async def send_message(self, peer_host: str, peer_port: int, msg_type: str, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to a peer."""
        url = f"http://{peer_host}:{peer_port}/rpc"
        payload = {"type": msg_type, **data}
        encrypted = self.security.encrypt_payload(payload)
        
        request_body = {
            "sender": self.node_id,
            "action": action,
            "payload": encrypted,
            "cert": Config.NODE_CERT_FINGERPRINT
        }
        
        metrics_registry.messages_sent += 1
        
        try:
            async with aiohttp.ClientSession() as session:
                # Simulate Multi-Region Geographic Latency
                # In real scenario, routing across regions incurs physical delay
                peer_region = self._get_peer_region(peer_host)
                latency = self._calculate_latency(Config.REGION, peer_region)
                if latency > 0:
                    await asyncio.sleep(latency)
            
                async with session.post(url, json=request_body, timeout=2.0 + latency) as response:
                    if response.status == 200:
                        resp_json = await response.json()
                        enc_resp = resp_json.get('payload')
                        self.audit.log_event({
                            "direction": "out",
                            "recipient": f"{peer_host}:{peer_port}",
                            "action": action,
                            "type": msg_type,
                            "status": "ok",
                        })
                        if enc_resp:
                            return self.security.decrypt_payload(enc_resp)
                        return {}
                    else:
                        self.audit.log_event({
                            "direction": "out",
                            "recipient": f"{peer_host}:{peer_port}",
                            "action": action,
                            "type": msg_type,
                            "status": "error",
                            "reason": f"http_{response.status}",
                        })
                        logger.warning(f"Failed to send to {url}, Status: {response.status}")
                        return None
        except Exception as e:
            self.audit.log_event({
                "direction": "out",
                "recipient": f"{peer_host}:{peer_port}",
                "action": action,
                "type": msg_type,
                "status": "error",
                "reason": "exception",
            })
            logger.debug(f"Communication error with {url}: {e}")
            return None
