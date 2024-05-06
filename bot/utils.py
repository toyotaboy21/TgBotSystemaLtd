import json
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

async def get_locations() -> Union[Dict[str, Any], bool]:

    """
    Получение списка всех локаций
    
    Если статус код 200 или 401, он возвращает json, если нет, даёт bool False (если происходит ошибка)

    ```json
    {
        "response": [
            {
                "location_id": 1,
                "location_name": "Сухум"
            },
            {
                "location_id": 2,
                "location_name": "Псоу"
            },
            {
                "location_id": 3,
                "location_name": "Гагра"
            },
            {
                "location_id": 4,
                "location_name": "Афон"
            },
            {
                "location_id": 5,
                "location_name": "Гал"
            },
            {
                "location_id": 6,
                "location_name": "Рица"
            }, 
            {
                "location_id": 7,
                "location_name": "Пицунда"
            },
            {
                "location_id": 8,
                "location_name": "Гудаута"
            },
            {
                "location_id": 9,
                "location_name": "Очамчира"
            },
            {
                "location_id": 10,
                "location_name": "Агудзера"
            }
        ]
    }
    ```
    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#получение-всех0-локаций
    """
    
    url = 'https://api.cyxym.net/bigbrother/v1?locations.get'
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False

async def get_camera(lid: int) -> Union[Dict[str, Any], bool]:

    """
    Получение списка всех локаций
    
    Если статус код 200 или 401, он возвращает json, если нет, даёт bool False (если происходит ошибка)

    ```json
    {
        "response": {
            "cams": [
                {
                    "id": 49,
                    "channel": "gudauta_lyhnenskiy_povorot",
                    "name": "Гудаута - Лыхненский поворот",
                    "preview": "https://apsny.camera/img/camera/gudauta_lyhnenskiy_povorot/preview.jpg",
                    "location": 8,
                    "clients": 6
                },
                {
                    "id": 51,
                    "channel": "gudauta_prospekt_geroev",
                    "name": "Гудаута - Проспект Героев",
                    "preview": "https://apsny.camera/img/camera/gudauta_prospekt_geroev/preview.jpg",
                    "location": 8,
                    "clients": 8
                },
                {
                    "id": 57,
                    "channel": "gudauta_park",
                    "name": "Гудаута - Парк Гуда и Ута",
                    "preview": "https://apsny.camera/img/camera/gudauta_park/preview.jpg",
                    "location": 8,
                    "clients": 5
                },
                {
                    "id": 110,
                    "channel": "gudauta_vokzal",
                    "name": "Гудаута - вокзал",
                    "preview": "https://apsny.camera/img/camera/gudauta_vokzal/preview.jpg",
                    "location": 8,
                    "clients": 3
                },
                {
                    "id": 111,
                    "channel": "gudauta_post_bambora",
                    "name": "Пост ГАИ - Бамбора",
                    "preview": "https://apsny.camera/img/camera/gudauta_post_bambora/preview.jpg",
                    "location": 8,
                    "clients": 3
                },
                {
                    "id": 112,
                    "channel": "gudauta_chachba_ochamchyrskaya",
                    "name": "Гудаута - пересечение ул. Чачба и Очамчирская",
                    "preview": "https://apsny.camera/img/camera/gudauta_chachba_ochamchyrskaya/preview.jpg",
                    "location": 8,
                    "clients": 3
                },
                {
                    "id": 216,
                    "channel": "lyhnashta_1",
                    "name": "Лыхнашта",
                    "preview": "https://apsny.camera/img/camera/lyhnashta_1/preview.jpg",
                    "location": 8,
                    "clients": 2
                }
            ],
            "count": 7,
            "users": 664
        }
    }
    ```
    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#получение-камер-по-локации
    """
    
    url = 'https://api.cyxym.net/bigbrother/v2?cams.get'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'lid': lid}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False
            

async def get_stream_info(channel: str) -> Union[Dict[str, Any], bool]:

    """
    Получение информации о канале (камеры)

    ```json
    {
        "response": {
            "link": "https://public.apsny.camera/psou_1/",
            "channel": "psou_1",
            "preview": "https://apsny.camera/img/camera/psou_1/preview.jpg",
            "favorite": false,
            "token": "d9286ee83db153aef4b6e18e8fa3f1432053341a-2e31cc8d60afd1f4363bfb68200a8227-1713706225-1713695425",
            "timelapse": true,
            "ip": "185.228.135.250",
            "cam": {
                "camera_name": "Псоу - Въезд на КПП (из Абхазии)",
                "camera_text": "<p>Камера установлена на КПП \"Псоу\".</p>\n<p>Въезд на таможенный терминал со стороны Республики Абхазия.</p>\n<p>Выражаем благодарность ГТК Республики Абхазия за содействие в установке камеры.</p>\n<p>Официальный сайт ГТК РА: <a href=\"http://www.customsra.com/\" class=\"content_a\" title=\"ГТК РА\" target=\"_blank\">www.customsra.com</a></p>",
                "users_count": 5,
                "timelapse_support": 1
            },
            "weather": {
                "now": 1713690002,
                "now_dt": "2024-04-21T09:00:02.193196Z",
                "info": {
                    "url": "https://yandex.ru/pogoda/105957?lat=43.393651&lon=40.011153",
                    "lat": 43.393651,
                    "lon": 40.011153
                },
                "fact": {
                    "obs_time": 1713688200,
                    "temp": 18,
                    "feels_like": 14,
                    "temp_water": 16,
                    "icon": "bkn_-ra_d",
                    "condition": "light-rain",
                    "wind_speed": 8,
                    "wind_dir": "w",
                    "pressure_mm": 759,
                    "pressure_pa": 1011,
                    "humidity": 72,
                    "daytime": "d",
                    "polar": false,
                    "season": "spring",
                    "wind_gust": 12.4
                },
                "forecast": {
                    "date": "2024-04-21",
                    "date_ts": 1713646800,
                    "week": 16,
                    "sunrise": "05:27",
                    "sunset": "19:09",
                    "moon_code": 15,
                    "moon_text": "moon-code-15",
                    "parts": [
                        {
                            "part_name": "evening",
                            "temp_min": 15,
                            "temp_avg": 17,
                            "temp_max": 18,
                            "temp_water": 16,
                            "wind_speed": 4.3,
                            "wind_gust": 9.8,
                            "wind_dir": "nw",
                            "pressure_mm": 763,
                            "pressure_pa": 1016,
                            "humidity": 73,
                            "prec_mm": 0,
                            "prec_prob": 0,
                            "prec_period": 240,
                            "icon": "bkn_n",
                            "condition": "cloudy",
                            "feels_like": 15,
                            "daytime": "n",
                            "polar": false
                        },
                        {
                            "part_name": "night",
                            "temp_min": 12,
                            "temp_avg": 13,
                            "temp_max": 14,
                            "temp_water": 16,
                            "wind_speed": 2.5,
                            "wind_gust": 4.6,
                            "wind_dir": "n",
                            "pressure_mm": 763,
                            "pressure_pa": 1017,
                            "humidity": 77,
                            "prec_mm": 0,
                            "prec_prob": 0,
                            "prec_period": 480,
                            "icon": "skc_n",
                            "condition": "clear",
                            "feels_like": 11,
                            "daytime": "n",
                            "polar": false
                        }
                    ]
                }
            }
        }
    }
    ```
    
    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#получение-информации-о-канале-камеры
    """

    url = 'https://api.cyxym.net/bigbrother/v1?cams.stream'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'channel': channel, 'ip': '0.0.0.0'}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False
            
async def change_password(id: int, token: str) -> Union[Dict[str, Any], bool]:

    """
    Отправка смс кода для смены пароля

    ```json
    {
        "response": {
            "status": true,
            "phone": "79*****9472"
        }
    }
    ```
    
    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#отправка-смс-кода-для-смены-пароля
    """

    url = 'https://api.cyxym.net/app/v1?account.sendSMS'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'token': token}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False
            
async def change_password_confim(id: int, password: str, token: str, code: int) -> Union[Dict[str, Any], bool]:

    """
    Подтверждение изменения пароля

    ```json
    {
        "response": {
            "status": true,
            "phone": "79*****9472"
        }
    }
    ```
    
    API Docs: https://github.com/reques6e/SystemUtilis/blob/main/API.md#false
    """

    url = 'https://api.cyxym.net/app/v1?account.password'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'password': password,'token': token, 'code': code}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False