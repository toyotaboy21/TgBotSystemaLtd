import aiogram
import pandas as pd
import io
import re
import json

from aiogram import types
from aiogram.utils.exceptions import ChatNotFound
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from bot.bot import dp, bot
from bot.keyboards.keyboard_admin import generate_admin_keyboard
from bot.keyboards import keyboard as kb
from bot.dictionaries.dictionary import Texts
from bot.states.state import SomeState, MailingState
from bot.services.db import DataBase

db = DataBase()
    
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

    user = await db.get_user_info(
        user_id=user_id
    )

    if user and user[4]: 
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
    user = await db.get_user_info(
        user_id=message.from_user.id
    )

    if user[4] == 1:
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
    user = await db.get_user_info(
        user_id=message.from_user.id
    )

    if user[4] == 1:
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

        user = await db.get_user_info(
            user_id=user_id
        )

        if user:
            if user_id == message.from_user.id:
                await bot.send_message(user_id, text=Texts.grant_access_me_text)
            elif user[4]:
                await bot.send_message(user_id, text=Texts.grant_access_is_admin_text)
            else:
                user = await db.get_user_info(
                    user_id=message.from_user.id
                )
                
                if user[4] == 1:
                    await db.update_admin(
                        user_id=user_id,
                        admin=1
                    )
                    
                    await bot.send_message(
                        message.chat.id,
                        text=Texts.grant_access_true_text.format(user_id=user_id),
                        parse_mode='HTML'
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

        user = await db.get_user_info(
            user_id=message.from_user.id
        )

        if user:
            if not user[4]:
                await bot.send_message(user_id, text=Texts.revoke_access_false_text)
            else:
                if user[4] == 1:
                    await db.update_admin(
                        user_id=user_id,
                        admin=0
                    )
                    await bot.send_message(
                        message.chat.id,
                        text=Texts.revoke_access_true_text.format(user_id=user_id),
                        parse_mode='HTML'
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

    user = await db.get_user_info(
        user_id=user_id
    )

    if user and user[4] == 1: 
        users = await db.get_all_user_id()

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