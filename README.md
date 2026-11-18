# 👟 BRODOTRACK
### Product Price Monitoring System for BRODO

BRODOTRACK merupakan sistem pemantauan harga produk sepatu BRODO berbasis Python yang memanfaatkan teknik **Web Scraping** untuk mengumpulkan dan memantau informasi produk, harga, diskon, serta ketersediaan stok secara berkala.

Sistem ini dilengkapi dengan dashboard berbasis web dan Telegram Bot untuk memudahkan pengguna memperoleh informasi serta memantau perubahan data produk BRODO.

---

## ✨ Fitur Utama

### 1. Web Scraping
- Mengambil data produk dari website resmi BRODO.
- Mengumpulkan informasi nama produk, harga, ukuran, diskon, dan ketersediaan stok.
- Menyimpan hasil scraping ke database SQLite.
- Memantau perubahan data melalui proses scraping berkala.

### 2. Dashboard Monitoring
Dashboard BRODOTRACK menyediakan beberapa halaman:

| Halaman | Fungsi |
|---|---|
| Dashboard | Menampilkan ringkasan data produk dan statistik pemantauan |
| Katalog Produk | Menampilkan daftar produk BRODO |
| Detail Produk | Menampilkan informasi harga dan stok berdasarkan ukuran |
| Riwayat Harga | Menampilkan riwayat harga dan aktivitas scraping |
| Monitoring Stok | Memantau ketersediaan stok produk |
| Monitoring Diskon | Menampilkan produk yang sedang mendapatkan diskon |

### 3. Telegram Bot
Telegram Bot menyediakan fitur:
- Ringkasan pemantauan produk.
- Daftar produk.
- Detail produk.
- Informasi perubahan harga.
- Informasi promo.
- Panduan penggunaan bot.

### 4. Notifikasi Otomatis
- Notifikasi ringkasan database.
- Informasi Top 5 diskon terbesar.
- Pengiriman notifikasi melalui Telegram.

### 5. Analisis dan Laporan
- Analisis data hasil scraping.
- Visualisasi perbandingan harga dan diskon.
- Grafik riwayat harga.
- Grafik ketersediaan stok.
- Pembuatan laporan dalam format CSV.

---

## 🛠️ Teknologi yang Digunakan

| Teknologi | Kegunaan |
|---|---|
| Python | Bahasa pemrograman utama |
| BeautifulSoup / Requests | Web Scraping |
| SQLite | Penyimpanan database |
| Flask | Pengembangan dashboard |
| HTML & CSS | Struktur dan tampilan dashboard |
| JavaScript | Interaksi antarmuka |
| Telegram Bot API | Notifikasi dan interaksi bot |
| Matplotlib | Visualisasi data |
| Pandas | Pengolahan data |

---

## 📁 Struktur Project

```text
BRODOTRACK/
│
├── analisis.py
├── app.py
├── bot.py
├── config.py
├── db.py
├── laporan.py
├── main.py
├── notifikasi.py
├── pesan.py
├── scraper.py
│
├── output/
│   ├── grafik/
│   └── laporan/
│
├── static/
│   ├── css/
│   └── js/
│
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── detail_produk.html
│   ├── diskon.html
│   ├── produk.html
│   ├── riwayat.html
│   └── stok.html
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Instalasi dan Konfigurasi

### 1. Clone Repository

```bash
git clone https://github.com/della436/BRODOTRACK.git
```

Masuk ke direktori project:

```bash
cd BRODOTRACK
```

### 2. Membuat Virtual Environment

```bash
python -m venv .venv
```

Aktifkan virtual environment.

**macOS / Linux:**

```bash
source .venv/bin/activate
```

**Windows:**

```bash
.venv\Scripts\activate
```

### 3. Instalasi Dependencies

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment

Buat file `.env` berdasarkan `.env.example`.

Contoh konfigurasi:

```env
TELEGRAM_BOT_TOKEN=isi_token_bot_telegram
TELEGRAM_CHAT_ID=isi_chat_id
FLASK_SECRET_KEY=isi_secret_key
```

Sesuaikan konfigurasi database dan direktori penyimpanan melalui `config.py` apabila diperlukan.

**Catatan:** File `.env` berisi informasi rahasia dan tidak boleh diunggah ke GitHub.

---

## ▶️ Menjalankan Aplikasi

### Menjalankan Dashboard

```bash
python app.py
```

Dashboard dapat diakses melalui:

```text
http://127.0.0.1:5001
```

### Menjalankan Telegram Bot

```bash
python bot.py
```

### Menjalankan Sistem Utama

```bash
python main.py
```

`main.py` digunakan sebagai pengelola proses utama sistem, termasuk scraping terjadwal dan proses otomatis lainnya sesuai konfigurasi aplikasi.

**Catatan:** Jalankan bot dan scheduler sesuai kebutuhan. Hindari menjalankan dua proses polling Telegram Bot menggunakan token yang sama secara bersamaan.

---

## 🔄 Alur Kerja Sistem

1. Sistem mengambil informasi produk dari website BRODO melalui proses web scraping.
2. Data hasil scraping diproses dan disimpan ke database SQLite.
3. Data harga dan stok dibandingkan dengan catatan sebelumnya.
4. Dashboard menampilkan informasi produk, harga, diskon, stok, dan riwayat pemantauan.
5. Telegram Bot menyediakan akses informasi produk.
6. Sistem mengirimkan notifikasi otomatis berdasarkan hasil pemantauan.

---

## 📊 Output Sistem

BRODOTRACK menghasilkan beberapa output, antara lain:

- Data produk BRODO.
- Riwayat perubahan harga.
- Informasi diskon produk.
- Informasi ketersediaan stok.
- Grafik analisis pemantauan.
- Laporan hasil scraping dalam format CSV.
- Notifikasi otomatis melalui Telegram.

---

## 🔐 Keamanan

Untuk menjaga keamanan project:

- Token Telegram disimpan dalam file `.env`.
- File `.env` dikecualikan melalui `.gitignore`.
- Virtual environment tidak diunggah ke repository.
- Database dan file log lokal dikecualikan dari Git.

---

## 🎯 Tujuan Project

BRODOTRACK dikembangkan sebagai implementasi pemanfaatan teknologi web scraping dan pengolahan data untuk membangun sistem pemantauan harga produk secara berkala.

Sistem ini diharapkan dapat membantu pengguna memperoleh informasi produk, memantau perubahan harga, mengetahui diskon, serta melihat ketersediaan stok produk BRODO melalui satu platform terintegrasi.

---

## 👩‍💻 Developer

**Adela Annur Aziiza**

GitHub: [@della436](https://github.com/della436)

---

*BRODOTRACK — Product Price Monitoring System for BRODO.*
