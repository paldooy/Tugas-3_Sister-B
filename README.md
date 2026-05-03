# Distributed Synchronization System

This is a comprehensive distributed synchronization system implementing advanced coordination primitives.

## Features

1. **Distributed Lock Manager**: Powered by the **Raft consensus algorithm**. Includes shared/exclusive lock support and wait-for graph deadlock detection.
2. **Distributed Queue System**: Uses **Consistent Hashing** for data distribution, handles node failures, and ensures at-least-once delivery with message persistence (saved to disk).
3. **Distributed Cache Coherence**: Implements the **MESI** protocol (Modified, Exclusive, Shared, Invalid) to maintain cache consistency across nodes with LRU eviction.
4. **Geo-Distributed System (Bonus)**: Network layer implements an artificial network partition and latency model representing deployments spread across Regions (US-East, EU-West, AP-South). Demonstrates delayed propagation over `aiohttp`.
5. **Security & Encryption (Bonus)**: Implements **AES GCM (Fernet)** for end-to-end payload encryption and **RBAC** (Role-Based Access Control) to secure inter-node and client access.
6. **Containerization**: Includes `Dockerfile` and `docker-compose.yml` for simplified setup and orchestration.

## Test Docs

- [C. Distributed Cache Coherence.md](C.%20Distributed%20Cache%20Coherence.md)
- [Geo-Distributed System.md](Geo-Distributed%20System.md)
- [Security & Encryption.md](Security%20%26%20Encryption.md)
- [D. Containerization.md](D.%20Containerization.md)

## Getting Started

### Prerequisites

* Docker
* Docker Compose

### Running the System

To start the system with 3 nodes and a Redis instance (for queueing backend if needed):

```bash
docker-compose -f docker/docker-compose.yml up --build
```

Nodes will run on ports `5001`, `5002`, and `5003`.

### Interacting with the API

You can interact with the exposed HTTP APIs on any of the nodes.
Examples using a local script or Postman:

**1. Queue System**
```bash
# Enqueue
curl -X POST http://localhost:5001/api/queue/enqueue -H "Content-Type: application/json" -d '{"topic": "tasks", "message": {"job": "build"}}'

# Dequeue
curl http://localhost:5001/api/queue/dequeue?topic=tasks
```

**2. Distributed Cache**
```bash
# Put
curl -X POST http://localhost:5002/api/cache/put -H "Content-Type: application/json" -d '{"key": "user_1", "value": "John"}'

# Get
curl http://localhost:5003/api/cache/get?key=user_1
```

**3. Metrics & ML Prediction**
```bash
# View the health, metrics, and regional configuration
curl http://localhost:5001/api/metrics
```

## Architecture

* **src/consensus/raft.py**: Implements Leader Election, Log Replication, Heartbeats.
* **src/nodes/lock_manager.py**: Relies on Raft replicated log to grant state machine distributed locks.
* **src/nodes/queue_node.py**: Consistent hashing routes topics to cluster owners. Memory-backed with JSON disk persistence.
* **src/nodes/cache_node.py**: Simple MESI-based invalidation scheme.
* **src/communication/message_passing.py**: Async HTTP server routing requests with integrated Geo-Distributed real-world latency simulators and E2E encryption.
* **src/utils/security.py**: Uses basic Fernet encryption over `aiohttp` payloads to demonstrate End-to-End Encryption.
