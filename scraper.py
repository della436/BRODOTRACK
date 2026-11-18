
import json
import logging
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import USER_AGENT, REQUEST_TIMEOUT, SITEMAP_URL

from db import (
    create_tables,
    simpan_produk,
    simpan_riwayat_harga,
    simpan_log
)


# ==================================================
# KONFIGURASI SCRAPING
# ==================================================

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml"
}

# Target jumlah data baru yang benar-benar tersimpan
TARGET_RECORD = 100

# Jeda antarpermintaan untuk menghindari permintaan berlebihan
SCRAPING_DELAY = 2

# Mengatur pencatatan aktivitas dan kesalahan scraping
logger = logging.getLogger(__name__)


# ==================================================
# MEMBUAT SESSION REQUESTS
# ==================================================

def buat_session():
    """
    Membuat session HTTP untuk mengambil halaman website BRODO.
    Session digunakan kembali agar koneksi lebih efisien.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    return session


def ambil_halaman(session, url):
    """
    Mengambil isi halaman website berdasarkan URL.

    Mengembalikan HTML jika berhasil.
    Mengembalikan None jika terjadi kesalahan.
    """

    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        # Memastikan respons HTTP berhasil
        response.raise_for_status()

        return response.text

    except requests.RequestException as error:

        logger.error(
            "Gagal mengambil halaman %s: %s",
            url,
            error
        )

        return None


# ==================================================
# NORMALISASI HARGA DAN DISKON
# ==================================================

def konversi_harga(nilai):
    """
    Mengubah nilai harga menjadi angka.

    Harga kosong, tidak valid, atau kurang dari sama dengan
    nol akan ditolak.
    """

    if nilai is None or isinstance(nilai, bool):
        return None

    try:
        # Menghilangkan pemisah ribuan sebelum konversi
        harga = float(
            str(nilai).replace(",", "").strip()
        )

        if harga <= 0:
            return None

        return harga

    except (ValueError, TypeError):
        return None


def hitung_diskon(harga_normal, harga_diskon):
    """
    Menghitung persentase diskon berdasarkan
    harga normal dan harga setelah diskon.
    """

    if harga_normal is None or harga_diskon is None:
        return None

    if harga_normal <= harga_diskon:
        return None

    persentase = (
        (harga_normal - harga_diskon)
        / harga_normal
    ) * 100

    return round(persentase, 2)


def normalisasi_stok(nilai):
    """
    Menyamakan berbagai format informasi stok
    menjadi Tersedia, Habis, atau None.
    """

    if nilai is None:
        return None

    teks = str(nilai).lower().strip()

    # Kondisi ketika produk masih tersedia
    if (
        "instock" in teks
        or teks == "true"
        or teks == "tersedia"
    ):
        return "Tersedia"

    # Kondisi ketika produk sudah habis
    if (
        "outofstock" in teks
        or "soldout" in teks
        or teks == "false"
        or teks == "habis"
    ):
        return "Habis"

    return None


# ==================================================
# MEMBACA REFERENSI PAYLOAD BRODO
# ==================================================

def resolve_payload(nilai, payload, kedalaman=0):
    """
    Mengubah referensi indeks payload Nuxt/devalue
    menjadi nilai aslinya.

    Proses dibatasi maksimal 15 tingkat untuk mencegah
    rekursi yang terlalu dalam.
    """

    if kedalaman > 15:
        return nilai

    # Mengikuti referensi indeks dalam payload
    if isinstance(nilai, int) and not isinstance(nilai, bool):

        if 0 <= nilai < len(payload):
            return resolve_payload(
                payload[nilai],
                payload,
                kedalaman + 1
            )

        return nilai

    # Memproses data berbentuk list
    if isinstance(nilai, list):

        return [
            resolve_payload(
                item,
                payload,
                kedalaman + 1
            )
            for item in nilai
        ]

    # Memproses data berbentuk dictionary
    if isinstance(nilai, dict):

        return {
            key: resolve_payload(
                value,
                payload,
                kedalaman + 1
            )
            for key, value in nilai.items()
        }

    return nilai


def cari_nilai_kunci(data, kunci):
    """
    Mencari nilai berdasarkan nama kunci
    pada struktur dictionary dan list bersarang.
    """

    hasil = []

    if isinstance(data, dict):

        for key, value in data.items():

            if key == kunci:
                hasil.append(value)

            hasil.extend(
                cari_nilai_kunci(value, kunci)
            )

    elif isinstance(data, list):

        for item in data:

            hasil.extend(
                cari_nilai_kunci(item, kunci)
            )

    return hasil


def ambil_ukuran(details):
    """
    Mengambil informasi ukuran sepatu
    dari detail varian produk.
    """

    if isinstance(details, list):

        for detail in details:

            if not isinstance(detail, dict):
                continue

            key = str(
                detail.get("key", "")
            ).lower()

            if key in ("size", "ukuran"):

                value = detail.get("value")

                if value is not None:
                    return str(value).strip()

    return None


def ambil_stok(inventories):
    """
    Menentukan ketersediaan produk berdasarkan
    jumlah inventory yang ditemukan.
    """

    quantities = cari_nilai_kunci(
        inventories,
        "quantity"
    )

    if not quantities:
        return None

    try:
        total = sum(
            float(quantity)
            for quantity in quantities
            if quantity is not None
        )

        return "Tersedia" if total > 0 else "Habis"

    except (ValueError, TypeError):
        return None


# ==================================================
# MEMBACA DATA PRODUK DARI PAYLOAD BRODO
# ==================================================

def baca_data_brodo(html):
    """
    Membaca data harga, ukuran, diskon, dan stok
    dari payload Nuxt/devalue yang tertanam dalam HTML.
    """

    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script"):

        isi = script.string or script.get_text()

        # Memeriksa apakah script mengandung informasi harga BRODO
        if not isi or "compareAtDiscount" not in isi:
            continue

        try:
            payload = json.loads(isi)

        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(payload, list):
            continue

        hasil = []

        for item in payload:

            if not isinstance(item, dict):
                continue

            # Memastikan struktur data memiliki informasi utama
            if not all(
                key in item
                for key in ("price", "discount", "details")
            ):
                continue

            # Mengambil harga normal
            harga_normal = konversi_harga(
                resolve_payload(
                    item["price"],
                    payload
                )
            )

            if harga_normal is None:
                continue

            # Mengambil nominal potongan harga
            nominal_diskon = konversi_harga(
                resolve_payload(
                    item["discount"],
                    payload
                )
            )

            # Menghitung harga setelah diskon
            harga_diskon = None

            if (
                nominal_diskon is not None
                and nominal_diskon < harga_normal
            ):
                harga_diskon = harga_normal - nominal_diskon

            harga_akhir = harga_diskon or harga_normal

            # Mengambil informasi ukuran
            details = resolve_payload(
                item["details"],
                payload
            )

            ukuran = ambil_ukuran(details)

            # Mengambil informasi persediaan
            inventories = resolve_payload(
                item.get("inventories"),
                payload
            )

            stok = ambil_stok(inventories)

            # Memasukkan hasil ekstraksi ke dalam list
            hasil.append({
                "ukuran": ukuran,
                "harga_normal": harga_normal,
                "harga_diskon": harga_diskon,
                "harga": harga_akhir,
                "persentase_diskon": hitung_diskon(
                    harga_normal,
                    harga_diskon
                ),
                "ketersediaan": stok,
                "mata_uang": "IDR"
            })

        if hasil:
            return hasil

    return []


# ==================================================
# MEMBACA DATA JSON-LD
# ==================================================

def cari_product(data):
    """
    Mencari objek Product pada struktur JSON-LD.
    Mendukung data berbentuk list maupun dictionary.
    """

    if isinstance(data, list):

        for item in data:

            hasil = cari_product(item)

            if hasil:
                return hasil

    elif isinstance(data, dict):

        tipe = data.get("@type", [])

        if isinstance(tipe, str):
            tipe = [tipe]

        if "Product" in tipe:
            return data

        # Memeriksa objek @graph jika tersedia
        hasil = cari_product(
            data.get("@graph", [])
        )

        if hasil:
            return hasil

    return None


def baca_jsonld(html):
    """
    Membaca informasi produk dari script JSON-LD
    pada halaman website.
    """

    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        try:
            isi = script.string or script.get_text()

            data = json.loads(isi)

            hasil = cari_product(data)

            if hasil:
                return hasil

        except (json.JSONDecodeError, TypeError):
            continue

    return None


def ambil_gambar(data):
    """
    Mengambil URL gambar utama produk.
    """

    gambar = data.get("image", [])

    if isinstance(gambar, str):
        return gambar

    if isinstance(gambar, list) and gambar:

        gambar_pertama = gambar[0]

        if isinstance(gambar_pertama, str):
            return gambar_pertama

        if isinstance(gambar_pertama, dict):
            return gambar_pertama.get("url")

    if isinstance(gambar, dict):
        return gambar.get("url")

    return None


# ==================================================
# EKSTRAKSI HARGA DARI JSON-LD
# ==================================================

def ekstrak_harga_jsonld(data):
    """
    Mengambil informasi harga dari bagian offers JSON-LD.

    Digunakan sebagai alternatif apabila payload utama
    BRODO tidak berhasil dibaca.
    """

    offers = data.get("offers", [])

    if isinstance(offers, dict):
        offers = [offers]

    hasil = []

    for offer in offers:

        if not isinstance(offer, dict):
            continue

        harga = konversi_harga(
            offer.get("price")
        )

        if harga is None:
            continue

        hasil.append({
            "ukuran": offer.get("name"),
            "harga": harga,
            "harga_normal": harga,
            "harga_diskon": None,
            "persentase_diskon": None,
            "mata_uang": offer.get(
                "priceCurrency",
                "IDR"
            ),
            "ketersediaan": normalisasi_stok(
                offer.get("availability")
            )
        })

    return hasil


# ==================================================
# EKSTRAKSI INFORMASI PRODUK
# ==================================================

def ekstrak_produk(data, url_produk, html):
    """
    Menggabungkan informasi produk dan seluruh variasinya.
    """

    # Mengutamakan payload utama BRODO
    daftar_harga = baca_data_brodo(html)

    # Menggunakan JSON-LD jika payload utama tidak tersedia
    if not daftar_harga:
        daftar_harga = ekstrak_harga_jsonld(data)

    return {
        "nama_produk": data.get("name"),
        "kategori": data.get("category"),
        "deskripsi": data.get("description"),
        "sku": data.get("sku"),
        "url_produk": url_produk,
        "url_gambar": ambil_gambar(data),
        "daftar_harga": daftar_harga
    }


# ==================================================
# FILTER PRODUK SEPATU
# ==================================================

def produk_sepatu(data):
    """
    Memeriksa apakah produk termasuk kategori alas kaki.

    Produk yang bukan sepatu atau alas kaki akan dilewati.
    """

    nama = str(
        data.get("nama_produk") or ""
    ).lower()

    kategori = str(
        data.get("kategori") or ""
    ).lower()

    kata_kunci = [
        "sepatu",
        "sneaker",
        "shoes",
        "footwear",
        "boots",
        "sandal"
    ]

    teks = nama + " " + kategori

    return any(
        kata in teks
        for kata in kata_kunci
    )


# ==================================================
# MENGAMBIL URL DARI SITEMAP
# ==================================================

def ambil_daftar_url_sitemap(session):
    """
    Mengambil daftar URL produk dari sitemap website BRODO.

    URL duplikat dihapus sebelum proses scraping dimulai.
    """

    print("\nMengambil daftar URL dari sitemap...")

    html = ambil_halaman(
        session,
        SITEMAP_URL
    )

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "xml"
    )

    daftar_url = []

    for loc in soup.find_all("loc"):

        url = loc.get_text(strip=True)

        if "/products/" in url:
            daftar_url.append(url)

    # Menghapus URL yang sama dengan tetap mempertahankan urutannya
    daftar_url = list(
        dict.fromkeys(daftar_url)
    )

    print(
        f"Jumlah URL produk ditemukan: {len(daftar_url)}"
    )

    return daftar_url


# ==================================================
# MEMVALIDASI HASIL SCRAPING
# ==================================================

def validasi_varian(item):
    """
    Memeriksa kelengkapan dan validitas satu varian produk.

    Data yang tidak memiliki harga valid atau memiliki
    nilai harga dan diskon yang tidak masuk akal akan dilewati.
    """

    if not isinstance(item, dict):
        return False

    # Harga utama wajib tersedia dan lebih besar dari nol
    harga = konversi_harga(
        item.get("harga")
    )

    if harga is None:
        return False

    # Memeriksa harga normal jika tersedia
    harga_normal = item.get("harga_normal")

    if harga_normal is not None:

        harga_normal = konversi_harga(harga_normal)

        if harga_normal is None:
            return False

    # Memeriksa harga diskon jika tersedia
    harga_diskon = item.get("harga_diskon")

    if harga_diskon is not None:

        harga_diskon = konversi_harga(harga_diskon)

        if harga_diskon is None:
            return False

        if (
            harga_normal is not None
            and harga_diskon >= harga_normal
        ):
            return False

    # Memastikan persentase diskon berada dalam rentang valid
    persentase = item.get("persentase_diskon")

    if persentase is not None:

        try:
            persentase = float(persentase)

        except (ValueError, TypeError):
            return False

        if not 0 <= persentase <= 100:
            return False

    return True


def filter_daftar_harga(daftar_harga):
    """
    Menyaring seluruh varian harga.

    Menghapus:
    - Data kosong.
    - Data tidak berbentuk dictionary.
    - Harga tidak valid.
    - Data varian yang identik dalam satu hasil halaman.

    Varian dengan ukuran berbeda tetap dipertahankan.
    """

    hasil = []
    data_terlihat = set()

    for item in daftar_harga:

        if not validasi_varian(item):
            continue

        ukuran = item.get("ukuran")

        # Menormalkan ukuran agar konsisten saat dibandingkan
        ukuran_normal = (
            str(ukuran).strip().lower()
            if ukuran is not None
            else ""
        )

        # Membuat identitas berdasarkan produk dan kondisi varian
        identitas = (
            ukuran_normal,
            item.get("harga"),
            item.get("harga_normal"),
            item.get("harga_diskon"),
            item.get("persentase_diskon"),
            item.get("mata_uang"),
            item.get("ketersediaan")
        )

        # Melewati varian identik dalam satu hasil scraping
        if identitas in data_terlihat:
            continue

        data_terlihat.add(identitas)
        hasil.append(item)

    return hasil


# ==================================================
# MENYIMPAN HASIL SCRAPING
# ==================================================

def simpan_hasil_scraping(data, batas_record=None):
    """
    Menyimpan informasi produk dan varian ke database.

    Hanya data yang benar-benar baru atau mengalami perubahan
    yang dihitung sebagai record berhasil.

    Data identik dilewati berdasarkan hasil pemeriksaan
    fungsi simpan_riwayat_harga() dari db.py.
    """

    waktu_mulai = datetime.now().isoformat(
        timespec="seconds"
    )

    try:

        # Mengambil seluruh varian harga dari hasil ekstraksi
        daftar_harga = data.get(
            "daftar_harga",
            []
        )

        # Melakukan filter validitas dan duplikasi dalam satu halaman
        daftar_harga = filter_daftar_harga(
            daftar_harga
        )

        if not daftar_harga:
            return 0

        # Menyimpan produk dan mendapatkan ID produk
        id_produk = simpan_produk(
            nama_produk=data.get("nama_produk"),
            url_produk=data.get("url_produk"),
            kategori=data.get("kategori"),
            deskripsi=data.get("deskripsi"),
            sku=data.get("sku"),
            url_gambar=data.get("url_gambar")
        )

        # Jika produk gagal disimpan, proses dihentikan
        if id_produk is None:
            return 0

        jumlah_tersimpan = 0
        jumlah_diskon = 0
        jumlah_duplikat = 0
        jumlah_invalid = 0

        # Memproses varian satu per satu
        for item in daftar_harga:

            # Menghentikan penyimpanan jika target data baru tercapai
            if (
                batas_record is not None
                and jumlah_tersimpan >= batas_record
            ):
                break

            # Memeriksa kembali validitas data varian
            if not validasi_varian(item):
                jumlah_invalid += 1
                continue

            # Memasukkan riwayat melalui fungsi deduplikasi database
            berhasil = simpan_riwayat_harga(
                id_produk=id_produk,
                harga=item["harga"],
                ukuran=item.get("ukuran"),
                mata_uang=item.get("mata_uang", "IDR"),
                ketersediaan=item.get("ketersediaan"),
                harga_normal=item.get("harga_normal"),
                harga_diskon=item.get("harga_diskon"),
                persentase_diskon=item.get(
                    "persentase_diskon"
                )
            )

            # Hanya data yang benar-benar tersimpan yang dihitung
            if berhasil:

                jumlah_tersimpan += 1

                if item.get("persentase_diskon") is not None:
                    jumlah_diskon += 1

            else:
                # False berarti data identik dilewati
                jumlah_duplikat += 1

        # Mencatat aktivitas penyimpanan produk
        if jumlah_tersimpan > 0:

            simpan_log(
                jumlah_produk=1,
                status="Berhasil",
                waktu_mulai=waktu_mulai,
                keterangan=(
                    f"Produk {data.get('nama_produk')} diproses. "
                    f"Data baru: {jumlah_tersimpan}. "
                    f"Data duplikat: {jumlah_duplikat}. "
                    f"Data invalid: {jumlah_invalid}. "
                    f"Varian diskon: {jumlah_diskon}."
                )
            )

            print(
                f"Berhasil menyimpan: "
                f"{data.get('nama_produk')}"
            )

            print(
                f"Data baru       : {jumlah_tersimpan}"
            )

            print(
                f"Data duplikat   : {jumlah_duplikat}"
            )

            print(
                f"Data invalid    : {jumlah_invalid}"
            )

            print(
                f"Varian diskon   : {jumlah_diskon}"
            )

        else:

            # Produk yang seluruh variannya identik tidak dihitung
            # sebagai produk baru pada sesi scraping ini
            if jumlah_duplikat > 0:

                print(
                    f"Data produk dilewati: "
                    f"{data.get('nama_produk')} "
                    f"(seluruh data identik)"
                )

        return jumlah_tersimpan

    except Exception as error:

        # Mencatat kesalahan jika penyimpanan gagal
        simpan_log(
            jumlah_produk=0,
            status="Gagal",
            waktu_mulai=waktu_mulai,
            keterangan=str(error)
        )

        logger.exception(
            "Gagal menyimpan hasil scraping."
        )

        print(
            "Gagal menyimpan hasil scraping:",
            error
        )

        return 0


# ==================================================
# SCRAPING SATU PRODUK
# ==================================================

def scrape_satu_produk(session, url):
    """
    Melakukan scraping pada satu halaman produk.

    Tahapan:
    1. Mengambil HTML.
    2. Membaca JSON-LD.
    3. Mengekstrak informasi produk.
    4. Memeriksa kategori produk.
    5. Memvalidasi varian harga.
    """

    # Mengambil halaman produk
    html = ambil_halaman(
        session,
        url
    )

    if not html:
        return None

    # Membaca struktur data produk dari JSON-LD
    data = baca_jsonld(html)

    if not data:

        logger.warning(
            "JSON-LD Product tidak ditemukan: %s",
            url
        )

        return None

    # Mengekstrak seluruh informasi produk
    hasil = ekstrak_produk(
        data,
        url,
        html
    )

    # Memeriksa nama produk
    if not hasil["nama_produk"]:
        return None

    # Memastikan produk termasuk kategori alas kaki
    if not produk_sepatu(hasil):

        logger.info(
            "Produk bukan kategori alas kaki: %s",
            url
        )

        return None

    # Memfilter seluruh varian harga
    hasil["daftar_harga"] = filter_daftar_harga(
        hasil["daftar_harga"]
    )

    # Produk tanpa varian valid tidak diproses
    if not hasil["daftar_harga"]:

        logger.warning(
            "Tidak ada varian valid: %s",
            url
        )

        return None

    return hasil


# ==================================================
# SCRAPING BANYAK PRODUK
# ==================================================

def scrape_banyak_produk(target_record=TARGET_RECORD):
    """
    Menjalankan scraping terhadap beberapa produk BRODO.

    Proses berhenti ketika jumlah data baru yang benar-benar
    tersimpan mencapai target.

    Produk yang hanya menghasilkan data duplikat tidak
    dihitung sebagai pencapaian target.
    """

    # Memastikan tabel database sudah tersedia
    create_tables()

    waktu_mulai = datetime.now()

    jumlah_record = 0
    jumlah_produk = 0
    jumlah_gagal = 0
    jumlah_dilewati = 0

    # Membuat session HTTP
    session = buat_session()

    try:

        # Mengambil seluruh URL produk dari sitemap
        daftar_url = ambil_daftar_url_sitemap(
            session
        )

        if not daftar_url:

            print(
                "Tidak ada URL produk yang ditemukan."
            )

            return 0

        print("\n" + "=" * 55)
        print("MEMULAI SCRAPING BRODOTRACK")
        print("=" * 55)

        print(
            f"Target data baru: {target_record}"
        )

        print(
            f"Total URL produk: {len(daftar_url)}"
        )

        # Memproses URL produk satu per satu
        for nomor, url in enumerate(
            daftar_url,
            start=1
        ):

            # Berhenti jika target penyimpanan tercapai
            if jumlah_record >= target_record:
                break

            print(
                f"\n[{nomor}/{len(daftar_url)}] "
                f"Mengambil produk..."
            )

            # Mengambil dan memfilter informasi produk
            hasil = scrape_satu_produk(
                session,
                url
            )

            if not hasil:

                jumlah_gagal += 1

                time.sleep(SCRAPING_DELAY)
                continue

            # Menghitung sisa target yang belum terpenuhi
            sisa_target = (
                target_record - jumlah_record
            )

            # Menyimpan hanya data baru atau data yang berubah
            jumlah_tersimpan = simpan_hasil_scraping(
                hasil,
                batas_record=sisa_target
            )

            if jumlah_tersimpan > 0:

                jumlah_record += jumlah_tersimpan
                jumlah_produk += 1

            else:

                # Halaman valid tetapi tidak menghasilkan data baru
                jumlah_dilewati += 1

            # Menampilkan perkembangan proses
            print(
                f"Progres data baru: "
                f"{jumlah_record}/{target_record}"
            )

            # Memberikan jeda sebelum mengambil halaman berikutnya
            time.sleep(SCRAPING_DELAY)

        waktu_selesai = datetime.now()

        # Menampilkan ringkasan akhir scraping
        print("\n" + "=" * 55)
        print("HASIL SCRAPING BRODOTRACK")
        print("=" * 55)

        print(
            f"Target data baru   : {target_record}"
        )

        print(
            f"Data berhasil      : {jumlah_record}"
        )

        print(
            f"Produk diproses    : {jumlah_produk}"
        )

        print(
            f"Produk dilewati    : {jumlah_dilewati}"
        )

        print(
            f"Halaman gagal      : {jumlah_gagal}"
        )

        print(
            f"Waktu proses       : "
            f"{waktu_selesai - waktu_mulai}"
        )

        if jumlah_record >= target_record:

            print(
                "Status             : TARGET TERCAPAI"
            )

        else:

            print(
                "Status             : TARGET BELUM TERCAPAI"
            )

        print("=" * 55)

        return jumlah_record

    finally:

        # Menutup session setelah scraping selesai
        session.close()


# ==================================================
# PROGRAM UTAMA
# ==================================================

if __name__ == "__main__":

    # Menjalankan scraping dengan target 100 data baru
    total = scrape_banyak_produk(
        target_record=TARGET_RECORD
    )

    print(
        f"\nScraping selesai. "
        f"Total data baru tersimpan: {total}"
    )
