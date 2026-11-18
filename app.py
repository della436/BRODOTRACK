
import os
import sqlite3

from flask import (
    Flask,
    render_template,
    abort,
    send_from_directory,
    redirect,
    url_for
)

from config import DATABASE_PATH, LAPORAN_DIR, GRAFIK_DIR


# ==========================================
# KONFIGURASI APLIKASI
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "FLASK_SECRET_KEY",
    "brodotrack-development-key"
)


# ==========================================
# KONEKSI DATABASE
# ==========================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ==========================================
# FORMAT STATUS STOK
# ==========================================

def format_status_stok(status):
    if not status:
        return "Tidak diketahui"

    status = str(status).strip().lower()

    if status == "tersedia" or status.endswith("instock"):
        return "Tersedia"

    if status in ["habis", "tidak tersedia", "out of stock", "sold out"]:
        return "Habis"

    if status.endswith("outofstock"):
        return "Habis"

    return "Tidak diketahui"


# ==========================================
# MENGAMBIL DATA TERBARU PER PRODUK DAN UKURAN
# ==========================================

def get_data_terbaru(conn):
    return conn.execute("""
        SELECT
            rh.id_riwayat,
            rh.id_produk,
            p.nama_produk,
            p.kategori,
            p.url_gambar,
            p.url_produk,
            rh.ukuran,
            rh.harga,
            rh.harga_normal,
            rh.harga_diskon,
            rh.persentase_diskon,
            rh.ketersediaan,
            rh.waktu_scraping
        FROM riwayat_harga rh
        INNER JOIN (
            SELECT
                id_produk,
                ukuran,
                MAX(id_riwayat) AS id_terbaru
            FROM riwayat_harga
            GROUP BY id_produk, ukuran
        ) terbaru
            ON rh.id_riwayat = terbaru.id_terbaru
        INNER JOIN produk p
            ON rh.id_produk = p.id_produk
        ORDER BY p.nama_produk, rh.ukuran
    """).fetchall()


# ==========================================
# MENGELOMPOKKAN DATA BERDASARKAN PRODUK
# ==========================================

def kelompokkan_produk(data):
    kelompok = {}

    for row in data:
        id_produk = row["id_produk"]

        if id_produk not in kelompok:
            kelompok[id_produk] = []

        kelompok[id_produk].append(row)

    return kelompok


# ==========================================
# DASHBOARD UTAMA
# ==========================================

@app.route("/")
def dashboard():

    conn = get_db_connection()

    try:
        # Total produk unik
        total_produk = conn.execute("""
            SELECT COUNT(*)
            FROM produk
        """).fetchone()[0]

        # Data terbaru setiap ukuran
        data_terbaru = get_data_terbaru(conn)

        # Kelompokkan varian berdasarkan produk
        kelompok_produk = kelompokkan_produk(data_terbaru)

        # Perhitungan statistik per produk
        stok_tersedia = 0
        stok_habis = 0
        total_produk_diskon = 0

        for varian in kelompok_produk.values():

            status_varian = [
                format_status_stok(row["ketersediaan"])
                for row in varian
            ]

            # Minimal satu ukuran tersedia
            if "Tersedia" in status_varian:
                stok_tersedia += 1

            # Seluruh ukuran harus diketahui habis
            elif status_varian and all(
                status == "Habis" for status in status_varian
            ):
                stok_habis += 1

            # Minimal satu ukuran mendapatkan diskon
            ada_diskon = any(
                row["persentase_diskon"] is not None
                and row["persentase_diskon"] > 0
                for row in varian
            )

            if ada_diskon:
                total_produk_diskon += 1

        # ======================================
        # TOP 5 DISKON TERBESAR PER PRODUK
        # ======================================

        data_promo = [
            row for row in data_terbaru
            if row["persentase_diskon"] is not None
            and row["persentase_diskon"] > 0
        ]

        # Ambil satu varian dengan diskon terbesar
        # untuk setiap produk
        promo_per_produk = {}

        for row in data_promo:
            id_produk = row["id_produk"]

            if (
                id_produk not in promo_per_produk
                or row["persentase_diskon"]
                > promo_per_produk[id_produk]["persentase_diskon"]
            ):
                promo_per_produk[id_produk] = row

        top_5_diskon = sorted(
            promo_per_produk.values(),
            key=lambda row: row["persentase_diskon"],
            reverse=True
        )[:5]

        # ======================================
        # HARGA TERTINGGI DAN TERENDAH
        # ======================================

        daftar_harga = [
            row["harga"]
            for row in data_terbaru
            if row["harga"] is not None
        ]

        harga_tertinggi = (
            max(daftar_harga) if daftar_harga else 0
        )

        harga_terendah = (
            min(daftar_harga) if daftar_harga else 0
        )

        return render_template(
            "dashboard.html",
            total_produk=total_produk,
            total_produk_diskon=total_produk_diskon,
            stok_tersedia=stok_tersedia,
            stok_habis=stok_habis,
            harga_tertinggi=harga_tertinggi,
            harga_terendah=harga_terendah,
            top_5_diskon=top_5_diskon
        )

    finally:
        conn.close()


# ==========================================
# KATALOG PRODUK
# ==========================================

@app.route("/produk")
def daftar_produk():

    conn = get_db_connection()

    try:
        produk = conn.execute("""
            SELECT
                p.*,
                rh.harga,
                rh.harga_normal,
                rh.harga_diskon,
                rh.persentase_diskon,
                rh.ketersediaan,
                rh.waktu_scraping
            FROM produk p
            LEFT JOIN riwayat_harga rh
                ON rh.id_riwayat = (
                    SELECT MAX(rh2.id_riwayat)
                    FROM riwayat_harga rh2
                    WHERE rh2.id_produk = p.id_produk
                )
            ORDER BY p.nama_produk
        """).fetchall()

        return render_template(
            "produk.html",
            produk=produk
        )

    finally:
        conn.close()


# ==========================================
# DETAIL PRODUK
# ==========================================

@app.route("/produk/<int:id_produk>")
def detail_produk(id_produk):

    conn = get_db_connection()

    try:
        produk = conn.execute("""
            SELECT *
            FROM produk
            WHERE id_produk = ?
        """, (id_produk,)).fetchone()

        if produk is None:
            abort(404)

        ukuran = conn.execute("""
            SELECT *
            FROM riwayat_harga
            WHERE id_produk = ?
            AND id_riwayat IN (
                SELECT MAX(id_riwayat)
                FROM riwayat_harga
                WHERE id_produk = ?
                GROUP BY ukuran
            )
            ORDER BY ukuran
        """, (id_produk, id_produk)).fetchall()

        riwayat = conn.execute("""
            SELECT *
            FROM riwayat_harga
            WHERE id_produk = ?
            ORDER BY id_riwayat DESC
            LIMIT 50
        """, (id_produk,)).fetchall()

        return render_template(
            "detail_produk.html",
            produk=produk,
            ukuran=ukuran,
            riwayat=riwayat
        )

    finally:
        conn.close()


# ==========================================
# RIWAYAT HARGA
# ==========================================

@app.route("/riwayat")
def riwayat_harga():

    conn = get_db_connection()

    try:
        total_riwayat = conn.execute("""
            SELECT COUNT(*)
            FROM riwayat_harga
        """).fetchone()[0]

        total_produk_dipantau = conn.execute("""
            SELECT COUNT(DISTINCT id_produk)
            FROM riwayat_harga
        """).fetchone()[0]

        perubahan_harga = conn.execute("""
            SELECT COUNT(*)
            FROM (
                SELECT
                    id_produk,
                    ukuran,
                    harga,
                    LAG(harga) OVER (
                        PARTITION BY id_produk, ukuran
                        ORDER BY id_riwayat
                    ) AS harga_sebelumnya
                FROM riwayat_harga
            )
            WHERE harga_sebelumnya IS NOT NULL
            AND harga != harga_sebelumnya
        """).fetchone()[0]

        riwayat = conn.execute("""
            SELECT
                rh.*,
                p.nama_produk
            FROM riwayat_harga rh
            JOIN produk p
                ON rh.id_produk = p.id_produk
            ORDER BY rh.id_riwayat DESC
            LIMIT 200
        """).fetchall()

        scraping = conn.execute("""
            SELECT *
            FROM log_scraping
            ORDER BY id_log DESC
            LIMIT 50
        """).fetchall()

        return render_template(
            "riwayat.html",
            riwayat=riwayat,
            scraping=scraping,
            total_riwayat=total_riwayat,
            total_produk_dipantau=total_produk_dipantau,
            perubahan_harga=perubahan_harga
        )

    finally:
        conn.close()


# ==========================================
# MONITORING STOK
# ==========================================

@app.route("/stok")
def monitoring_stok():

    conn = get_db_connection()

    try:
        data_stok = get_data_terbaru(conn)

        stok_tersedia = [
            row for row in data_stok
            if format_status_stok(row["ketersediaan"]) == "Tersedia"
        ]

        stok_habis = [
            row for row in data_stok
            if format_status_stok(row["ketersediaan"]) == "Habis"
        ]

        stok_tidak_diketahui = [
            row for row in data_stok
            if format_status_stok(row["ketersediaan"]) == "Tidak diketahui"
        ]

        return render_template(
            "stok.html",
            data_stok=data_stok,
            stok_tersedia=stok_tersedia,
            stok_habis=stok_habis,
            stok_tidak_diketahui=stok_tidak_diketahui,
            total_tersedia=len(stok_tersedia),
            total_habis=len(stok_habis),
            total_tidak_diketahui=len(stok_tidak_diketahui),
            total_kombinasi=len(data_stok),
            format_status_stok=format_status_stok
        )

    finally:
        conn.close()


# ==========================================
# MONITORING DISKON
# ==========================================

@app.route("/diskon")
def monitoring_diskon():

    conn = get_db_connection()

    try:
        data_terbaru = get_data_terbaru(conn)

        data_promo = [
            row for row in data_terbaru
            if row["persentase_diskon"] is not None
            and row["persentase_diskon"] > 0
        ]

        data_promo.sort(
            key=lambda row: row["persentase_diskon"],
            reverse=True
        )

        total_promo = len(data_promo)

        diskon_terbesar = max(
            (
                row["persentase_diskon"]
                for row in data_promo
            ),
            default=0
        )

        rata_diskon = (
            sum(row["persentase_diskon"] for row in data_promo)
            / total_promo
            if total_promo > 0
            else 0
        )

        return render_template(
            "diskon.html",
            data_promo=data_promo,
            total_promo=total_promo,
            diskon_terbesar=diskon_terbesar,
            rata_diskon=rata_diskon
        )

    finally:
        conn.close()


# ==========================================
# ALIAS RIWAYAT SCRAPING
# ==========================================

@app.route("/scraping")
def riwayat_scraping():

    return redirect(
        url_for("riwayat_harga")
    )


# ==========================================
# UNDUH LAPORAN
# ==========================================

@app.route("/laporan/<path:nama_file>")
def unduh_laporan(nama_file):

    if not os.path.isfile(
        os.path.join(LAPORAN_DIR, nama_file)
    ):
        abort(404)

    return send_from_directory(
        LAPORAN_DIR,
        nama_file,
        as_attachment=True
    )


# ==========================================
# MENAMPILKAN GRAFIK ANALISIS
# ==========================================

@app.route("/grafik/<path:nama_file>")
def tampilkan_grafik(nama_file):

    if not os.path.isfile(
        os.path.join(GRAFIK_DIR, nama_file)
    ):
        abort(404)

    return send_from_directory(
        GRAFIK_DIR,
        nama_file
    )


# ==========================================
# HALAMAN TIDAK DITEMUKAN
# ==========================================

@app.errorhandler(404)
def halaman_tidak_ditemukan(error):

    return """
    <h1>404 - Halaman Tidak Ditemukan</h1>
    <p>Halaman atau data yang diminta tidak tersedia.</p>
    <a href="/">Kembali ke Dashboard</a>
    """, 404


# ==========================================
# MENJALANKAN APLIKASI
# ==========================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5001,
        debug=True
    )
