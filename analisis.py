
import os
import sqlite3
import logging

import pandas as pd
import matplotlib.pyplot as plt

from config import DATABASE_PATH, GRAFIK_DIR


# ==========================================
# KONFIGURASI
# ==========================================

logger = logging.getLogger(__name__)

os.makedirs(GRAFIK_DIR, exist_ok=True)


# ==========================================
# MENGAMBIL DATA DATABASE
# ==========================================

def ambil_data():
    """
    Mengambil data produk dan riwayat harga,
    termasuk informasi harga normal dan diskon.
    """

    query = """
        SELECT
            p.id_produk,
            p.nama_produk,
            p.kategori,
            p.sku,
            p.url_produk,
            r.ukuran,
            r.harga,
            r.harga_normal,
            r.harga_diskon,
            r.persentase_diskon,
            r.mata_uang,
            r.ketersediaan,
            r.waktu_scraping
        FROM produk p
        JOIN riwayat_harga r
            ON p.id_produk = r.id_produk
        ORDER BY r.waktu_scraping ASC
    """

    try:
        with sqlite3.connect(DATABASE_PATH) as connection:
            df = pd.read_sql_query(query, connection)

        if df.empty:
            print("Belum ada data untuk dianalisis.")
            return df

        kolom_numerik = [
            "harga",
            "harga_normal",
            "harga_diskon",
            "persentase_diskon"
        ]

        for kolom in kolom_numerik:
            df[kolom] = pd.to_numeric(
                df[kolom],
                errors="coerce"
            )

        df["waktu_scraping"] = pd.to_datetime(
            df["waktu_scraping"],
            errors="coerce"
        )

        return df

    except sqlite3.Error:
        logger.exception("Gagal mengambil data database.")
        print("Terjadi kesalahan saat mengambil data.")
        return pd.DataFrame()


# ==========================================
# NORMALISASI STOK
# ==========================================

def normalisasi_stok(nilai):

    if nilai is None or pd.isna(nilai):
        return "Tidak diketahui"

    teks = str(nilai).lower().strip()

    if (
        teks == "tersedia"
        or teks.endswith("/instock")
        or teks == "true"
    ):
        return "Tersedia"

    if (
        teks == "habis"
        or teks.endswith("/outofstock")
        or teks.endswith("/soldout")
        or teks == "false"
    ):
        return "Habis"

    return "Tidak diketahui"


# ==========================================
# MENGAMBIL DATA TERBARU
# ==========================================

def ambil_data_terbaru(df):
    """
    Mengambil catatan terbaru setiap kombinasi
    produk dan ukuran.
    """

    if df.empty:
        return df

    data = df.dropna(
        subset=["waktu_scraping", "harga"]
    ).copy()

    if data.empty:
        return data

    data = (
        data.sort_values("waktu_scraping")
        .drop_duplicates(
            subset=["id_produk", "ukuran"],
            keep="last"
        )
        .copy()
    )

    return data


# ==========================================
# ANALISIS STATISTIK HARGA
# ==========================================

def analisis_harga(df):

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data harga.")
        return None

    statistik = {
        "harga_minimum": data["harga"].min(),
        "harga_maksimum": data["harga"].max(),
        "harga_rata_rata": data["harga"].mean(),
        "jumlah_ukuran": len(data)
    }

    print("\n" + "=" * 50)
    print("ANALISIS STATISTIK HARGA BRODO")
    print("=" * 50)

    print(
        f"Harga Minimum  : Rp{statistik['harga_minimum']:,.0f}"
    )

    print(
        f"Harga Maksimum : Rp{statistik['harga_maksimum']:,.0f}"
    )

    print(
        f"Harga Rata-rata: Rp{statistik['harga_rata_rata']:,.2f}"
    )

    print(
        f"Jumlah Kombinasi Produk-Ukuran: "
        f"{statistik['jumlah_ukuran']}"
    )

    return statistik


# ==========================================
# ANALISIS DISKON
# ==========================================

def analisis_diskon(df):
    """
    Menganalisis jumlah produk yang sedang diskon,
    rata-rata persentase diskon, dan diskon terbesar.
    """

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data diskon.")
        return None

    data_diskon = data[
        data["persentase_diskon"].fillna(0) > 0
    ].copy()

    jumlah_total = len(data)
    jumlah_diskon = len(data_diskon)
    jumlah_tanpa_diskon = jumlah_total - jumlah_diskon

    if jumlah_diskon > 0:

        rata_rata_diskon = data_diskon[
            "persentase_diskon"
        ].mean()

        diskon_terbesar = data_diskon.loc[
            data_diskon["persentase_diskon"].idxmax()
        ]

        print("\n" + "=" * 50)
        print("ANALISIS DISKON PRODUK BRODO")
        print("=" * 50)

        print(f"Total kombinasi produk-ukuran : {jumlah_total}")
        print(f"Produk dengan diskon          : {jumlah_diskon}")
        print(f"Produk tanpa diskon           : {jumlah_tanpa_diskon}")

        print(
            f"Rata-rata persentase diskon   : "
            f"{rata_rata_diskon:.2f}%"
        )

        print(
            f"Diskon terbesar               : "
            f"{diskon_terbesar['persentase_diskon']:.2f}%"
        )

        print(
            f"Produk                         : "
            f"{diskon_terbesar['nama_produk']}"
        )

        print(
            f"Ukuran                         : "
            f"{diskon_terbesar['ukuran']}"
        )

        print(
            f"Harga normal                   : "
            f"Rp{diskon_terbesar['harga_normal']:,.0f}"
        )

        print(
            f"Harga diskon                   : "
            f"Rp{diskon_terbesar['harga_diskon']:,.0f}"
        )

    else:
        rata_rata_diskon = 0
        diskon_terbesar = None

        print("\nBelum ditemukan produk yang sedang diskon.")

    ringkasan = {
        "total_record": jumlah_total,
        "jumlah_diskon": jumlah_diskon,
        "tanpa_diskon": jumlah_tanpa_diskon,
        "rata_rata_diskon": rata_rata_diskon,
        "diskon_terbesar": diskon_terbesar
    }

    return ringkasan


# ==========================================
# DAFTAR DISKON TERBESAR
# ==========================================

def daftar_diskon_terbesar(df, batas=10):
    """
    Menampilkan produk dengan persentase diskon terbesar.
    """

    data = ambil_data_terbaru(df)

    if data.empty:
        return None

    hasil = data[
        data["persentase_diskon"].fillna(0) > 0
    ].copy()

    if hasil.empty:
        print("Tidak ada produk yang sedang diskon.")
        return hasil

    hasil = hasil.sort_values(
        "persentase_diskon",
        ascending=False
    ).head(batas)

    kolom = [
        "nama_produk",
        "ukuran",
        "harga_normal",
        "harga_diskon",
        "persentase_diskon"
    ]

    print("\n" + "=" * 50)
    print(f"TOP {batas} DISKON TERBESAR BRODO")
    print("=" * 50)

    print(
        hasil[kolom].to_string(index=False)
    )

    return hasil


# ==========================================
# ANALISIS KETERSEDIAAN STOK
# ==========================================

def analisis_stok(df):

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data stok.")
        return None

    data["status_stok"] = data["ketersediaan"].apply(
        normalisasi_stok
    )

    hasil = data["status_stok"].value_counts()

    print("\n" + "=" * 50)
    print("ANALISIS KETERSEDIAAN STOK")
    print("=" * 50)

    for status, jumlah in hasil.items():
        print(f"{status}: {jumlah} kombinasi produk-ukuran")

    return hasil


# ==========================================
# ANALISIS BERDASARKAN UKURAN
# ==========================================

def analisis_ukuran(df):

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data ukuran.")
        return None

    data["status"] = data["ketersediaan"].apply(
        normalisasi_stok
    )

    kolom = [
        "nama_produk",
        "ukuran",
        "harga_normal",
        "harga_diskon",
        "harga",
        "persentase_diskon",
        "status"
    ]

    hasil = data[kolom].copy()

    hasil = hasil.sort_values(
        ["nama_produk", "ukuran"]
    )

    print("\n" + "=" * 50)
    print("HARGA PRODUK BERDASARKAN UKURAN")
    print("=" * 50)

    print(hasil.to_string(index=False))

    return hasil


# ==========================================
# GRAFIK PERBANDINGAN HARGA
# ==========================================

def grafik_harga(df):

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data untuk grafik harga.")
        return

    data = data.sort_values(
        ["nama_produk", "ukuran"]
    ).copy()

    data["label"] = (
        data["nama_produk"].astype(str)
        + " - "
        + data["ukuran"].astype(str)
    )

    plt.figure(figsize=(12, 7))

    plt.bar(
        data["label"],
        data["harga"]
    )

    plt.title("Perbandingan Harga Produk Sepatu BRODO")
    plt.xlabel("Produk dan Ukuran")
    plt.ylabel("Harga (Rupiah)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    nama_file = os.path.join(
        GRAFIK_DIR,
        "grafik_harga.png"
    )

    plt.savefig(nama_file, dpi=300)
    plt.close()

    print(f"Grafik harga disimpan: {nama_file}")


# ==========================================
# GRAFIK PERBANDINGAN HARGA NORMAL DAN DISKON
# ==========================================

def grafik_perbandingan_diskon(df):

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data untuk grafik diskon.")
        return

    data = data[
        data["persentase_diskon"].fillna(0) > 0
    ].copy()

    if data.empty:
        print("Belum ada produk diskon untuk digrafikkan.")
        return

    data = data.sort_values(
        "persentase_diskon",
        ascending=False
    ).head(15)

    data["label"] = (
        data["nama_produk"].astype(str)
        + " - "
        + data["ukuran"].astype(str)
    )

    posisi = range(len(data))

    plt.figure(figsize=(13, 7))

    plt.bar(
        [x - 0.2 for x in posisi],
        data["harga_normal"],
        width=0.4,
        label="Harga Normal"
    )

    plt.bar(
        [x + 0.2 for x in posisi],
        data["harga_diskon"],
        width=0.4,
        label="Harga Diskon"
    )

    plt.title("Perbandingan Harga Normal dan Harga Diskon BRODO")
    plt.xlabel("Produk dan Ukuran")
    plt.ylabel("Harga (Rupiah)")

    plt.xticks(
        list(posisi),
        data["label"],
        rotation=45,
        ha="right"
    )

    plt.legend()
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    nama_file = os.path.join(
        GRAFIK_DIR,
        "grafik_perbandingan_diskon.png"
    )

    plt.savefig(nama_file, dpi=300)
    plt.close()

    print(f"Grafik perbandingan diskon disimpan: {nama_file}")


# ==========================================
# GRAFIK PERSENTASE DISKON
# ==========================================

def grafik_persentase_diskon(df):

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data untuk grafik persentase diskon.")
        return

    data = data[
        data["persentase_diskon"].fillna(0) > 0
    ].copy()

    if data.empty:
        print("Tidak ada data diskon untuk digrafikkan.")
        return

    data = data.sort_values(
        "persentase_diskon",
        ascending=False
    ).head(15)

    data["label"] = (
        data["nama_produk"].astype(str)
        + " - "
        + data["ukuran"].astype(str)
    )

    plt.figure(figsize=(12, 7))

    plt.barh(
        data["label"],
        data["persentase_diskon"]
    )

    plt.title("Persentase Diskon Produk Sepatu BRODO")
    plt.xlabel("Persentase Diskon (%)")
    plt.ylabel("Produk dan Ukuran")
    plt.gca().invert_yaxis()
    plt.grid(axis="x", alpha=0.3)

    plt.tight_layout()

    nama_file = os.path.join(
        GRAFIK_DIR,
        "grafik_persentase_diskon.png"
    )

    plt.savefig(nama_file, dpi=300)
    plt.close()

    print(f"Grafik persentase diskon disimpan: {nama_file}")


# ==========================================
# GRAFIK KETERSEDIAAN STOK
# ==========================================

def grafik_stok(df):

    data = ambil_data_terbaru(df)

    if data.empty:
        print("Tidak ada data untuk grafik stok.")
        return

    status = data["ketersediaan"].apply(
        normalisasi_stok
    )

    jumlah = status.value_counts()

    plt.figure(figsize=(7, 7))

    plt.pie(
        jumlah.values,
        labels=jumlah.index,
        autopct="%1.1f%%",
        startangle=90
    )

    plt.title("Ketersediaan Stok Produk Sepatu BRODO")
    plt.tight_layout()

    nama_file = os.path.join(
        GRAFIK_DIR,
        "grafik_stok.png"
    )

    plt.savefig(nama_file, dpi=300)
    plt.close()

    print(f"Grafik stok disimpan: {nama_file}")


# ==========================================
# GRAFIK RIWAYAT PERUBAHAN HARGA
# ==========================================

def grafik_riwayat_harga(df):

    if df.empty:
        print("Tidak ada data riwayat harga.")
        return

    data = df.dropna(
        subset=["waktu_scraping", "harga"]
    ).copy()

    if data.empty:
        print("Tidak ada data valid untuk grafik riwayat harga.")
        return

    plt.figure(figsize=(13, 7))

    for (nama_produk, ukuran), kelompok in data.groupby(
        ["nama_produk", "ukuran"]
    ):

        kelompok = kelompok.sort_values("waktu_scraping")

        plt.plot(
            kelompok["waktu_scraping"],
            kelompok["harga"],
            marker="o",
            label=f"{nama_produk} - Ukuran {ukuran}"
        )

    plt.title("Riwayat Perubahan Harga Produk Sepatu BRODO")
    plt.xlabel("Waktu Scraping")
    plt.ylabel("Harga (Rupiah)")

    plt.legend(
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=8
    )

    plt.grid(alpha=0.3)
    plt.xticks(rotation=30)
    plt.tight_layout()

    nama_file = os.path.join(
        GRAFIK_DIR,
        "grafik_riwayat_harga.png"
    )

    plt.savefig(
        nama_file,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print(f"Grafik riwayat harga disimpan: {nama_file}")


# ==========================================
# PROGRAM UTAMA
# ==========================================

if __name__ == "__main__":

    print("\nMEMULAI ANALISIS DATA BRODOTRACK")

    df = ambil_data()

    if not df.empty:

        print("\nJumlah catatan riwayat harga:", len(df))
        print("Jumlah produk:", df["id_produk"].nunique())

        # Analisis statistik
        analisis_harga(df)
        analisis_diskon(df)
        daftar_diskon_terbesar(df)
        analisis_stok(df)
        analisis_ukuran(df)

        # Visualisasi
        grafik_harga(df)
        grafik_perbandingan_diskon(df)
        grafik_persentase_diskon(df)
        grafik_stok(df)
        grafik_riwayat_harga(df)

        print("\n" + "=" * 50)
        print("ANALISIS BRODOTRACK SELESAI")
        print("=" * 50)

    else:
        print(
            "Analisis tidak dapat dilakukan "
            "karena data kosong."
        )
