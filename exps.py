import requests
import logging
import os, importlib
from datetime import datetime
import sqlite3
import json
import time
from config import tg_webhook_url, admin_id, sl_webhook_url
from loguru import logger

with open('b.txt', 'rU') as f:
    service_cods = f.read().split('\n')
#logger.info(f'service_cods: {service_cods}')

db_path = 'src/db.sqlite'
conn = sqlite3.connect(db_path)  # Инициируем подключение к БД
cursor = conn.cursor()


for code in service_cods:
    cursor.execute(f'INSERT INTO service_cods VALUES (Null, "{code}", Null, "B")')
    conn.commit()