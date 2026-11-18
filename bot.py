
"""
BOT TELEGRAM BRODOTRACK
Sistem Pemantauan Harga Produk BRODO

Fitur:
- Sambutan dan menu utama
- Ringkasan pemantauan
- Daftar produk
- Detail produk melalui tombol pilihan
- Perubahan harga
- Bantuan
- ID Telegram
- Notifikasi hasil scraping
"""

# ============================================================
# 1. IMPORT LIBRARY
# ============================================================

import os
import sqlite3
import logging
from pathlib import Path
from html import escape

from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.constants import ParseMode

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config import DATABASE_PATH

from pesan import (
    buat_pesan_ringkasan,
    buat_pesan_perubahan_harga
)


# ============================================================
# 2. KONFIGURASI
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ============================================================
# 3. LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("BRODOTRACK_BOT")


# ============================================================
# 4. MENU UTAMA
# ============================================================

MENU_UTAMA = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton("📊 Ringkasan"),
            KeyboardButton("👟 Daftar Produk")
        ],
        [
            KeyboardButton("🔎 Detail Produk"),
            KeyboardButton("📈 Perubahan Harga")
        ],
        [
            KeyboardButton("❓ Bantuan")
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder="Pilih menu BRODOTRACK..."
)


# ============================================================
# 5. KONEKSI DATABASE
# ============================================================

def get_connection():
    """Membuat koneksi ke database BRODOTRACK."""

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# ============================================================
# 6. FUNGSI BANTU
# ============================================================

def format_rupiah(nilai):
    """Mengubah angka menjadi format Rupiah."""

    if nilai is None:
        return "Tidak tersedia"

    try:
        nilai = float(nilai)
        return f"Rp{nilai:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "Tidak tersedia"


def format_diskon(nilai):
    """Mengubah angka menjadi format diskon."""

    if nilai is None:
        return "-"

    try:
        nilai = float(nilai)

        if nilai <= 0:
            return "-"

        return f"{nilai:.2f}%"

    except (ValueError, TypeError):
        return "-"


def status_stok(ketersediaan):
    """Mengubah status stok menjadi teks."""

    if ketersediaan is None:
        return "Tidak diketahui"

    nilai = str(ketersediaan).strip().lower()

    if (
        nilai in ("tersedia", "instock", "true", "1")
        or nilai.endswith("/instock")
    ):
        return "Tersedia"

    if (
        nilai in ("habis", "outofstock", "false", "0")
        or nilai.endswith("/outofstock")
    ):
        return "Habis"

    return "Tidak diketahui"


def format_waktu(waktu):
    """Mengatur tampilan waktu scraping."""

    if not waktu:
        return "Tidak tersedia"

    return str(waktu)


async def kirim_pesan(context, chat_id, pesan, reply_markup=None):
    """
    Mengirim pesan panjang dalam beberapa bagian.

    Batas dibuat 3.900 karakter agar tidak melewati
    batas maksimal pesan Telegram.
    """

    batas = 3900
    bagian = []
    teks_sementara = ""

    for baris in str(pesan).splitlines():

        while len(baris) > batas:

            if teks_sementara:
                bagian.append(teks_sementara)
                teks_sementara = ""

            bagian.append(baris[:batas])
            baris = baris[batas:]

        calon_teks = (
            teks_sementara + "\n" + baris
            if teks_sementara
            else baris
        )

        if len(calon_teks) > batas:

            if teks_sementara:
                bagian.append(teks_sementara)

            teks_sementara = baris

        else:
            teks_sementara = calon_teks

    if teks_sementara:
        bagian.append(teks_sementara)

    if not bagian:
        bagian = ["Tidak ada informasi untuk ditampilkan."]

    for indeks, teks in enumerate(bagian):

        await context.bot.send_message(
            chat_id=chat_id,
            text=teks,
            reply_markup=(
                reply_markup
                if indeks == len(bagian) - 1
                else None
            )
        )


# ============================================================
# 7. MENGAMBIL DATA TERBARU
# ============================================================

def ambil_data_terbaru():
    """
    Mengambil catatan terbaru untuk setiap
    kombinasi produk dan ukuran.
    """

    query = """
        SELECT
            p.id_produk,
            p.nama_produk,
            p.kategori,
            p.url_produk,
            r.ukuran,
            r.harga,
            r.harga_normal,
            r.harga_diskon,
            r.persentase_diskon,
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


# ============================================================
# 8. DAFTAR PRODUK DAN PILIHAN DETAIL
# ============================================================

def buat_tombol_produk(data):
    """Membuat tombol pilihan produk untuk menu Detail Produk."""

    tombol = []

    for row in data:

        nama = row["nama_produk"] or "Produk tanpa nama"

        if len(nama) > 45:
            nama = nama[:42] + "..."

        tombol.append([
            InlineKeyboardButton(
                text=f"👟 {nama}",
                callback_data=f"detail:{row['id_produk']}"
            )
        ])

    tombol.append([
        InlineKeyboardButton(
            text="🏠 Menu Utama",
            callback_data="menu_utama"
        )
    ])

    return InlineKeyboardMarkup(tombol)


async def tampilkan_daftar_produk(
    update,
    context,
    dari_callback=False
):
    """Menampilkan pilihan produk untuk melihat detail."""

    query = """
        SELECT
            id_produk,
            nama_produk,
            kategori
        FROM produk
        ORDER BY nama_produk
    """

    with get_connection() as connection:
        data = connection.execute(query).fetchall()

    if not data:

        pesan = "Belum ada produk yang tersimpan di database."

        if dari_callback:

            await update.callback_query.edit_message_text(
                pesan
            )

        else:

            await update.message.reply_text(
                pesan,
                reply_markup=MENU_UTAMA
            )

        return

    pesan = (
        "👟 <b>PILIH PRODUK BRODO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Silakan pilih produk yang ingin dilihat.\n\n"
        "Tekan nama produk untuk menampilkan "
        "informasi harga, diskon, ukuran, dan stok."
    )

    keyboard = buat_tombol_produk(data)

    if dari_callback:

        await update.callback_query.edit_message_text(
            text=pesan,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    else:

        await update.message.reply_text(
            text=pesan,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )


async def tampilkan_daftar_produk_saja(update, context):
    """Menampilkan nama produk saja tanpa tombol detail."""

    query = """
        SELECT id_produk, nama_produk, kategori
        FROM produk
        ORDER BY nama_produk
    """

    with get_connection() as connection:
        data = connection.execute(query).fetchall()

    if not data:

        await update.message.reply_text(
            "Belum ada produk yang tersimpan di database.",
            reply_markup=MENU_UTAMA
        )
        return

    pesan = [
        "👟 DAFTAR PRODUK BRODO",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Total produk: {len(data)}",
        ""
    ]

    for nomor, row in enumerate(data, start=1):

        nama = row["nama_produk"] or "Produk tanpa nama"
        pesan.append(f"{nomor}. {nama}")

    await kirim_pesan(
        context,
        update.effective_chat.id,
        "\n".join(pesan),
        reply_markup=MENU_UTAMA
    )


# ============================================================
# 9. MEMBUAT DETAIL PRODUK
# ============================================================

def buat_pesan_detail_produk(id_produk):
    """Mengambil dan menyusun detail produk."""

    query = """
        SELECT
            p.id_produk,
            p.nama_produk,
            p.kategori,
            p.url_produk,
            r.ukuran,
            r.harga,
            r.harga_normal,
            r.harga_diskon,
            r.persentase_diskon,
            r.ketersediaan,
            r.waktu_scraping

        FROM riwayat_harga r

        JOIN produk p
            ON p.id_produk = r.id_produk

        WHERE p.id_produk = ?

        AND r.id_riwayat = (
            SELECT MAX(r2.id_riwayat)
            FROM riwayat_harga r2
            WHERE r2.id_produk = r.id_produk
            AND r2.ukuran IS r.ukuran
        )

        ORDER BY r.ukuran
    """

    with get_connection() as connection:

        data = connection.execute(
            query,
            (id_produk,)
        ).fetchall()

    if not data:
        return None

    produk_data = data[0]

    nama = escape(
        str(produk_data["nama_produk"] or "-")
    )

    kategori = escape(
        str(produk_data["kategori"] or "-")
    )

    url = produk_data["url_produk"]

    pesan = [
        "👟 <b>DETAIL PRODUK BRODO</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"<b>{nama}</b>",
        f"ID Produk: {produk_data['id_produk']}",
        f"Kategori: {kategori}",
        ""
    ]

    if url:

        url_aman = escape(str(url), quote=True)

        if str(url).startswith(("http://", "https://")):

            pesan.append(
                f'<a href="{url_aman}">'
                "Lihat Produk di Website BRODO</a>"
            )

        else:

            pesan.append(
                f"Link: {escape(str(url))}"
            )

    pesan.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💰 <b>INFORMASI HARGA DAN STOK</b>"
    ])

    for row in data:

        ukuran = escape(str(row["ukuran"] or "-"))

        harga = format_rupiah(row["harga"])
        harga_normal = format_rupiah(row["harga_normal"])
        harga_diskon = format_rupiah(row["harga_diskon"])
        diskon = format_diskon(row["persentase_diskon"])
        stok = status_stok(row["ketersediaan"])
        waktu = format_waktu(row["waktu_scraping"])

        pesan.extend([
            "",
            f"📏 <b>Ukuran: {ukuran}</b>",
            f"Harga tercatat: {harga}",
            f"Harga normal: {harga_normal}",
            f"Harga diskon: {harga_diskon}",
            f"Diskon: {diskon}",
            f"Stok: {stok}",
            f"🕒 Diperbarui: {escape(waktu)}",
            "--------------------"
        ])

    pesan.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "<i>Data berdasarkan hasil scraping terakhir.</i>"
    ])

    return "\n".join(pesan)


async def tampilkan_detail_produk(
    update,
    context,
    id_produk,
    dari_callback=False
):
    """Menampilkan detail produk yang dipilih."""

    pesan = buat_pesan_detail_produk(id_produk)

    if pesan is None:

        pesan = (
            "Produk tidak ditemukan atau belum memiliki "
            "riwayat harga."
        )

        if dari_callback:

            await update.callback_query.edit_message_text(
                pesan,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "⬅️ Kembali ke Daftar Produk",
                            callback_data="daftar_produk"
                        )
                    ]
                ])
            )

        else:

            await update.message.reply_text(
                pesan,
                reply_markup=MENU_UTAMA
            )

        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ Kembali ke Daftar Produk",
                callback_data="daftar_produk"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 Menu Utama",
                callback_data="menu_utama"
            )
        ]
    ])

    if dari_callback:

        await update.callback_query.edit_message_text(
            text=pesan,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    else:

        await update.message.reply_text(
            text=pesan,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )


# ============================================================
# 10. COMMAND START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan sambutan dan menu utama."""

    context.user_data["menunggu_id_produk"] = False

    pesan = (
        "👟 <b>SELAMAT DATANG DI BRODOTRACK!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>PRODUCT MONITORING SYSTEM</b>\n"
        "Sistem Pemantauan Harga Produk BRODO.\n\n"
        "Pantau informasi katalog, harga, "
        "dan ketersediaan stok produk BRODO "
        "secara berkala.\n\n"
        "📦 Informasi Produk\n"
        "💰 Pemantauan Harga\n"
        "📊 Riwayat Perubahan Harga\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Silakan pilih fitur melalui menu di bawah."
    )

    await update.message.reply_text(
        pesan,
        parse_mode=ParseMode.HTML,
        reply_markup=MENU_UTAMA
    )


# ============================================================
# 11. COMMAND MENU
# ============================================================

async def menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan kembali menu utama."""

    context.user_data["menunggu_id_produk"] = False

    await update.message.reply_text(
        "🏠 <b>MENU UTAMA BRODOTRACK</b>\n\n"
        "Silakan pilih fitur yang ingin digunakan.",
        parse_mode=ParseMode.HTML,
        reply_markup=MENU_UTAMA
    )


# ============================================================
# 12. COMMAND BANTUAN
# ============================================================

async def bantuan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan panduan penggunaan bot."""

    context.user_data["menunggu_id_produk"] = False

    pesan = (
        "📖 <b>PANDUAN BRODOTRACK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 <b>Ringkasan</b>\n"
        "Melihat statistik pemantauan produk.\n\n"
        "👟 <b>Daftar Produk</b>\n"
        "Menampilkan daftar nama produk.\n\n"
        "🔎 <b>Detail Produk</b>\n"
        "Memilih produk dan melihat detail harga, "
        "diskon, ukuran, serta stok.\n\n"
        "📈 <b>Perubahan Harga</b>\n"
        "Melihat perubahan harga produk.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>PERINTAH LANGSUNG</b>\n"
        "/start - Memulai bot\n"
        "/menu - Menu utama\n"
        "/ringkasan - Ringkasan\n"
        "/produk - Daftar produk\n"
        "/detail - Pilih detail produk\n"
        "/detail ID - Detail produk berdasarkan ID\n"
        "/perubahan - Perubahan harga\n"
        "/id - ID Telegram\n"
        "/bantuan - Panduan"
    )

    await update.message.reply_text(
        pesan,
        parse_mode=ParseMode.HTML,
        reply_markup=MENU_UTAMA
    )


# ============================================================
# 13. COMMAND ID TELEGRAM
# ============================================================

async def id_telegram(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan ID Telegram pengguna."""

    user_id = update.effective_user.id

    await update.message.reply_text(
        f"🆔 ID Telegram kamu: <code>{user_id}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=MENU_UTAMA
    )


# ============================================================
# 14. COMMAND RINGKASAN
# ============================================================

async def ringkasan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan ringkasan pemantauan."""

    context.user_data["menunggu_id_produk"] = False

    pesan = buat_pesan_ringkasan()

    await kirim_pesan(
        context,
        update.effective_chat.id,
        pesan
    )


# ============================================================
# 15. COMMAND DAFTAR PRODUK
# ============================================================

async def produk(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan daftar nama produk tanpa tombol detail."""

    context.user_data["menunggu_id_produk"] = False

    await tampilkan_daftar_produk_saja(update, context)


# ============================================================
# 16. COMMAND DETAIL PRODUK
# ============================================================

async def detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan pilihan produk atau detail berdasarkan ID."""

    context.user_data["menunggu_id_produk"] = False

    if not context.args:

        await tampilkan_daftar_produk(update, context)
        return

    try:

        id_produk = int(context.args[0])

        if id_produk <= 0:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "ID produk harus berupa angka positif."
        )
        return

    await tampilkan_detail_produk(
        update,
        context,
        id_produk
    )


# ============================================================
# 17. COMMAND PERUBAHAN HARGA
# ============================================================

async def perubahan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menampilkan perubahan harga produk."""

    context.user_data["menunggu_id_produk"] = False

    pesan = buat_pesan_perubahan_harga()

    await kirim_pesan(
        context,
        update.effective_chat.id,
        pesan
    )


# ============================================================
# 18. CALLBACK TOMBOL PRODUK
# ============================================================

async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menangani tombol inline daftar dan detail produk."""

    query = update.callback_query

    await query.answer()

    data = query.data

    if data == "daftar_produk":

        await tampilkan_daftar_produk(
            update,
            context,
            dari_callback=True
        )

        return

    if data == "menu_utama":

        context.user_data["menunggu_id_produk"] = False

        await query.edit_message_text(
            "🏠 <b>MENU UTAMA BRODOTRACK</b>\n\n"
            "Gunakan tombol menu utama di bagian bawah chat.",
            parse_mode=ParseMode.HTML
        )

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Silakan pilih menu yang tersedia.",
            reply_markup=MENU_UTAMA
        )

        return

    if data.startswith("detail:"):

        try:

            id_produk = int(data.split(":", 1)[1])

            if id_produk <= 0:
                raise ValueError

        except ValueError:

            await query.edit_message_text(
                "ID produk tidak valid."
            )
            return

        await tampilkan_detail_produk(
            update,
            context,
            id_produk,
            dari_callback=True
        )

        return

    await query.edit_message_text(
        "Pilihan tidak dikenali. Silakan gunakan menu kembali."
    )


# ============================================================
# 19. MENU INTERAKTIF
# ============================================================

async def handle_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """Menangani pilihan tombol menu Telegram."""

    teks = update.message.text.strip()

    context.user_data["menunggu_id_produk"] = False

    if teks == "📊 Ringkasan":

        await ringkasan(update, context)

    elif teks == "👟 Daftar Produk":

        await produk(update, context)

    elif teks == "🔎 Detail Produk":

        await tampilkan_daftar_produk(update, context)

    elif teks == "📈 Perubahan Harga":

        await perubahan(update, context)

    elif teks == "❓ Bantuan":

        await bantuan(update, context)

    else:

        await update.message.reply_text(
            "Pilihan menu tidak dikenali.\n"
            "Silakan gunakan tombol menu BRODOTRACK.",
            reply_markup=MENU_UTAMA
        )


# ============================================================
# 20. NOTIFIKASI HASIL SCRAPING
# ============================================================

async def kirim_notifikasi_scraping(
    application,
    chat_id,
    jumlah_record,
    target=25
):
    """Mengirim notifikasi hasil scraping."""

    status = (
        "TARGET TERCAPAI"
        if jumlah_record >= target
        else "TARGET BELUM TERCAPAI"
    )

    pesan = (
        "🔄 HASIL SCRAPING BRODOTRACK\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Target record: {target}\n"
        f"Berhasil: {jumlah_record}\n"
        f"Status: {status}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    await application.bot.send_message(
        chat_id=chat_id,
        text=pesan
    )


# ============================================================
# 21. ERROR HANDLER
# ============================================================

async def error_handler(update, context):
    """Mencatat kesalahan bot."""

    logger.error(
        "Terjadi kesalahan saat memproses update:",
        exc_info=context.error
    )


# ============================================================
# 22. PROGRAM UTAMA
# ============================================================

def main():
    """Menjalankan Telegram Bot BRODOTRACK."""

    if not TOKEN:

        raise ValueError(
            "Token Telegram belum diatur. "
            "Atur TELEGRAM_BOT_TOKEN melalui file .env."
        )

    if not os.path.exists(DATABASE_PATH):

        raise FileNotFoundError(
            f"Database tidak ditemukan: {DATABASE_PATH}"
        )

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    # Registrasi command
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("bantuan", bantuan))
    application.add_handler(CommandHandler("id", id_telegram))
    application.add_handler(CommandHandler("ringkasan", ringkasan))
    application.add_handler(CommandHandler("produk", produk))
    application.add_handler(CommandHandler("detail", detail))
    application.add_handler(CommandHandler("perubahan", perubahan))

    # Registrasi tombol inline
    application.add_handler(
        CallbackQueryHandler(handle_callback)
    )

    # Registrasi tombol menu utama
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_menu
        )
    )

    application.add_error_handler(error_handler)

    print("======================================")
    print("       BRODOTRACK TELEGRAM BOT")
    print("======================================")
    print("Database :", DATABASE_PATH)
    print("Status   : Bot siap dijalankan")
    print("Fitur    : Daftar Produk dan Detail Produk")
    print("Tekan CTRL + C untuk menghentikan bot.")
    print("======================================")

    application.run_polling()


# ============================================================
# 23. EKSEKUSI PROGRAM
# ============================================================

if __name__ == "__main__":
    main()
