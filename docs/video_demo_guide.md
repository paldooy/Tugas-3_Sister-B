# Panduan Demonstrasi Video (Video Demonstration Guide)

Dokumen ini berisi panduan langkah demi langkah untuk merekam video demonstrasi yang memenuhi kriteria **Video Demonstration (Wajib - 10 poin)**. Pastikan durasi rekaman Anda berada di rentang **10 hingga 15 menit** dan menggunakan bahasa Indonesia yang jelas dan profesional.

---

## 1. Pendahuluan dan Tujuan (1-2 menit)
- **Perkenalan:** Sebutkan nama Anda, NIM (jika ada), dan judul proyek (Distributed Synchronization System).
- **Tujuan Sistem:** Jelaskan secara singkat bahwa sistem ini dibangun untuk mensimulasikan mekanisme sinkronisasi pada sistem terdistribusi (Distributed Lock, Queue, Cache) dengan penambahan fitur keamanan dan ketahanan terhadap segmentasi jaringan (Geo-Distributed).

## 2. Penjelasan Arsitektur Sistem (2-3 menit)
- **Tampilkan Diagram/Struktur Kode:** Tampilkan *file explorer* di VS Code dan jelaskan pembagian foldernya.
- **Komponen Utama:** 
  1. *Raft Consensus* untuk *Lock Manager*.
  2. *Consistent Hashing* untuk *Message Queue*.
  3. *MESI Protocol* untuk *Cache Coherence*.
- **Bonus Fitur:** Jelaskan implementasi **Geo-Distributed** yang mensimulasikan latensi antar-benua (misal: US-East ke EU-West) menggunakan *aiohttp*, serta implementasi **Security (End-to-End Encryption - AES GCM)** dan RBAC.

## 3. Live Demo Semua Fitur (5-7 menit) - *Core Demonstration*
Gunakan pembagian layar (split screen): satu sisi untuk terminal/log (Docker), satu sisi lagi untuk mengeksekusi request (Postman atau PowerShell).

> Catatan PowerShell: `curl` adalah alias dari `Invoke-WebRequest`, sehingga format `-H "Content-Type: application/json"` akan error. Gunakan `Invoke-RestMethod` (direkomendasikan) atau `curl.exe`.

### A. Inisialisasi Cluster dan Pemilihan Leader (Raft)
1. Buka terminal dan jalankan:
   ```powershell
   docker-compose -f docker/docker-compose.yml up --build -d
   ```
2. **Perlihatkan log Docker:** Tunjukkan ke kamera bagaimana `node1`, `node2`, dan `node3` mulai melakukan inisialisasi. 
3. **Sorot status Raft:** Tunjukkan baris log ketika node berstatus `FOLLOWER`, lalu transisi menjadi `CANDIDATE` (saat *election timeout*), hingga salah satu node memenangkan voting dan menjadi `LEADER` (misalnya: `Node node1 became LEADER in term 1`). Tunjukkan bahwa *heartbeat* rutin mulai dikirimkan.
4. **Temukan Leader (disarankan):**
   ```powershell
   docker-compose -f docker/docker-compose.yml logs --no-color node3 | Select-String -Pattern "became LEADER|election timeout"
   docker-compose -f docker/docker-compose.yml logs --no-color node2 | Select-String -Pattern "became LEADER|election timeout"
   docker-compose -f docker/docker-compose.yml logs --no-color node1 | Select-String -Pattern "became LEADER|election timeout"
   ```

### B. Demonstrasi DLM (Distributed Lock Manager)
1. **Acquire Lock (Leader):** Jalankan API Lock pada node yang menjadi *Leader* (contoh: `node3`).
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5003/api/lock/acquire -Method POST -ContentType "application/json" -Body '{"lock_id":"resource_A","owner":"client-1","type":"exclusive"}'
   ```
2. **Penjelasan:** Jelaskan bahwa *Leader* menulis perintah ke log Raft, lalu mereplikasi ke follower sebelum keputusan final.
3. **Demonstrasi Follower Ditolak:** Kirim request ke Follower (contoh: `node2`), tunjukkan respons `success: false`.
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5002/api/lock/acquire -Method POST -ContentType "application/json" -Body '{"lock_id":"resource_A","owner":"client-2","type":"exclusive"}'
   ```
4. **Konflik Lock:** Coba acquire lock yang sama (`resource_A`) dengan owner berbeda pada *Leader*.
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5003/api/lock/acquire -Method POST -ContentType "application/json" -Body '{"lock_id":"resource_A","owner":"client-3","type":"exclusive"}'
   ```
   Tunjukkan bahwa *response* bernilai `success: false` (ditolak).

### C. Demonstrasi Distributed Queue (Consistent Hashing)
1. **Enqueue Data:** Masukkan task ke node1.
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5001/api/queue/enqueue -Method POST -ContentType "application/json" -Body '{"topic":"order_events","message":{"order_id":123}}'
   ```
2. **Penjelasan Consistent Hashing:** Jelaskan bahwa algoritma *hash ring* secara otomatis mendistribusikan `order_events` ke node tertentu sebagai koordinator *topic*-nya.
3. **Dequeue Data:** Tarik data dari node lain (misal node3).
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:5002/api/queue/dequeue?topic=order_events" -Method GET
   ```
   Tunjukkan bahwa sistem berhasil mengambil pesan tersebut dari node pemilik sebenarnya (*seamless routing* antar peer).

### D. Demonstrasi Cache Coherence (MESI)
1. **Put Cache (Status: Modified):**
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5001/api/cache/put -Method POST -ContentType "application/json" -Body '{"key":"product_1","value":"Laptop"}'
   ```
   Jelaskan bahwa ini akan membroadcast pesan *Invalidate* ke node lainnya.
2. **Get Cache dari Node Lain (Status berubah ke Shared):**
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:5002/api/cache/get?key=product_1" -Method GET
   ```
   Data akan merespon `"Laptop"`. Jelaskan ada protokol *Read* tersembunyi antar-node untuk menjaga agar data *up-to-date*.

## 4. Performance Testing & Status Metrik (2-3 menit)
1. Akses API Metrik dari terminal atau browser:
   ```powershell
   Invoke-RestMethod -Uri http://localhost:5001/api/metrics -Method GET
   ```
2. **Bahasa Demo:** "Di sini kita bisa melihat JSON yang merangkum *counters* performa sistem kita—jumlah *requests* dan *grants* pada Lock, jumlah *enqueue/dequeue* pada Queue, serta rasio *hits* dan *misses* pada Cache. Di metrik ini juga terlihat 'Region: us-east' (pada Node 1) yang menggambarkan Geo-Distributed setup kita."
3. **Soroti Latensi Bukti Geo-Distributed:** Jika memungkinkan, soroti bahwa aksi-aksi antar-node tertentu membutuhkan waktu ~90ms hingga ~200ms secara lokal berkat latensi yang disimulasikan di Network Layer.

## 5. Kesimpulan dan Tantangan (1-2 menit)
- **Ringkasan:** Rangkum bahwa sistem berhasil mensimulasikan Raft Consensus yang stabil, Queue yang tangguh, Cache koheren dengan sistem enkripsi E2E, serta replikasi *cross-region*.
- **Tantangan:** Jelaskan 1-2 tantangan teknis yang Anda hadapi selama pengembangan, misalnya:
  - *Tuning Election Timeout* Raft agar tidak *split vote* terus-menerus.
  - Memastikan *payload* terenkripsi (AES) dan didekripsi dengan baik via arsitektur asinkron (`aiohttp`) tanpa mengorbankan performa atau mendempetkan latensi.
- **Penutup:** Salam penutup dan ucapkan terima kasih.
