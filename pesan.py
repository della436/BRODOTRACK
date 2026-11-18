
import sqlite3

from config import DATABASE_PATH


# ==========================================
# KONEKSI DATABASE
# ==========================================

def get_connection():
    """Membuat koneksi ke database BRODOTRACK."""

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


# ==========================================
# FORMAT RUPIAH
# ==========================================

def format_rupiah(nilai):
    """Mengubah angka menjadi format Rupiah."""

    if nilai is None:
        return "Tidak tersedia"

    return f"Rp{nilai:,.0f}".replace(",", ".")


# ==========================================
# MENGAMBIL DATA TERBARU
# ==========================================

def ambil_data_terbaru():
    """
    Mengambil harga dan stok terbaru
    untuk setiap produk dan ukuran.
    """

    query = """
        SELECT
            p.id_produk,
            p.nama_produk,
            p.kategori,
            p.url_produk,
            r.ukuran,
            r.harga,
            r.mata_uang,
            r.ketersediaan,
            r.waktu_scraping

        FROM riwayat_harga r

        JOIN produk p
            ON p.id_produk = r.id_produk

        WHERE r.id_riwayat = (
            SELECT MAX(r2.id_riwayat)
            FROM riwayat_harga r2
            WHERE r2.id_produk = r.id_produk
            AND r2.ukuran IS r.ukuran
        )

        ORDER BY p.nama_produk, r.ukuran
    """

    with get_connection() as connection:
        return connection.execute(query).fetchall()


# ==========================================
# MENGAMBIL WAKTU SCRAPING TERAKHIR
# ==========================================

def ambil_waktu_scraping_terakhir():
    """Mengambil waktu scraping paling baru."""

    with get_connection() as connection:

        hasil = connection.execute("""
            SELECT MAX(waktu_scraping) AS terakhir
            FROM riwayat_harga
        """).fetchone()

    return hasil["terakhir"]


# ==========================================
# STATUS STOK
# ==========================================

def status_stok(ketersediaan):
    """Mengubah informasi ketersediaan menjadi teks."""

    if isinstance(ketersediaan, str):

        if ketersediaan.endswith("/InStock"):
            return "Tersedia"

        if ketersediaan.endswith("/OutOfStock"):
            return "Habis"

    return "Tidak diketahui"


# ==========================================
# PESAN RINGKASAN
# ==========================================

def buat_pesan_ringkasan():
    """
    Membuat ringkasan database terbaru.

    Ringkasan hanya menampilkan:
    - Total produk
    - Stok tersedia
    - Stok habis
    - Harga tertinggi
    - Harga terendah
    - Waktu pembaruan terakhir
    """

    data = ambil_data_terbaru()

    if not data:
        return "Belum ada data produk BRODOTRACK."

    daftar_produk = set()
    jumlah_tersedia = 0
    jumlah_habis = 0

    harga = []

    for row in data:

        daftar_produk.add(row["id_produk"])

        if row["harga"] is not None:
            harga.append(float(row["harga"]))

        status = status_stok(row["ketersediaan"])

        if status == "Tersedia":
            jumlah_tersedia += 1

        elif status == "Habis":
            jumlah_habis += 1

    harga_tertinggi = max(harga) if harga else None
    harga_terendah = min(harga) if harga else None

    waktu_terakhir = ambil_waktu_scraping_terakhir()

    if waktu_terakhir is None:
        waktu_terakhir = "Belum tersedia"

    pesan = (
        "📊 RINGKASAN BRODOTRACK\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Total produk       : {len(daftar_produk)}\n"
        f"Stok tersedia      : {jumlah_tersedia}\n"
        f"Stok habis         : {jumlah_habis}\n"
        f"Harga tertinggi    : {format_rupiah(harga_tertinggi)}\n"
        f"Harga terendah     : {format_rupiah(harga_terendah)}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Terakhir diperbarui: {waktu_terakhir}"
    )

    return pesan


# ==========================================
# DAFTAR PRODUK
# ==========================================

def buat_pesan_daftar_produk():
    """Menampilkan daftar produk BRODO."""

    data = ambil_data_terbaru()

    if not data:
        return "Belum ada produk yang tersimpan."

    produk = {}

    for row in data:

        produk[row["id_produk"]] = {
            "nama": row["nama_produk"],
            "url": row["url_produk"]
        }

    pesan = [
        "👟 DAFTAR PRODUK BRODO",
        "━━━━━━━━━━━━━━━━━━"
    ]

    for nomor, item in enumerate(produk.values(), start=1):

        pesan.append(
            f"{nomor}. {item['nama']}\n"
            f"   {item['url']}"
        )

    return "\n".join(pesan)


# ==========================================
# DETAIL PRODUK
# ==========================================

def buat_pesan_detail_produk(id_produk):
    """Menampilkan detail harga dan stok berdasarkan ID."""

    data = ambil_data_terbaru()

    hasil = [
        row for row in data
        if row["id_produk"] == id_produk
    ]

    if not hasil:
        return "Produk tidak ditemukan."

    nama_produk = hasil[0]["nama_produk"]
    url_produk = hasil[0]["url_produk"]

    pesan = [
        f"👟 {nama_produk}",
        "━━━━━━━━━━━━━━━━━━",
        f"Link produk: {url_produk}",
        "",
        "DAFTAR HARGA DAN UKURAN"
    ]

    for row in hasil:

        pesan.append(
            f"Ukuran {row['ukuran']} | "
            f"{format_rupiah(row['harga'])} | "
            f"{status_stok(row['ketersediaan'])}"
        )

    return "\n".join(pesan)


# ==========================================
# PERUBAHAN HARGA
# ==========================================

def buat_pesan_perubahan_harga():
    """Membandingkan dua catatan terakhir setiap produk dan ukuran."""

    with get_connection() as connection:

        query = """
            SELECT
                p.id_produk,
                p.nama_produk,
                r.ukuran,
                r.harga,
                r.waktu_scraping

            FROM riwayat_harga r

            JOIN produk p
                ON p.id_produk = r.id_produk

            ORDER BY
                r.id_produk,
                r.ukuran,
                r.id_riwayat DESC
        """

        rows = connection.execute(query).fetchall()

    kelompok = {}

    for row in rows:

        key = (row["id_produk"], row["ukuran"])

        kelompok.setdefault(key, []).append(row)

    pesan = [
        "📈 PERUBAHAN HARGA BRODO",
        "━━━━━━━━━━━━━━━━━━"
    ]

    jumlah_perubahan = 0

    for (id_produk, ukuran), riwayat in kelompok.items():

        if len(riwayat) < 2:
            continue

        terbaru = riwayat[0]
        sebelumnya = riwayat[1]

        harga_baru = terbaru["harga"]
        harga_lama = sebelumnya["harga"]

        if harga_baru is None or harga_lama is None:
            continue

        if harga_baru == harga_lama:
            continue

        selisih = harga_baru - harga_lama

        keterangan = "Naik" if selisih > 0 else "Turun"

        pesan.append(
            f"\n{terbaru['nama_produk']}\n"
            f"Ukuran: {ukuran}\n"
            f"Harga sebelumnya: {format_rupiah(harga_lama)}\n"
            f"Harga terbaru: {format_rupiah(harga_baru)}\n"
            f"Perubahan: {keterangan} "
            f"{format_rupiah(abs(selisih))}"
        )

        jumlah_perubahan += 1

    if jumlah_perubahan == 0:
        pesan.append("\nBelum ditemukan perubahan harga.")

    return "\n".join(pesan)


# ==========================================
# PESAN HASIL SCRAPING
# ==========================================

def buat_pesan_scraping(jumlah_record, target=100):
    """Membuat notifikasi hasil scraping."""

    status = (
        "TARGET TERCAPAI"
        if jumlah_record >= target
        else "TARGET BELUM TERCAPAI"
    )

    pesan = (
        "🔄 HASIL SCRAPING BRODOTRACK\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Target record : {target}\n"
        f"Berhasil      : {jumlah_record}\n"
        f"Status        : {status}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    return pesan


# ==========================================
# PENGUJIAN PESAN
# ==========================================

if __name__ == "__main__":

    print("\nMEMULAI PENGUJIAN PESAN BRODOTRACK")

    print("\n")
    print(buat_pesan_ringkasan())

    print("\n")
    print(buat_pesan_daftar_produk())

    print("\n")
    print(buat_pesan_perubahan_harga())

    print("\n")
    print("Waktu scraping terakhir:")
    print(ambil_waktu_scraping_terakhir())

    print("\nPENGUJIAN PESAN SELESAI.")
