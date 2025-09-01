import asyncio
import imaplib
from quart import jsonify
import os
from pathlib import Path
from werkzeug.utils import secure_filename
import config
from database.db_pool import fetch_all
from src.methods.receive_mails.receive_mail_file_manager import sanitize_filename



to_int_or_none = lambda v: None if v is None or (isinstance(v,str) and (s:=v.strip()).lower() in ("","null","none")) else (int(v) if str(v).strip().lstrip("+-").isdigit() else None)

async def fetch_compose_mail_from_list() -> list[dict]:
   try:
      query = """
         SELECT username, name FROM public.mail_credentials WHERE is_active = $1;
      """
      rows = await fetch_all(query, True)
      return [r[0] for r in rows]
   except Exception as e:
      print(f"Error fetching compose mail from list: {e}")
      return jsonify({"error": e}), 400
   


async def save_sent_mail_attachments(input_object, mail_id, attachments, base_path=config.UPLOAD_MAILS_PATH):
   try:
      
      saved = []
      # 1) Base account folder
      account_folder = os.path.join(base_path, sanitize_filename(input_object.get("mail_id_name")))
      account_folder = os.path.normpath(account_folder)
      os.makedirs(account_folder, exist_ok=True)
      
      # 2) Make ID Folder
      id_folder = os.path.join(account_folder, str(mail_id))
      id_folder = os.path.normpath(id_folder)
      os.makedirs(id_folder, exist_ok=True)
      
      # 3) Save attachments (async)
      for attachment in attachments:
         if not attachment or not getattr(attachment, "filename", None):
            continue
         name = secure_filename(attachment.filename)
         if not name:
            continue
         target = Path(id_folder) / name
         try: target.unlink()  # remove if exists
         except FileNotFoundError: pass
         await attachment.save(target)  # overwrite
         
         saved.append(str(target))
   except Exception as e:
      print(f"Error saving sent mail attachments: {e}")
      return jsonify({"error": e}), 400