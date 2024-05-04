import aiohttp

from datetime import datetime, timedelta


def get_first_day_last_month():
    today = datetime.now()
    first_day_last_month = today.replace(day=1) - timedelta(days=today.day)
    return first_day_last_month.strftime("%Y-%m-%d")

async def fetch_profile(cursor, user_id):
    cursor.execute("SELECT token FROM users WHERE user_id = ?", (user_id,))
    token = cursor.fetchone()[0] 
    url = 'https://api.cyxym.net/app/v1?account'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': user_id, 'token': token}) as response:
            return await response.json()

async def auth_profile(id, password):
    url = 'https://api.cyxym.net/app/v1?auth'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'password': password}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False

async def generate_pay_link(id, amount):
    url = 'https://api.cyxym.net/pay/v1?init'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'amount': amount}) as response:
            if response.status == 200 or 401:
                js = await response.json()
                return js['response']['confirmation']['confirmation_url']
            else:
                return False
            
async def promised_payment(id, token):
    url = 'https://api.cyxym.net/app/v1?pay.temp'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'token': token}) as response:
            if response.status == 200 or 401:
                js = await response.json()
                return js['response']['status']
            else:
                return False
            
async def pay_list(id, token):
    url = 'https://api.cyxym.net/app/v1?pay.list'
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data={'id': id, 'token': token, 'from': '2016-05-01', 'to': datetime.now().strftime("%Y-%m-%d"), 'payment': 1, 'writeoff': 1, 'overdraft': 1}) as response:
            if response.status == 200 or 401:
                return await response.json()
            else:
                return False