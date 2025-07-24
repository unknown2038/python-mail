import os
import zipfile
import re
from datetime import datetime
import config
import asyncio
import aiofiles

async def save_mail_attachments(mail_objects):  
   for mail in mail_objects:
      await save_attachments_to_folder(mail)

async def save_attachments_to_folder(mail, base_path=config.RECEIVE_FOLDER_PATH):
   try:
      # 1) Base account folder
      account_folder = os.path.join(base_path, sanitize_filename(mail["mail_id_name"]))
      os.makedirs(account_folder, exist_ok=True)
      
      # 2) Sender folder
      sender_name, sender_email = parse_sender(mail["from_id"])
      sender_folder_name = f"{sanitize_filename(sender_name)}_{sanitize_filename(sender_email)}"
      sender_folder = os.path.join(account_folder, sender_folder_name)
      os.makedirs(sender_folder, exist_ok=True)

      # 3) Get index count (existing folder count + 1)
      existing_folders = [f for f in os.listdir(sender_folder) if os.path.isdir(os.path.join(sender_folder, f))]
      folder_count = len(existing_folders) + 1
      index_padded = str(folder_count).zfill(2 if folder_count < 100 else 3)  # 01, 034, etc.
      
      # 4) Format date for folder
      formatted_date = format_date_for_folder(mail["receive_date"])

      # 5) Create mail folder name
      subject_clean = sanitize_filename(mail['subject'])
      mail_folder_name = f"{index_padded}_{formatted_date}_{subject_clean}"
      mail_folder = os.path.join(sender_folder, mail_folder_name)
      os.makedirs(mail_folder, exist_ok=True)
      
      
      # 6) Save attachments (async)
      for attachment in mail.get("attachments_data", []):
         filename = sanitize_filename(attachment["filename"])
         filepath = os.path.join(mail_folder, filename)

         async with aiofiles.open(filepath, "wb") as f:
               await f.write(attachment["content"])

         # If it's a zip, extract asynchronously
         if filename.lower().endswith(".zip"):
            await extract_zip_async(filepath, mail_folder)
      
      # 7) Save mail body into read.txt
      read_txt_path = os.path.join(mail_folder, "read.txt")
      with open(read_txt_path, "w", encoding="utf-8") as f:
         f.write(mail.get("body", ""))

   except Exception as e:
      print(f"Error saving attachments to folder: {e}")

async def extract_zip_async(zip_path, extract_to):
   """Run zip extraction in a background thread (non-blocking)."""
   def _extract():
      with zipfile.ZipFile(zip_path, "r") as z:
         z.extractall(extract_to)
   await asyncio.to_thread(_extract)

def sanitize_filename(name: str) -> str:
   """Remove illegal characters for filenames."""
   return re.sub(r'[\\/*?:"<>|]', "_", name)

def parse_sender(from_field: str):
   """
   Extracts name and email from a 'From' field like:
   - 'ALCOI <alcoiindia.media@153509026.mailchimpapp.com>'
   - 'communication@cpc.incometax.gov.in'
   Returns (name, email).
   """
   from_field = from_field.strip()
   if "<" in from_field and ">" in from_field:
      # Extract name and email
      name_part = from_field.split("<")[0].strip()
      email_part = from_field.split("<")[1].replace(">", "").strip()
      return name_part or email_part, email_part
   else:
      return from_field, from_field  # Only email, no name

def format_date_for_folder(date_str):
   """
   Convert '2025-07-23 13:29:03.000' -> '23_07_2025'
   """
   # If already datetime, use it directly
   if isinstance(date_str, datetime):
      return date_str.strftime("%d_%m_%Y")
   # Else, parse the string
   dt = datetime.strptime(date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
   return dt.strftime("%d_%m_%Y")
