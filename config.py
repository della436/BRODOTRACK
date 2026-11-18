
import os

# ==========================================
# INFORMASI APLIKASI
# ==========================================

APP_NAME = "BRODOTRACK"
APP_VERSION = "1.0.0"


# ==========================================
# DIREKTORI UTAMA PROYEK
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ==========================================
# DIREKTORI DATA
# ==========================================

DATA_DIR = os.path.join(BASE_DIR, "data")

DATABASE_PATH = os.path.join(
    DATA_DIR,
    "brodotrack.db"
)


# ==========================================
# DIREKTORI OUTPUT
# ==========================================

OUTPUT_DIR = os.path.join(BASE_DIR, "output")

LAPORAN_DIR = os.path.join(
    OUTPUT_DIR,
    "laporan"
)

GRAFIK_DIR = os.path.join(
    OUTPUT_DIR,
    "grafik"
)


# ==========================================
# DIREKTORI LOG
# ==========================================

LOG_DIR = os.path.join(BASE_DIR, "logs")

LOG_FILE = os.path.join(
    LOG_DIR,
    "brodotrack.log"
)


# ==========================================
# KONFIGURASI WEBSITE BRODO
# ==========================================

BASE_URL = "https://www.bro.do"

SITEMAP_URL = (
    "https://www.bro.do/sitemaps/products-0001.xml"
)


# ==========================================
# KONFIGURASI WEB SCRAPING
# ==========================================

USER_AGENT = "BRODOTRACK-Academic-Project/1.0"

REQUEST_TIMEOUT = 20

SCRAPING_DELAY = 2


# ==========================================
# KONFIGURASI DATABASE
# ==========================================

DATABASE_TIMEOUT = 30


# ==========================================
# DAFTAR DIREKTORI YANG HARUS DIBUAT
# ==========================================

DIRECTORIES = [
    DATA_DIR,
    OUTPUT_DIR,
    LAPORAN_DIR,
    GRAFIK_DIR,
    LOG_DIR
]


# ==========================================
# MEMBUAT DIREKTORI OTOMATIS
# ==========================================

def buat_direktori():
    """
    Membuat seluruh direktori proyek
    apabila belum tersedia.
    """

    for directory in DIRECTORIES:
        os.makedirs(directory, exist_ok=True)


# ==========================================
# MENJALANKAN KONFIGURASI
# ==========================================

buat_direktori()


# ==========================================
# INFORMASI KONFIGURASI
# ==========================================

if __name__ == "__main__":
    print("=" * 45)
    print(f"APLIKASI : {APP_NAME}")
    print(f"VERSI    : {APP_VERSION}")
    print("=" * 45)

    print(f"BASE DIR : {BASE_DIR}")
    print(f"DATABASE : {DATABASE_PATH}")
    print(f"WEBSITE  : {BASE_URL}")
    print(f"SITEMAP  : {SITEMAP_URL}")

    print("\nDirektori proyek berhasil diperiksa.")
