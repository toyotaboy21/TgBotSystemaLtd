import aiogram
import io
import json
import time
import asyncio
import sqlite3

from aiogram import types
from aiogram.utils.exceptions import ChatNotFound
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from bot.bot import dp, bot
from bot.utils import pay_list, fetch_profile, auth_profile, generate_pay_link, promised_payment
from bot.keyboards.keyboard_admin import generate_admin_keyboard
from bot.keyboards import keyboard as kb
from bot.states.state import SomeState, MailingState, Registration, SubscribeBuy


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

    print('Бот запущен!')

@dp.message_handler(commands=['start'], state="*")
async def start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)

    cursor.execute("SELECT user_id, is_admin FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result:
        await message.answer("Добро пожаловать! Для начала работы введите ваш ID:")
        await Registration.waiting_for_token.set()
    else:
        is_admin = result
        welcome_message = f"👋 {message.from_user.first_name}, <b>добро пожаловать в Систему</b>"
        await message.reply(welcome_message, parse_mode="HTML", reply_markup=kb.generate_main_menu(is_admin))

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

        await message.reply(f"👋 {message.from_user.first_name}, <b>добро пожаловать в Систему</b>",
                            parse_mode="HTML", reply_markup=kb.generate_main_menu(user_id))
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

        profile_text = f"🙋🏻‍♂️ Твой ID: [<code>{user_id}</code>]\n" \
                    f"💰 Баланс: <b>{balance}</b>\n" \
                    f"📜 Лицевой счет: <b>{account_number}</b>\n" \
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
    back_button = InlineKeyboardButton("🔙 Назад", callback_data='back_to_start')
    promised_payment = InlineKeyboardButton("📅 Обещанный платёж", callback_data='promised_payment')

    keyboard = InlineKeyboardMarkup().row(buy_balance, payment_history).row(change_password, back_button).add(promised_payment)

    await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                text=profile_text, parse_mode="HTML", reply_markup=keyboard)

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

    await bot.send_message(user_id, "Введите сумму для пополнения платежа:")
    await SubscribeBuy.waiting_for_amount.set()

@dp.message_handler(state=SubscribeBuy.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    amount = message.text
    user_id = message.from_user.id

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
    main_menu = kb.generate_main_menu(user_id)
    await bot.edit_message_text(chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                text="<b>👋 Добро пожаловать в систему.</b>",
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

                await bot.send_message(user_id, "🥳")
                await asyncio.sleep(1)
                await bot.send_message(user_id, "Вам был предоставлен доступ к админ панели.")
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

        delete_button = types.InlineKeyboardButton("🗑Удалить", callback_data='delete_admin_menu')
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

@dp.message_handler(state=SomeState.waiting_to_revoke)
async def process_revoke_access(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        db = '123'

        if str(user_id) in db:
            if user_id == str(message.from_user.id):
                await bot.send_message(user_id, "Вы не можете отозвать админа у себя.")
            if db[str(user_id)]["is_admin"] == False:
                await bot.send_message(user_id, "Пользователь не являлся администратором")
                return 
            else:
                db[str(user_id)]["is_admin"] = False
                
                try:
                    await bot.send_message(user_id, "🥳")
                    time.sleep(1)
                    await bot.send_message(user_id, "У вас отозвали доступ к админ панели")
                    await bot.send_message(
                        message.chat.id,
                        f"У пользователя с ID <code>{user_id}</code> отозвали доступ к админ панели.",
                        parse_mode='HTML',
                        reply_markup=generate_admin_keyboard()
                    )
                except ChatNotFound:
                    pass
        else:
            await message.reply("Пользователь с таким ID не найден в базе данных.")
    except ValueError:
        await message.reply("Ошибка. Введите корректный ID пользователя.")
    finally:
        await state.finish()

@dp.message_handler()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id

    try:
        await bot.delete_message(message.chat.id, message.message_id)
        await bot.send_sticker(message.chat.id, 'CAACAgIAAxkBAAJc5GVXHyKMoj-oSZYYNhrirj9egu_DAAIoAwACtXHaBpB6SodelUpuMwQ')
    except Exception as e:
        await message.reply(f"<b>⚠️ К сожалению, я не смог распознать Вашу команду.</b>", parse_mode='HTML', reply_markup=kb.keyboard)
        
@dp.callback_query_handler(lambda c: c.data == 'delete_info_message')
async def delete_info_message(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    await bot.delete_message(chat_id, message_id=message_id)    

@dp.callback_query_handler(lambda c: c.data == 'delete_admin_menu')
async def delete_admin_menu(callback_query: types.CallbackQuery):
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
