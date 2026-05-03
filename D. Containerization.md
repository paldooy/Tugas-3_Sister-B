## 1. Dockerfile untuk setiap komponen

Project ini memakai satu Dockerfile untuk node aplikasi karena lock, queue, dan cache berjalan dalam satu process. Redis memakai image resmi.

File terkait:
- docker/Dockerfile.node (app nodes)
- docker/docker-compose.yml (orchestration)

### Cara cek
```powershell
Get-Content docker/Dockerfile.node
```

Expected:
- Base image Python
- Install dependencies
- Jalankan src/nodes/base_node.py

## 2. docker-compose untuk orchestration

Semua service dijalankan oleh docker-compose.

### Cara cek
```powershell
Get-Content docker/docker-compose.yml
```

### Cara jalan
```powershell
docker-compose -f docker/docker-compose.yml up --build -d
```

Expected:
- Container redis + node1 + node2 + node3 berjalan
- Healthcheck OK

## 3. Scaling nodes secara dinamis

Scaling paling aman dilakukan dengan menambah service node baru dan menyesuaikan PEERS. Dengan cara ini jumlah node bisa ditambah atau dikurangi sesuai kebutuhan.

### Contoh langkah
1) Tambahkan service node4 di docker-compose.yml (copy dari node3, ubah NODE_ID dan port).
2) Update PEERS di semua node agar mengenal node baru.
3) Jalankan ulang compose.

Catatan: PEERS harus konsisten agar Raft dan cache invalidation tetap benar.

## 4. Environment configuration menggunakan .env

Docker Compose membaca file .env di root project. Contohnya sudah ada di .env.example.

### Cara pakai
```powershell
Copy-Item .env.example .env
```

Isi yang bisa diatur:
- CACHE_CAPACITY untuk test LRU
- ENCRYPTION_KEY / SECRET_TOKEN opsional
- NODE1_PORT, NODE2_PORT, NODE3_PORT untuk override port host

### Cara cek
```powershell
Get-Content .env
```
