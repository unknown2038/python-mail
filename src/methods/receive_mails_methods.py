import asyncio
import email
from email import policy
import imaplib
from database.db import get_db_connection
from src.methods.receive_mail_helper import mail_object
from src.methods.employee_methods import fetch_employee_by_id
from src.methods.google_auth import get_google_access_token
import datetime



def fetch_receive_mails(user_id, mail_id_name):
   conn = get_db_connection()
   if not conn:
      return []
   
   try:
      cur = conn.cursor()
      employee = fetch_employee_by_id(user_id)
      return employee
   #   cur.execute(
   #       "SELECT * FROM receive_mails WHERE user_id = %s AND mail_id_name = %s",
   #       (user_id, mail_id_name),
   #   )
   #   rows = cur.fetchall()
   #   return rows
   except Exception as e:
      print(f"Error fetching employees: {e}")
      return []
   finally:
      conn.close()

async def fetch_mail_creds():
   conn =await get_db_connection()
   if not conn:
      print("No connection to the database")
      return None
   try:
      rows = await conn.fetch("""
         SELECT username, client_id, client_secret, refresh_token, name
         FROM public.mail_credentials WHERE is_active = $1
         """,True)   
   
      if rows:
         for row in rows:
            mails = await fetch_mail_from_gmail(row[0], row[1], row[2], row[3])
            await save_mails(mails, row[0], row[4])

   except Exception as e:
      print(f"Error fetching mail creds: {e}")
   finally:
      await conn.close()

async def fetch_mail_from_gmail(username, client_id, client_secret, refresh_token):
   if not username or not client_id or not client_secret or not refresh_token:
         return None
      
   # Run the whole function logic in a thread to avoid blocking the event loop
   def run_fetch():
      try:
         all_mails = []
         mail_creds = imaplib.IMAP4_SSL('imap.gmail.com', 993)
         access_token = get_google_access_token(client_id, client_secret, refresh_token)
         auth_string = f"user={username}\x01auth=Bearer {access_token.token}\x01\x01"
         mail_creds.authenticate('XOAUTH2', lambda x: auth_string.encode('utf-8'))
         date = (datetime.datetime.today() - datetime.timedelta(days=0)).strftime("%d-%b-%Y")
         
         # INBOX unseen mails
         mail_creds.select("INBOX")
         status, messages = mail_creds.search(None, f'(UNSEEN ON "{date}")') 
         if status == 'OK':
            inbox_mails = messages[0].split()[::1]
            for mail_id in inbox_mails:
               mail_content = extract_mail_content(mail_id, mail_creds)
               all_mails.append({ "content": mail_content, "is_sent": False})   
               mail_creds.store(mail_id, "-FLAGS", "\\Seen")
         
         # SENT mails
         mail_creds.select('"[Gmail]/Sent Mail"')
         status, messages = mail_creds.search(None, f'(ON "{date}")')
         if status == 'OK':
            sent_mails = messages[0].split()[::1]
            for mail_id in sent_mails:
               mail_content = extract_mail_content(mail_id, mail_creds)
               all_mails.append({ "content": mail_content, "is_sent": True})
               mail_creds.store(mail_id, "-FLAGS", "\\Seen")
   
         return all_mails
   
      except Exception as e:
         print(f"Error fetching mail from gmail: {e}")
         return []
   
   mails = await asyncio.to_thread(run_fetch)
   return mails

# Extract Mail Content
def extract_mail_content(mail_id, creds):
   try:
      status, data = creds.fetch(mail_id, '(RFC822)')
      raw = data[0][1]
      return email.message_from_bytes(raw, policy=policy.default)

   except Exception as e:
      print(f"Error fetching mail from gmail: {e}")

async def save_mails(mails, username, name):
   conn = await get_db_connection()
   if not conn:
      print("No connection to the database")
      return None
   try:
      mail_objects = []
      for mail in mails:
         msg_id = mail["content"].get("Message-ID", "")
         if not msg_id:
            continue      
         mail_in_not_receive = await is_mail_not_exists(msg_id)
         if mail_in_not_receive:
            mail_obj = mail_object(mail["content"], mail["is_sent"], username, name)
            mail_objects.append(mail_obj)
         else:
            continue
      if mail_objects:
         await reset_primary_key(conn, "mail_receive")
         await inset_mail_in_db(conn,mail_objects)
   except Exception as e:
      print(f"Error while saving mails: {e}")
   finally:
      await conn.close()

async def is_mail_not_exists(msg_id):
   conn = await get_db_connection()
   if not conn:
      print("No connection to the database")
      return None
   try:
      mail_in_receive = await conn.fetchval("""
         SELECT NOT EXISTS (SELECT 1 FROM public.mail_receive WHERE message_id = $1)
         """,msg_id)
      # True if mail not exists, False if mail exists
      if mail_in_receive: # Mail Not exists in table
         mail_in_trash = await conn.fetchval("""
            SELECT NOT EXISTS (SELECT 1 FROM public.mail_trash WHERE message_id = $1)
            """,msg_id)
         return mail_in_trash
      else:
         return mail_in_receive # Mail Exists in table
   except Exception as e:
      print(f"Error while checking if mail exists: {e}")
   finally:
      await conn.close()

async def inset_mail_in_db(conn,mail_objects):
   try:
      query = """ 
      INSERT INTO public.mail_receive
      (mail_id, mail_id_name, is_self_sent_mail, from_id, to_ids, cc_ids, bcc_ids, subject, message_id, html, body, receive_date, attachments, in_reply_to, "references")
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
      """
      values = [
         (mail_obj["mail_id"], mail_obj["mail_id_name"], mail_obj["is_self_sent_mail"], mail_obj["from_id"], mail_obj["to_ids"], mail_obj["cc_ids"], mail_obj["bcc_ids"], 
         mail_obj["subject"], mail_obj["message_id"], mail_obj["html"], mail_obj["body"], mail_obj["receive_date"], mail_obj["attachments"], mail_obj["in_reply_to"], mail_obj["references"])
         for mail_obj in mail_objects
      ]
      
      async with conn.transaction(): 
         await conn.executemany(query, values)
         print(f"Mail inserted in db: {len(mail_objects)} of {mail_objects[0]['mail_id_name']}")
   except Exception as e:
      print(f"Error while inserting mail in db: {e}")

async def reset_primary_key(conn, table):
   try:
      seq_row = await conn.fetchrow(f"SELECT pg_get_serial_sequence('public.\"{table}\"', 'id') AS seq;")
      seq_name = seq_row["seq"]
      max_row = await conn.fetchrow(f'SELECT COALESCE(MAX(id), 0) AS max_id FROM public."{table}";')
      max_id = max_row["max_id"]
      await conn.execute(f"ALTER SEQUENCE {seq_name} RESTART WITH {max_id + 1};")
   except Exception as e:
      print(f"Error while resetting primary key: {e}")