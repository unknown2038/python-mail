import asyncio
import imaplib
from quart import jsonify
from database.db_pool import execute_one, executemany_returning, fetch_all, fetch_one
from src.methods.receive_mails.receive_mail_file_manager import save_mail_attachments
from src.methods.receive_mails.receive_mail_helper import assign_mail_to_project, extract_mail_content, generate_light_color, mail_object, reset_primary_key
from src.methods.employee_methods import fetch_employee_by_id
from src.methods.google_auth import get_google_access_token
import datetime


async def fetch_receive_mails(user_id, mail_id_name, date_filter, is_self_sent, mail_of) -> list[dict]:
   # Ensure boolean
   if isinstance(is_self_sent, str):
      is_self_sent = is_self_sent.lower() in ("true", "1", "yes")
   elif not isinstance(is_self_sent, bool):
      is_self_sent = bool(is_self_sent)

   try:
      start_dt = date_filter.replace(hour=0, minute=0, second=0, microsecond=0)
      end_dt = date_filter.replace(hour=23, minute=59, second=59, microsecond=999000)
      employee = await fetch_employee_by_id(user_id)

      if mail_of == 'Trash':
         query = """
            SELECT id, from_id, subject, receive_date, body, message_id, status
            FROM public.mail_receive
            where mail_id_name = $1 
               AND is_removed = $2 
               AND receive_date BETWEEN $3 AND $4
            ORDER BY receive_date DESC         
         """
         mails = await fetch_all(query,mail_id_name, True, start_dt, end_dt)
         return [dict(r) for r in mails]
      else:
         if employee['role'] == 'Admin' or employee['department'] == 'MDO' or employee['department'] == 'Management':
            query = """
               SELECT *
                  FROM (
                  SELECT DISTINCT ON (mr.id) 
                     mr.id, 
                     mr.from_id, 
                     mr.subject, 
                     mr.receive_date, 
                     mr.body, 
                     mr.message_id,
                     mr.status
                  FROM public.mail_receive mr
                  LEFT JOIN public.mail_receive_project_mails_projects prmp
                     ON prmp."mailReceiveId" = mr.id
                  LEFT JOIN public.projects p
                     ON p.id = prmp."projectsId"
                  LEFT JOIN public.project_client_details pc
                     ON pc.id = p."projectClientId"
                  WHERE mr.mail_id_name = $1 
                     AND mr.is_self_sent_mail = $2 
                     AND mr.is_removed = $5 
                     AND mr.receive_date BETWEEN $3 AND $4
                  ORDER BY mr.id, mr.receive_date DESC
                  ) sub
                  ORDER BY sub.receive_date DESC;
            """
            mails = await fetch_all(query,mail_id_name, is_self_sent, start_dt, end_dt, False)
            return [dict(r) for r in mails]
         elif employee['role'] == 'HOD':
            query = """
               SELECT *
                  FROM (
                  SELECT DISTINCT ON (mr.id)
                           mr.id,
                           mr.from_id,
                           mr.subject,
                           mr.receive_date,
                           mr.message_id,
                           mr.body,
                           mr.status
                  FROM public.mail_receive mr
                  LEFT JOIN public.mail_receive_project_mails_projects prmp
                     ON prmp."mailReceiveId" = mr.id
                  LEFT JOIN public.projects p
                     ON p.id = prmp."projectsId"
                  LEFT JOIN public.projects_poc_employees ppe
                     ON ppe."projectsId" = p.id
                  WHERE mr.mail_id_name = $1
                     AND mr.is_self_sent_mail = $2
                     AND mr.is_removed = $6
                     AND mr.receive_date BETWEEN $3 AND $4
                     AND (
                           ppe."employeesId" = $5
                           OR p.id = 186
                     )
                  ORDER BY mr.id, mr.receive_date DESC
                  ) sub
                  ORDER BY sub.receive_date DESC;
            """
            mails = await fetch_all(query,mail_id_name, is_self_sent, start_dt, end_dt, user_id, False)
            return [dict(r) for r in mails]
         elif any(key in employee['role'] for key in ['Jr.','Sr.','Intern']):
            query = """
               SELECT *
                  FROM (
                  SELECT DISTINCT ON (mr.id) 
                     mr.id, 
                     mr.from_id, 
                     mr.subject, 
                     mr.receive_date, 
                     mr.message_id,
                     mr.body,
                     mr.status
                  FROM public.mail_receive mr
                  LEFT JOIN public.mail_receive_project_mails_projects prmp
                     ON prmp."mailReceiveId" = mr.id
                  LEFT JOIN public.projects p
                     ON p.id = prmp."projectsId"
                  WHERE mr.mail_id_name = $1
                     AND mr.is_self_sent_mail = $2
                     AND mr.is_removed = $6
                     AND mr.receive_date BETWEEN $3 AND $4
                     AND (
                           EXISTS (SELECT 1 FROM public.projects_designers_employees die 
                                 WHERE die."projectsId" = p.id AND die."employeesId" = $5)
                        OR EXISTS (SELECT 1 FROM public.projects_detailers_employees dte 
                                 WHERE dte."projectsId" = p.id AND dte."employeesId" = $5)
                        OR EXISTS (SELECT 1 FROM public.projects_3d_designers_employees tde 
                                 WHERE tde."projectsId" = p.id AND tde."employeesId" = $5)
                        OR EXISTS (SELECT 1 FROM public.projects_site_poc_employees spe 
                                 WHERE spe."projectsId" = p.id AND spe."employeesId" = $5)
                        OR EXISTS (SELECT 1 FROM public.projects_site_support_poc_employees sspe 
                                 WHERE sspe."projectsId" = p.id AND sspe."employeesId" = $5)
                        OR p.id = 186
                     )
                  ORDER BY mr.id, mr.receive_date DESC
                  ) sub
                  ORDER BY sub.receive_date DESC;
            """
            mails = await fetch_all(query,mail_id_name, is_self_sent, start_dt, end_dt, user_id, False)
            return [dict(r) for r in mails]
   except Exception as e:
      print(f"Error fetching receive mails: {e}")
      return []

async def fetch_gmail_mails(date_filter) -> None:
   try:
      query = """
         SELECT username, client_id, client_secret, refresh_token, name
         FROM public.mail_credentials WHERE is_active = $1
      """
      rows = await fetch_all(query,True)   
      if rows:
         for row in rows:
            mails = await fetch_mail_from_gmail(row[0], row[1], row[2], row[3], date_filter)
            await save_mails(mails, row[0], row[4])

   except Exception as e:
      print(f"Error fetching mail creds: {e}")

async def fetch_mail_from_gmail(username, client_id, client_secret, refresh_token, date_filter) -> list[dict]:
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
         # date = (datetime.datetime.today() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")
         
         # INBOX unseen mails
         mail_creds.select("INBOX")
         status, messages = mail_creds.search(None, f'(UNSEEN ON "{date_filter}")') 
         
         # print(f"date_filter: {date}")
         # status, messages = mail_creds.search(None, f'(ON "{date}")') 
         if status == 'OK':
            inbox_mails = messages[0].split()[::1]
            for mail_id in inbox_mails:
               mail_content = extract_mail_content(mail_id, mail_creds)
               all_mails.append({ "content": mail_content, "is_sent": False})   
               mail_creds.store(mail_id, "-FLAGS", "\\Seen")
         
         # SENT mails
         mail_creds.select('"[Gmail]/Sent Mail"')
         status, messages = mail_creds.search(None, f'(ON "{date_filter}")')
         if status == 'OK':
            sent_mails = messages[0].split()[::1]
            for mail_id in sent_mails:
               mail_content = extract_mail_content(mail_id, mail_creds)
               all_mails.append({ "content": mail_content, "is_sent": True})
   
         return all_mails
   
      except Exception as e:
         print(f"Error fetching mail from gmail: {e}")
         return []
   
   mails = await asyncio.to_thread(run_fetch)
   return mails

async def save_mails(mails, username, name):
   try:
      mail_objects = []
      for mail in mails:
         msg_id = mail["content"].get("Message-ID", "")
         if not msg_id:
            continue      
         mail_in_receive = await is_mail_exists(msg_id)
         if not mail_in_receive:
            mail_obj = mail_object(mail["content"], mail["is_sent"], username, name)
            mail_objects.append(mail_obj)
         else:
            continue
      if mail_objects:
         await reset_primary_key("mail_receive")
         await inset_mail_in_db(mail_objects)
   except Exception as e:
      print(f"Error while saving mails: {e}")


async def is_mail_exists(msg_id) -> bool:
   try:
      query = """ select exists (select 1 from public.mail_receive where message_id = $1) as is_exists; """
      mail_in_receive = await fetch_one(query,msg_id)
      
      # True if mail exists, False if mail not exists
      if not mail_in_receive.get('is_exists'): # Mail not exists in table
         query = """ select exists (select 1 from public.mail_trash where message_id = $1) as is_exists; """
         mail_in_trash = await fetch_one(query,msg_id)
         return mail_in_trash.get('is_exists') # True if mail exists, False if mail not exists
      else:
         return mail_in_receive.get('is_exists') # Mail Exists in table
   except Exception as e:
      print(f"Error while checking if mail exists: {e}")


async def inset_mail_in_db(mail_objects):
   try:
      query = """ 
      INSERT INTO public.mail_receive
      (mail_id, mail_id_name, is_self_sent_mail, from_id, to_ids, cc_ids, bcc_ids, subject, message_id, html, body, receive_date, attachments, in_reply_to, "references", we_are_in)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16) RETURNING id;
      """
      
      params = [
         (
            mail["mail_id"], mail["mail_id_name"], mail["is_self_sent_mail"],
            mail["from_id"], mail["to_ids"], mail["cc_ids"], mail["bcc_ids"],
            mail["subject"], mail["message_id"], mail["html"], mail["body"],
            mail["receive_date"], mail["attachments"], mail["in_reply_to"],
            mail["references"], mail["we_are_in"]
         )
         for mail in mail_objects
      ]
      inserted_ids = await executemany_returning(query, params)
      # Process attachments and assign projects
      await save_mail_attachments(mail_objects)
      await assign_mail_to_project(inserted_ids)
   except Exception as e:
      print(f"Error while inserting mail in db: {e}")

async def fetch_mail_creds():
   try:
      query = """ SELECT username, name FROM public.mail_credentials WHERE is_active = $1; """
      rows = await fetch_all(query,True)  
      if not rows: 
         return []
      else:
         result = []
         for row in rows:
            color = generate_light_color()
            row_dict = dict(row)
            row_dict['color'] = color
            result.append(row_dict)
         return result
   except Exception as e:
      print(f"Error while fetching mail creds: {e}")

async def search_any_mail(search_query, user_id, mail_id_name) -> list[dict]:
   try:
      employee = await fetch_employee_by_id(user_id)
      if employee['role'] == 'Admin' or employee['department'] == 'MDO' or employee['department'] == 'Management':
         query = """
            SELECT id, from_id, subject, receive_date, body, message_id, status
            FROM public.mail_receive 
            WHERE mail_id_name = $2
               AND (
                     from_id ILIKE '%' || $1::text || '%'
                  OR array_to_string(to_ids, ',') ILIKE '%' || $1::text || '%'
                  OR array_to_string(cc_ids, ',') ILIKE '%' || $1::text || '%'
                  OR array_to_string(bcc_ids, ',') ILIKE '%' || $1::text || '%'
                  OR subject ILIKE '%' || $1::text || '%'
                  OR from_id ILIKE '%' || $1::text || '%'
               )
            ORDER BY receive_date DESC;
         """
         mails = await fetch_all(query,search_query, mail_id_name)
         return [dict(r) for r in mails]
      
      elif employee['role'] == 'HOD':
         query = """
            SELECT mr.id, mr.from_id, mr.subject, mr.receive_date, mr.body, mr.message_id, status
            FROM public.mail_receive mr
            JOIN public.mail_receive_project_mails_projects prmp
               ON prmp."mailReceiveId" = mr.id
            JOIN public.projects p
               ON p.id = prmp."projectsId"
            JOIN public.projects_poc_employees ppe
               ON ppe."projectsId" = p.id
            WHERE ppe."employeesId" = $2
               AND mr.mail_id_name = $3
               AND (
                     mr.from_id ILIKE '%' || $1::text || '%'
                  OR array_to_string(mr.to_ids, ',') ILIKE '%' || $1::text || '%'
                  OR array_to_string(mr.cc_ids, ',') ILIKE '%' || $1::text || '%'
                  OR array_to_string(mr.bcc_ids, ',') ILIKE '%' || $1::text || '%'
                  OR mr.subject ILIKE '%' || $1::text || '%'
                  OR mr.from_id ILIKE '%' || $1::text || '%'
               )
            ORDER BY mr.receive_date DESC;
         """
         mails = await fetch_all(query,search_query, user_id, mail_id_name)
         return [dict(r) for r in mails]
      
      elif any(key in employee['role'] for key in ['Jr.','Sr.','Intern']):
         query = """
            SELECT mr.id, mr.from_id, mr.subject, mr.receive_date, mr.body, mr.message_id, status
            FROM public.mail_receive mr
            JOIN public.mail_receive_project_mails_projects prmp
               ON prmp."mailReceiveId" = mr.id
            JOIN public.projects p
               ON p.id = prmp."projectsId"
            WHERE mr.mail_id_name = $2
               AND (
                  EXISTS (SELECT 1 FROM public.projects_designers_employees die WHERE die."projectsId" = p.id AND die."employeesId" = $3)
                  OR EXISTS (SELECT 1 FROM public.projects_detailers_employees dte WHERE dte."projectsId" = p.id AND dte."employeesId" = $3)
                  OR EXISTS (SELECT 1 FROM public.projects_3d_designers_employees tde WHERE tde."projectsId" = p.id AND tde."employeesId" = $3)
                  OR EXISTS (SELECT 1 FROM public.projects_site_poc_employees spe WHERE spe."projectsId" = p.id AND spe."employeesId" = $3)
                  OR EXISTS (SELECT 1 FROM public.projects_site_support_poc_employees sspe WHERE sspe."projectsId" = p.id AND sspe."employeesId" = $3)
               )
               AND (
                  mr.from_id ILIKE '%' || $1::text || '%'
                  OR array_to_string(mr.to_ids, ',') ILIKE '%' || $1::text || '%'
                  OR array_to_string(mr.cc_ids, ',') ILIKE '%' || $1::text || '%'
                  OR array_to_string(mr.bcc_ids, ',') ILIKE '%' || $1::text || '%'
                  OR mr.subject ILIKE '%' || $1::text || '%'
                  OR mr.from_id ILIKE '%' || $1::text || '%'
               );
            ORDER BY mr.receive_date DESC;
         """
         mails = await fetch_all(query,search_query, mail_id_name, user_id)
         return [dict(r) for r in mails]
      else:
         return []
   except Exception as e:
      print(f"Error while searching mail: {e}")
      return []

async def move_to_trash(mail_ids: list[int]):
   try:
      query = """
         UPDATE public.mail_receive
         SET is_removed = TRUE
         WHERE id = ANY($1);
      """
      # Execute the update and return updated IDs
      await execute_one(query, mail_ids)
      return jsonify({"message": "Mails moved to trash successfully"}), 200
   except Exception as e:
      print(f"Error while moving mails to trash: {e}")
      return jsonify({"error": str(e)}), 500
   
async def remove_from_trash(mail_ids: list[int]):
   try:
      query = """
         UPDATE public.mail_receive
         SET is_removed = FALSE
         WHERE id = ANY($1);
      """
      # Execute the update and return updated IDs
      updated_rows = await execute_one(query, mail_ids)
      return jsonify({"message": "Mails moved to inbox successfully"}), 200
   except Exception as e:
      print(f"Error while moving mails to inbox: {e}")
      return jsonify({"error": str(e)}), 500


async def fetch_mail_details(message_id: str):
   try:
      query = """
         SELECT * FROM public.mail_receive 
         WHERE message_id  = $1
            OR in_reply_to = $1
            OR "references" = $1
         ORDER BY receive_date ASC;
         """
      mail_details = await fetch_all(query,message_id)
      return [dict(r) for r in mail_details]
   except Exception as e:
      print(f"Error while fetching mail details: {e}")
      return None


async def fetch_receive_mail(id: int):
   try:
      query = """
         select id, from_id, mail_id, cc_ids, bcc_ids, subject, message_id from public.mail_receive 
         where is_self_sent_mail = false
            and id = $1;
         """
      mail_details = await fetch_one(query,id)
      if mail_details:  
         mail =  dict(mail_details)
         mail['attachments'] = []
         return mail
      else:
         return None
   except Exception as e:
      print(f"Error while fetching mail details: {e}")
      return None