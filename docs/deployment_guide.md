# Deployment Guide

This document describes how to deploy the Distributed Synchronization System using Docker and manually utilizing Python.

## Prerequisites
- Docker Engine >= 20.10
- Docker Compose >= 1.29
- Python 3.11+ (Local execution)
- Redis Server (Optionally provided via Docker)

## Configuration (`.env`)
The system expects several environment variables which are optionally loaded from a `.env` file via `python-dotenv`:

```ini
# Core Configuration
NODE_ID=node1
HOST=0.0.0.0
PORT=5000
REGION=us-east

# Peers Network Discovery (comma-separated <host>:<port>)
PEERS=node2:5000,node3:5000

# Redis Backing Store (if used)
REDIS_HOST=redis
REDIS_PORT=6379

# Security (32-byte key)
ENCRYPTION_KEY=0123456789abcdef0123456789abcdef
SECRET_TOKEN=super-secret-token

# Storage
DATA_DIR=./data/node1
```

## Running with Docker Compose (Recommended)
We provide a structured setup spanning 3 nodes (`node1`, `node2`, `node3`) attached to a single network bridged over `localhost`. The `docker-compose.yml` configures node locations artificially simulating `us-east`, `eu-west`, and `ap-south` respectively to showcase network partition and latency emulation capabilities.

**Execute:**
```bash
docker-compose -f docker/docker-compose.yml up --build -d
```

**Check Service Logs:**
```bash
docker-compose -f docker/docker-compose.yml logs -f node1
docker-compose -f docker/docker-compose.yml logs -f node2
```

## Running Locally (Manual Setup)
You can spawn individual nodes directly on your host machine. Make sure to vary the `PORT` and `NODE_ID` for each terminal session.

**Step 1: Install Dependencies**
```bash
pip install -r requirements.txt
```

**Step 2: Start a Redis Instance**
```bash
docker run -p 6379:6379 -d redis:alpine
```

**Step 3: Start Node 1 (us-east, port 5001)**
```bash
env NODE_ID=node1 REGION=us-east PORT=5001 PEERS=localhost:5002,localhost:5003 python src/nodes/base_node.py
```

**Step 4: Start Node 2 (eu-west, port 5002)**
```bash
env NODE_ID=node2 REGION=eu-west PORT=5002 PEERS=localhost:5001,localhost:5003 python src/nodes/base_node.py
```

**Step 5: Start Node 3 (ap-south, port 5003)**
```bash
env NODE_ID=node3 REGION=ap-south PORT=5003 PEERS=localhost:5001,localhost:5002 python src/nodes/base_node.py
```

## Troubleshooting

- Node cannot join cluster:
	- Verify `PEERS` environment variable uses correct host:port pairs and that target nodes are reachable.
	- Check node logs for `handshake` or `auth` failures; confirm `ENCRYPTION_KEY` and `SECRET_TOKEN` match across nodes.

- High replication latency or leader thrashing:
	- Ensure system time is synchronized (use NTP) across hosts to avoid election flapping.
	- Increase Raft heartbeat interval or tune election timeouts in `config.py` for unstable networks.

- Persistent storage issues (queues or cache not surviving restart):
	- Confirm `DATA_DIR` is writeable by the process and that disk is not full.
	- Inspect local JSON persistence files for corruption; use provided `utils/audit.py` to validate formats.

- Zipkin/tracing or monitoring missing metrics:
	- Ensure `METRICS_ENABLED=true` and that `METRICS_ENDPOINT` is reachable. Check `docs/api_spec.yaml` for metrics path `/api/metrics`.

