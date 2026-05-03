import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    NODE_ID = os.getenv("NODE_ID", "node-0")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    PEERS = os.getenv("PEERS", "").split(",") if os.getenv("PEERS") else []
    REGION = os.getenv("REGION", "us-east")

    # Cache
    CACHE_CAPACITY = int(os.getenv("CACHE_CAPACITY", 1000))
    
    # Security
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")  # 32 bytes for AES
    SECRET_TOKEN = os.getenv("SECRET_TOKEN", "super-secret-token")
    NODE_CERT_FINGERPRINT = os.getenv("NODE_CERT_FINGERPRINT", "")
    ALLOWED_NODE_CERTS = os.getenv("ALLOWED_NODE_CERTS", "")
    
    # Storage paths
    DATA_DIR = os.getenv("DATA_DIR", f"./data/{NODE_ID}")
    
    @classmethod
    def setup_data_dirs(cls):
        os.makedirs(cls.DATA_DIR, exist_ok=True)

Config.setup_data_dirs()
