import requests
import logging
import os, importlib
from datetime import datetime
import sqlite3
import json
import time
from config import tg_webhook_url, admin_id, sl_webhook_url

# глобальные переменные
s = requests.Session()
# s.cert = ('src/cert.pem', 'src/dec.key')  # Подстановка сертификата
db_path = os.getcwd() + os.sep + 'src' + os.sep + 'db.sqlite'
start_time = datetime.now()

# Храним чувствительные данные в переменной окружения
# Это значение по умолчанию на случай, если переменной окружения не будет
os.environ.setdefault('SETTINGS_MODULE', 'config')
# Импортируем модуль, указанный в переменной окружения
config = importlib.import_module(os.getenv('SETTINGS_MODULE'))

logging.basicConfig(filename="log/postmon_3.0.log", format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger('postmon_3.0')


