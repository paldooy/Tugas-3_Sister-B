# Demonstrasi Distributed Lock Manager Berbasis Raft

## A. Pembukaan

Bagian ini menampilkan Distributed Lock Manager berbasis Raft. Tiga node berjalan dalam container dan saling berkomunikasi untuk memilih leader serta mengelola akses resource.

---


## B. Menjalankan Sistem

Pertama, saya jalankan seluruh service dengan Docker Compose.

```powershell
docker-compose -f docker/docker-compose.yml down -v 
docker-compose -f docker/docker-compose.yml up --build -d
```

Setelah itu, semua node aktif dan siap mengikuti leader election.

---


## 1. Menampilkan Proses Leader Election

Berikutnya, saya cek log untuk melihat leader election Raft.

```powershell
docker-compose -f docker/docker-compose.yml logs --no-color node3 | Select-String -Pattern "became LEADER|election timeout"
docker-compose -f docker/docker-compose.yml logs --no-color node2 | Select-String -Pattern "became LEADER|election timeout"
docker-compose -f docker/docker-compose.yml logs --no-color node1 | Select-String -Pattern "became LEADER|election timeout"
```

Output ini menunjukkan node yang timeout lalu terpilih sebagai leader. Catat port leader karena semua request lock harus dikirim ke sana.

Ini membuktikan Raft berjalan dan leader dipilih lewat voting mayoritas.

---

## 2. Demonstrasi Shared Lock

Setelah leader terbentuk, saya uji shared lock.

Shared lock mengizinkan beberapa client memakai resource yang sama.

---

### Client A Mengambil Shared Lock

Gunakan port leader. Contoh di bawah memakai port `5002` jika leader adalah node2.

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_shared","owner":"client-A","type":"shared"}'
```

`success: True` berarti client A berhasil mendapat shared lock.

---

### Client B Mengambil Shared Lock yang Sama

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_shared","owner":"client-B","type":"shared"}'
```

`success: True` juga muncul untuk client B.

Artinya shared lock memang bisa dipakai bersamaan.

---

### Mencoba Exclusive Lock Saat Shared Aktif

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_shared","owner":"client-C","type":"exclusive"}'
```

Hasilnya `success: False`.

Itu terjadi karena resource masih dipakai dalam mode shared.

---

### Melepaskan Shared Lock

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/lock/release `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_shared","owner":"client-A","type":"shared"}'

Invoke-RestMethod -Uri http://localhost:5002/api/lock/release `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_shared","owner":"client-B","type":"shared"}'
```

Setelah shared lock dilepas, resource kembali bebas.

---

## 3. Demonstrasi Exclusive Lock

Berikutnya, saya uji exclusive lock.

Exclusive lock hanya mengizinkan satu client pada satu waktu.

---

### Client Pertama Mengambil Lock

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_A","owner":"client-1","type":"exclusive"}'
```

`success: True` berarti client pertama berhasil mengambil lock.

---

### Client Lain Mencoba Mengakses Resource yang Sama

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_A","owner":"client-2","type":"exclusive"}'
```

Hasilnya `success: False`.

Sistem menolak karena resource sudah dikunci client lain.

---

### Konflik di Leader dengan Owner Berbeda

```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"resource_A","owner":"client-3","type":"exclusive"}'
```

Hasilnya tetap `success: False`.
Ini menegaskan exclusive lock hanya untuk satu client.

---

## 4. Demonstrasi Network Partition

Setelah mode normal, saya demonstrasikan network partition.

Di sini salah satu node dimatikan untuk mensimulasikan gangguan jaringan.

---

### Simulasi Pemutusan Node

Saya hentikan salah satu node, misalnya node1.

```powershell
docker stop docker-node1-1
```
Dengan node1 berhenti, cluster masih bisa berjalan selama mayoritas node aktif.

---

### Observasi Leader Setelah Partition

Lalu saya cek log untuk melihat apakah leader tetap ada atau berpindah.

```powershell
docker-compose -f docker/docker-compose.yml logs --no-color node2 | Select-String "became LEADER"
docker-compose -f docker/docker-compose.yml logs --no-color node3 | Select-String "became LEADER"
```

Hasil ini menunjukkan cluster masih punya leader. Jika leader putus, node lain akan memilih pengganti.

Ini membuktikan Raft menjaga ketersediaan selama quorum masih ada.

---

### Pengujian Lock Saat Partition

Berikutnya saya coba request lock saat partition.

 ```powershell
Invoke-RestMethod -Uri http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"partition_test","owner":"client-1","type":"exclusive"}'
```

Jika request berhasil, quorum masih terpenuhi.

Jika dikirim ke node non-leader, request ditolak dan konsistensi tetap terjaga.

---

### Penjelasan

Saat partition, hanya mayoritas node yang boleh lanjut. Node terisolasi tidak bisa jadi leader, jadi split-brain terhindar.

---

## 5. Demonstrasi Deadlock Detection

Berikutnya saya demo deadlock detection.

Deadlock terjadi saat client saling menunggu resource milik lawan.

---

### Skenario Deadlock

Saya pakai dua resource, R1 dan R2, serta dua client, A dan B.

Pertama, client A ambil lock pada R1.

```powershell
Invoke-RestMethod http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"R1","owner":"A","type":"exclusive"}'
```

Lalu client B ambil lock pada R2.

```powershell
Invoke-RestMethod http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"R2","owner":"B","type":"exclusive"}'

```

Di titik ini, masing-masing client memegang resource berbeda.

---

### Kondisi Waiting

Kemudian, client A mencoba mengambil resource R2 yang sudah dimiliki oleh B.

```powershell
Invoke-RestMethod http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"R2","owner":"A","type":"exclusive"}'
```

Hasilnya ditolak dengan alasan waiting karena resource masih dipakai.

---

### Terjadinya Deadlock

Selanjutnya, client B mencoba mengambil resource R1 yang dimiliki oleh A.

```powershell
Invoke-RestMethod http://localhost:5002/api/lock/acquire `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"R1","owner":"B","type":"exclusive"}'
```

Di tahap ini sistem mendeteksi deadlock.

Hasilnya `success: False` dengan alasan `Deadlock detected`.

---

### Penjelasan Konsep

Deadlock muncul karena siklus di wait-for graph:

- Client A menunggu resource yang dimiliki oleh B
- Client B menunggu resource yang dimiliki oleh A

Siklus ini membuat eksekusi berhenti. Sistem mendeteksinya lewat traversal graph lalu menolak request terakhir.

---

### Recovery dari Deadlock

Untuk recovery, salah satu lock dilepaskan.

```powershell
Invoke-RestMethod http://localhost:5002/api/lock/release `
-Method POST `
-ContentType "application/json" `
-Body '{"lock_id":"R1","owner":"A"}'
```

Setelah itu, client lain bisa mencoba lagi dan sistem kembali normal.

---

## 6. Kesimpulan Akhir

Kesimpulannya, sistem bisa mengelola lock dengan Raft, tetap jalan saat gangguan jaringan, dan mendeteksi deadlock.

Ini menunjukkan konsistensi, ketersediaan, dan kontrol akses resource sudah terpenuhi.