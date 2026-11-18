
"""
LAPORAN BRODOTRACK
Ekspor data produk dan riwayat harga ke satu file CSV.
"""

# ==================================================
# 1. IMPORT LIBRARY
# ==================================================

import os
import sqlite3
import logging
import tempfile

import pandas as pd

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from config import DATABASE_PATH, LAPORAN_DIR


# ==================================================
# 2. KONFIGURASI
# ==================================================

BASE_DIR = Path(__file__).resolve().parent

FOLDER_LAPORAN = Path(LAPORAN_DIR)
FOLDER_LAPORAN.mkdir(parents=True, exist_ok=True)

# Nama file tetap agar tidak membuat file baru setiap sesi.
NAMA_CSV = FOLDER_LAPORAN / "laporan_brodotrack.csv"

ZONA_WAKTU = ZoneInfo("Asia/Jakarta")

logger = logging.getLogger("BRODOTRACK_LAPORAN")


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

    return connection


# ==================================================
# 4. MENGAMBIL DATA DATABASE
# ==================================================

def ambil_data_database():
    """
    Mengambil seluruh riwayat produk dan harga
    yang sudah tersimpan di database.
    """

    query = """
        SELECT
            r.id_riwayat,
            p.id_produk,
            p.nama_produk,
            p.kategori,
            p.deskripsi,
            p.sku,
            p.url_produk,
            p.url_gambar,
            r.ukuran,
            r.harga,
            r.harga_normal,
            r.harga_diskon,
            r.persentase_diskon,
            r.mata_uang,
            r.ketersediaan,
            r.waktu_scraping

        FROM riwayat_harga r

        INNER JOIN produk p
            ON p.id_produk = r.id_produk

        ORDER BY
            r.id_riwayat ASC
    """

    with get_connection() as connection:

        df = pd.read_sql_query(
            query,
            connection
        )

    return df


# ==================================================
# 5. VALIDASI DAN FILTER DATA
# ==================================================

def filter_data_laporan(df):
    """
    Memastikan data laporan valid dan tidak memiliki
    ID riwayat yang sama.

    Riwayat perubahan harga, diskon, dan stok tetap
    dipertahankan selama memiliki ID riwayat berbeda.
    """

    if df.empty:
        return df.copy()

    data = df.copy()

    # Menghapus data tanpa identitas riwayat.
    data = data.dropna(
        subset=["id_riwayat", "id_produk"]
    )

    # Menghapus duplikasi berdasarkan ID riwayat.
    data = data.drop_duplicates(
        subset=["id_riwayat"],
        keep="last"
    )

    # Memastikan kolom harga berupa angka.
    kolom_numerik = [
        "harga",
        "harga_normal",
        "harga_diskon",
        "persentase_diskon"
    ]

    for kolom in kolom_numerik:

        data[kolom] = pd.to_numeric(
            data[kolom],
            errors="coerce"
        )

    # Mengurutkan riwayat berdasarkan ID.
    data = data.sort_values(
        by="id_riwayat",
        ascending=True
    )

    return data.reset_index(drop=True)


# ==================================================
# 6. FORMAT DATA CSV
# ==================================================

def format_data_csv(df):
    """
    Menyiapkan kolom dan format data
    sebelum diekspor ke CSV.
    """

    if df.empty:
        return df.copy()

    data = df.copy()

    # Mengubah waktu menjadi format yang konsisten.
    waktu = pd.to_datetime(
        data["waktu_scraping"],
        errors="coerce"
    )

    data["waktu_scraping"] = waktu.dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # Mengubah data kosong menjadi string kosong.
    data = data.fillna("")

    # Mengatur urutan kolom CSV.
    kolom_csv = [
        "id_riwayat",
        "id_produk",
        "nama_produk",
        "kategori",
        "deskripsi",
        "sku",
        "url_produk",
        "url_gambar",
        "ukuran",
        "harga",
        "harga_normal",
        "harga_diskon",
        "persentase_diskon",
        "mata_uang",
        "ketersediaan",
        "waktu_scraping"
    ]

    return data[kolom_csv]


# ==================================================
# 7. MENYIMPAN CSV
# ==================================================

def simpan_laporan_csv(df):
    """
    Memperbarui satu file CSV secara keseluruhan.

    File sementara digunakan agar file laporan
    tidak rusak jika proses penulisan terganggu.
    """

    file_sementara = None

    try:

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            prefix="laporan_brodotrack_",
            dir=FOLDER_LAPORAN,
            delete=False,
            encoding="utf-8-sig",
            newline=""
        ) as file:

            file_sementara = file.name

            df.to_csv(
                file,
                index=False,
                encoding="utf-8-sig"
            )

        # Mengganti file lama dengan file terbaru.
        os.replace(
            file_sementara,
            NAMA_CSV
        )

        logger.info(
            "Laporan CSV berhasil diperbarui: %s",
            NAMA_CSV
        )

        return True

    except Exception:

        logger.exception(
            "Gagal menyimpan laporan CSV."
        )

        # Menghapus file sementara jika gagal.
        if file_sementara and os.path.exists(file_sementara):

            os.remove(file_sementara)

        return False


# ==================================================
# 8. PROGRAM UTAMA
# ==================================================

def main():
    """Menjalankan proses pembaruan laporan CSV."""

    print("\n======================================")
    print("PEMBARUAN LAPORAN BRODOTRACK")
    print("======================================")

    try:

        # Mengambil data dari database.
        df = ambil_data_database()

        if df.empty:

            print("Belum ada data untuk dibuat laporan.")
            return

        # Memvalidasi dan menghapus duplikasi.
        data_bersih = filter_data_laporan(df)

        if data_bersih.empty:

            print("Tidak ada data valid untuk laporan.")
            return

        # Menyiapkan format CSV.
        data_csv = format_data_csv(data_bersih)

        # Memperbarui file CSV.
        berhasil = simpan_laporan_csv(data_csv)

        if not berhasil:
            return

        print("\nHASIL PEMBARUAN LAPORAN")
        print("--------------------------------------")

        print(
            "Total riwayat database :",
            len(df)
        )

        print(
            "Total riwayat CSV      :",
            len(data_csv)
        )

        print(
            "Total produk           :",
            data_csv["id_produk"].nunique()
        )

        print(
            "Waktu pembaruan        :",
            datetime.now(ZONA_WAKTU).strftime(
                "%d-%m-%Y %H:%M:%S"
            )
        )

        print(
            "Lokasi laporan         :",
            NAMA_CSV
        )

        print("\n======================================")
        print("PEMBARUAN LAPORAN SELESAI")
        print("======================================")

    except Exception:

        logger.exception(
            "Terjadi kesalahan saat membuat laporan."
        )

        print("Pembuatan laporan gagal.")


# ==================================================
# 9. EKSEKUSI PROGRAM
# ==================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    main()
