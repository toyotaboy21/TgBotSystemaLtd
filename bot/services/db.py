import aiosqlite

class DataBase:
    def __init__(self) -> None:
        self.db_path = 'db.db'

    async def table_create(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS users(
                    user_id INTEGER PRIMARY KEY,
                    token TEXT,
                    id INTEGER,
                    password TEXT,
                    is_admin INTEGER 
                )
            ''')

            await db.execute('''CREATE TABLE IF NOT EXISTS favorites(
                    user_id INTEGER PRIMARY KEY,
                    cams TEXT
                )
            ''')

            await db.commit()

        return
    
    async def get_user_info(
        self,
        user_id: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()
        
    async def delete_user_data(
        self,
        user_id: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))

            await db.commit()

    async def update_token(
        self,
        user_id: int,
        token: str
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET token = ? WHERE user_id = ?", (token, user_id))

            await db.commit()

    async def update_password(
        self,
        user_id: int,
        password: str
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET password = ? WHERE user_id = ?", (password, user_id))

            await db.commit()

    async def update_admin(
        self,
        user_id: int,
        admin: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (admin, user_id))

            await db.commit()

    async def add_user(
        self,
        user_id: int,
        token: str,
        id: int,
        password: str,
        is_admin: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('INSERT INTO users (user_id, token, id, password, is_admin) VALUES (?, ?, ?, ?, ?)', (user_id, token, id, password, is_admin))
            await db.execute('INSERT INTO favorites (user_id, cams) VALUES (?, ?)', (user_id, '[]'))
            
            await db.commit()

    async def get_cams(
        self,
        user_id: int
    ):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT cams FROM favorites WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()
        
    async def cam_update(
        self,
        user_id: int,
        dump: dict
    ):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("REPLACE INTO favorites (user_id, cams) VALUES (?, ?)", (user_id, dump))

            await db.commit()

    async def get_all_user_id(
        self
    ):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                return await cursor.fetchall()