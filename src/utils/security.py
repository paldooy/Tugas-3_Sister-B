import base64
import json
from cryptography.fernet import Fernet
from typing import Dict, Any

from src.utils.config import Config

class SecurityManager:
    def __init__(self):
        # Derive a valid URL-safe base64-encoded 32-byte key
        key = Config.ENCRYPTION_KEY.encode('utf-8')[:32]
        if len(key) < 32:
            key = key.ljust(32, b'0')
        self.fernet = Fernet(base64.urlsafe_b64encode(key))

    def encrypt_payload(self, payload: Dict[str, Any]) -> str:
        """Encrypt JSON serializable payload to string."""
        json_payload = json.dumps(payload).encode('utf-8')
        return self.fernet.encrypt(json_payload).decode('utf-8')

    def decrypt_payload(self, encrypted_payload: str) -> Dict[str, Any]:
        """Decrypt string back to dictionary."""
        try:
            json_payload = self.fernet.decrypt(encrypted_payload.encode('utf-8'))
            return json.loads(json_payload.decode('utf-8'))
        except Exception as e:
            raise ValueError(f"Invalid or corrupted payload: {e}")

class RBACManager:
    # Simple role mapping for demonstration
    ROLES = {
        "admin": ["read", "write", "lock", "queue", "cache", "manage"],
        "node": ["read", "write", "lock", "queue", "cache"],
        "client": ["read", "write", "queue_push", "queue_pop", "cache_get"],
    }
    
    # In a real scenario, this would be backed by Redis or auth server
    USERS = {
        "node-0": "node",
        "node-1": "node",
        "node-2": "node",
        "node1": "node",
        "node2": "node",
        "node3": "node",
        "client-1": "client",
        "admin-1": "admin",
    }

    @classmethod
    def check_permission(cls, user_id: str, action: str) -> bool:
        role = cls.USERS.get(user_id)
        if not role:
            return False
        
        permissions = cls.ROLES.get(role, [])
        return action in permissions


def parse_allowed_node_certs(value: str) -> Dict[str, str]:
    allowed = {}
    if not value:
        return allowed
    for item in value.split(','):
        item = item.strip()
        if not item or ':' not in item:
            continue
        node_id, cert_fp = item.split(':', 1)
        allowed[node_id.strip()] = cert_fp.strip()
    return allowed


class NodeAuthManager:
    def __init__(self, allowed: Dict[str, str]):
        self.allowed = allowed

    @classmethod
    def from_config(cls):
        return cls(parse_allowed_node_certs(Config.ALLOWED_NODE_CERTS))

    def validate(self, sender_id: str, cert_fingerprint: str) -> bool:
        if not self.allowed:
            return True
        expected = self.allowed.get(sender_id)
        if not expected:
            return False
        return expected == (cert_fingerprint or "")
