import telebot
import time
import queue as Queue
import threading


TOKEN = "{{sensitive data}}"
bot = telebot.TeleBot(TOKEN)
# Инициализируем очередь
real_queue = Queue.Queue()
# Глобальная переменная для хранения пользователя, который получает уведомление
current_user_to_notify = None
# Функция добавления в очередь
def add_to_queue(chat_id):
    real_queue.put(chat_id)
    bot.send_message(chat_id, "Вы добавлены в очередь. Дождитесь уведомления.")
# Функция получения следующего в очереди
def get_next_in_queue():
    if not real_queue.empty():
        return real_queue.get()
    else:
        return None
# Функция получения статуса
def get_queue_status(chat_id):
  current_position = real_queue.qsize() - real_queue._qsize() + 1
  bot.send_message(chat_id, f"Ваше текущее место в очереди: {current_position}")
# Функция отправки уведомления
def send_notification():
    global current_user_to_notify
    while True:
        if current_user_to_notify:
            bot.send_message(current_user_to_notify, "Ваша очередь скоро подойдет!")
            current_user_to_notify = None
            time.sleep(5)
        else:
            time.sleep(1)
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Привет! Я бот, который уведомляет о приближении вашей очереди.")
@bot.message_handler(commands=['queue'])
def queue_command(message):
    add_to_queue(message.chat.id)
@bot.message_handler(commands=['status'])
def status_command(message):
    get_queue_status(message.chat.id)
# Запускаем поток для отправки уведомлений
notification_thread = threading.Thread(target=send_notification)
notification_thread.daemon = True
notification_thread.start()
# Цикл для проверки очереди
while True:
    next_in_queue = get_next_in_queue()
    if next_in_queue:
        current_user_to_notify = next_in_queue  # Устанавливаем пользователя для уведомления
        time.sleep(10)
    else:
        time.sleep(1)
bot.polling()