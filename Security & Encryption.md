## Security & Encryption

Bagian ini menunjukkan komunikasi antar-node yang terenkripsi end-to-end. Dari sisi client request tetap normal, tetapi RPC internal berjalan lewat payload terenkripsi.

```powershell
docker-compose -f docker/docker-compose.yml up --build -d

Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"secure_key","value":"secure_value"}'
```

Kalau request berhasil, berarti API publik tetap lancar sementara jalur internal sudah aman.

RBAC saya uji dengan RPC langsung dari sender yang tidak dikenal. Saya kirim payload terenkripsi dengan sender dan cert palsu untuk memastikan identitas dan hak akses dicek.

```powershell
@'
from cryptography.fernet import Fernet
import base64, json
from urllib.request import Request, urlopen

key = b'0123456789abcdef0123456789abcdef'
fernet = Fernet(base64.urlsafe_b64encode(key))
payload = fernet.encrypt(json.dumps({"type":"cache_get","key":"x"}).encode()).decode()
body = json.dumps({"sender":"fake-node","action":"cache","payload":payload,"cert":"fake-cert"}).encode()
req = Request("http://localhost:5002/rpc", data=body, headers={"Content-Type":"application/json"}, method="POST")
try:
    print(urlopen(req).read().decode())
except Exception as e:
    print(e)
'@ | python -
```

Jika hasilnya 403, berarti sender tidak sah ditolak.

Audit logging saya cek dengan operasi antar-node, lalu melihat `audit.log` dan memverifikasi hash chain-nya. `Get-Content` melihat isi log, sementara skrip Python mengecek konsistensi hash.

```powershell
Invoke-RestMethod -Uri http://localhost:5001/api/cache/put `
-Method POST `
-ContentType "application/json" `
-Body '{"key":"audit_key","value":"v1"}'

Get-Content .\data\node1\audit.log -Tail 5

@'
import json, hashlib
from pathlib import Path

path = Path("data/node1/audit.log")
prev = ""
for line in path.read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    expected = row["hash"]
    current = dict(row)
    current.pop("hash", None)
    calc = hashlib.sha256(json.dumps(current, sort_keys=True).encode("utf-8")).hexdigest()
    assert calc == expected
    assert row["prev_hash"] == prev
    prev = expected
print("audit chain ok")
'@ | python -
```

Jika verifikasi sukses, audit log valid. Kalau file diubah manual, hash akan gagal cocok.

Certificate management memakai fingerprint node di environment. Setiap RPC membawa `cert`, lalu penerima mengecek apakah fingerprint cocok dengan allowlist.

```powershell
Invoke-RestMethod "http://localhost:5001/api/metrics" | ConvertTo-Json -Depth 5
```

Terakhir, metrics dipakai untuk memastikan RPC dan audit logging aktif. Jika `net.sent` dan `net.recv` naik, berarti traffic antar-node memang berjalan.
