
"""
MAIN PROGRAM BRODOTRACK

Mengatur seluruh proses utama sistem BRODOTRACK.

Alur pipeline:
Scraping -> Database -> Analisis -> Laporan -> Notifikasi Telegram

Penjadwalan:
Scraping otomatis dilakukan satu kali sehari
pada pukul 08.00 WIB.

Target:
100 data baru setiap sesi scraping.
"""

import argparse
import logging
import subprocess
import sys
import time
import threading

import schedule

import config
import db

from scraper import scrape_banyak_produk
from notifikasi import kirim_notifikasi_scraping


# ==================================================
# 1. KONFIGURASI PROGRAM
# ==================================================

# Target jumlah data baru yang berhasil disimpan
TARGET_PER_SESI = 100

# Jadwal scraping otomatis satu kali sehari
JADWAL_SCRAPING = "08:00"

# Target harian sama dengan target satu sesi
TARGET_HARIAN = TARGET_PER_SESI

# Interval pemeriksaan scheduler dalam detik
# Hanya memeriksa jadwal, bukan menjalankan scraping.
INTERVAL_PEMERIKSAAN = 30


# ==================================================
# 2. PENGAMAN PIPELINE
# ==================================================

# Mencegah dua pipeline berjalan bersamaan.
pipeline_lock = threading.Lock()


# ==================================================
# 3. LOGGING
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            config.LOG_FILE,
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("BRODOTRACK")


# ==================================================
# 4. MENJALANKAN PROGRAM EKSTERNAL
# ==================================================

def jalankan_program(nama_file):
    """
    Menjalankan file Python lain sebagai bagian pipeline.

    Contoh:
    - analisis.py
    - laporan.py

    Jika program gagal, proses menghasilkan error.
    """

    logger.info(
        "Menjalankan program %s...",
        nama_file
    )

    subprocess.run(
        [sys.executable, nama_file],
        cwd=config.BASE_DIR,
        check=True
    )

    logger.info(
        "Program %s berhasil diselesaikan.",
        nama_file
    )


# ==================================================
# 5. MENJALANKAN PIPELINE BRODOTRACK
# ==================================================

def jalankan_pipeline():
    """
    Menjalankan seluruh proses utama BRODOTRACK.

    Tahapan:
    1. Persiapan database.
    2. Melakukan scraping.
    3. Menjalankan analisis.
    4. Membuat laporan CSV.
    5. Mengirim notifikasi Telegram.

    Notifikasi otomatis:
    - Ringkasan Database.
    - Top 5 Diskon Terbesar.

    Pipeline tidak dijalankan bersamaan dengan
    proses pipeline lain yang masih berlangsung.
    """

    # Memastikan tidak ada pipeline lain yang berjalan
    if not pipeline_lock.acquire(blocking=False):

        logger.warning(
            "Pipeline masih berjalan. "
            "Pemanggilan baru dilewati."
        )

        return

    waktu_mulai = time.time()

    logger.info("=" * 55)
    logger.info("MEMULAI PIPELINE BRODOTRACK")
    logger.info("=" * 55)

    try:

        # --------------------------------------------------
        # 1. PERSIAPAN DATABASE
        # --------------------------------------------------

        logger.info("Menyiapkan database...")

        db.create_tables()

        logger.info(
            "Database berhasil disiapkan."
        )

        # --------------------------------------------------
        # 2. PROSES SCRAPING
        # --------------------------------------------------

        logger.info(
            "Memulai scraping dengan target %s data baru...",
            TARGET_PER_SESI
        )

        # Scraper hanya menghitung data baru yang berhasil
        # disimpan setelah proses validasi dan penyaringan.
        jumlah_record = scrape_banyak_produk(
            target_record=TARGET_PER_SESI
        )

        logger.info(
            "Scraping selesai. Data baru tersimpan: %s",
            jumlah_record
        )

        # --------------------------------------------------
        # 3. ANALISIS DATA
        # --------------------------------------------------

        logger.info("Memulai analisis data...")

        jalankan_program("analisis.py")

        logger.info(
            "Analisis data selesai."
        )

        # --------------------------------------------------
        # 4. PEMBUATAN LAPORAN CSV
        # --------------------------------------------------

        logger.info(
            "Memulai pembuatan laporan CSV..."
        )

        # Memperbarui satu file CSV yang sudah ada.
        jalankan_program("laporan.py")

        logger.info(
            "Pembuatan laporan CSV selesai."
        )

        # --------------------------------------------------
        # 5. NOTIFIKASI TELEGRAM
        # --------------------------------------------------

        logger.info(
            "Memproses notifikasi Telegram..."
        )

        # Maksimal dua jenis notifikasi otomatis:
        # 1. Ringkasan Database.
        # 2. Top 5 Diskon Terbesar.
        #
        # Pengamanan duplikasi dilakukan oleh
        # tabel notifikasi_terkirim di notifikasi.py.
        #
        # Notifikasi dibatasi satu kali per tanggal WIB.

        berhasil = kirim_notifikasi_scraping(
            jumlah_record=jumlah_record,
            target=TARGET_PER_SESI
        )

        if berhasil:

            logger.info(
                "Notifikasi Telegram berhasil diproses."
            )

        else:

            logger.warning(
                "Notifikasi Telegram gagal atau "
                "sudah pernah diproses hari ini."
            )

        # --------------------------------------------------
        # 6. PIPELINE SELESAI
        # --------------------------------------------------

        logger.info(
            "PIPELINE BRODOTRACK SELESAI"
        )

    except Exception:

        logger.exception(
            "PIPELINE BRODOTRACK GAGAL"
        )

    finally:

        # Menghitung total waktu pelaksanaan
        durasi = time.time() - waktu_mulai

        logger.info(
            "Durasi proses: %.2f detik",
            durasi
        )

        logger.info("=" * 55)

        # Melepaskan lock agar pipeline berikutnya
        # dapat berjalan sesuai jadwal.
        pipeline_lock.release()


# ==================================================
# 6. MENJALANKAN SCHEDULER
# ==================================================

def mulai_scheduler():
    """
    Menjalankan scheduler BRODOTRACK.

    Scraping dijadwalkan satu kali sehari
    pada pukul 08.00 waktu lokal komputer.

    Pemeriksaan scheduler setiap 30 detik tidak
    menyebabkan scraping berjalan setiap 30 detik.
    """

    # Menghapus jadwal lama
    schedule.clear()

    # Mendaftarkan jadwal scraping harian
    schedule.every().day.at(
        JADWAL_SCRAPING
    ).do(jalankan_pipeline)

    logger.info("=" * 55)
    logger.info("SCHEDULER BRODOTRACK AKTIF")
    logger.info("=" * 55)

    logger.info(
        "Jadwal scraping: setiap hari pukul %s",
        JADWAL_SCRAPING
    )

    logger.info(
        "Target setiap sesi: %s data baru",
        TARGET_PER_SESI
    )

    logger.info(
        "Target harian: %s data baru",
        TARGET_HARIAN
    )

    logger.info(
        "Pemeriksaan jadwal setiap %s detik.",
        INTERVAL_PEMERIKSAAN
    )

    logger.info(
        "Menunggu jadwal scraping berikutnya..."
    )

    try:

        # Scheduler terus memeriksa jadwal.
        # Scraping hanya berjalan saat jadwal tercapai.
        while True:

            schedule.run_pending()

            time.sleep(
                INTERVAL_PEMERIKSAAN
            )

    except KeyboardInterrupt:

        logger.info(
            "Scheduler BRODOTRACK dihentikan pengguna."
        )

    finally:

        schedule.clear()

        logger.info(
            "Scheduler BRODOTRACK berhenti."
        )


# ==================================================
# 7. PROGRAM UTAMA
# ==================================================

def main():
    """
    Menentukan mode pelaksanaan BRODOTRACK.

    Mode 1:
    Tanpa argumen --jadwal.
    Pipeline langsung dijalankan satu kali.

    Mode 2:
    Dengan argumen --jadwal.
    Scheduler aktif dan menunggu pukul 08.00.
    """

    parser = argparse.ArgumentParser(
        description="Sistem Pemantauan Harga BRODOTRACK"
    )

    parser.add_argument(
        "--jadwal",
        action="store_true",
        help=(
            "Menjalankan scraping otomatis "
            "setiap hari pukul 08.00."
        )
    )

    args = parser.parse_args()

    if args.jadwal:

        mulai_scheduler()

    else:

        jalankan_pipeline()


# ==================================================
# 8. MENJALANKAN PROGRAM
# ==================================================

if __name__ == "__main__":

    main()
