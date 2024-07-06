from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import Config

bot = Bot(token=Config.bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)