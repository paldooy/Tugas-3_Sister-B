"""Synthetic benchmarking harness

Generates sample latency/throughput data for three scenarios:
- single-node
- distributed (3-node)
- geo-distributed (3-node with higher inter-region latency)

The script produces PNG charts in `docs/images/` for inclusion in the performance report.
"""
import os
import numpy as np
import matplotlib.pyplot as plt


def synth_data(clients, base_throughput, base_latency, scale_with_nodes=1.0, jitter=0.05):
    th = base_throughput * (1 - 0.001 * clients) * scale_with_nodes
    th = np.maximum(th, 1.0)
    latency = base_latency * (1 + 0.01 * clients) / scale_with_nodes
    # add random jitter
    th = th * (1 + np.random.normal(0, jitter, size=th.shape))
    latency = latency * (1 + np.random.normal(0, jitter, size=latency.shape))
    return th, latency


def make_plots(clients_range, results, outdir):
    os.makedirs(outdir, exist_ok=True)

    # Throughput
    plt.figure(figsize=(8, 5))
    for label, (th, lat) in results.items():
        plt.plot(clients_range, th, marker='o', label=label)
    plt.xlabel('Concurrent Clients')
    plt.ylabel('Throughput (ops/sec)')
    plt.title('Throughput vs Concurrent Clients')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, 'throughput.png'))
    plt.close()

    # Latency
    plt.figure(figsize=(8, 5))
    for label, (th, lat) in results.items():
        plt.plot(clients_range, lat, marker='o', label=label)
    plt.xlabel('Concurrent Clients')
    plt.ylabel('Latency (ms)')
    plt.title('Latency vs Concurrent Clients')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, 'latency.png'))
    plt.close()

    # Scalability (throughput per node)
    plt.figure(figsize=(8, 5))
    nodes = np.array([1, 3, 5, 10])
    base = 10000
    scalability = base * (1 - 0.02 * (nodes - 1)) * nodes
    plt.plot(nodes, scalability, marker='o')
    plt.xlabel('Number of Nodes')
    plt.ylabel('Aggregate Throughput (ops/sec)')
    plt.title('Aggregate Throughput vs Cluster Size (Synthetic)')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, 'scalability.png'))
    plt.close()


def main():
    clients = np.array([10, 50, 100, 200, 400])

    # Scenario: single-node (no replication overhead)
    th_single, lat_single = synth_data(clients, base_throughput=12000.0 / (1 + 0.0005 * clients), base_latency=10.0, scale_with_nodes=1.0)

    # Scenario: distributed (3 nodes) - slight replication overhead but better throughput scaling
    th_dist, lat_dist = synth_data(clients, base_throughput=10000.0 / (1 + 0.0004 * clients), base_latency=15.0, scale_with_nodes=1.1)

    # Scenario: geo-distributed (3 nodes across regions) - higher latency, similar throughput
    th_geo, lat_geo = synth_data(clients, base_throughput=9000.0 / (1 + 0.0006 * clients), base_latency=40.0, scale_with_nodes=0.95)

    results = {
        'single-node': (th_single, lat_single),
        'distributed-3node': (th_dist, lat_dist),
        'geo-distributed-3node': (th_geo, lat_geo),
    }

    outdir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'images')
    outdir = os.path.abspath(outdir)
    make_plots(clients, results, outdir)
    print('Charts written to', outdir)


if __name__ == '__main__':
    main()
