import aiogram
import io
import re
import json
import time
import asyncio
import sqlite3

from aiogram import types
from aiogram.utils.exceptions import ChatNotFound
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from bot.bot import dp, bot
from bot.utils import pay_list, fetch_profile, auth_profile, generate_pay_link, promised_payment, get_camera, get_locations, get_stream_info, change_password, change_password_confim, lock_lk_rs
from bot.keyboards.keyboard_admin import generate_admin_keyboard
from bot.keyboards import keyboard as kb
from bot.states.state import SomeState, MailingState, Registration, SubscribeBuy, ChangePasswordState


connection = sqlite3.connect('bot/database/db.db')
cursor = connection.cursor()

async def on_startup_commands(_):
    cursor.execute('''CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            token TEXT,
            id INTEGER,
            password TEXT,
            is_admin INTEGER 
        )''')
    connection.commit()

    cursor.execute('''CREATE TABLE IF NOT EXISTS favorites(
            user_id INTEGER PRIMARY KEY,
            cams TEXT
        )''')
    connection.commit()

    print('Бот запущен!')

@dp.message_handler(commands=['start'], state="*")
async def start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)

    cursor.execute("SELECT user_id, is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        try:
            await bot.send_message(
                6681723799,
                f'Новый пользователь зарегистрировался в боте, ID: {user_id}',
                parse_mode='HTML',
                reply_markup=delete_message
            )
        except:
            pass

        await message.answer("Добро пожаловать!\nДанный бот не является официальным! Вы делаете всё на свой страх и риск, мы не несём ответственность за ваши действия.\n\nДля начала работы введите ваш ID:")
        await Registration.waiting_for_token.set()
    else:
        welcome_message = f"👋 {message.from_user.first_name}, <b>добро пожаловать в Систему</b>\n\nЗакрытый репозиторий для разработчиков бота: https://github.com/reques6e/TgBotSystemaLtd/"
        await message.reply(welcome_message, parse_mode="HTML", reply_markup=kb.generate_main_menu(is_admin=result[1]))

@dp.message_handler(commands=['del_data'])
async def del_data(message: types.Message):
    user_id = str(message.from_user.id)

    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    connection.commit()
    
    await message.reply(f"Данные для пользователя с user_id {user_id} успешно удалены.")

@dp.message_handler(commands=['re_auth'], state="*")
async def re_auth(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    cursor.execute("SELECT id, password FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        id = result[0]
        password = result[1]

        re_auth_response = await auth_profile(id, password)
        if re_auth_response and re_auth_response['response']['status']:
            cursor.execute("UPDATE users SET token = ? WHERE user_id = ?", (re_auth_response['response']['token'], user_id))
            connection.commit()

            await message.answer("Профиль успешно переавторизован.")
        else:
            await message.answer("Не удалось выполнить переавторизацию.")
    else:
        await message.answer("Профиль не найден в базе данных.")

    await state.finish()

@dp.message_handler(state=Registration.waiting_for_token)
async def process_token_input(message: types.Message, state: FSMContext):
    id = message.text
    await state.update_data(id=id)
    await message.answer("Теперь введите ваш пароль:")
    await Registration.next()

@dp.message_handler(state=Registration.waiting_for_id)
async def process_id_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    id = data.get("id")
    password = message.text

    rs = await auth_profile(id, password)
    if rs['response']['status']:
        cursor.execute('INSERT INTO users (user_id, token, id, password, is_admin) VALUES (?, ?, ?, ?, ?)', (user_id, rs['response']['token'], id, password, 0))
        connection.commit()

        cursor.execute('INSERT INTO favorites (user_id, cams) VALUES (?, ?)', (user_id, '[]'))
        connection.commit()

        await message.reply(f"👋 {message.from_user.first_name}, <b>добро пожаловать в Систему</b>",
                            parse_mode="HTML", reply_markup=kb.generate_main_menu(is_admin=False))
        await state.finish()
    else:
        await message.reply(f"Неверный логин или пароль")
    
@dp.callback_query_handler(lambda c: c.data.startswith('delete_message_'))
async def delete_message(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id

    await bot.delete_message(chat_id, message_id=callback_query.message.message_id)
    await bot.answer_callback_query(callback_query.id, text="Сообщение удалено", show_alert=True)
    
@dp.callback_query_handler(lambda c: c.data == 'info')
async def process_callback_button(callback_query: types.CallbackQuery):
    keyboard = kb.generate_keyboard_info()

    back_to_start_button = InlineKeyboardButton("⤶ Назад", callback_data='back_to_start')
    keyboard.add(back_to_start_button)

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="<b>❗️ Выберите действие:</b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'delete_menu')
async def delete_menu(callback_query: types.CallbackQuery):
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
    await bot.answer_callback_query(callback_query.id, text="Меню скрыто", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == 'cancel', state=SomeState)
async def cancel_action(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    message_id = data.get('message_id')
    if message_id:
        sent_message = await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                                  message_id=message_id,
                                                  text="Отменено",
                                                  parse_mode="HTML")
        delete_button = InlineKeyboardButton("🗑Удалить", callback_data=f'delete_message_{sent_message.message_id}')
        keyboard = InlineKeyboardMarkup().add(delete_button)
        await bot.edit_message_reply_markup(callback_query.from_user.id, message_id=sent_message.message_id, reply_markup=keyboard)

    await state.finish()
    await callback_query.answer("✅ Успешно отменено", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == 'cams')
async def get_cams_list(callback_query: types.CallbackQuery):    
    user_id = callback_query.from_user.id
    
    locations_response = await get_locations()
    if locations_response and locations_response.get('response'):
        locations = locations_response['response']
        
        keyboard = InlineKeyboardMarkup()
        for location in locations:
            location_id = location['location_id']
            location_name = location['location_name']
            keyboard.insert(InlineKeyboardButton(location_name, callback_data=f'location_{location_id}'))
        
        await bot.edit_message_text(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id,
            text='Выберите локацию:',
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await bot.answer_callback_query(callback_query.id, "Ошибка при получении локаций")

@dp.callback_query_handler(lambda c: c.data.startswith('location_'))
async def location_selected(callback_query: types.CallbackQuery):
    location_id = callback_query.data.split('_', 1)[-1]

    cameras_response = await get_camera(location_id)
    if cameras_response:
        cameras = cameras_response['response']['cams']
        camera_groups = [cameras[i:i+9] for i in range(0, len(cameras), 9)]
        current_page = 0
        
        async def send_camera_message(page):
            keyboard = InlineKeyboardMarkup()
            for camera in camera_groups[page]:
                camera_id = camera['channel']
                camera_name = camera['name']
                keyboard.insert(InlineKeyboardButton(camera_name, callback_data=f'camera_{camera_id}'))
            
            if len(camera_groups) > 1:
                if page == 0:
                    keyboard.row(InlineKeyboardButton("🗑Удалить", callback_data='button_delete_message'),
                                 InlineKeyboardButton("Вперёд➡️", callback_data='next'))
                elif page == len(camera_groups) - 1:
                    keyboard.row(InlineKeyboardButton("⬅️ Назад", callback_data='back'),
                                 InlineKeyboardButton("🗑Удалить", callback_data='button_delete_message'))
                else:
                    keyboard.row(InlineKeyboardButton("⬅️ Назад", callback_data='back'),
                                 InlineKeyboardButton("🗑Удалить", callback_data='button_delete_message'),
                                 InlineKeyboardButton("Вперёд➡️", callback_data='next'))
            else:
                keyboard.row(InlineKeyboardButton("🔙 Назад", callback_data='back'),
                             InlineKeyboardButton("🗑Удалить", callback_data='button_delete_message'),
                             InlineKeyboardButton("Вперёд➡️", callback_data='next'))
            
            message_text = 'Выберите камеру:'
            
            if callback_query.message:
                try:
                    await bot.edit_message_text(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        text=message_text,
                        reply_markup=keyboard
                    )
                except aiogram.utils.exceptions.MessageNotModified:
                    try:
                        await bot.answer_callback_query(callback_query.id, "Отображены все камеры")
                    except:
                        pass
                except aiogram.utils.exceptions.MessageToEditNotFound:
                    pass
            else:
                await bot.send_message(
                    callback_query.from_user.id,
                    text=message_text,
                    reply_markup=keyboard
                )
        
        await send_camera_message(current_page)
        
        @dp.callback_query_handler(lambda c: c.data in {'back', 'next'})
        async def handle_navigation(callback_query: types.CallbackQuery):
            nonlocal current_page
            if callback_query.data == 'back':
                current_page = max(current_page - 1, 0)
            elif callback_query.data == 'next':
                current_page = min(current_page + 1, len(camera_groups) - 1)
            await send_camera_message(current_page)
    else:
        await bot.answer_callback_query(callback_query.id, "Ошибка при получении камер по локации")

@dp.callback_query_handler(lambda c: c.data.startswith('camera_'))
async def camera_selected(callback_query: types.CallbackQuery):
    channel_name = callback_query.data.replace('camera_', '')
    user_id = callback_query.from_user.id

    async def is_favorite(user_id, channel_name):
        cursor.execute("SELECT cams FROM favorites WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            favorites = json.loads(row[0])
            return channel_name in favorites
        else:
            return False

    camera_response = await get_stream_info(channel_name)
    if camera_response and camera_response.get('response'):
        camera = camera_response['response']
        image_url = camera.get('preview')
        channel = camera.get('cam')['camera_name']
        description = camera.get('cam')['camera_text']
        weather = camera.get('weather', {}).get('fact', {})
        temperature = weather.get('temp')
        condition = weather.get('condition')
        wind_speed = weather.get('wind_speed')
        
        description = re.sub(r'<\s*p\s*>', '', description)
        description = re.sub(r'</\s*p\s*>', '', description)

        weather_conditions = {
            'clear': 'Ясно',
            'partly-cloudy': 'Малооблачно',
            'cloudy': 'Облачно с прояснениями',
            'overcast': 'Пасмурно',
            'light-rain': 'Небольшой дождь',
            'rain': 'Дождь',
            'heavy-rain': 'Сильный дождь',
            'showers': 'Ливень',
            'wet-snow': 'Дождь со снегом',
            'light-snow': 'Небольшой снег',
            'snow': 'Снег',
            'snow-showers': 'Снегопад',
            'hail': 'Град',
            'thunderstorm': 'Гроза',
            'thunderstorm-with-rain': 'Дождь с грозой',
            'thunderstorm-with-hail': 'Гроза с градом'
        }

        if condition in weather_conditions:
            condition = weather_conditions[condition]

        if len(description) > 430:
            description = description[:430-3] + '...'

        message_text = f"📷 Канал: <b>{channel}</b>\n\n"
        message_text += f"{description}\n\n"
        message_text += f"🌡️ Температура: <b>{temperature}°C</b>\n"
        message_text += f"☁️ Погодные условия: <b>{condition}</b>\n"
        message_text += f"💨 Скорость ветра: <b>{wind_speed} м/c</b>\n\n"
        
        keyboard = InlineKeyboardMarkup()
        if await is_favorite(callback_query.from_user.id, camera.get("channel")):
            keyboard.add(InlineKeyboardButton("📺Смотреть трансляцию", url=f'https://apsny.camera/?{camera.get("channel")}'))
            keyboard.add(InlineKeyboardButton("🗑Удалить из избранного", callback_data=f"remove_from_favorites_{channel_name}")) # Изменено на channel_name
        else:
            keyboard.add(InlineKeyboardButton("📺Смотреть трансляцию", url=f'https://apsny.camera/?{camera.get("channel")}'))
            keyboard.add(InlineKeyboardButton("⭐ В избранное", callback_data=f"add_to_favorites_{channel_name}")) # Изменено на channel_name
        keyboard.add(InlineKeyboardButton("🗑Удалить", callback_data="button_delete_message"))

        await bot.send_photo(callback_query.from_user.id, image_url, caption=message_text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await bot.answer_callback_query(callback_query.id, "Произошла ошибка при получении камеры")

@dp.callback_query_handler(lambda c: c.data.startswith('remove_from_favorites_'))
async def remove_from_favorites(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    channel_name = callback_query.data.replace('remove_from_favorites_', '')
    
    cursor.execute("SELECT cams FROM favorites WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        favorites = json.loads(row[0])
        if channel_name in favorites:
            favorites.remove(channel_name)
            cursor.execute("REPLACE INTO favorites (user_id, cams) VALUES (?, ?)", (user_id, json.dumps(favorites)))
            connection.commit()
            await bot.answer_callback_query(callback_query.id, "Камера удалена из избранного")
            return

    await bot.answer_callback_query(callback_query.id, "Камера не найдена в избранном")


@dp.callback_query_handler(lambda c: c.data.startswith('add_to_favorites_'))
async def add_to_favorites(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    channel_name = callback_query.data.replace('add_to_favorites_', '') 
    
    cursor.execute("SELECT cams FROM favorites WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        favorites = json.loads(row[0])
    else:
        favorites = []

    if len(favorites) >= 9: # Ограничения, больше 9 камер нельзя.
        await bot.answer_callback_query(callback_query.id, "Вы достигли максимального количества избранных камер (9)")
        return

    favorites.append(channel_name)

    cursor.execute("REPLACE INTO favorites (user_id, cams) VALUES (?, ?)", (user_id, json.dumps(favorites)))
    connection.commit()

    await bot.answer_callback_query(callback_query.id, "Камера добавлена в избранное")


@dp.callback_query_handler(lambda c: c.data == 'get_favorites')
async def get_favorites(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT cams FROM favorites WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        favorites = json.loads(row[0])
        if favorites:
            message_text = "Ваши избранные камеры:"
            keyboard = InlineKeyboardMarkup()
            for favorite in favorites:
                keyboard.add(InlineKeyboardButton(favorite, callback_data=f'camera_{favorite}'))
        else:
            message_text = "Ваши избранные камеры пусты."
            keyboard = None
    else:
        message_text = "У вас пока нет избранных камер."
        keyboard = None

    await bot.send_message(callback_query.from_user.id, message_text, reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id) 

@dp.callback_query_handler(lambda c: c.data == 'profile')
async def profile(callback_query: types.CallbackQuery):    
    user_id = callback_query.from_user.id
    
    profile_data = await fetch_profile(cursor, user_id)
    if profile_data['response']['status']:
        data = profile_data['response']['data']
        balance = data['balance']
        account_number = data['id']
        last_payment_date = data['last_pay']
        tariff = data['tariff']
        state = data['state']
        last_pay = data['last_pay']
        is_locked = data['is_locked']

        if is_locked:
            is_lock_desc = 'Не заблокирован'
        else:
            is_lock_desc = 'Заблокирован'

        profile_text = f"🙋🏻‍♂️ Твой ID: [<code>{user_id}</code>]\n" \
                    f"💰 Баланс: <b>{balance}</b>\n" \
                    f"📜 Лицевой счет: <b>{account_number}</b>\n" \
                    f"💣 Статус блокировк: <b>{is_lock_desc}</b>\n" \
                    f"📅 Дата последнего платежа: <b>{last_payment_date}</b>\n" \
                    f"💳 Последнее пополнение: <b>{last_pay}</b>\n" \
                    f"🔍 Состояние: <b>{state}</b>\n" \
                    f"📶 Тариф: <b>{tariff}</b>\n"
    else:
        error_description = profile_data['response']['message']
        if error_description == 'Выполнен вход на другом устройстве':
            error_description += '\n\nВыполните команду для переавторизации:\n/re_auth'
            
        profile_text = "Произошла ошибка при получении данных о профиле:" \
                       f"<b>{error_description}</b>\n"

    buy_balance = InlineKeyboardButton("💰 Пополнить баланс", callback_data='subscribe_buy')      
    payment_history = InlineKeyboardButton("📅 История платежей", callback_data='payment_history')           
    change_password = InlineKeyboardButton("🔑 Сменить пароль", callback_data='change_password') 
    promised_payment = InlineKeyboardButton("📅 Обещанный платёж", callback_data='promised_payment')
    lock_lk = InlineKeyboardButton("💣 Блокировка ЛК", callback_data='lock_lk')
    back_button = InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')

    keyboard = InlineKeyboardMarkup().row(buy_balance, payment_history).row(change_password, lock_lk).add(promised_payment, back_button)

    await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                text=profile_text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'lock_lk')
async def lock_lk(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if user_data:
        rs = await fetch_profile(cursor, user_id)
        if rs['response']['data']['is_locked']:
            is_lock = 0
            is_lock_desc = 'Заблокирован'
        else:
            is_lock = 1
            is_lock_desc = 'Не заблокирован'
            
        status = await lock_lk_rs(id, user_data[1], is_lock)

        if status:
            await bot.send_message(user_id, f"Статус блокировки: {is_lock_desc}")
            await bot.answer_callback_query(callback_query.id, "Обещанный платёж успешно активирован")
        else:
            await bot.answer_callback_query(callback_query.id, "Обещанный платёж не был активирован")
    else:
        await bot.answer_callback_query(callback_query.id, "Ваш профиль не определён")

@dp.callback_query_handler(lambda c: c.data == 'change_password')
async def change_password_callback(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите новый пароль:")
    await ChangePasswordState.first()

@dp.message_handler(state=ChangePasswordState.waiting_for_new_password)
async def process_new_password(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()

    async with state.proxy() as data:
        data['new_password'] = message.text

        data['id'] = user_data[0]
        data['token'] = user_data[1]

    rs = await change_password(user_data[0], user_data[1])
    if rs['response']['status']:
        await message.answer(f"Введите SMS-код, который был отправлен на номер телефона +{rs['response']['phone']}:")
        await ChangePasswordState.next()
    else:
        await message.answer(f"Не удалось отправить SMS-код.\n{rs['response']['message']}")
        await state.finish()


@dp.message_handler(state=ChangePasswordState.waiting_for_sms_code)
async def process_sms_code(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    code = message.text
    async with state.proxy() as data:
        id = data['id']
        token = data['token']
        new_password = data['new_password']

        result = await change_password_confim(id, new_password, token, code)

        cursor.execute("UPDATE users SET password = ? WHERE user_id = ?", (new_password, user_id))
        connection.commit()
        
        if result:
            await message.answer("Пароль успешно изменён.")
        else:
            await message.answer("Ошибка при изменении пароля. Пожалуйста, попробуйте ещё раз.")

    await state.finish()


@dp.callback_query_handler(lambda c: c.data == 'payment_history')
async def payment_history(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        status = await pay_list(user_data[0], user_data[1])
        if status and status.get("response", {}).get("status"):
            payment_list = status["response"]["data"]
            await show_payment_list(callback_query.message, payment_list, 1)
        else:
            await bot.answer_callback_query(callback_query.id, "Ошибка при получении истории платежей")
    else:
        await bot.answer_callback_query(callback_query.id, "Ваш профиль не определен")

async def show_payment_list(message, payment_list, page):
    if not payment_list:
        await message.answer("История платежей пуста.")
        return

    items_per_page = 5
    total_pages = (len(payment_list) + items_per_page - 1) // items_per_page

    start_index = (page - 1) * items_per_page
    end_index = min(start_index + items_per_page, len(payment_list))

    message_text = f"<b>Страница: {page}/{total_pages}</b>\n\n"

    for payment in payment_list[start_index:end_index]:
        description = payment.get("v_description", "Неизвестный тип")
        amount = payment.get("v_sum", "Неизвестная сумма")
        message_text += f"<b>Тип:</b> {description}\n<b>Сумма:</b> {amount}\n\n"

    keyboard = InlineKeyboardMarkup(row_width=3)
    if page > 1:
        keyboard.insert(InlineKeyboardButton("⬅️ Назад", callback_data=f"payment_page_{page - 1}"))
    if end_index < len(payment_list):
        keyboard.insert(InlineKeyboardButton("➡️ Вперёд", callback_data=f"payment_page_{page + 1}"))
    keyboard.row()  
    keyboard.insert(InlineKeyboardButton("Скачать в формате JSON", callback_data=f"download_payment_list"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='back_to_start'))

    try:
        await message.edit_text(text=message_text, parse_mode="HTML", reply_markup=keyboard)
    except aiogram.utils.exceptions.MessageNotModified:
        pass
    except aiogram.utils.exceptions.MessageCantBeEdited:
        await message.answer(message_text, parse_mode="HTML", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith('payment_page_'))
async def handle_payment_pagination(callback_query: types.CallbackQuery):
    page = int(callback_query.data.split('_')[2])

    user_id = callback_query.from_user.id
    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        status = await pay_list(user_data[0], user_data[1])
        if status and status.get("response", {}).get("status"):
            payment_list = status["response"]["data"]
            await show_payment_list(callback_query.message, payment_list, page)
        else:
            await bot.answer_callback_query(callback_query.id, "Ошибка при получении истории платежей")
    else:
        await bot.answer_callback_query(callback_query.id, "Ваш профиль не определён")

@dp.callback_query_handler(lambda c: c.data == 'download_payment_list')
async def download_payment_list(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        status = await pay_list(user_data[0], user_data[1])
        if status and status.get("response", {}).get("status"):
            payment_list = status["response"]["data"]
            json_data = json.dumps(payment_list, ensure_ascii=False, indent=2)

            document = io.BytesIO(json_data.encode())
            document.name = 'pay_list.json' 

            await bot.send_document(callback_query.from_user.id, document, caption='Ваша история платежей')
        else:
            await bot.answer_callback_query(callback_query.id, "Ошибка при получении истории платежей")
    else:
        await bot.answer_callback_query(callback_query.id, "Ваш профиль не определен")

@dp.callback_query_handler(lambda c: c.data == 'promised_payment')
async def activate_promised_payment(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        status = await promised_payment(user_data[0], user_data[1])

        if status:
            await bot.send_message(user_id, "Обещанный платёж успешно активирован")
            await bot.answer_callback_query(callback_query.id, "Обещанный платёж успешно активирован")
        else:
            await bot.answer_callback_query(callback_query.id, "Обещанный платёж не был активирован")
    else:
        await bot.answer_callback_query(callback_query.id, "Ваш профиль не определён")

@dp.callback_query_handler(lambda c: c.data == 'subscribe_buy')
async def subscribe_buy(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    await bot.send_message(user_id, "Введите сумму для пополнения баланса:")
    await SubscribeBuy.waiting_for_amount.set()

@dp.message_handler(state=SubscribeBuy.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    amount = int(message.text)
    user_id = message.from_user.id

    if amount >= 25000:
        await message.reply("Введите сумму меньше 25000")
    else:
        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            id = user_data[0]
            pay_link = await generate_pay_link(id, amount)

            text = f"Ваша ссылка для пополнения лицевого счёта:" \
                f"\n\n{pay_link}\n\n" \
                f"Ссылка работает: <b>10 минут</b>\n" \
                f"Сумма пополнения: <b>{amount}</b>" \
                f"\n\n⚠️Ваш баланс автоматически пополнится после оплаты."
            
            await message.reply(text, parse_mode="HTML")
        else:
            await message.reply("Пользователь не найден в базе данных.")

    await state.finish()
    
@dp.callback_query_handler(lambda c: c.data == 'back_to_start')
async def back_to_start(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    main_menu = kb.generate_main_menu(is_admin=result[0])
    await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                text="<b>👋 Добро пожаловать в систему.</b>\n\nЗакрытый репозиторий для разработчиков бота: https://github.com/reques6e/TgBotSystemaLtd/",
                                parse_mode="HTML", reply_markup=main_menu)
    
@dp.callback_query_handler(lambda c: c.data == 'admin_panel')
async def admin_panel(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user = callback_query.from_user

    admin_markup = generate_admin_keyboard()

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"🌟<b>Приветствую</b> <a href='tg://user?id={user_id}'>// {user.username}</a><b>, в админ-панели!</b>",
        parse_mode='HTML',
        reply_markup=admin_markup
    )

@dp.callback_query_handler(lambda c: c.data == 'grant_access')
async def grant_access_callback(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)

    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result and result[0]: 
        await bot.send_message(user_id,
                               "<b>Введите ID пользователя, которому вы хотите предоставить доступ админа</b>",
                               parse_mode='HTML')
        await SomeState.waiting_for_user_id.set()
    else:
        await bot.send_message(user_id, "У вас нет прав на выдачу администраторских прав.")

@dp.callback_query_handler(lambda c: c.data == 'send_personal_message')
async def send_personal_message(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    cancel_button = InlineKeyboardButton("Отменить действие", callback_data='cancel')
    keyboard.row(cancel_button)

    await bot.send_message(callback_query.from_user.id,
                           "<b>Введите ID пользователя, которому хотите отправить личное сообщение:</b>",
                           parse_mode='HTML',
                           reply_markup=keyboard)
    await SomeState.waiting_for_personal_message_id.set()

@dp.message_handler(state=SomeState.waiting_for_personal_message_id)
async def process_personal_message_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)

        await state.update_data(user_id=user_id)
        await bot.send_message(message.chat.id,
                                "Введите сообщение, которое хотите отправить этому пользователю:")
        await SomeState.waiting_for_personal_message_text.set()

    except ValueError:
        await message.reply("Ошибка. Введите корректный ID пользователя.")

@dp.message_handler(state=SomeState.waiting_for_personal_message_text)
async def process_personal_message_text(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        user_id = data.get('user_id')
        personal_message = message.text

        delete_button = types.InlineKeyboardButton("🗑Удалить", callback_data='button_delete_message')
        delete_message = types.InlineKeyboardMarkup().add(delete_button)
        await bot.send_message(
            user_id,
            personal_message,
            parse_mode='HTML',
            reply_markup=delete_message
        )
        await bot.send_message(
            message.chat.id,
            f"Личное сообщение было успешно отправлено пользователю с ID <code>{user_id}</code>.",
            parse_mode='HTML',
            reply_markup=generate_admin_keyboard()
        )
    except Exception as e:
        await message.reply("Произошла ошибка при отправке сообщения. Попробуйте еще раз.")
    finally:
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'revoke_access')
async def revoke_access_from_user(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id,
                           "<b>Введите ID пользователя, у которого нужно отозвать доступ:</b>",
                           parse_mode='HTML')
    await SomeState.waiting_to_revoke.set()

@dp.message_handler(state=SomeState.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)

        cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            if user_id == message.from_user.id:
                await bot.send_message(user_id, "Вы не можете выдать админа самому себе")
            elif result[0]:
                await bot.send_message(user_id, "Пользователь уже является администратором")
            else:
                cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
                connection.commit()
                
                await bot.send_message(
                    message.chat.id,
                    f"Пользователь с ID <code>{user_id}</code> получил доступ к админ панели.",
                    parse_mode='HTML',
                    reply_markup=generate_admin_keyboard()
                )
        else:
            await message.reply("Пользователь с таким ID не найден в базе данных.")
    except ValueError:
        await message.reply("Ошибка. Введите корректный ID пользователя.")
    finally:
        await state.finish()
        
@dp.message_handler(state=SomeState.waiting_to_revoke)
async def process_revoke_access(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)

        cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            if not result[0]:
                await bot.send_message(user_id, "Пользователь не является администратором")
            else:
                cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
                connection.commit()

                await bot.send_message(
                    message.chat.id,
                    f"У пользователя с ID <code>{user_id}</code> отозвали доступ к админ панели.",
                    parse_mode='HTML',
                    reply_markup=generate_admin_keyboard()
                )
        else:
            await message.reply("Пользователь с таким ID не найден в базе данных.")
    except ValueError:
        await message.reply("Ошибка. Введите корректный ID пользователя.")
    finally:
        await state.finish()
        
@dp.message_handler()
async def handle_messages(message: types.Message):
    try:
        await message.delete()
        await message.answer("К сожалению, я не смог распознать Вашу команду.")
    except Exception as e:
        await message.answer("К сожалению, я не смог распознать Вашу команду.")
        
@dp.callback_query_handler(lambda c: c.data == 'delete_info_message')
async def delete_info_message(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    await bot.delete_message(chat_id, message_id=message_id)    

@dp.callback_query_handler(lambda c: c.data == 'button_delete_message')
async def button_delete_message(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    await bot.delete_message(chat_id, message_id=message_id) 

@dp.callback_query_handler(lambda c: c.data == 'mailing')
async def mailing_text(callback_query: types.CallbackQuery, state: FSMContext):
    msg = await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                      message_id=callback_query.message.message_id,
                                      text="<i>Введите текст для рассылки или отправьте изображение</i>",
                                      parse_mode="HTML")
    await state.set_state(MailingState.waiting_for_content)
    await state.update_data(message_id=msg.message_id)

@dp.message_handler(state=MailingState.waiting_for_content, content_types=['text', 'photo'])
async def process_content_input(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()

    if user_data and user_data[4] == 1: 
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        await message.answer("Начинаю рассылку...")

        for user in users:
            try:
                await message.copy_to(user[0])
            except ChatNotFound:
                pass

        await message.answer('Рассылка закончена.')
    else:
        await message.answer('У вас нет прав.')

    await state.finish()
