## 1. Cache Coherence Protocol (MESI)

Bagian ini menunjukkan konsistensi cache antar node memakai MESI. Saya simpan data di node 1 lalu baca dari node lain untuk melihat apakah state cache tetap sinkron.

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"user_1","value":"Alice"}'
```

Lalu saya baca data yang sama dari node 2. Jika node 2 belum punya datanya, akan terjadi cache miss dan node akan meminta value dari peer.

```powershell
Invoke-RestMethod "http://localhost:5002/api/cache/get?key=user_1"
```

Jika node 2 tetap mengembalikan `Alice`, berarti konsistensi berhasil dan data masuk state shared.

## 2. Multiple Cache Nodes

Bagian ini menunjukkan cache bisa dipakai di beberapa node sekaligus. Saya simpan data di node 3 lalu baca dari node 1.

```powershell
Invoke-RestMethod -Uri http://localhost:5003/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"product_9","value":"Book"}'
```
Jika node 1 belum punya key itu, ia akan cache miss lalu meminta data dari node lain.

```powershell
Invoke-RestMethod "http://localhost:5001/api/cache/get?key=product_9"
```

Jika node 1 tetap mengembalikan `Book`, berarti cache terdistribusi dan bisa diakses dari node mana saja.

## 3. Invalidation dan Update Propagation

Bagian ini memperlihatkan invalidation saat data di-update. Saya simpan nilai awal di node 1, lalu update dari node lain.

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"session_x","value":"v1"}'
```

Lalu saya baca dari node 2 supaya data tersebar ke cache lain dalam state shared.

```powershell
Invoke-RestMethod "http://localhost:5002/api/cache/get?key=session_x"
```

Setelah itu, saya update dari node 2. Node lain yang masih menyimpan data lama akan di-invalidate.

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"session_x","value":"v2"}'
```

Terakhir, saya baca lagi dari node 1. Jika cache lama sudah invalid, node 1 akan mengambil value terbaru dari peer.

```powershell
Invoke-RestMethod "http://localhost:5001/api/cache/get?key=session_x"
```

Jika hasilnya `v2`, berarti invalidation dan update propagation berjalan benar.

## 4. Cache Replacement Policy (LRU)

Bagian ini menguji LRU. Saya jalankan ulang sistem dengan kapasitas kecil supaya eviction mudah terlihat.

```powershell
$env:CACHE_CAPACITY=2
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up --build -d
```

Setelah sistem berjalan, saya isi cache dengan k1 dan k2.

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"k1","value":"v1"}'

Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"k2","value":"v2"}'
```

Lalu saya tambahkan k3. Karena kapasitas hanya 2, item terlama yaitu k1 harus ter-evict.

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"k3","value":"v3"}'
```

Untuk membuktikannya, saya baca lagi k1.

```powershell
Invoke-RestMethod "http://localhost:5001/api/cache/get?key=k1"
```

Jika k1 tidak ditemukan, LRU berjalan benar.

Jika k1 masih ada, pastikan `CACHE_CAPACITY=2` aktif dan k3 memang sudah dijalankan setelah restart.

## 5. Performance Monitoring dan Metrics

Bagian terakhir menunjukkan monitoring cache. Saya lakukan operasi untuk memunculkan hit dan miss.

```powershell
Invoke-RestMethod "http://localhost:5001/api/cache/get?key=user_1"
Invoke-RestMethod "http://localhost:5001/api/cache/get?key=unknown_key"
```

Setelah itu, saya ambil metrics sistem.

```powershell
Invoke-RestMethod "http://localhost:5001/api/metrics" | ConvertTo-Json -Depth 5
```

Jika hits, misses, dan invalidations muncul, berarti monitoring cache aktif.