import asyncio
import imaplib
from database.db import get_db_connection
from src.methods.receive_mails.receive_mail_file_manager import save_mail_attachments
from src.methods.receive_mails.receive_mail_helper import assign_mail_to_project, extract_mail_content, mail_object, reset_primary_key
from src.methods.employee_methods import fetch_employee_by_id
from src.methods.google_auth import get_google_access_token
import datetime


async def fetch_receive_mails(user_id, mail_id_name, date_filter, is_self_sent):
   # Ensure boolean
   if isinstance(is_self_sent, str):
      is_self_sent = is_self_sent.lower() in ("true", "1", "yes")
   elif not isinstance(is_self_sent, bool):
      is_self_sent = bool(is_self_sent)
   conn = await get_db_connection()
   if not conn:
      return []
   
   try:
      start_dt = date_filter.replace(hour=0, minute=0, second=0, microsecond=0)
      end_dt = date_filter.replace(hour=23, minute=59, second=59, microsecond=999000)
      
      employee = await fetch_employee_by_id(user_id)
      if employee['department'] == 'department' or employee['department'] == 'MDO' or employee['department'] == 'Management':
         mails = await conn.fetch("""
            SELECT id, from_id, to_ids, cc_ids, bcc_ids, subject, receive_date, attachments, status, is_self_sent_mail 
            FROM public.mail_receive
            where mail_id_name = $1 
               AND is_self_sent_mail = $2 
               AND receive_date BETWEEN $3 AND $4
            ORDER BY receive_date DESC
            """,mail_id_name, is_self_sent, start_dt, end_dt)
         return [dict(r) for r in mails]
      elif employee['role'] == 'HOD':
         mails = await conn.fetch("""
            SELECT mr.id, mr.from_id, mr.to_ids, mr.cc_ids, mr.bcc_ids, mr.subject, mr.receive_date, mr.attachments, mr.status, mr.is_self_sent_mail
            FROM public.mail_receive mr
            JOIN public.project_receive_mails_projects prmp
               ON prmp."mailReceiveId" = mr.id
            JOIN public.projects p
               ON p.id = prmp."projectsId"
            JOIN public.projects_poc_employees ppe
               ON ppe."projectsId" = p.id
            WHERE ppe."employeesId" = $5
               AND mr.mail_id_name = $1
               AND mr.is_self_sent_mail = $2
               AND mr.receive_date BETWEEN $3 AND $4
            ORDER BY mr.receive_date DESC;
            """,mail_id_name, is_self_sent, start_dt, end_dt, user_id)
         return [dict(r) for r in mails]
      elif any(key in employee['role'] for key in ['Jr.','Sr.']):
         mails = await conn.fetch("""
            SELECT mr.id, mr.from_id, mr.to_ids, mr.cc_ids, mr.bcc_ids, mr.subject, mr.receive_date, mr.attachments, mr.status, mr.is_self_sent_mail
            FROM public.mail_receive mr
            JOIN public.project_receive_mails_projects prmp
               ON prmp."mailReceiveId" = mr.id
            JOIN public.projects p
               ON p.id = prmp."projectsId"
            WHERE mr.mail_id_name = $1
               AND mr.is_self_sent_mail = $2
               AND mr.receive_date BETWEEN $3 AND $4
               AND (
                  EXISTS (SELECT 1 FROM public.projects_designers_employees die WHERE die."projectsId" = p.id AND die."employeesId" = $5)
               OR EXISTS (SELECT 1 FROM public.projects_detailers_employees dte WHERE dte."projectsId" = p.id AND dte."employeesId" = $5)
               OR EXISTS (SELECT 1 FROM public.projects_3d_designers_employees tde WHERE tde."projectsId" = p.id AND tde."employeesId" = $5)
               OR EXISTS (SELECT 1 FROM public.projects_site_poc_employees spe WHERE spe."projectsId" = p.id AND spe."employeesId" = $5)
               OR EXISTS (SELECT 1 FROM public.projects_site_support_poc_employees sspe WHERE sspe."projectsId" = p.id AND sspe."employeesId" = $5)
               )	
            ORDER BY mr.receive_date DESC;
            """,mail_id_name, is_self_sent, start_dt, end_dt, user_id)
         return [dict(r) for r in mails]
   except Exception as e:
      print(f"Error fetching receive mails: {e}")
      return []
   finally:
      await conn.close()

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
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15) RETURNING id;
      """
      
      inserted_ids = []
      async with conn.transaction(): 
         for mail_obj in mail_objects:
               row = await conn.fetchrow(
                  query,
                  mail_obj["mail_id"], mail_obj["mail_id_name"], mail_obj["is_self_sent_mail"],
                  mail_obj["from_id"], mail_obj["to_ids"], mail_obj["cc_ids"], mail_obj["bcc_ids"],
                  mail_obj["subject"], mail_obj["message_id"], mail_obj["html"], mail_obj["body"],
                  mail_obj["receive_date"], mail_obj["attachments"], mail_obj["in_reply_to"], mail_obj["references"]
               )
               inserted_ids.append(row["id"])
         
         # Process attachments and assign projects
         await save_mail_attachments(mail_objects)
         await assign_mail_to_project(conn,inserted_ids)
         print(f"Mail inserted in db: {len(mail_objects)}")
   except Exception as e:
      print(f"Error while inserting mail in db: {e}")


