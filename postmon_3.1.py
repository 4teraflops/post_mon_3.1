import requests
import logging
import os, importlib
from datetime import datetime
import sqlite3
import json
import time

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


def create_urls_list():
    service_cods = []
    urls = []
    stop_list_cods = []
    logger.info(' Составляю список ссылок для итераций...')
    conn = sqlite3.connect(db_path)  # Инициируем подключение к БД
    cursor = conn.cursor()
    #  Собираем список сервис-кодов
    cursor.execute("SELECT code FROM service_cods_tst")
    for cod in cursor:
        service_cods.append(cod[0])
    #  Собираемсписок по стоп листу
    cursor.execute('SELECT code FROM stop_list')
    for stop_cod in cursor:
        stop_list_cods.append(stop_cod[0])

    for s in service_cods:  # теперь составляем список ссылок, которые будем тестить
        if s not in stop_list_cods:
            # превращаем код услуги в ссылку для теста (отсекая коды из стоп листа)
            url = (
                    'https://uat.autopays.ru/api-shop/rs/shop/test?sec-key=96abc9ad-24dc-4125-9fc4-a8072f7b83c3'
                    '&service-code=' + '{}').format(s)
            urls.append(url)  # запись в общий список ссылок
    conn.commit()
    logger.info(" Ок")
    # если надо будет чекнуть сколько кодов услуг отсечено, выводим метрики и смотрим.
    logger.info(f'Кол-во кодов услуг для мониторинга:\nService cods - {len(service_cods)}\nStop list - {len(stop_list_cods)}\nUrls - {len(urls)}\nОтсечено - {(len(service_cods) - len(urls))}\nService cods Итого - {len(service_cods)}')
    open_urls(urls)


def open_urls(urls):
    first_id = get_cursor_id('global_answers_data')
    n = 0
    conn = sqlite3.connect(db_path)  # Инициируем подключение к БД
    cursor = conn.cursor()
    for url in urls:
        n += 1
        r = s.get(url)
        timeout = round(r.elapsed.total_seconds(), 3)  # Округление до 3 знаков после запятой
        answer_text = r.text.replace('--ERROR--\ncom.techinfocom.bisys.pay.utils.shared.exception.', '').replace('\n',
                                                                                                                 '').replace(
            "'", '')
        status = check_answer(answer_text)
        code = str(url).replace(
            'https://uat.autopays.ru/api-shop/rs/shop/test?sec-key=96abc9ad-24dc-4125-9fc4-a8072f7b83c3&service-code=',
            '')
        #  вытащил значение в виде list, забрал первое значение этого list
        category = cursor.execute(f"SELECT category FROM service_cods_tst WHERE code = '{code}'").fetchall()[0][0]
        now = datetime.now()
        operation_time = now.strftime('%d-%m-%Y %H:%M:%S')
        cursor.execute(
            f"INSERT INTO global_answers_data VALUES (Null, '{operation_time}', '{code}', '{category}', '{timeout}', '{status}')")
        conn.commit()
        #print(f'{n}|{code}||{timeout}||{category}||{operation_time}||{status}')
    logger.info('Итерация по кодам услуг завершена.')
    last_id = get_cursor_id('global_answers_data')
    logger.info('Обновляю данные в часовой таблице')
    cursor.execute("DELETE from res_h")  # предварительно затираем то, что было в таблице res_h
    res = cursor.execute(f"SELECT * FROM global_answers_data WHERE id > {first_id} and id <= {last_id}").fetchall()
    conn.commit()
    # Записываем результаты последней проверки в таблицу res
    for r in res:
        r1 = r[1:6:1]  # Отсек первый элемент в каждом из списков (это id, чтоб не было конфликтов)
        cursor.execute(f"INSERT INTO res_h VALUES (Null, ?, ?, ?, ?, ?)", r1)
    conn.commit()


def check_answer(answer_text):
    text = answer_text.replace('--ERROR--\ncom.techinfocom.bisys.pay.utils.shared.exception.', '').replace('\n',
                                                                                                           '').replace(
        "'", '')
    lst_format = ['BIS-01275', 'Неверный формат', 'Недостаточно параметров', 'Отсутствуют требуемые доп параметры',
                  'BIS-01656']
    lst_ok = ["BIS-01640", "BIS-01654", "--SUCCESS--", "OtherError:21:", "OtherError:4:", "OtherError:29:",
              "OtherError:99:",
              "Отсутствует разрешение на прием платежей", "OtherError:41:", "Проверка не завершилась",
              "Ошибочный номер абонента", "OtherError:1:"]
    lst_errors = ["BIS-01262", "BIS-01658", "BIS-01295", "Ошибка подключения к серверу", "Ошибка HTTP", "OtherError:?:",
                  "Неизвестный протокол в параметрах услуг", "Работа шлюза приостановлена", "OtherError:1:",
                  "OtherError:Ошибка ?:", "OtherError:242:", "OtherError:79:", "OtherError:Ошибка связи"]

    for frmt in lst_format:
        if frmt in text:
            status = 'format'
            return status
    for ok in lst_ok:
        if ok in text:
            status = 'ok'
            return status
    for error in lst_errors:
        if error in text:
            status = 'error'
            return status
    if 'provider == null' in text:
        status = 'услуга не выведена'
        return status
    else:
        status = 'Null'
        return status


def get_cursor_id(table_name):
    conn = sqlite3.connect(db_path)  # Инициируем подключение к БД
    cursor = conn.cursor()
    line_id = cursor.execute(f"select seq from sqlite_sequence where name='{table_name}'").fetchall()[0][0]
    conn.commit()
    return line_id


def do_alarm(alarmtext):  # отправка сообщения в канал slack
    headers = {"Content-type": "application/json"}
    url = config.webhook_url
    payload = {"text": f"{alarmtext}"}
    requests.post(url, headers=headers, data=json.dumps(payload))


def digest():
    conn = sqlite3.connect(db_path)  # Инициируем подключение к БД
    cursor = conn.cursor()

    id_errors = cursor.execute("SELECT id FROM res_h WHERE status = 'error'").fetchall()
    id_oks = cursor.execute("SELECT id FROM res_h WHERE status = 'ok'").fetchall()
    id_with_format = cursor.execute("SELECT id FROM res_h WHERE status = 'format'").fetchall()
    id_shadow = cursor.execute("SELECT id FROM res_h WHERE status = 'услуга не выведена'").fetchall()
    # Смотрим неопознанные ошибки (которым не присвоилась категория)
    manual_check = cursor.execute(f"SELECT id FROM res_h WHERE status is NULL").fetchall()
    # Подсчитаем общее кол-во проанализированных ПУ
    len_all_table = cursor.execute(f"SELECT id from res_h").fetchall()
    # Посмотрим есть ли ошибки у клиентов категории А
    errors_a = cursor.execute(
        f"SELECT code, status, operation_time FROM res_h WHERE category = 'A' AND (status = 'error' OR status = 'услуга не выведена')").fetchall()
    errors_b = cursor.execute(f"SELECT code, status, operation_time FROM res_h WHERE category = 'B' AND (status = 'error' OR status = 'услуга не выведена')").fetchall()
    # Выводим срез по цифрам:
    logger.info(f'\nВсего проанализировано: {len(len_all_table)} ПУ.\nИз них: \n{len(id_errors)} - С техническинми ошибками\n{len(id_oks)} - В состоянии OK\n{len(id_with_format)} - Не совпали по формату запроса проверки\n{len(manual_check)}   - Неопознанные ошибки\n{len(id_shadow)} - услуга не выведена\n')
    print(f'Клиентов категории А с ошибками: {len(errors_a)}\n')
    logger.info(f'Клиентов категории А с ошибками: {len(errors_a)}\n')
    for a in errors_a:
        print(f'Код услуги: {a[0]}\nСтатус услуги: {a[1]}\nВремя проверки: {a[2]}\n')
    print(f'\nКлиентов категории B с ошибками: {len(errors_b)}\n')
    logger.info(f'\nКлиентов категории B с ошибками: {len(errors_b)}\n')
    for b in errors_b:
        print(f'Код услуги: {b[0]}\nСтатус услуги: {b[1]}\nВремя проверки: {b[2]}\n')
    conn.commit()
    if errors_a or errors_b:
        for a in errors_a:
            alarmtext = f'Категория клиента: A\nКод услуги: {a[0]}\nСтатус услуги: {a[1]}\nВремя проверки: {a[2]}'
            do_alarm(alarmtext)
            logger.warning('Сработал Alarm для клиентов категории А')

        for b in errors_b:
            alarmtext = f'Категория клиента: B\nКод услуги: {b[0]}\nСтатус услуги: {b[1]}\nВремя проверки: {b[2]}'
            do_alarm(alarmtext)
            logger.warning('Сработал Alarm для клиентов категории B')


if __name__ == '__main__':
    try:
        while True:
            create_urls_list()
            digest()
            end_time = datetime.now()  # для рассчета времени выполнения скрипта
            work_time = end_time - start_time  # рассчет времени вполнения скрипта
            print('\nВремя работы скрипта = ', work_time)
            logger.info(f'\nВремя работы скрипта = {work_time}')
            logger.info('Встаю на паузу.')
            time.sleep(2400)
    except KeyboardInterrupt:
        print('\n Вы завершили работу программы. Закрываюсь.')
