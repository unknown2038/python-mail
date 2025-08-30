import asyncio
import imaplib
from quart import jsonify

from database.db_pool import fetch_all


async def fetch_compose_mail_from_list() -> list[dict]:
   try:
      query = """
         SELECT username, name FROM public.mail_credentials WHERE is_active = $1;
      """
      rows = await fetch_all(query, True)
      return [f"{r[1]} - {r[0]}" for r in rows]
   except Exception as e:
      print(f"Error fetching compose mail from list: {e}")
      return jsonify({"error": e}), 400