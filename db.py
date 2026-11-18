
import sqlite3
from config import DATABASE_PATH


# ==================================================
# KONEKSI DATABASE
# ==================================================

def get_connection():
    """Membuat koneksi ke database BRODOTRACK."""

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# ==================================================
# MEMBUAT DAN MEMPERBARUI TABEL
# ==================================================

def create_tables():
    """Membuat tabel dan memperbarui struktur database."""

    with get_connection() as connection:

        # Tabel utama untuk menyimpan informasi produk
        connection.execute("""
            CREATE TABLE IF NOT EXISTS produk (
                id_produk INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_produk TEXT NOT NULL,
                kategori TEXT,
                deskripsi TEXT,
                sku TEXT,
                url_produk TEXT UNIQUE NOT NULL,
                url_gambar TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabel untuk menyimpan riwayat harga, diskon, dan stok
        connection.execute("""
            CREATE TABLE IF NOT EXISTS riwayat_harga (
                id_riwayat INTEGER PRIMARY KEY AUTOINCREMENT,
                id_produk INTEGER NOT NULL,
                ukuran TEXT,
                harga REAL NOT NULL,
                harga_normal REAL,
                harga_diskon REAL,
                persentase_diskon REAL,
                mata_uang TEXT DEFAULT 'IDR',
                ketersediaan TEXT,
                waktu_scraping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (id_produk)
                    REFERENCES produk(id_produk)
                    ON DELETE CASCADE
            )
        """)

        # Memeriksa kolom tabel riwayat harga
        kolom_riwayat = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(riwayat_harga)"
            ).fetchall()
        }

        # Kolom tambahan untuk pemantauan diskon
        kolom_baru = {
            "harga_normal": "REAL",
            "harga_diskon": "REAL",
            "persentase_diskon": "REAL"
        }

        # Menambahkan kolom yang belum tersedia
        for nama_kolom, tipe_data in kolom_baru.items():

            if nama_kolom not in kolom_riwayat:
                connection.execute(
                    f"""
                    ALTER TABLE riwayat_harga
                    ADD COLUMN {nama_kolom} {tipe_data}
                    """
                )

        # Tabel untuk mencatat aktivitas scraping
        connection.execute("""
            CREATE TABLE IF NOT EXISTS log_scraping (
                id_log INTEGER PRIMARY KEY AUTOINCREMENT,
                waktu_mulai TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                waktu_selesai TIMESTAMP,
                jumlah_produk INTEGER DEFAULT 0,
                status TEXT,
                keterangan TEXT
            )
        """)

    print("Database BRODOTRACK berhasil disiapkan.")


# ==================================================
# FILTER DATA
# ==================================================

def validasi_data_produk(nama_produk, url_produk):
    """
    Memeriksa kelengkapan informasi produk.

    Data yang tidak memiliki nama atau URL ditolak.
    """

    if not nama_produk or not str(nama_produk).strip():
        return False

    if not url_produk or not str(url_produk).strip():
        return False

    if not str(url_produk).startswith(("http://", "https://")):
        return False

    return True


def validasi_data_harga(id_produk, harga, ukuran=None):
    """
    Memeriksa validitas data harga sebelum disimpan.
    """

    if id_produk is None:
        return False

    try:
        harga = float(harga)
    except (TypeError, ValueError):
        return False

    if harga <= 0:
        return False

    if ukuran is not None and not str(ukuran).strip():
        return False

    return True


def data_sama(nilai_lama, nilai_baru):
    """Membandingkan dua nilai dengan toleransi angka desimal."""

    if nilai_lama is None and nilai_baru is None:
        return True

    if nilai_lama is None or nilai_baru is None:
        return False

    try:
        return abs(float(nilai_lama) - float(nilai_baru)) < 0.000001
    except (TypeError, ValueError):
        return str(nilai_lama).strip() == str(nilai_baru).strip()


# ==================================================
# MEMBERSIHKAN DUPLIKASI RIWAYAT LAMA
# ==================================================

def bersihkan_riwayat_duplikat():
    """
    Menghapus pencatatan berulang yang kondisinya identik
    secara berurutan untuk produk dan ukuran yang sama.

    Riwayat perubahan harga, diskon, dan stok tetap dipertahankan.
    """

    jumlah_dihapus = 0

    with get_connection() as connection:

        data = connection.execute("""
            SELECT *
            FROM riwayat_harga
            ORDER BY id_produk, COALESCE(TRIM(ukuran), ''), id_riwayat
        """).fetchall()

        data_terakhir = {}
        id_duplikat = []

        for row in data:

            # Identitas kombinasi produk dan ukuran
            ukuran = (row["ukuran"] or "").strip().lower()
            kunci = (row["id_produk"], ukuran)

            kondisi_sekarang = (
                row["harga"],
                row["harga_normal"],
                row["harga_diskon"],
                row["persentase_diskon"],
                row["mata_uang"],
                row["ketersediaan"]
            )

            kondisi_sebelumnya = data_terakhir.get(kunci)

            # Jika kondisi sama dengan pencatatan sebelumnya,
            # data dianggap duplikat dan tidak diperlukan
            if kondisi_sebelumnya is not None:

                sama = all(
                    data_sama(lama, baru)
                    for lama, baru in zip(
                        kondisi_sebelumnya,
                        kondisi_sekarang
                    )
                )

                if sama:
                    id_duplikat.append(row["id_riwayat"])
                    continue

            # Memperbarui kondisi terakhir untuk kombinasi tersebut
            data_terakhir[kunci] = kondisi_sekarang

        # Menghapus hanya baris yang teridentifikasi duplikat
        if id_duplikat:

            connection.executemany("""
                DELETE FROM riwayat_harga
                WHERE id_riwayat = ?
            """, [(id_data,) for id_data in id_duplikat])

            jumlah_dihapus = len(id_duplikat)

    print(f"Jumlah riwayat duplikat dibersihkan: {jumlah_dihapus}")

    return jumlah_dihapus


# ==================================================
# MENYIMPAN DATA PRODUK
# ==================================================

def simpan_produk(
    nama_produk,
    url_produk,
    kategori=None,
    deskripsi=None,
    sku=None,
    url_gambar=None
):
    """
    Menyimpan produk baru atau memperbarui produk yang sudah ada.

    URL produk digunakan sebagai identitas unik.
    """

    # Menolak data produk yang tidak valid
    if not validasi_data_produk(nama_produk, url_produk):
        print("Data produk ditolak karena tidak valid.")
        return None

    # Membersihkan spasi pada nama dan URL
    nama_produk = str(nama_produk).strip()
    url_produk = str(url_produk).strip()

    with get_connection() as connection:

        # Memasukkan produk.
        # Jika URL sudah ada, informasi produk diperbarui.
        connection.execute("""
            INSERT INTO produk (
                nama_produk,
                kategori,
                deskripsi,
                sku,
                url_produk,
                url_gambar
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(url_produk) DO UPDATE SET
                nama_produk = excluded.nama_produk,
                kategori = excluded.kategori,
                deskripsi = excluded.deskripsi,
                sku = excluded.sku,
                url_gambar = excluded.url_gambar,
                updated_at = CURRENT_TIMESTAMP
        """, (
            nama_produk,
            kategori,
            deskripsi,
            sku,
            url_produk,
            url_gambar
        ))

        # Mengambil ID produk untuk digunakan pada riwayat harga
        result = connection.execute("""
            SELECT id_produk
            FROM produk
            WHERE url_produk = ?
        """, (url_produk,)).fetchone()

        return result["id_produk"]


# ==================================================
# MENYIMPAN RIWAYAT HARGA DAN DISKON
# ==================================================

def simpan_riwayat_harga(
    id_produk,
    harga,
    ukuran=None,
    mata_uang="IDR",
    ketersediaan=None,
    harga_normal=None,
    harga_diskon=None,
    persentase_diskon=None
):
    """
    Menyimpan riwayat harga jika terdapat perubahan data.

    Data identik dengan pencatatan terakhir tidak disimpan ulang.

    Jika harga, diskon, atau stok berubah, riwayat baru tetap dibuat.
    """

    # Memvalidasi data harga
    if not validasi_data_harga(id_produk, harga, ukuran):
        print("Data harga ditolak karena tidak valid.")
        return False

    harga = float(harga)
    ukuran = str(ukuran).strip() if ukuran is not None else None

    # Memeriksa validitas kolom harga tambahan
    for nilai in (harga_normal, harga_diskon, persentase_diskon):

        if nilai is not None:
            try:
                nilai = float(nilai)
            except (TypeError, ValueError):
                print("Data diskon ditolak karena tidak valid.")
                return False

            if nilai < 0:
                print("Data diskon tidak boleh negatif.")
                return False

    with get_connection() as connection:

        # Memastikan produk benar-benar tersedia
        produk = connection.execute("""
            SELECT id_produk
            FROM produk
            WHERE id_produk = ?
        """, (id_produk,)).fetchone()

        if produk is None:
            print("Data ditolak: produk tidak ditemukan.")
            return False

        # Mengambil riwayat terakhir untuk produk dan ukuran yang sama
        riwayat_terakhir = connection.execute("""
            SELECT *
            FROM riwayat_harga
            WHERE id_produk = ?
              AND LOWER(TRIM(COALESCE(ukuran, ''))) =
                  LOWER(TRIM(COALESCE(?, '')))
            ORDER BY id_riwayat DESC
            LIMIT 1
        """, (id_produk, ukuran)).fetchone()

        kondisi_baru = (
            harga,
            harga_normal,
            harga_diskon,
            persentase_diskon,
            mata_uang,
            ketersediaan
        )

        # Membandingkan data baru dengan pencatatan terakhir
        if riwayat_terakhir is not None:

            kondisi_lama = (
                riwayat_terakhir["harga"],
                riwayat_terakhir["harga_normal"],
                riwayat_terakhir["harga_diskon"],
                riwayat_terakhir["persentase_diskon"],
                riwayat_terakhir["mata_uang"],
                riwayat_terakhir["ketersediaan"]
            )

            sama = all(
                data_sama(lama, baru)
                for lama, baru in zip(kondisi_lama, kondisi_baru)
            )

            # Menghentikan penyimpanan jika data tidak berubah
            if sama:
                print("Data identik dilewati, tidak disimpan ulang.")
                return False

        # Menyimpan riwayat baru hanya jika ada perubahan
        connection.execute("""
            INSERT INTO riwayat_harga (
                id_produk,
                ukuran,
                harga,
                harga_normal,
                harga_diskon,
                persentase_diskon,
                mata_uang,
                ketersediaan
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_produk,
            ukuran,
            harga,
            harga_normal,
            harga_diskon,
            persentase_diskon,
            mata_uang,
            ketersediaan
        ))

        print("Riwayat baru berhasil disimpan.")
        return True


# ==================================================
# MENYIMPAN LOG SCRAPING
# ==================================================

def simpan_log(
    jumlah_produk,
    status,
    waktu_mulai=None,
    keterangan=None
):
    """Mencatat aktivitas scraping."""

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO log_scraping (
                waktu_mulai,
                waktu_selesai,
                jumlah_produk,
                status,
                keterangan
            )
            VALUES (
                COALESCE(?, CURRENT_TIMESTAMP),
                CURRENT_TIMESTAMP,
                ?,
                ?,
                ?
            )
        """, (
            waktu_mulai,
            jumlah_produk,
            status,
            keterangan
        ))


# ==================================================
# MENJALANKAN DATABASE
# ==================================================

if __name__ == "__main__":

    # Menyiapkan seluruh tabel database
    create_tables()

    # Membersihkan duplikasi riwayat yang berurutan
    bersihkan_riwayat_duplikat()

    print("Database BRODOTRACK siap digunakan.")
