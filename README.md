# 🤖 Rumah Sehat Dani Sabri – Telegram Bot Bekam

Bot Telegram ini digunakan untuk **mengatur jadwal terapi bekam** di *Rumah Sehat Dani Sabri*.  
Pasien dapat memesan jadwal dengan terapis sesuai jenis kelamin, melihat jadwal mereka, dan menerima pengingat otomatis.  
Bot juga menampilkan **tanggal sunnah bekam** berdasarkan kalender Hijriah dan mengirim **tips kesehatan harian**.  

Admin dapat mengelola terapis, janji pasien, daftar tunggu, hari libur, dan (🚧 *akan datang*) broadcast pesan ke semua pengguna.

---

## ✨ Fitur Utama

### 👥 Untuk Pengguna (Pasien)
- Pemesanan janji terapi dengan filter **gender pasien–terapis**
- Kalender interaktif dengan tampilan ketersediaan waktu
- Pengingat otomatis 30 menit sebelum jadwal
- Notifikasi tanggal **sunnah bekam** (17, 19, 21 Hijriah)
- Tips kesehatan harian (AI/OpenAI GPT-4o-mini atau default)
- Tampilan kalender cepat tanpa emoji agar bot lebih responsif

### 🛠️ Untuk Admin
- **Kelola Terapis**
  - Tambah terapis baru  
  - Edit informasi terapis (nama, gender, status)  
  - Hapus terapis  
  - Aktifkan atau nonaktifkan terapis (misalnya untuk cuti)  
  - Jadwal nonaktif sementara bisa diatur otomatis berdasarkan tanggal  
- **Kelola Janji Pasien**
  - Lihat semua jadwal aktif  
  - Ubah status janji (misalnya “selesai” atau “dibatalkan”)  
- **Daftar Tunggu**
  - Lihat pasien yang menunggu slot kosong  
  - Detail kontak pasien (nomor telepon) kini tampil dengan benar  
- **Hari Libur**
  - Atur hari libur mingguan (misalnya setiap Jumat)  
  - Tambah hari libur tanggal tertentu  
- **(🚧 Akan Datang)** Broadcast pesan ke semua pengguna  
- Semua fungsi admin bisa diakses langsung lewat panel interaktif Telegram

---

## 🧩 Arsitektur Sistem

### 🧠 Framework
- **Library**: `python-telegram-bot==22.5`
- Sistem percakapan multi-state dengan `PicklePersistence`
- Asynchronous event handling untuk performa tinggi dan non-blocking

### 💾 Database
Menggunakan **SQLite + aiosqlite** (async).  
Struktur utama:
- `therapists` – Data terapis (gender, status aktif/nonaktif, jadwal cuti)
- `appointments` – Data janji pasien
- `waitlist` – Daftar tunggu pasien
- `holiday_weekly`, `holiday_dates` – Hari libur tetap & tanggal khusus
- `daily_health_content` – Cache tips kesehatan harian
- `prayer_times_cache` – Cache waktu salat (persisten, 30 hari ke depan)
- `broadcasts` – (akan digunakan untuk riwayat pesan broadcast)

🧠 **Alasan**: SQLite dipilih karena ringan, mudah digunakan, dan tidak butuh setup server tambahan.

### ⏰ Scheduler
Menggunakan **APScheduler (AsyncIOScheduler)** untuk:
- Reminder janji 30 menit sebelum terapi  
- Notifikasi tanggal sunnah bekam (7, 3, 1 hari sebelumnya)  
- Prefetch waktu salat setiap 00:00 WIB (30 hari ke depan)  
- Aktivasi/deaktivasi terapis otomatis berdasarkan jadwal cuti  

Zona waktu: **Asia/Jakarta (WIB)**.

### 🕒 Algoritma Slot Jadwal
Slot dibuat berdasarkan:
- Jam kerja & jam istirahat  
- Waktu salat (blokir 20 menit sebelum/sesudah)  
- Hari libur mingguan & tanggal tertentu  
- Status & gender terapis  

Sistem otomatis mencegah bentrok antar slot dan hanya menampilkan jadwal valid.

---

## 🕌 Integrasi Kalender Islam

- Menggunakan **`hijri-converter`** untuk konversi tanggal Masehi ↔ Hijriah  
- Menentukan **tanggal sunnah bekam** (17, 19, 21 Hijriah)  
- Mengirim notifikasi ke semua pengguna menjelang tanggal sunnah  

---

## 💡 Tips Kesehatan Harian

- Menggunakan **OpenAI GPT-4o-mini** (jika `OPENAI_API_KEY` tersedia)  
- Menyimpan hasil di database agar tidak memanggil API berulang kali  
- Jika API tidak tersedia, sistem menggunakan tips bawaan  

---

## ⚙️ Konfigurasi & Deployment

### 📁 File `.env` Contoh
```env
TOKEN=1234567890:ABCDEFyourTelegramBotToken
ADMIN_IDS=123456789,987654321
DB_PATH=bekam.db
OPENAI_API_KEY=your_openai_api_key_here  # opsional
START_HOUR=08
END_HOUR=17
BREAK_START_HOUR=12
BREAK_END_HOUR=13
