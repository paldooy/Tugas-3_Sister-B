import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class Metrics:
    def __init__(self):
        self.lock_requests = 0
        self.lock_grants = 0
        self.lock_denials = 0
        self.lock_releases = 0
        
        self.messages_sent = 0
        self.messages_received = 0
        
        self.queue_enqueues = 0
        self.queue_dequeues = 0
        
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_invalidations = 0

        self.last_reset = time.time()
        self.logger = logging.getLogger("Metrics")

    def log_metrics(self):
        self.logger.info(f"--- METRICS REPORT ---")
        self.logger.info(f"Locks: Req={self.lock_requests}, Grants={self.lock_grants}, Denials={self.lock_denials}, Releases={self.lock_releases}")
        self.logger.info(f"Queue: Enq={self.queue_enqueues}, Deq={self.queue_dequeues}")
        self.logger.info(f"Cache: Hits={self.cache_hits}, Misses={self.cache_misses}, Inv={self.cache_invalidations}")
        self.logger.info(f"Net: Sent={self.messages_sent}, Recv={self.messages_received}")
        self.logger.info(f"----------------------")

metrics_registry = Metrics()
