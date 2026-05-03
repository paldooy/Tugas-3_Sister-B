import asyncio
from typing import Any, Dict, Optional
from collections import OrderedDict

from src.utils.metrics import metrics_registry
from src.communication.message_passing import NetworkManager

class MESIState:
    MODIFIED = "M"
    EXCLUSIVE = "E"
    SHARED = "S"
    INVALID = "I"

class CacheNode:
    def __init__(self, node_id: str, peers: list[str], network: NetworkManager, capacity: int = 1000):
        self.node_id = node_id
        self.peers = peers
        self.network = network
        self.capacity = capacity
        
        # LRU Cache dictionary: key -> (value, state)
        self.cache = OrderedDict()

    def _evict_if_needed(self):
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)

    async def get_value(self, key: str) -> Optional[Any]:
        if key in self.cache:
            val, state = self.cache[key]
            if state != MESIState.INVALID:
                metrics_registry.cache_hits += 1
                self.cache.move_to_end(key)
                return val
                
        metrics_registry.cache_misses += 1
        
        # In a real MESI, we would broadcast a read request to peers
        # For simplicity, if we don't have it, we fake a read broadcast
        tasks = []
        for peer in self.peers:
            host, port = peer.split(':')
            tasks.append(self.network.send_message(
                host, int(port), 'mesi_read', 'cache', {'key': key}
            ))
            
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        found_value = None
        for resp in responses:
            if isinstance(resp, dict) and resp.get('value') is not None:
                found_value = resp['value']
                break
                
        if found_value is not None:
            self._evict_if_needed()
            self.cache[key] = (found_value, MESIState.SHARED)
            
        return found_value

    async def put_value(self, key: str, value: Any, broadcast: bool = True):
        self._evict_if_needed()
        self.cache[key] = (value, MESIState.MODIFIED)
        
        if broadcast:
            # Broadcast invalidation
            tasks = []
            for peer in self.peers:
                host, port = peer.split(':')
                tasks.append(self.network.send_message(
                    host, int(port), 'mesi_invalidate', 'cache', {'key': key}
                ))
            await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_mesi_read(self, key: str) -> Dict[str, Any]:
        if key in self.cache:
            val, state = self.cache[key]
            if state in [MESIState.MODIFIED, MESIState.EXCLUSIVE]:
                self.cache[key] = (val, MESIState.SHARED)
            
            if state != MESIState.INVALID:
                return {'value': val, 'state': self.cache[key][1]}
        return {'value': None, 'state': MESIState.INVALID}

    async def handle_mesi_invalidate(self, key: str) -> Dict[str, Any]:
        if key in self.cache:
            val, _ = self.cache[key]
            self.cache[key] = (val, MESIState.INVALID)
            metrics_registry.cache_invalidations += 1
        return {'success': True}
