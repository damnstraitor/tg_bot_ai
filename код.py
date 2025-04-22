import os
import sqlite3
import json
import time
import base64
import requests
import telebot
import io

API_KEY1 = ''
API_URL = ""
API_KEY = ''
SECRET_KEY = ''

SUPER_ADMIN_ID = 00000000

bot = telebot.TeleBot("")

class Text2ImageAPI:
    def init(self, url, api_key, secret_key):
        self.URL = url
        self.AUTH_HEADERS = {
            'X-Key': f'Key {api_key}',
            'X-Secret': f'Secret {secret_key}',
        }

    def get_model(self):
        response = requests.get(self.URL + 'key/api/v1/models', headers=self.AUTH_HEADERS)
        data = response.json()
        return data[0]['id']

    def generate(self, prompt, model, images=1, width=1024, height=1024):
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": f"{prompt}"
            }
        }
        data = {
            'model_id': (None, model),
            'params': (None, json.dumps(params), 'application/json')
        }
        response = requests.post(self.URL + 'key/api/v1/text2image/run', headers=self.AUTH_HEADERS, files=data)
        data = response.json()
        return data['uuid']

    def check_generation(self, request_id, attempts=10, delay=10):
        while attempts > 0:
            response = requests.get(self.URL + 'key/api/v1/text2image/status/' + request_id, headers=self.AUTH_HEADERS)
            data = response.json()
            if data['status'] == 'DONE':
                return data['images']
            attempts -= 1
            time.sleep(delay)

    def save_image(self, base64_string, filename):
        image_data = base64.b64decode(base64_string)
        return image_data

def init_db():
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interactions (
            user_id INTEGER PRIMARY KEY,
            total_count INTEGER DEFAULT 0,
            chat_count INTEGER DEFAULT 0,
            image_count INTEGER DEFAULT 0,
            huggingface_count INTEGER DEFAULT 0,
            tag TEXT DEFAULT '',
            comment TEXT DEFAULT ''
        )
    ''')

    try:
        cursor.execute("ALTER TABLE interactions ADD COLUMN tag TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE interactions ADD COLUMN comment TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            admin_comment TEXT DEFAULT ''
        )
    ''')

    try:
        cursor.execute("ALTER TABLE admins ADD COLUMN admin_comment TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def ensure_user_in_db(user_id):
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO interactions (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    ensure_user_in_db(user_id)
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    if user_id == SUPER_ADMIN_ID:
        start_neiro(message)
    else:
        cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            start_neiro(message)
        else:
            handle_non_admin_user(message)

    conn.close()

def handle_non_admin_user(message):
    user_id = message.from_user.id
    ensure_user_in_db(user_id)
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('SELECT total_count FROM interactions WHERE user_id = ?', (user_id,))
    total_count = cursor.fetchone()

    cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if total_count and total_count[0] > 5 and not result and user_id != SUPER_ADMIN_ID:
        bot.reply_to(message, "Вы превысили лимит обращений к боту. Доступ заблокирован.")
        conn.close()
        return
    else:
        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        keyboard.add('/chat', '/image')
        response = (
            "Ваша информация сохранена в базе данных. Доступные команды:\n"
            "/chat - Чат с нейронной сетью\n"
            "/image - Генерация изображений\n"
        )
        bot.reply_to(message, response, reply_markup=keyboard, parse_mode="Markdown")

    conn.close()

@bot.message_handler(commands=['neiro'])
def start_neiro(message):
    user_id = message.from_user.id
    ensure_user_in_db(user_id)
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if user_id == SUPER_ADMIN_ID:
        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=False)
        keyboard.add('/StartChat', '/GeneratePicture', '/Back', '/viewdata', '/addcomment', '/addadmin', '/listadmins', '/addadmincomment', '/removeadmin', '/broadcast')
        bot.reply_to(message, 'Выберите нейросеть:', reply_markup=keyboard, parse_mode="Markdown")
    elif result:
        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        keyboard.add('/StartChat', '/GeneratePicture', '/Back', '/viewdata', '/addcomment')
        bot.reply_to(message, 'Выберите нейросеть:', reply_markup=keyboard, parse_mode="Markdown")
    else:
        keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        keyboard.add('/StartChat', '/GeneratePicture', '/Back')
        bot.reply_to(message, 'Выберите нейросеть:', reply_markup=keyboard, parse_mode="Markdown")

@bot.message_handler(commands=['StartChat', 'chat'])
def chat(message):
    user_id = message.from_user.id
    ensure_user_in_db(user_id)
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('SELECT total_count FROM interactions WHERE user_id = ?', (user_id,))
    total_count = cursor.fetchone()

    cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if total_count and total_count[0] > 5 and not result and user_id != SUPER_ADMIN_ID:
        bot.reply_to(message, "Вы превысили лимит обращений к боту. Доступ заблокирован.")
        conn.close()
        return

    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    keyboard.add('/Back')
    bot.reply_to(message, "Пожалуйста, введите ваш запрос для нейросети. Чтобы выйти, введите /Back.", reply_markup=keyboard)
    bot.register_next_step_handler(message, receive_text_prompt)

def receive_text_prompt(message):
    if message.text == '/Back':
        back_to_main_menu(message)
        return

    user_id = message.from_user.id
    prompt = message.text
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    headers = {
        "Authorization": f"Bearer {API_KEY1}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mistral-medium",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(API_URL, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        bot_response = result["choices"][0]["message"]["content"]
        bot.reply_to(message, f"Ответ от нейросети: {bot_response}")

        cursor.execute('SELECT chat_count, total_count FROM interactions WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if result:
            chat_count = result[0] + 1
            total_count = result[1] + 1
            cursor.execute('UPDATE interactions SET chat_count = ?, total_count = ? WHERE user_id = ?', (chat_count, total_count, user_id))
        else:
            cursor.execute('INSERT INTO interactions (user_id, chat_count, total_count) VALUES (?, ?, ?)', (user_id, 1, 1))

        conn.commit()

        bot.reply_to(message, "Введите следующий запрос или /Back для выхода.")
        bot.register_next_step_handler(message, receive_text_prompt)

    else:
        bot.reply_to(message, f"Произошла ошибка: {response.status_code} {response.text}")

    conn.close()

@bot.message_handler(commands=['GeneratePicture', 'image'])
def image(message):
    user_id = message.from_user.id
    ensure_user_in_db(user_id)
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('SELECT total_count FROM interactions WHERE user_id = ?', (user_id,))
    total_count = cursor.fetchone()

    cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if total_count and total_count[0] > 5 and not result and user_id != SUPER_ADMIN_ID:
        bot.reply_to(message, "Вы превысили лимит обращений к боту. Доступ заблокирован.")
        conn.close()
        return
    keyboard = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
    keyboard.add('/Back')
    bot.reply_to(message, "Пожалуйста, введите текст для генерации изображения. Чтобы выйти, введите /Back.", reply_markup=keyboard)
    bot.register_next_step_handler(message, receive_text_prompt_image)

def receive_text_prompt_image(message):
    if message.text == '/Back':
        back_to_main_menu(message)
        return

    user_id = message.from_user.id
    prompt = message.text
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    api = Text2ImageAPI('https://api-key.fusionbrain.ai/', API_KEY, SECRET_KEY)
    model_id = api.get_model()
    uuid = api.generate(prompt, model_id)
    images = api.check_generation(uuid)

    if images:
        image_data = api.save_image(images[0], None)
        bot.send_photo(message.chat.id, io.BytesIO(image_data))

        cursor.execute('SELECT image_count, total_count FROM interactions WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()

        if result:
            image_count = result[0] + 1
            total_count = result[1] + 1
            cursor.execute('UPDATE interactions SET image_count = ?, total_count = ? WHERE user_id = ?', (image_count, total_count, user_id))
        else:
            cursor.execute('INSERT INTO interactions (user_id, image_count, total_count) VALUES (?, ?, ?)', (user_id, 1, 1))

        conn.commit()

        bot.reply_to(message, "Введите следующий текст для генерации изображения или /Back для выхода.")
        bot.register_next_step_handler(message, receive_text_prompt_image)

    conn.close()

@bot.message_handler(commands=['Back'])
def back_to_main_menu(message):
    handle_non_admin_user(message)

@bot.message_handler(commands=['addadmin'])
def add_admin(message):
    user_id = message.from_user.id

    if user_id == SUPER_ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, отправьте ID пользователя, которого хотите сделать админом.")
        bot.register_next_step_handler(message, process_add_admin)
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

def process_add_admin(message):
    try:
        new_admin_id = int(message.text)
        conn = sqlite3.connect('user_interactions.db')
        cursor = conn.cursor()

        cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (new_admin_id,))
        conn.commit()

        bot.reply_to(message, f"Пользователь с ID {new_admin_id} успешно добавлен в админы.")
    except ValueError:
        bot.reply_to(message, "Неверный формат ID. Пожалуйста, отправьте числовое значение.")
    finally:
        conn.close()

@bot.message_handler(commands=['viewdata'])
def view_data(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result or user_id == SUPER_ADMIN_ID:
        cursor.execute('SELECT * FROM interactions')
        data = cursor.fetchall()

        response = "Данные о пользователях:\n"
        for row in data:
            user_id = row[0] if len(row) > 0 else 'N/A'
            total_count = row[1] if len(row) > 1 else 'N/A'
            chat_count = row[2] if len(row) > 2 else 'N/A'
            image_count = row[3] if len(row) > 3 else 'N/A'
            huggingface_count = row[4] if len(row) > 4 else 'N/A'
            tag = row[5] if len(row) > 5 else 'N/A'
            comment = row[6] if len(row) > 6 else 'N/A'

            response += (f"User ID: {user_id}, Total Count: {total_count}, Chat Count: {chat_count}, "
                         f"Image Count: {image_count}, HuggingFace Count: {huggingface_count}, "
                         f"Tag: {tag}, Comment: {comment}\n")

        bot.reply_to(message, response)
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

    conn.close()

@bot.message_handler(commands=['addcomment'])
def add_comment(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result or user_id == SUPER_ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, отправьте ID пользователя и комментарий через пробел (например, '123456789 Ваш комментарий'):")
        bot.register_next_step_handler(message, process_add_comment)
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

    conn.close()

def process_add_comment(message):
    try:
        user_id, comment = message.text.split(maxsplit=1)
        user_id = int(user_id)
        conn = sqlite3.connect('user_interactions.db')
        cursor = conn.cursor()

        cursor.execute('UPDATE interactions SET comment = ? WHERE user_id = ?', (comment, user_id))
        conn.commit()

        bot.reply_to(message, f"Комментарий для пользователя с ID {user_id} успешно обновлен.")
    except ValueError:
        bot.reply_to(message, "Неверный формат. Пожалуйста, отправьте ID пользователя и комментарий через пробел.")
    finally:
        conn.close()

@bot.message_handler(commands=['listadmins'])
def list_admins(message):
    user_id = message.from_user.id

    if user_id == SUPER_ADMIN_ID:
        conn = sqlite3.connect('user_interactions.db')
        cursor = conn.cursor()

        cursor.execute('SELECT user_id, admin_comment FROM admins')
        admins = cursor.fetchall()

        response = "Список админов:\n"
        for admin in admins:
            admin_id = admin[0]
            admin_comment = admin[1] if admin[1] else 'N/A'
            response += f"Admin ID: {admin_id}, Comment: {admin_comment}\n"

        bot.reply_to(message, response)
        conn.close()
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

@bot.message_handler(commands=['addadmincomment'])
def add_admin_comment(message):
    user_id = message.from_user.id

    if user_id == SUPER_ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, отправьте ID админа и комментарий через пробел (например, '123456789 Ваш комментарий'):")
        bot.register_next_step_handler(message, process_add_admin_comment)
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

def process_add_admin_comment(message):
    try:
        admin_id, comment = message.text.split(maxsplit=1)
        admin_id = int(admin_id)
        conn = sqlite3.connect('user_interactions.db')
        cursor = conn.cursor()

        cursor.execute('UPDATE admins SET admin_comment = ? WHERE user_id = ?', (comment, admin_id))
        conn.commit()

        bot.reply_to(message, f"Комментарий для админа с ID {admin_id} успешно обновлен.")
    except ValueError:
        bot.reply_to(message, "Неверный формат. Пожалуйста, отправьте ID админа и комментарий через пробел.")
    finally:
        conn.close()

@bot.message_handler(commands=['removeadmin'])
def remove_admin(message):
    user_id = message.from_user.id

    if user_id == SUPER_ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, отправьте ID пользователя, которого хотите удалить из админов:")
        bot.register_next_step_handler(message, process_remove_admin)
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

def process_remove_admin(message):
    try:
        admin_id = int(message.text)
        conn = sqlite3.connect('user_interactions.db')
        cursor = conn.cursor()

        cursor.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()

        bot.reply_to(message, f"Пользователь с ID {admin_id} успешно удален из админов.")
    except ValueError:
        bot.reply_to(message, "Неверный формат ID. Пожалуйста, отправьте числовое значение.")
    finally:
        conn.close()

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    user_id = message.from_user.id

    if user_id == SUPER_ADMIN_ID:
        bot.reply_to(message, "Пожалуйста, отправьте сообщение, которое хотите разослать всем пользователям:")
        bot.register_next_step_handler(message, process_broadcast)
    else:
        bot.reply_to(message, "У вас нет прав для выполнения этой команды.")

def process_broadcast(message):
    broadcast_message = message.text
    conn = sqlite3.connect('user_interactions.db')
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM interactions')
    user_ids = cursor.fetchall()

    for user in user_ids:
        try:
            bot.send_message(user[0], broadcast_message)
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user[0]}: {e}")

    bot.reply_to(message, "Сообщение успешно разослано всем пользователям.")
    conn.close()

def main():
    try:
        init_db()
        bot.polling(none_stop=True, timeout=600000)
    except Exception as e:
        print(e)
        main()

if __name__ == '__main__':
    main()
