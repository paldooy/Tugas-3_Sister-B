## 1. Distributed Queue dengan Consistent Hashing
### Inti Konsep

Consistent hashing dipakai untuk menentukan node penyimpan topic.

- Setiap topic → di-hash → masuk ke ring
- Ring berisi node-node (node1, node2, node3)
- Topic akan “jatuh” ke satu node tertentu

👉 Artinya:

- Tidak semua node menyimpan semua data
- Data terdistribusi otomatis

### Kenapa penting?

Kalau node nambah / mati:

- Tidak semua data pindah
- Hanya sebagian kecil (minimal disruption)

### Cara Uji

### Step 1 — Kirim beberapa topic berbeda

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"A","message":"msg-A"}'
Invoke-RestMethod -Uri http://localhost:5001/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"B","message":"msg-B"}'
Invoke-RestMethod -Uri http://localhost:5001/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"C","message":"msg-C"}'
```

Penjelasan saat demo:


Saya mengirim beberapa topic berbeda untuk melihat topic mana masuk ke node tertentu lewat consistent hashing.

### Step 2 — Dequeue dari node berbeda

```powershell
Invoke-RestMethod "http://localhost:5002/api/queue/dequeue?topic=A"
Invoke-RestMethod "http://localhost:5003/api/queue/dequeue?topic=B"
```

Penjelasan:

Walau request dikirim dari node berbeda, data tetap diambil dari node pemiliknya.

## 2. Multiple Producers & Consumers

### Inti Konsep
- Banyak producer bisa enqueue
- Banyak consumer bisa dequeue
- Sistem tetap konsisten

👉 Ini simulasi dunia nyata (banyak client)

### Cara Uji

### Step 1 — Simulasi multiple producer

```powershell
Invoke-RestMethod http://localhost:5001/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"test","message":"P1"}'
Invoke-RestMethod http://localhost:5002/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"test","message":"P2"}'
Invoke-RestMethod http://localhost:5003/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"test","message":"P3"}'
```

Penjelasan:

Ini mensimulasikan beberapa producer yang mengirim message ke topic yang sama.

### Step 2 — Simulasi multiple consumer

```powershell
Invoke-RestMethod "http://localhost:5001/api/queue/dequeue?topic=test"
Invoke-RestMethod "http://localhost:5002/api/queue/dequeue?topic=test"
Invoke-RestMethod "http://localhost:5003/api/queue/dequeue?topic=test"
```

Penjelasan:

Multiple consumer mengambil message bergantian dari queue.

## 3. Message Persistence & Recovery

### Inti Konsep
- Data queue disimpan ke file (queues.json)
- Kalau node mati, data tetap ada
- Saat node hidup lagi, data bisa dipakai lagi

Ini bikin sistem durable.

### Cara Uji

### Step 1 — Enqueue

```powershell
Invoke-RestMethod http://localhost:5001/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"persist","message":"important"}'
```

### Step 2 — Stop node

```powershell
docker stop docker-node1-1
```

### Step 3 — Start lagi

```powershell
docker start docker-node1-1
```

### Step 4 — Dequeue

```powershell
Invoke-RestMethod "http://localhost:5001/api/queue/dequeue?topic=persist"
```

Penjelasan:
Message tetap ada walaupun node sempat mati karena disimpan secara persistent.

## 4. Handle Node Failure Tanpa Kehilangan Data

### Inti Konsep
- Data disimpan di 2 node (primary + replica) lewat consistent hashing.
- Kalau primary mati, dequeue mencoba replica sebagai failover.

### Cara Uji

### Step 1 — Enqueue ke topic khusus

```powershell
Invoke-RestMethod http://localhost:5001/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"fail_test","message":"msg-1"}'
```

### Step 2 — Matikan salah satu node

```powershell
docker stop docker-node1-1
```

### Step 3 — Dequeue dari node lain

```powershell
Invoke-RestMethod "http://localhost:5002/api/queue/dequeue?topic=fail_test"
```

Penjelasan:

Jika primary mati, sistem mencoba replica supaya data tidak hilang.

## 5. At-least-once Delivery Guarantee

### Inti Konsep
- Message boleh dikirim lebih dari sekali.
- Message tidak boleh hilang.
- Setelah dequeue, message masuk ke `unacked` dan bisa dikirim ulang jika tidak di-ack.

### Cara Uji

### Step 1 — Enqueue

```powershell
Invoke-RestMethod http://localhost:5001/api/queue/enqueue `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"delivery_test","message":"important-msg"}'
```

### Step 2 — Dequeue pertama

```powershell
Invoke-RestMethod "http://localhost:5001/api/queue/dequeue?topic=delivery_test"
```

Catat `id` dari message yang diterima.

### Step 3 — Jangan ACK (simulasi consumer crash)

Tunggu ~30 detik, lalu dequeue lagi:

```powershell
Invoke-RestMethod "http://localhost:5001/api/queue/dequeue?topic=delivery_test"
```

Output yang diharapkan: message dengan `id` yang sama muncul lagi.

### Step 4 — ACK agar message tidak dikirim ulang

```powershell
Invoke-RestMethod http://localhost:5001/api/queue/ack `
-Method POST `
-ContentType "application/json" `
-Body '{"topic":"delivery_test","msg_id":"PASTE_ID_DI_SINI"}'
```