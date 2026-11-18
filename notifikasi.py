
"""
NOTIFIKASI BRODOTRACK
Mengirim maksimal dua notifikasi otomatis per hari:
1. Ringkasan Database
2. Top 5 Diskon Terbesar
"""

# ==================================================
# 1. IMPORT LIBRARY
# ==================================================

import os
import sqlite3
import logging
import asyncio

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape

from dotenv import load_dotenv
from telegram import Bot

from config import DATABASE_PATH
from pesan import buat_pesan_ringkasan


# ==================================================
# 2. KONFIGURASI
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ZONA_WAKTU = ZoneInfo("Asia/Jakarta")

logger = logging.getLogger("BRODOTRACK_NOTIFIKASI")


# ==================================================
# 3. KONEKSI DATABASE
# ==================================================

def get_connection():
    """Membuat koneksi ke database BRODOTRACK."""

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def buat_tabel_notifikasi():
    """
    Membuat tabel pencatatan notifikasi.
    Tabel ini mencegah pesan yang sama dikirim
    berulang kali pada tanggal yang sama.
    """

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS notifikasi_terkirim (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal_sesi TEXT NOT NULL,
                jenis_pesan TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                waktu_terkirim TEXT,
                UNIQUE(tanggal_sesi, jenis_pesan)
            )
        """)

        connection.commit()


def ambil_tanggal_sesi():
    """Mengambil tanggal berdasarkan zona waktu WIB."""

    return datetime.now(ZONA_WAKTU).date().isoformat()


# ==================================================
# 4. FORMAT DATA
# ==================================================

def format_rupiah(nilai):
    """Mengubah angka menjadi format Rupiah."""

    if nilai is None:
        return "Tidak tersedia"

    try:
        return f"Rp{float(nilai):,.0f}".replace(",", ".")

    except (ValueError, TypeError):
        return "Tidak tersedia"


def format_diskon(nilai):
    """Mengubah angka menjadi format persentase."""

    try:
        nilai = float(nilai or 0)

        if nilai <= 0:
            return "0%"

        return f"{nilai:.2f}%"

    except (ValueError, TypeError):
        return "0%"


# ==================================================
# 5. MENGAMBIL TOP 5 DISKON TERBESAR
# ==================================================

def buat_pesan_top_5_diskon():
    """
    Mengambil lima kombinasi produk dan ukuran
    dengan diskon terbesar berdasarkan riwayat terbaru.

    Ukuran tetap digunakan untuk identifikasi varian,
    tetapi tidak ditampilkan dalam pesan Telegram.
    """

    with get_connection() as connection:

        data = connection.execute("""
    WITH data_terbaru AS (
        SELECT
            p.id_produk,
            p.nama_produk,
            p.url_produk,
            r.harga,
            r.harga_normal,
            r.harga_diskon,
            r.persentase_diskon,
            r.ukuran

        FROM riwayat_harga r

        JOIN produk p
            ON p.id_produk = r.id_produk

        WHERE r.id_riwayat = (
            SELECT MAX(r2.id_riwayat)
            FROM riwayat_harga r2
            WHERE r2.id_produk = r.id_produk
            AND r2.ukuran IS r.ukuran
        )
    ),

    peringkat_produk AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY id_produk
                ORDER BY
                    CAST(persentase_diskon AS REAL) DESC,
                    ukuran ASC
            ) AS nomor_varian

        FROM data_terbaru

        WHERE COALESCE(persentase_diskon, 0) > 0
    )

    SELECT *
    FROM peringkat_produk

    WHERE nomor_varian = 1

    ORDER BY
        CAST(persentase_diskon AS REAL) DESC

    LIMIT 5

""").fetchall()

    pesan = [
        "🔥 <b>TOP 5 DISKON TERBESAR BRODOTRACK</b>",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    if not data:

        pesan.append(
            "\nBelum ada produk dengan diskon aktif."
        )

    else:

        for nomor, item in enumerate(data, start=1):

            nama = escape(
                str(item["nama_produk"] or "-")
            )

            harga_normal = (
                item["harga_normal"]
                if item["harga_normal"] is not None
                else item["harga"]
            )

            harga_diskon = (
                item["harga_diskon"]
                if item["harga_diskon"] is not None
                else item["harga"]
            )

            url = str(
                item["url_produk"] or ""
            ).strip()

            tambahan_link = ""

            if url.startswith(("https://", "http://")):

                tambahan_link = (
                    f'\n<a href="{escape(url, quote=True)}">'
                    "Lihat produk di website BRODO</a>"
                )

            pesan.append(
                f"\n<b>{nomor}. {nama}</b>\n"
                f"Harga normal: {format_rupiah(harga_normal)}\n"
                f"Harga promo: <b>{format_rupiah(harga_diskon)}</b>\n"
                f"Diskon: 🔥 <b>{format_diskon(item['persentase_diskon'])}</b>"
                f"{tambahan_link}"
            )

    pesan.append(
        "\n\n<i>BRODOTRACK — Automatic Price Monitoring</i>"
    )

    return "\n".join(pesan)


# ==================================================
# 6. PENGAMAN NOTIFIKASI DUPLIKAT
# ==================================================

def klaim_notifikasi(tanggal_sesi, jenis_pesan):
    """
    Mencatat klaim sebelum pesan dikirim.
    UNIQUE mencegah dua proses mengklaim pesan
    yang sama pada tanggal yang sama.
    """

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT OR IGNORE INTO notifikasi_terkirim (
                tanggal_sesi,
                jenis_pesan,
                status
            )
            VALUES (?, ?, 'pending')
        """, (
            tanggal_sesi,
            jenis_pesan
        ))

        connection.commit()

        return cursor.rowcount == 1


def tandai_berhasil(tanggal_sesi, jenis_pesan):
    """Mencatat bahwa pesan berhasil dikirim."""

    waktu = datetime.now(ZONA_WAKTU).isoformat()

    with get_connection() as connection:

        connection.execute("""
            UPDATE notifikasi_terkirim
            SET status = 'terkirim',
                waktu_terkirim = ?
            WHERE tanggal_sesi = ?
            AND jenis_pesan = ?
        """, (
            waktu,
            tanggal_sesi,
            jenis_pesan
        ))

        connection.commit()


def batalkan_klaim(tanggal_sesi, jenis_pesan):
    """Menghapus klaim jika pengiriman gagal."""

    with get_connection() as connection:

        connection.execute("""
            DELETE FROM notifikasi_terkirim
            WHERE tanggal_sesi = ?
            AND jenis_pesan = ?
            AND status = 'pending'
        """, (
            tanggal_sesi,
            jenis_pesan
        ))

        connection.commit()


# ==================================================
# 7. MENGIRIM PESAN TELEGRAM
# ==================================================

async def kirim_pesan_telegram(pesan):
    """Mengirim satu pesan ke Telegram."""

    if not TOKEN or not CHAT_ID:

        raise ValueError(
            "TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID "
            "belum diatur di file .env."
        )

    async with Bot(token=TOKEN) as bot:

        await bot.send_message(
            chat_id=int(CHAT_ID),
            text=pesan,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


def kirim_satu_notifikasi(
    tanggal_sesi,
    jenis_pesan,
    isi_pesan
):
    """
    Mengirim satu jenis pesan hanya jika
    belum pernah diklaim pada tanggal tersebut.
    """

    berhasil_diklaim = klaim_notifikasi(
        tanggal_sesi,
        jenis_pesan
    )

    if not berhasil_diklaim:

        logger.info(
            "Notifikasi %s tanggal %s sudah diproses. Dilewati.",
            jenis_pesan,
            tanggal_sesi
        )

        return False

    try:

        asyncio.run(
            kirim_pesan_telegram(isi_pesan)
        )

        tandai_berhasil(
            tanggal_sesi,
            jenis_pesan
        )

        logger.info(
            "Notifikasi %s berhasil dikirim.",
            jenis_pesan
        )

        return True

    except Exception:

        batalkan_klaim(
            tanggal_sesi,
            jenis_pesan
        )

        logger.exception(
            "Gagal mengirim notifikasi %s.",
            jenis_pesan
        )

        return False


# ==================================================
# 8. NOTIFIKASI HASIL SCRAPING
# ==================================================

def kirim_notifikasi_scraping(
    jumlah_record,
    target=100,
    id_riwayat_awal=None
):
    """
    Mengirim maksimal dua pesan:
    1. Ringkasan database.
    2. Top 5 diskon terbesar.

    Notifikasi dibatasi satu kali per tanggal WIB.
    Parameter lama tetap dipertahankan agar
    kompatibel dengan main.py.
    """

    try:

        buat_tabel_notifikasi()

        tanggal_sesi = ambil_tanggal_sesi()

        # ------------------------------------------
        # PESAN 1: RINGKASAN DATABASE
        # ------------------------------------------

        ringkasan = buat_pesan_ringkasan()

        pesan_ringkasan = (
            "<b>📊 RINGKASAN DATABASE BRODOTRACK</b>\n\n"
            + escape(str(ringkasan))
        )

        berhasil_ringkasan = kirim_satu_notifikasi(
            tanggal_sesi,
            "ringkasan_database",
            pesan_ringkasan
        )

        # ------------------------------------------
        # PESAN 2: TOP 5 DISKON TERBESAR
        # ------------------------------------------

        pesan_top_5 = buat_pesan_top_5_diskon()

        berhasil_top_5 = kirim_satu_notifikasi(
            tanggal_sesi,
            "top_5_diskon",
            pesan_top_5
        )

        jumlah_berhasil = sum([
            berhasil_ringkasan,
            berhasil_top_5
        ])

        logger.info(
            "Sesi %s selesai. Pesan baru terkirim: %s dari 2.",
            tanggal_sesi,
            jumlah_berhasil
        )

        return jumlah_berhasil > 0

    except Exception:

        logger.exception(
            "Terjadi kesalahan saat memproses notifikasi."
        )

        return False


# ==================================================
# 9. PENGUJIAN MANDIRI
# ==================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("======================================")
    print("PENGUJIAN NOTIFIKASI BRODOTRACK")
    print("======================================")

    buat_tabel_notifikasi()

    print(
        "\nTanggal sesi WIB:",
        ambil_tanggal_sesi()
    )

    print("\nPengujian Top 5 Diskon:")

    print(
        buat_pesan_top_5_diskon()
    )

    print("\nPengujian selesai.")
    print(
        "Pengujian ini tidak mengirim pesan Telegram."
    )
