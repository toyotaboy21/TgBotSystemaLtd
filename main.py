from aiogram import executor
from bot.bot import dp
from bot.handlers import user
from bot.handlers import admin 

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=user.on_startup_commands, skip_updates=True)