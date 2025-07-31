from datetime import datetime
import re
import pytz
import email.utils
from bs4 import BeautifulSoup
import email
from email import policy

from database.db import get_db_connection

def convert_email_date_to_ist(date_header_value):
   try:
      if not date_header_value:
         return None

      # Parse RFC 2822 date (e.g., "Mon, 22 Jul 2025 10:15:00 -0700")
      dt = email.utils.parsedate_to_datetime(date_header_value)
      # Ensure it's timezone-aware (some emails might lack tzinfo)
      if dt.tzinfo is None:
         dt = pytz.UTC.localize(dt)
      # Convert to IST
      ist = pytz.timezone("Asia/Kolkata")
      ist_dt = dt.astimezone(ist)
      
      # Remove tzinfo for PostgreSQL timestamp (if your column is without tz)
      return ist_dt.replace(tzinfo=None)

   except Exception as e:
      print(f"Error while converting email date to IST: {e}")
      return None

def mail_object(mail_content, is_sent, username, name):
   try:
      def split_emails(value):
         return [x.strip() for x in value.split(',')] if value else [] # Convert "a@b.com, c@d.com" -> ['a@b.com', 'c@d.com'] or [] if None

      # Convert date to IST (if exists)
      date_header = mail_content.get('Date')
      ist_date = convert_email_date_to_ist(date_header) if date_header else None
      plain_content, html_content = extract_mail_bodies(mail_content)
      attachment_count = 0
      for part in mail_content.walk():
         content_disposition = str(part.get("Content-Disposition") or "")
         if "attachment" in content_disposition.lower():
               attachment_count += 1
      
      to_ids = split_emails(mail_content.get('To'))
      cc_ids = split_emails(mail_content.get('Cc'))
      bcc_ids = split_emails(mail_content.get('Bcc'))
      we_are_in = None
      if username in to_ids:
         we_are_in = 'to'
      elif username in cc_ids:
         we_are_in = 'cc'
      elif username in bcc_ids:
         we_are_in = 'bcc'
      else:
         we_are_in = None
      
      
      return {
         "mail_id": username,
         "mail_id_name": name,
         "is_self_sent_mail": is_sent,
         "from_id": mail_content.get('From') or None,
         "to_ids": to_ids,
         "cc_ids": cc_ids,
         "bcc_ids": bcc_ids,
         "subject": mail_content.get('Subject') or 'No Subject',
         "html":html_content,
         "body": plain_content,
         "message_id": mail_content['Message-ID'] or '',
         "receive_date": ist_date,
         "in_reply_to": None if not mail_content.get('In-Reply-To') or mail_content.get('In-Reply-To').strip() in ("", "<>") else mail_content.get('In-Reply-To').strip(),
         "references": None if not mail_content.get('References') or mail_content.get('References').strip() in ("", "<>") else mail_content.get('References').strip(),
         "attachments": attachment_count,
         "attachments_data": get_attachments_from_email(mail_content),
         "we_are_in": we_are_in
      }
   except Exception as e:
      print(f"Error while making mail object: {e}")
      return None

def extract_mail_bodies(mail_content):
   """
   Extract plain text and HTML bodies from an email.
   Returns: (plain_text, html_text)
   """
   plain_body = None
   html_body = None

   for part in mail_content.walk():
      content_type = part.get_content_type()
      if content_type == "text/plain" and not plain_body:
         plain_body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
      elif content_type == "text/html" and not html_body:
         html_body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")

   # Fallback: convert HTML to plain if no plain part exists
   if not plain_body and html_body:
      soup = BeautifulSoup(html_body, "html.parser")
      plain_body = soup.get_text()

   return plain_body.strip() if plain_body else "", html_body.strip() if html_body else ""

def get_attachments_from_email(msg):
   attachments = []
   for part in msg.walk():
      content_disposition = part.get("Content-Disposition")
      if content_disposition and "attachment" in content_disposition:
         filename = part.get_filename()
         file_data = part.get_payload(decode=True)  # Get raw file content (bytes)

         if filename and file_data:
               attachments.append({
                  "filename": filename,
                  "content": file_data,  # Binary data (store or process later)
                  "size_bytes": len(file_data)
               })

   return attachments

# Extract Mail Content
def extract_mail_content(mail_id, creds):
   try:
      status, data = creds.fetch(mail_id, '(RFC822)')
      raw = data[0][1]
      return email.message_from_bytes(raw, policy=policy.default)

   except Exception as e:
      print(f"Error fetching mail from gmail: {e}")

async def assign_mail_to_project(conn,mail_ids: list[int], project_ids: list[int] = [0]):
   try:
      p_ids = project_ids
      if 0 in p_ids:
         p_ids = [await get_project_id(conn, 'DesignCore Studio', 'Manish', 'Choksi')]
      # Remove existing mail from project
      remove_query = """ DELETE FROM public.mail_receive_project_mails_projects WHERE "mailReceiveId" = $1 """
      async with conn.transaction():
         for mail_id in mail_ids:
               await conn.execute(remove_query, mail_id)
      
      # Assign mail to project
      query = """ 
      INSERT INTO public.mail_receive_project_mails_projects ("mailReceiveId", "projectsId") VALUES ($1, $2)
      ON CONFLICT DO NOTHING;
      """
      async with conn.transaction():
            for mail_id in mail_ids:
               for p_id in p_ids:
                  await conn.execute(query,mail_id,p_id)

   except Exception as e:
      print(f"Error while assigning mail to project: {e}")

async def get_project_id(conn, project_name: str, first_name: str, last_name: str) -> int:
   try:
      query = """
      SELECT p.id FROM public.projects p 
      JOIN public.project_client_details c
      ON p."projectClientId" = c.id
      WHERE p.project_name = $1 AND c.first_name = $2 AND c.last_name = $3
      """
      project_id = await conn.fetchval(query, project_name, first_name, last_name)
      return project_id
   except Exception as e:
      print(f"Error while getting project id: {e}")

async def reset_primary_key(conn, table):
   try:
      seq_row = await conn.fetchrow(f"SELECT pg_get_serial_sequence('public.\"{table}\"', 'id') AS seq;")
      seq_name = seq_row["seq"]
      max_row = await conn.fetchrow(f'SELECT COALESCE(MAX(id), 0) AS max_id FROM public."{table}";')
      max_id = max_row["max_id"]
      await conn.execute(f"ALTER SEQUENCE {seq_name} RESTART WITH {max_id + 1};")
   except Exception as e:
      print(f"Error while resetting primary key: {e}")

async def assign_mails_to_project(project_ids: list[int], mail_ids: list[int]) -> bool:
   conn = await get_db_connection()
   try:
      if not conn:
         return False
      await assign_mail_to_project(conn, mail_ids, project_ids)
      return True
   except Exception as e:
      print(f"Error while assigning mails to project: {e}")
      return False
   finally:
      await conn.close()

import random

def generate_light_color() -> str:
   # Generate a random light color (RGB values 180-255 so it stays bright)
   r = random.randint(150, 255)
   g = random.randint(150, 225)
   b = random.randint(150, 255)
   return f"#{r:02X}{g:02X}{b:02X}"


def format_date(date_value: datetime) -> str:
   dt = datetime.strftime(date_value, "%Y-%m-%d")
   current_date = datetime.strftime(datetime.now(), "%Y-%m-%d")
   
   if dt == current_date:
      return date_value.strftime("%H:%M")
   else:
      return date_value.strftime("%Y-%m-%d %H:%M")


def modify_receive_mails (mails: list[dict]) -> list[dict]:
   try:
      # Regex to capture "Name <email>" OR just "email"
      pattern = re.compile(r"^(.*?)\s*<(.+?)>$|(.+)$", re.MULTILINE)
      result = []
      for item in mails:
         raw = item["from_id"].strip()
         match = pattern.match(raw)
         if match:
            if match.group(2):  # Case: "Name <email>"
               name = match.group(1).strip()
               email = match.group(2).strip()
            else:  # Case: Only email
               email = match.group(3).strip()
               name = email.split("@")[0]  # Use local part as name

            result.append(
               {
                  "id": item["id"],
                  "name": " ".join(word.capitalize() for word in name.strip().split()),
                  "from_id": email,
                  "subject": item["subject"],
                  "receive_date": format_date(item["receive_date"]),
                  "preview": item["body"],
                  "message_id": item["message_id"],
                  "project_name": item["project_name"] or None,
                  "first_name": item["first_name"] or None,
                  "last_name": item["last_name"] or None,
                  "project_id": item["project_id"] or None
               }
            )
      return result
   except Exception as e:
      print(f"Error while modifying receive mails: {e}")
      return []
   