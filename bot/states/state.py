from aiogram.dispatcher.filters.state import StatesGroup, State

class SomeState(StatesGroup):
    waiting_to_revoke = State()
    waiting_for_personal_message_text = State()
    waiting_for_personal_message_id = State()
    waiting_for_user_id = State()

class MailingState(StatesGroup):
    waiting_for_content = State()

class Registration(StatesGroup):
    waiting_for_token = State()
    waiting_for_id = State()

class SubscribeBuy(StatesGroup):
    waiting_for_amount = State()

class ChangePasswordState(StatesGroup):
    waiting_for_new_password = State() 
    waiting_for_sms_code = State() 

class Kino(StatesGroup):
    waiting_for_kino_name = State()