import mysql.connector
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from mysql.connector import Error
from telebot import types

from config import TOKEN, CHAT_IDS, DB_HOST, DB_USER, DB_PASSWORD, DB_DATABASE, DB_TABLE


# Инициализация Telegram бота
bot = telebot.TeleBot(TOKEN)

# Инициализация планировщика
scheduler = BackgroundScheduler()

# Переменная для отслеживания последнего отправленного уведомления
last_sent_notification_id = None


# Функция для подключения к базе данных MySQL
def connect():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_DATABASE
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Ошибка подключения: {e}")
        return None


# Функция для получения последней записи из таблицы
def get_last_record_id(connection):
    try:
        cursor = connection.cursor()
        query = f"SELECT id FROM {DB_TABLE} ORDER BY id DESC LIMIT 1"
        cursor.execute(query)
        record = cursor.fetchone()
        if record:
            return record[0]
    except Error as e:
        print(f"Ошибка: {e}")
    finally:
        cursor.close()


# Функция для получения содержимого новой записи
def get_new_record_data(connection, record_id):
    try:
        cursor = connection.cursor()
        query = f"SELECT * FROM {DB_TABLE} WHERE id = {record_id}"
        cursor.execute(query)
        record = cursor.fetchone()
        if record:
            return record
    except Error as e:
        print(f"Ошибка: {e}")
    finally:
        cursor.close()


# Функция для отправки уведомления
def send_notification():
    global last_sent_notification_id
    connection = connect()
    if connection:
        last_record_id = get_last_record_id(connection)
        if last_record_id and last_record_id != last_sent_notification_id:
            new_record_data = get_new_record_data(connection, last_record_id)
            if new_record_data:
                # Формируем текст уведомления с содержимым новой записи
                message_text = (
                    f"Добавлена новая запись в таблицу {DB_TABLE} (ID: {last_record_id})\n"
                    f"Имя: {new_record_data[5]}\n"
                    f"Фамилия: {new_record_data[3]}\n"
                    f"Телефон: {new_record_data[4]}\n"
                    f"Описание проблемы: {new_record_data[2]}"
                )

                # Создаем клавиатуру с инлайн-кнопкой и reply keyboard
                inline_keyboard = types.InlineKeyboardMarkup()
                button_text = "Посмотреть последние 10 заказов"
                button_callback = "last_orders"
                inline_button = types.InlineKeyboardButton(text=button_text, callback_data=button_callback)
                inline_keyboard.add(inline_button)

                reply_keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
                reply_button = types.KeyboardButton("/last_orders")
                reply_keyboard.add(reply_button)

                for chat_id in CHAT_IDS:
                    try:
                        bot.send_message(chat_id, message_text, reply_markup=inline_keyboard)
                        last_sent_notification_id = last_record_id
                    except Exception as e:
                        print(f"Ошибка отправки уведомления: {e}")

# Обработчик инлайн-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "last_orders":
        last_orders_handler(call.message)

# Команда для просмотра последних 10 заказов
@bot.message_handler(commands=['last_orders'])
def last_orders_handler(message):
    connection = connect()
    if connection:
        try:
            cursor = connection.cursor()
            query = f"SELECT * FROM {DB_TABLE} ORDER BY id DESC LIMIT 10"
            cursor.execute(query)
            orders = cursor.fetchall()

            response_text = "Последние 10 заказов:\n"
            for order in orders:
                response_text += f"ID: {order[0]}, Имя: {order[5]}, Фамилия: {order[3]}, Телефон: {order[4]}, Описание проблемы: {order[2]}\n"

            bot.send_message(message.chat.id, response_text)
        except Error as e:
            print(f"Ошибка: {e}")
        finally:
            cursor.close()

# Запуск планировщика для выполнения задачи каждую секунду
scheduler.add_job(send_notification, 'interval', seconds=1)
scheduler.start()

# Запуск бота
bot.polling(none_stop=True, interval=1)