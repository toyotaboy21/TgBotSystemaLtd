import aiohttp

from typing import Dict, Any, Union
from datetime import datetime, timedelta


def get_first_day_last_month():
    today = datetime.now()
    first_day_last_month = today.replace(day=1) - timedelta(days=today.day)
    return first_day_last_month.strftime("%Y-%m-%d")

async def fetch_profile(cursor, user_id: int) -> Union[Dict[str, Any], bool]:
    
    """
    Получение информации о профиле

    Если статус код 200 или 401, он возвращает json, если нет, даёт bool False (если происходит ошибка)

    ```json
    {
        "response": {
            "status": true,
            "data": {
                "address": "Гудаутский р-н, г. Гудаута, ул. ?, д. ?",
                "id": "2020202020",
                "tariff": "Домашний 160 (1300 руб./мес.)",
                "contract": "А-20/0000 от 13.12.2013",
                "state": "Услуга оказывается",
                "balance": 4832,
                "price": 1300,
                "alllllwerwe": "0",
                "temp_pay_allowed": false,
                "rec_pay": 0,
                "last_pay": "01.01.2024",
                "last_pay_sum": "1300",
                "fullname": "Медведев Александр Сергеевич",
                "private_cams_status": false,
                "is_locked": false,
                "new_messages": false,
                "password_changed": true,
                "phone": "79409999999"
            }
        }
    }
    ```

    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#получение-информации-о-профиле
    """

    cursor.execute("SELECT id, token FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return False
    
    id = row[0]
    token = row[1]

    url = 'https://api.cyxym.net/app/v1?account'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'token': token}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False
            
async def auth_profile(id: int, password) -> Union[Dict[str, Any], bool]:

    """
    Вход в аккаунт

    Если статус код 200 или 401, он возвращает json, если нет, даёт bool False (если происходит ошибка)

    ```json
    {
        "response": {
            "status": true,
            "auth": true,
            "token": ".....",
            "password_changed": true
        }
    }
    ```

    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#вход-в-личный-кабинет
    """
        
    url = 'https://api.cyxym.net/app/v1?auth'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'password': password}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False

async def generate_pay_link(id: int, amount: float) -> Union[Dict[str, Any], bool]:

    """
    Создание счёта на оплату

    Если статус код 200 или 401, он возвращает json, если нет, даёт bool False (если происходит ошибка)
    ```json
    {
        "response": {
            "id": "2db70ac0-000f-5000-a000-191a8ccff769",
            "status": "pending",
            "recipient": {
                "account_id": "636554",
                "gateway_id": "1619655"
            },
            "amount": {
                "value": "500.20",
                "currency": "RUB"
            },
            "description": "1",
            "payment_method": {
                "type": "bank_card",
                "id": "2db70ac0-000f-5000-a000-191a8ccff769",
                "saved": false
            },
            "created_at": "2024-04-21T11:22:40.680+00:00",
            "confirmation": {
                "enforce": false,
                "return_url": "https://cyxym.net",
                "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=2db70ac0-000f-5000-a000-191a8ccff769",
                "type": "redirect"
            },
            "paid": false,
            "refundable": false,
            "transfers": []
        }
    }
    ```

    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#создание-счёта-на-оплату
    """

    url = 'https://api.cyxym.net/pay/v1?init'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'amount': amount}) as response:
            if response.status == 200 or 401:
                js = await response.json()
                return js['response']['confirmation']['confirmation_url']
            else:
                return False
            
async def promised_payment(id: int, token: str) -> Union[Dict[str, Any], bool]:

    """
    Активация обещанного платежа
    
    Если статус код 200 или 401, он возвращает json, если нет, даёт bool False (если происходит ошибка)

    ```json
    {
        "response": {
            "status": true,
            "data": {
                "response": {
                    "result": "0",
                    "message": "Обещанный платеж успешно активирован"
                }
            }
        }
    }
    ```

    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#активировать-обещанный-платёж
    """

    url = 'https://api.cyxym.net/app/v1?pay.temp'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'token': token}) as response:
            if response.status == 200 or 401:
                js = await response.json()
                return js['response']['status']
            else:
                return False
            
async def pay_list(id: int, token: str) -> Union[Dict[str, Any], bool]:

    """
    Получение списка платежей
    
    Если статус код 200 или 401, он возвращает json, если нет, даёт bool False (если происходит ошибка)

    ```json
    {
        "response": {
            "status": true,
            "data": [
                {
                    "n_line_no": "8",
                    "dt_oper": "21.04.2024 15:16",
                    "d_oper": "21.04.24",
                    "v_description": "Установка временного кредита (Вручную)",
                    "v_sum": null
                },
                {
                    "n_line_no": "7",
                    "dt_oper": "21.04.2024 15:16",
                    "d_oper": "21.04.24",
                    "v_description": "Закрытие временного кредита (Вручную)",
                    "v_sum": null
                }
            ]
        }
    }
    ```
    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#получение-списка-платежей
    """
    
    url = 'https://api.cyxym.net/app/v1?pay.list'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'token': token, 'from': '2016-05-01', 'to': datetime.now().strftime("%Y-%m-%d"), 'payment': 1, 'writeoff': 1, 'overdraft': 1}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False
