"""Veritabanı bağlantı ayarları (ortam değişkenlerinden / .env dosyasından).

Tek tanım yeri: `server.sunucu` ve ondan ayrılan modüller aynı sözlük nesnesini kullanır (testler içeriğini yerinde değiştirebilir).
"""
import os

from dotenv import load_dotenv

load_dotenv()

VT_AYARLARI = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}
