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
      account_folder = os.path.join(base_path, sanitize_filename(mail.get("mail_id_name")))
      account_folder = os.path.normpath(account_folder)
      os.makedirs(account_folder, exist_ok=True)
      
      # 2) Sender folder
      sender_name, sender_email = parse_sender(mail.get("from_id"))
      sender_folder_name = f"{sanitize_filename(sender_name)}_{sanitize_filename(sender_email)}"
      sender_folder = os.path.join(account_folder, sender_folder_name)
      sender_folder = os.path.normpath(sender_folder)
      os.makedirs(sender_folder, exist_ok=True)

      # 3) Get index count (existing folder count + 1)
      existing_folders = [f for f in os.listdir(sender_folder) if os.path.isdir(os.path.join(sender_folder, f))]
      folder_count = len(existing_folders) + 1
      index_padded = str(folder_count).zfill(2 if folder_count < 100 else 3)  # 01, 034, etc.
      
      # 4) Format date for folder
      formatted_date = format_date_for_folder(mail.get("receive_date"))

      # 5) Create mail folder name
      subject_clean = sanitize_filename(mail.get("subject"), max_length=80)
      mail_folder_name = f"{index_padded}_{formatted_date}_{subject_clean}"
      mail_folder = os.path.join(sender_folder, mail_folder_name)
      mail_folder = os.path.normpath(mail_folder)
      os.makedirs(mail_folder, exist_ok=True)
      
      
      # 6) Save attachments (async)
      for attachment in mail.get("attachments_data", []):
         filename = sanitize_filename(attachment["filename"])
         filepath = os.path.join(mail_folder, filename)
         filepath = os.path.normpath(filepath)

         # Create parent directories if they don't exist
         os.makedirs(os.path.dirname(filepath), exist_ok=True)

         async with aiofiles.open(filepath, "wb") as f:
               await f.write(attachment.get("content", b""))

         # If it's a zip, extract asynchronously
         if filename.lower().endswith(".zip"):
            await extract_zip_async(filepath, mail_folder)
      
      # 7) Save mail body into read.txt
      read_txt_path = os.path.normpath(os.path.join(mail_folder, "read.txt"))
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

def sanitize_filename(name: str, max_length=100) -> str:
   """
   Cleans strings for safe filenames:
   - Removes slashes, quotes, and invalid chars
   - Collapses multiple dots/spaces
   - Trims overly long names (to avoid path length issues)
   """
   if not name:
      return "unknown"
   # Replace unwanted characters with underscore
   name = re.sub(r"[\\/:*?\"'<>|]+", "_", str(name))  # also removes single quotes
   # Replace multiple consecutive dots or spaces
   name = re.sub(r"\s+", " ", name)      # collapse spaces
   name = re.sub(r"\.{2,}", ".", name)   # collapse repeated dots
   # Strip and limit length
   return name.strip()[:max_length]

def parse_sender(from_field: str):
   """
   Dummy parser - replace with your real logic.
   Expected format: 'Sender Name <email@domain>'
   Returns (sender_name, sender_email)
   """
   if not from_field:
      return ("unknown", "unknown")
   parts = from_field.split('<')
   sender_name = parts[0].strip() if parts else "unknown"
   sender_email = parts[1].strip('> ') if len(parts) > 1 else "unknown"
   return (sender_name, sender_email)


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
