## Geo-Distributed System

Bagian ini menunjukkan cluster multi-region. Tiga node dipetakan ke `us-east`, `eu-west`, dan `ap-south`, lalu saya cek `/health` untuk memastikan region tiap node sudah sesuai.

```powershell
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up --build -d

Invoke-RestMethod http://localhost:5001/health
Invoke-RestMethod http://localhost:5002/health
Invoke-RestMethod http://localhost:5003/health
```

Hasilnya memastikan node hidup dan metadata region sesuai deployment.

Latency-aware routing diuji dengan operasi yang memicu komunikasi antar-node lalu diukur memakai `Measure-Command`. Jika lintas region lebih lambat, berarti simulasi delay bekerja.

```powershell
Measure-Command {
    Invoke-RestMethod -Uri http://localhost:5001/api/queue/enqueue `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"topic":"geo_test_1","message":"hello"}'
}

Measure-Command {
    Invoke-RestMethod -Uri http://localhost:5001/api/queue/enqueue `
    -Method POST `
    -ContentType "application/json" `
    -Body '{"topic":"geo_test_2","message":"hello"}'
}
```

Durasi yang lebih lama bukan error, melainkan bukti delay lintas region aktif.

Eventual consistency ditunjukkan lewat cache update yang dibaca dari node berbeda. Saya tulis nilai awal, lalu update dari node lain.

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"geo_session","value":"v1"}'

Invoke-RestMethod "http://localhost:5003/api/cache/get?key=geo_session"

Invoke-RestMethod -Uri http://localhost:5003/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"geo_session","value":"v2"}'

Invoke-RestMethod "http://localhost:5001/api/cache/get?key=geo_session"
```

Kalau hasil akhirnya nilai terbaru, berarti konsistensi tercapai setelah propagasi selesai.

Untuk replication antar region, saya jalankan cache dan queue lalu cek metrics. Naiknya `net.sent` dan `net.recv` berarti ada komunikasi antar-node.

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"replica_key","value":"replica_value"}'

Invoke-RestMethod -Uri http://localhost:5002/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"replica_topic","message":"msg"}'

Invoke-RestMethod "http://localhost:5001/api/metrics" | ConvertTo-Json -Depth 5
```

Kalau metrics naik, berarti komunikasi antar-region memang terjadi.
