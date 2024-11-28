import os
import pandas as pd
import pdfplumber
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from pathlib import Path
import logging
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress detailed logging for telegram and httpx libraries
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Load API Token from .env file
load_dotenv()
API_TOKEN = os.getenv('BOT_API_TOKEN')

# Check if API_TOKEN is loaded correctly
if not API_TOKEN:
    raise ValueError("API Token tidak ditemukan! Pastikan file .env ada dan BOT_API_TOKEN sudah diatur.")

# Load allowed usernames from .env file
allowed_usernames = os.getenv('ALLOWED_USERNAMES')

# Convert the string to a set
if allowed_usernames:
    allowed_usernames = set(allowed_usernames.split(','))  # Splitting by comma
else:
    allowed_usernames = set()

# Create cache folder if not exists
cache_dir = Path('cache')
cache_dir.mkdir(exist_ok=True)

def get_custom_keyboard():
    keyboard = [
        [KeyboardButton("/start"), KeyboardButton("/sisa")],
        [KeyboardButton("/jumlah"), KeyboardButton("/pecah")],
        [KeyboardButton("/excel"), KeyboardButton("/text")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Function to manage cache if there are more than 50 files
def manage_cache():
    try:
        files = list(cache_dir.glob('*'))
        if len(files) > 50:
            files.sort(key=lambda f: f.stat().st_mtime)
            for file in files[:len(files) - 50]:
                file.unlink()
    except Exception as e:
        logger.error(f"Error managing cache: {e}")

async def convert_to_xlsx(file_path: Path, file_name: str) -> Path:
    try:
        df = None
        if file_name.endswith('.xlsb'):
            df = pd.read_excel(file_path, engine='pyxlsb')
        elif file_name.endswith('.xls'):
            df = pd.read_excel(file_path, engine='xlrd')
        elif file_name.endswith(('.xlsx', '.xlsm')):
            df = pd.read_excel(file_path, engine='openpyxl')
        elif file_name.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_name.endswith('.txt'):
            df = pd.read_csv(file_path, delimiter='\t')
        elif file_name.endswith('.xml'):
            df = pd.read_xml(file_path)
        elif file_name.endswith('.ods'):
            df = pd.read_excel(file_path, engine='odf')
        elif file_name.endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                first_page = pdf.pages[0]
                table = first_page.extract_table()
            df = pd.DataFrame(table[1:], columns=table[0])
        else:
            raise ValueError("Format file tidak didukung untuk konversi ke .xlsx")

        new_file_name = file_path.stem + '.xlsx'
        new_file_path = file_path.parent / new_file_name
        df.to_excel(new_file_path, index=False)
        return new_file_path
    except ValueError as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise ValueError(f"File {file_name} tidak dapat dibaca karena format tidak didukung atau file rusak.")
    except Exception as e:
        logger.error(f"Error converting to XLSX: {e}")
        raise ValueError(f"Terjadi kesalahan saat mengonversi file: {e}")

async def convert_to_txt(file_path: Path, file_name: str) -> Path:
    try:
        df = None
        if file_name.endswith('.xlsb'):
            df = pd.read_excel(file_path, engine='pyxlsb')
        elif file_name.endswith('.xls'):
            df = pd.read_excel(file_path, engine='xlrd')
        elif file_name.endswith(('.xlsx', '.xlsm', '.ods')):
            df = pd.read_excel(file_path, engine='openpyxl')
        elif file_name.endswith('.csv') or file_name.endswith('.xml'):
            df = pd.read_csv(file_path)
        elif file_name.endswith('.pdf'):
            with pdfplumber.open(file_path) as pdf:
                first_page = pdf.pages[0]
                table = first_page.extract_table()
            df = pd.DataFrame(table[1:], columns=table[0])
        else:
            raise ValueError("Format file tidak didukung untuk konversi ke .txt")

        new_file_name = file_path.stem + '.txt'
        new_file_path = file_path.parent / new_file_name
        df.to_csv(new_file_path, sep='\t', index=False)
        return new_file_path
    except Exception as e:
        logger.error(f"Error converting to TXT: {e}")
        raise ValueError(f"Terjadi kesalahan saat mengonversi file: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return
        
        # Reset the command state on start
        context.user_data.clear()
        
        message = (
            f"Selamat datang {username} di Bot Pecah File,!\n\n"
            "Berikut adalah fitur-fitur yang tersedia:\n"
            "/jumlah - Untuk mengecek jumlah kontak\n"
            "/pecah - Untuk memecah file menjadi beberapa bagian\n"
            "/excel - Untuk mengubah format file menjadi .xlsx\n"
            "/text - Untuk mengubah format file menjadi .txt\n"
            "/sisa - Untuk mengubah file CSV menjadi .txt\n\n"
            "Dibuat oleh @KazuhaID0"
        )
        
        await update.message.reply_text(message, reply_markup=get_custom_keyboard())
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

async def pecah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return

        # Bersihkan data terkait perintah lain yang mungkin ada di user_data
        context.user_data.clear()

        await update.message.reply_text("Silakan kirim file txt atau xlsx yang ingin Anda pecah.")
        context.user_data['waiting_for'] = 'split'
    except Exception as e:
        logger.error(f"Error in pecah command: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

async def jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return

        # Bersihkan data terkait perintah lain yang mungkin ada di user_data
        context.user_data.clear()

        await update.message.reply_text("Silakan kirim file txt atau xlsx yang ingin Anda cek jumlahnya. Ketik /done setelah semua file dikirim.")
        context.user_data['waiting_for'] = 'count'
        context.user_data['total_contacts'] = 0  # Untuk menyimpan jumlah total kontak dari semua file
        context.user_data['file_paths'] = []  # Untuk menyimpan file yang sudah diterima
    except Exception as e:
        logger.error(f"Error in jumlah command: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

async def excel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return

        context.user_data.clear()  # Bersihkan data sebelumnya

        await update.message.reply_text("Silakan kirim file yang ingin Anda ubah formatnya ke .xlsx.")
        context.user_data['waiting_for'] = 'convert'
    except Exception as e:
        logger.error(f"Error in excel command: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return

        context.user_data.clear()  # Bersihkan data sebelumnya

        await update.message.reply_text("Silakan kirim file yang ingin Anda ubah formatnya ke .txt.")
        context.user_data['waiting_for'] = 'convert_to_txt'
    except Exception as e:
        logger.error(f"Error in text command: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

async def sisa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return
        
        # Reset previous commands
        context.user_data.clear()

        await update.message.reply_text("Silakan kirim file CSV yang berisi NAMA,NOMOR.")
        context.user_data['waiting_for'] = 'sisa'
    except Exception as e:
        logger.error(f"Error in sisa command: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        waiting_for = context.user_data.get('waiting_for')

        if not waiting_for:
            await update.message.reply_text("Silakan masukkan perintah terlebih dahulu sebelum mengirimkan file.")
            return

        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return

        file = await update.message.document.get_file()
        file_name = update.message.document.file_name
        file_path = cache_dir / file_name
        await file.download_to_drive(file_path)

        if waiting_for in ['convert_to_txt', 'convert', 'sisa']:
            context.user_data['file_paths'] = context.user_data.get('file_paths', []) + [file_path]

            if not context.user_data.get('file_received'):
                # Pesan hanya dikirim saat file pertama diterima
                await update.message.reply_text("File diterima. Kirim file lain atau ketik /done setelah semua file dikirim.")
                context.user_data['file_received'] = True

        elif waiting_for == 'split':
            context.user_data['file_name'] = file_name
            context.user_data['file_path'] = file_path
            await update.message.reply_text("Berapa kontak yang ingin Anda pecah per file?")
            context.user_data['waiting_for'] = 'split_confirm'

        elif waiting_for == 'count':
            contacts_count = 0
            if file_name.endswith('.txt'):
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                contacts_count = len(lines)
            elif file_name.endswith('.xlsx') or file_name.endswith('.xls'):
                df = pd.read_excel(file_path)
                contacts_count = len(df)

            context.user_data['total_contacts'] = context.user_data.get('total_contacts', 0) + contacts_count
            file_details = context.user_data.get('file_details', [])
            file_details.append(f"Jumlah kontak {file_name}: {contacts_count}")
            context.user_data['file_details'] = file_details

            if len(file_details) == 1:
                # Pesan hanya dikirim saat file pertama diterima
                await update.message.reply_text(f"File telah diterima. Silakan kirim file lain atau ketik /done jika selesai.")

    except Exception as e:
        logger.error(f"Error handling file: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")



async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    waiting_for = context.user_data.get('waiting_for')

    if waiting_for == 'count':
        file_details = context.user_data.get('file_details', [])
        total_contacts = context.user_data.get('total_contacts', 0)

        if file_details:
            # Gabungkan detail per file dan total menjadi satu pesan
            detail_message = "\n".join(file_details)
            final_message = f"{detail_message}\n\nJumlah total kontak dari semua file adalah: {total_contacts} kontak."
            await update.message.reply_text(final_message)
        else:
            await update.message.reply_text("Tidak ada file yang diproses.")

        context.user_data.clear()  # Reset setelah selesai

    elif waiting_for == 'convert':
        await convert_files_to_xlsx(update, context)

    elif waiting_for == 'convert_to_txt':
        await convert_files_to_txt(update, context)

    elif waiting_for == 'sisa':
        await convert_files_to_sisa(update, context)

    else:
        await update.message.reply_text("Tidak ada tindakan yang sedang berlangsung.")



async def convert_files_to_sisa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        file_paths = context.user_data.get('file_paths', [])
        if not file_paths:
            await update.message.reply_text("Tidak ada file CSV atau VCF yang ditemukan untuk dikonversi.")
            return

        if 'file_name' not in context.user_data:
            await update.message.reply_text("Silakan masukkan nama file output yang diinginkan (tanpa ekstensi .txt):")
            context.user_data['waiting_for'] = 'file_name'
            return

        all_numbers = []
        total_contacts = 0
        message_text = ""  # String untuk menyimpan semua informasi

        for file_path in file_paths:
            try:
                if file_path.suffix == '.csv':
                    df = pd.read_csv(file_path)
                    if 'NOMOR' in df.columns:
                        numbers = df['NOMOR'].dropna().astype(str).tolist()
                    elif '+NOMOR' in df.columns:  
                        numbers = df['+NOMOR'].dropna().astype(str).tolist()
                    else:
                        raise ValueError("File CSV tidak memiliki kolom 'NOMOR' atau '+NOMOR'")
                
                elif file_path.suffix == '.vcf':
                    # Parse VCF file to extract phone numbers
                    numbers = []
                    with open(file_path, 'r', encoding='utf-8') as vcf_file:
                        for line in vcf_file:
                            # Look for lines that contain phone numbers
                            if line.startswith("TEL"):
                                phone_number = re.search(r'(\+?\d+)', line)
                                if phone_number:
                                    numbers.append(phone_number.group(1))

                else:
                    raise ValueError("Format file tidak didukung untuk konversi di perintah /sisa")

                contacts_count = len(numbers)
                total_contacts += contacts_count
                all_numbers.extend(numbers)
                message_text += f"File '{file_path.name}' memiliki {contacts_count} kontak.\n"

            except ValueError as e:
                logger.error(f"Error reading file {file_path}: {e}")
                await update.message.reply_text(f"File {file_path.name} tidak dapat diproses: {e}")

        if all_numbers:
            file_name = context.user_data['file_name']
            new_file_path = cache_dir / f"{file_name}.txt"
            with open(new_file_path, 'w') as f:
                for number in all_numbers:
                    f.write(number + '\n')

            # Kirim file txt yang dihasilkan terlebih dahulu
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(new_file_path, 'rb'))

            # Tambahkan informasi akhir tentang file yang dihasilkan
            message_text += f"\nSemua nomor telepon berhasil diubah ke format .txt dengan nama file '{file_name}.txt'. Jumlah kontak: {total_contacts}."

            # Kirim pesan yang berisi semua informasi setelah file
            await update.message.reply_text(message_text)

        context.user_data['file_paths'] = []
        context.user_data['waiting_for'] = None

    except Exception as e:
        logger.error(f"Error converting files to TXT: {e}")
        await update.message.reply_text(f"Terjadi kesalahan saat mengonversi file: {e}")



async def convert_files_to_xlsx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        file_paths = context.user_data.get('file_paths', [])
        if not file_paths:
            await update.message.reply_text("Tidak ada file yang ditemukan untuk dikonversi.")
            return

        successful_files = []
        failed_files = []

        for file_path in file_paths:
            file_name = file_path.name
            try:
                new_file_path = await convert_to_xlsx(file_path, file_name)
                successful_files.append(new_file_path)
            except ValueError as e:
                failed_files.append((file_name, str(e)))

        for file_path in successful_files:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))

        if successful_files:
            await update.message.reply_text("Semua file berhasil diubah ke format .xlsx.")

        if failed_files:
            error_messages = "\n".join([f"File {name}: {error}" for name, error in failed_files])
            await update.message.reply_text(f"Terjadi kesalahan pada file berikut:\n{error_messages}")

        context.user_data['file_paths'] = []
        context.user_data['waiting_for'] = None

    except Exception as e:
        logger.error(f"Error converting files to XLSX: {e}")
        await update.message.reply_text(f"Terjadi kesalahan saat mengonversi file: {e}")

async def convert_files_to_txt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        file_paths = context.user_data.get('file_paths', [])
        if not file_paths:
            await update.message.reply_text("Tidak ada file yang ditemukan untuk dikonversi.")
            return

        successful_files = []
        failed_files = []
        
        for file_path in file_paths:
            file_name = file_path.name
            try:
                new_file_path = await convert_to_txt(file_path, file_name)
                successful_files.append(new_file_path)
            except ValueError as e:
                failed_files.append((file_name, str(e)))
        
        for file_path in successful_files:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
        
        if successful_files:
            await update.message.reply_text("Semua file berhasil diubah ke format .txt.")
        
        if failed_files:
            error_messages = "\n".join([f"File {name}: {error}" for name, error in failed_files])
            await update.message.reply_text(f"Terjadi kesalahan pada file berikut:\n{error_messages}")
        
        context.user_data['file_paths'] = []
        context.user_data['waiting_for'] = None

    except Exception as e:
        logger.error(f"Error converting files to TXT: {e}")
        await update.message.reply_text(f"Terjadi kesalahan saat mengonversi file: {e}")

async def split_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return
        
        num_per_file = context.user_data['num_per_file']
        file_name = context.user_data['file_name']
        file_path = context.user_data['file_path']
        
        part_number = 1

        if file_name.endswith('.txt'):
            with open(file_path, 'r') as f:
                lines = f.readlines()
            total_contacts = len(lines)
            base_name = file_path.stem

            for i in range(0, total_contacts, num_per_file):
                part_lines = lines[i:i + num_per_file]
                if not part_lines:
                    break
                part_file_name = cache_dir / f"{base_name} {part_number}.txt"
                with open(part_file_name, 'w') as part_file:
                    part_file.writelines(part_lines)

                await context.bot.send_document(chat_id=update.effective_chat.id, document=open(part_file_name, 'rb'))
                part_number += 1

        elif file_name.endswith('.xlsx'):
            df = pd.read_excel(file_path)
            total_contacts = len(df)
            base_name = file_path.stem

            for i in range(0, total_contacts, num_per_file):
                part_df = df.iloc[i:i + num_per_file]
                if part_df.empty:
                    break
                part_file_name = cache_dir / f"{base_name} {part_number}.xlsx"
                part_df.to_excel(part_file_name, index=False)

                await context.bot.send_document(chat_id=update.effective_chat.id, document=open(part_file_name, 'rb'))
                part_number += 1

        await update.message.reply_text(f"File '{file_name}' telah dipecah menjadi {part_number - 1} bagian.")
    except Exception as e:
        logger.error(f"Error splitting file: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")
    finally:
        context.user_data.clear()

async def jumlah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        manage_cache()
        username = update.message.from_user.username
        if username not in allowed_usernames:
            await update.message.reply_text(f"{username} tidak diizinkan menggunakan bot ini. Hubungi @KazuhaID0 untuk meminta izin.")
            return

        # Reset previous commands
        context.user_data.clear()

        await update.message.reply_text("Silakan kirim file txt atau xlsx yang ingin Anda cek jumlahnya.")
        context.user_data['waiting_for'] = 'count'
        context.user_data['total_contacts'] = 0  # Untuk menyimpan jumlah total kontak dari semua file
        context.user_data['file_paths'] = []  # Untuk menyimpan file yang sudah diterima
    except Exception as e:
        logger.error(f"Error in jumlah command: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        waiting_for = context.user_data.get('waiting_for')

        if waiting_for == 'split_confirm':
            if not update.message.text.isdigit():
                await update.message.reply_text("Input tidak valid. Mohon masukkan angka.")
                return

            context.user_data['num_per_file'] = int(update.message.text)
            await split_file(update, context)

        elif waiting_for == 'file_name':
            file_name = update.message.text.strip()
            if file_name:
                context.user_data['file_name'] = file_name
                await convert_files_to_sisa(update, context)
            else:
                await update.message.reply_text("Nama file tidak boleh kosong. Silakan masukkan nama file yang valid.")

        else:
            await update.message.reply_text("Silakan masukkan perintah terlebih dahulu sebelum mengirimkan input.")
    
    except Exception as e:
        logger.error(f"Error handling text input: {e}")
        await update.message.reply_text(f"Terjadi kesalahan: {e}")


def main():
    try:
        application = Application.builder().token(API_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("pecah", pecah))
        application.add_handler(CommandHandler("jumlah", jumlah))
        application.add_handler(CommandHandler("excel", excel))
        application.add_handler(CommandHandler("text", text))
        application.add_handler(CommandHandler("sisa", sisa))
        application.add_handler(CommandHandler("done", done))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        logger.info("Bot sedang berjalan...")
        application.run_polling()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == '__main__':
    main()
