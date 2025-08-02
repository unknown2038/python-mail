import asyncpg
import config

db_pool = None

# 🟢 Call on app startup
async def get_db_pool():
   global db_pool
   if db_pool is None:
      db_pool = await asyncpg.create_pool(
            user=config.DATABASE_USER,
            password=config.DATABASE_PASSWORD,
            database=config.DATABASE_NAME,
            host=config.DATABASE_HOST,
            port=config.DATABASE_PORT,
            max_size=50,
            min_size=1,
      )
      print("DB pool initialized")

# 🔴 Call on shutdown (optional cleanup)
async def clear_db_pool():
   global db_pool
   if db_pool:
      await db_pool.close()
      print("DB pool closed")

# 🔍 Fetch a single row
async def fetch_one(query: str, *args):
   if db_pool is None:
      raise RuntimeError("DB pool not initialized.")
   async with db_pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


# 🔍 Fetch multiple rows
async def fetch_all(query: str, *args):
   if db_pool is None:
      raise RuntimeError("DB pool not initialized.")
   async with db_pool.acquire() as conn:
        return await conn.fetch(query, *args)


# 🟢 Get a single value (e.g., count, id)
async def fetch_val(query: str, *args):
   if db_pool is None:
      raise RuntimeError("DB pool not initialized.")
   async with db_pool.acquire() as conn:
        return await conn.fetchval(query, *args)


# ⚙️ Insert, Update, Delete — single execution
async def execute_one(query: str, *args):
   if db_pool is None:
      raise RuntimeError("DB pool not initialized.")
   async with db_pool.acquire() as conn:
        return await conn.execute(query, *args)

async def call_db_pool():
   if db_pool is None:
      raise RuntimeError("DB pool not initialized.")
   async with db_pool.acquire() as conn:
      return conn

# ⚙️ Bulk insert or updates
async def executemany(query: str, args_list: list):
   if db_pool is None:
      raise RuntimeError("DB pool not initialized.")
   async with db_pool.acquire() as conn:
      async with conn.transaction():
            await conn.executemany(query, args_list)
            
async def executemany_returning(query: str, args_list: list, returning_key: str = "id"):
   if db_pool is None:
      raise RuntimeError("DB pool not initialized.")

   inserted_ids = []

   async with db_pool.acquire() as conn:
      async with conn.transaction():
         for args in args_list:
               row = await conn.fetchrow(query, *args)
               if row:
                  inserted_ids.append(row[returning_key])

   return inserted_ids