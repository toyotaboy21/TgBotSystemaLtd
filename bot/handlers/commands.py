import aiogram
import pandas as pd
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
from bot.utils import pay_list, fetch_profile, auth_profile, generate_pay_link, promised_payment, get_camera, get_locations, get_stream_info, change_password, change_password_confim, lock_lk_rs, upload_cdn
from bot.keyboards.keyboard_admin import generate_admin_keyboard
from bot.keyboards import keyboard as kb
from bot.dictionaries.dictionary import Texts
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
                text=Texts.notification_registration_text.format(user_id),
                parse_mode='HTML',
                reply_markup=delete_message
            )
        except:
            pass

        await message.answer(Texts.welcome_registration_text.format(user=message.from_user.first_name))
        await Registration.waiting_for_token.set()
    else:
        await message.reply(Texts.welcome_registered_text.format(user=message.from_user.first_name), parse_mode="HTML", reply_markup=kb.generate_main_menu(is_admin=result[1]))

@dp.message_handler(commands=['del_data'])
async def del_data(message: types.Message):
    user_id = str(message.from_user.id)

    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    connection.commit()

    cursor.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
    connection.commit()
    
    await message.reply(Texts.delete_user_data_text.format(user_id=user_id))

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

            await message.answer(Texts.re_auth_true_text)
        else:
            await message.answer("Не удалось выполнить переавторизацию.")
    else:
        await message.answer("Профиль не найден в базе данных.")

    await state.finish()

@dp.message_handler(state=Registration.waiting_for_token)
async def process_token_input(message: types.Message, state: FSMContext):
    id = message.text
    await state.update_data(id=id)
    await message.answer(Texts.send_me_your_password_text)
    await Registration.next()

@dp.message_handler(state=Registration.waiting_for_id)
async def process_id_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    id = data.get("id")
    password = message.text

    await message.delete()

    rs = await auth_profile(id, password)
    if rs['response']['status']:
        cursor.execute('INSERT INTO users (user_id, token, id, password, is_admin) VALUES (?, ?, ?, ?, ?)', (user_id, rs['response']['token'], id, password, 0))
        connection.commit()

        try:
            cursor.execute('INSERT INTO favorites (user_id, cams) VALUES (?, ?)', (user_id, '[]'))
            connection.commit()
        except sqlite3.IntegrityError:
            pass

        await bot.send_message(message.chat.id, Texts.welcome_registered_text.format(user=message.from_user.first_name),
            parse_mode="HTML", reply_markup=kb.generate_main_menu(is_admin=False))
        await state.finish()
    else:
        await bot.send_message(message.chat.id, Texts.password_or_login_error_text)
    
@dp.callback_query_handler(lambda c: c.data.startswith('delete_message_'))
async def delete_message(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id

    await bot.delete_message(chat_id, message_id=callback_query.message.message_id)
    await bot.answer_callback_query(callback_query.id, text=Texts.message_delete_text, show_alert=True)
    
@dp.callback_query_handler(lambda c: c.data == 'info')
async def process_callback_button(callback_query: types.CallbackQuery):
    keyboard = kb.generate_keyboard_info()

    back_to_start_button = InlineKeyboardButton("⤶ Назад", callback_data='back_to_start')
    keyboard.add(back_to_start_button)

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=Texts.take_action,
        parse_mode='HTML',
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'delete_menu')
async def delete_menu(callback_query: types.CallbackQuery):
    await bot.delete_message(callback_query.message.chat.id, callback_query.message.message_id)
    await bot.answer_callback_query(callback_query.id, text=Texts.menu_delete_text, show_alert=True)

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
    await callback_query.answer(Texts.menu_delete_notification_text, show_alert=True)

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
            text=Texts.select_location_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await bot.answer_callback_query(callback_query.id, text=Texts.select_location_false_text)

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
                        
            if callback_query.message:
                try:
                    await bot.edit_message_text(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        text=Texts.select_camera_text,
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
                    text=Texts.select_camera_text,
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
        await bot.answer_callback_query(callback_query.id, Texts.all_cameras_displayed_false_text)

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
        token = camera.get('token')
        channel = camera.get('cam')['camera_name']
        description = camera.get('cam')['camera_text']
        weather = camera.get('weather', {}).get('fact', {})
        temperature = weather.get('temp')
        condition = weather.get('condition')
        wind_speed = weather.get('wind_speed')
        
        description = re.sub(r'<\s*p\s*>', '', description)
        description = re.sub(r'</\s*p\s*>', '', description)

        if condition in Texts.weather_conditions_text:
            condition = Texts.weather_conditions_text[condition]

        if len(description) > 430:
            description = description[:430-3] + '...'
        
        keyboard = InlineKeyboardMarkup()
        if await is_favorite(callback_query.from_user.id, camera.get("channel")):
            keyboard.add(InlineKeyboardButton("📺Смотреть трансляцию", url=f'https://apsny.camera/?{camera.get("channel")}'))
            keyboard.add(InlineKeyboardButton("🗑Удалить из избранного", callback_data=f"remove_from_favorites_{channel_name}")) # Изменено на channel_name
        else:
            keyboard.add(InlineKeyboardButton("📺Смотреть трансляцию", url=f'https://apsny.camera/?{camera.get("channel")}'))
            keyboard.add(InlineKeyboardButton("⭐ В избранное", callback_data=f"add_to_favorites_{channel_name}")) # Изменено на channel_name
        keyboard.add(InlineKeyboardButton("🗑Удалить", callback_data="button_delete_message"))

        await bot.send_photo(callback_query.from_user.id, f'{image_url}?token={token}', caption=Texts.camera_info_text.format(channel=channel, description=description, temperature=temperature, condition=condition, wind_speed=wind_speed), parse_mode="HTML", reply_markup=keyboard)
    else:
        await bot.answer_callback_query(callback_query.id, text=Texts.get_camera_error_text)

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
            await bot.answer_callback_query(callback_query.id, Texts.camera_remove_from_favorites_text)
            return

    await bot.answer_callback_query(callback_query.id, text=Texts.camera_remove_from_favorites_false_text)


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

    if len(favorites) >= 9: # Ограничение, больше 9 камер нельзя.
        await bot.answer_callback_query(callback_query.id, Texts.add_to_favorites_error_text)
        return

    favorites.append(channel_name)

    cursor.execute("REPLACE INTO favorites (user_id, cams) VALUES (?, ?)", (user_id, json.dumps(favorites)))
    connection.commit()

    await bot.answer_callback_query(callback_query.id, text=Texts.add_to_favorites_text)


@dp.callback_query_handler(lambda c: c.data == 'get_favorites')
async def get_favorites(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT cams FROM favorites WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        favorites = json.loads(row[0])
        if favorites:
            message_text = Texts.your_favorite_cameras_text
            keyboard = InlineKeyboardMarkup()
            for favorite in favorites:
                keyboard.add(InlineKeyboardButton(favorite, callback_data=f'camera_{favorite}'))
        else:
            message_text = Texts.your_favorite_cameras_false_text
            keyboard = None
    else:
        message_text = Texts.favorite_cameras_none_text
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
            is_lock_desc = 'Заблокирован'
        else:
            is_lock_desc = 'Не заблокирован'
        
        buy_balance = InlineKeyboardButton("💰 Пополнить баланс", callback_data='subscribe_buy')      
        payment_history = InlineKeyboardButton("📅 История платежей", callback_data='payment_history')           
        change_password = InlineKeyboardButton("🔑 Сменить пароль", callback_data='change_password') 
        promised_payment = InlineKeyboardButton("📅 Обещанный платёж", callback_data='promised_payment')
        lock_lk = InlineKeyboardButton("💣 Блокировка ЛК", callback_data='lock_lk')
        back_button = InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')

        keyboard = InlineKeyboardMarkup().row(buy_balance, payment_history).row(change_password, lock_lk).add(promised_payment, back_button)

        profile_text = Texts.profile_info_text.format(user_id=user_id, balance=balance, account_number=account_number, is_lock_desc=is_lock_desc, last_payment_date=last_payment_date, last_pay=last_pay, state=state, tariff=tariff)
    else:
        error_description = profile_data['response']['message']
        if error_description == 'Выполнен вход на другом устройстве':
            error_description += '\n\nВыполните команду для переавторизации:\n/re_auth'
            
        profile_text = Texts.profile_info_false_text.format(error_description=error_description)

        keyboard = None

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
        else:
            is_lock = 1
            
        status = await lock_lk_rs(id, user_data[1], is_lock)

        if status:
            await bot.send_message(user_id, text=Texts.status_blocking_edited_text)
        else:
            await bot.answer_callback_query(callback_query.id, "Error")
    else:
        await bot.answer_callback_query(callback_query.id, text=Texts.profile_not_found_text)

@dp.callback_query_handler(lambda c: c.data == 'change_password')
async def change_password_callback(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, text=Texts.send_me_new_password_text)
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
        await message.answer(text=Texts.get_sms_code_text)
        await ChangePasswordState.next()
    else:
        await message.answer(text=Texts.get_sms_code_false_text)
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
            await message.answer(text=Texts.password_edited_text)
        else:
            await message.answer(text=Texts.password_edited_false_text)

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
            await bot.answer_callback_query(callback_query.id, text=Texts.payment_history_false_text)
    else:
        await bot.answer_callback_query(callback_query.id, text=Texts.re_auth_user_not_in_database_text)

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
    keyboard.insert(InlineKeyboardButton("Скачать в формате XLSX", callback_data=f"download_payment_list"))
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
            await bot.answer_callback_query(callback_query.id, text=Texts.payment_history_false_text)
    else:
        await bot.answer_callback_query(callback_query.id, text=Texts.profile_not_found_text)

@dp.callback_query_handler(lambda c: c.data == 'download_payment_list')
async def download_payment_list(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        status = await pay_list(user_data[0], user_data[1])
        if status and status.get("response", {}).get("status"):
            payment_list = status["response"]["data"]

            df = pd.DataFrame(payment_list)

            df = df.filter(['v_description', 'dt_oper', 'v_sum'])
            df.rename(columns={
                'v_description': 'Цель',
                'dt_oper': 'Дата операции',
                'v_sum': 'Сумма'
            }, inplace=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            output.seek(0)

            upload_document = io.BytesIO(output.getvalue())
            upload_document.name = 'pay_list.xlsx'
            
            link = await upload_cdn(upload_document)  
            if link:
                await bot.send_document(callback_query.from_user.id, (f'История платежей абонента {user_data[0]}.xlsx', output), caption=Texts.your_payment_history_text.format(link=link))
            else:
                await bot.answer_callback_query(callback_query.id, text=Texts.upload_file_to_cdn_error_text)
                await bot.send_document(callback_query.from_user.id, (f'История платежей абонента {user_data[0]}.xlsx', output), caption=Texts.your_payment_history_no_cdn_text)
        else:
            await bot.answer_callback_query(callback_query.id, text=Texts.payment_history_false_text)
    else:
        await bot.answer_callback_query(callback_query.id, text=Texts.re_auth_user_not_in_database_text)

@dp.callback_query_handler(lambda c: c.data == 'promised_payment')
async def activate_promised_payment(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        status = await promised_payment(user_data[0], user_data[1])

        if status:
            await bot.send_message(user_id, text=Texts.activate_promised_payment_text)
            await bot.answer_callback_query(callback_query.id, text=Texts.activate_promised_payment_text)
        else:
            await bot.answer_callback_query(callback_query.id, text=Texts.activate_promised_payment_false_text)
    else:
        await bot.answer_callback_query(callback_query.id, text=Texts.re_auth_user_not_in_database_text)

@dp.callback_query_handler(lambda c: c.data == 'subscribe_buy')
async def subscribe_buy(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    await bot.send_message(user_id, text=Texts.subscribe_buy_text)
    await SubscribeBuy.waiting_for_amount.set()

@dp.message_handler(state=SubscribeBuy.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    amount = int(message.text)
    user_id = message.from_user.id

    if amount >= 25000:
        await message.reply(text=Texts.process_amount_limit_text)
    else:
        cursor.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            id = user_data[0]
            pay_link = await generate_pay_link(id, amount)
            
            await message.reply(text=Texts.process_amount_text.format(pay_link=pay_link, amount=amount), parse_mode="HTML")
        else:
            await message.reply(text=Texts.re_auth_user_not_in_database_text)

    await state.finish()
    
@dp.callback_query_handler(lambda c: c.data == 'back_to_start')
async def back_to_start(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    main_menu = kb.generate_main_menu(is_admin=result[0])
    await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                text=Texts.welcome_registered_text.format(user=callback_query.from_user.first_name),
                                parse_mode="HTML", reply_markup=main_menu)
    
@dp.callback_query_handler(lambda c: c.data == 'admin_panel')
async def admin_panel(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user = callback_query.from_user

    admin_markup = generate_admin_keyboard()

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=Texts.welcome_to_admin_panel_text.format(user_id=user_id, user_name=user.username),
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
                               text=Texts.grant_access_text,
                               parse_mode='HTML')
        await SomeState.waiting_for_user_id.set()
    else:
        await bot.send_message(user_id, text=Texts.grant_access_false_text)

@dp.callback_query_handler(lambda c: c.data == 'send_personal_message')
async def send_personal_message(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    cancel_button = InlineKeyboardButton("Отменить действие", callback_data='cancel')
    keyboard.row(cancel_button)

    await bot.send_message(callback_query.from_user.id,
                           text=Texts.send_personal_text,
                           parse_mode='HTML',
                           reply_markup=keyboard)
    await SomeState.waiting_for_personal_message_id.set()

@dp.message_handler(state=SomeState.waiting_for_personal_message_id)
async def process_personal_message_id(message: types.Message, state: FSMContext):
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
    result = cursor.fetchone()

    if result[0] == 1:
        try:
            await state.update_data(user_id=int(message.text))
            await bot.send_message(message.chat.id, text=Texts.process_personal_text)
            await SomeState.waiting_for_personal_message_text.set()
        except ValueError:
            await message.reply(text=Texts.user_id_not_found)
    else:
        await bot.send_message(message.chat.id, text=Texts.process_content_input_false_text)

@dp.message_handler(state=SomeState.waiting_for_personal_message_text)
async def process_personal_message_text(message: types.Message, state: FSMContext):
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
    result = cursor.fetchone()

    if result[0] == 1:
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
                text=Texts.send_personal_true_text.format(user_id=user_id),
                parse_mode='HTML',
                reply_markup=generate_admin_keyboard()
            )
        except Exception as e:
            await message.reply(text=Texts.send_personal_false_text)
        finally:
            await state.finish()
    else:
        await bot.send_message(message.chat.id, text=Texts.process_content_input_false_text)

@dp.callback_query_handler(lambda c: c.data == 'revoke_access')
async def revoke_access_from_user(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id,
                           text=Texts.revoke_access_text,
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
                await bot.send_message(user_id, text=Texts.grant_access_me_text)
            elif result[0]:
                await bot.send_message(user_id, text=Texts.grant_access_is_admin_text)
            else:
                cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
                result = cursor.fetchone()

                if result[0] == 1:
                    cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
                    connection.commit()
                    
                    await bot.send_message(
                        message.chat.id,
                        text=Texts.grant_access_true_text.format(user_id=user_id),
                        parse_mode='HTML',
                        reply_markup=generate_admin_keyboard()
                    )
                else:
                    await bot.send_message(message.chat.id, text=Texts.process_content_input_false_text)
        else:
            await message.reply(text=Texts.re_auth_user_not_in_database_text)
    except ValueError:
        await message.reply(text=Texts.user_id_not_found)
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
                await bot.send_message(user_id, text=Texts.revoke_access_false_text)
            else:
                cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
                result = cursor.fetchone()

                if result[0] == 1:
                    cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
                    connection.commit()

                    await bot.send_message(
                        message.chat.id,
                        text=Texts.revoke_access_true_text.format(user_id=user_id),
                        parse_mode='HTML',
                        reply_markup=generate_admin_keyboard()
                    )
                else:
                    await bot.send_message(message.chat.id, text=Texts.process_content_input_false_text)
        else:
            await message.reply(text=Texts.re_auth_user_not_in_database_text)
    except ValueError:
        await message.reply(text=Texts.user_id_not_found)
    finally:
        await state.finish()
        
@dp.message_handler()
async def handle_messages(message: types.Message):
    await message.answer(text=Texts.command_not_found_text)
        
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
                                      text=Texts.mailing_text,
                                      parse_mode="HTML")
    await state.set_state(MailingState.waiting_for_content)
    await state.update_data(message_id=msg.message_id)

@dp.message_handler(state=MailingState.waiting_for_content, content_types=['text', 'photo'])
async def process_content_input(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)

    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
    result = cursor.fetchone()

    if result[0] == 1:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()

        if user_data and user_data[4] == 1: 
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()

            await message.answer(text=Texts.process_content_input_text)

            for user in users:
                try:
                    await message.copy_to(user[0])
                except ChatNotFound:
                    pass

            await message.answer(text=Texts.process_content_input_true_text)
        else:
            await message.answer(text=Texts.process_content_input_false_text)

        await state.finish()
    else:
        await bot.send_message(message.chat.id, text=Texts.process_content_input_false_text)
