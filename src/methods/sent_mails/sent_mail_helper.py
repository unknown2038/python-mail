import asyncio
from datetime import datetime
import imaplib
import mimetypes
import shutil
from quart import json, jsonify
import os
from pathlib import Path
from werkzeug.utils import secure_filename
import config
from database.db_pool import execute_one, fetch_all, fetch_one
from src.methods.sent_mails.sent_mail_google import send_gmail_with_attachments_async
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
      for p in Path(id_folder.replace("\\", "/")).iterdir():
         if p.is_file() or p.is_symlink():
            p.unlink()
         elif p.is_dir():
            shutil.rmtree(p)
      
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


async def fetch_mail_attachments(mail_id, mail_id_name, base_path=config.UPLOAD_MAILS_PATH):
   try:
      # 1) find Base folder
      account_folder = os.path.join(base_path, sanitize_filename(mail_id_name))
      account_folder = os.path.normpath(account_folder)
      if not os.path.exists(account_folder) or not os.path.isdir(account_folder):
         return []
      
      # 2) find ID Folder
      id_folder = os.path.join(account_folder, str(mail_id))
      id_folder = os.path.normpath(id_folder)
      if not os.path.exists(id_folder) or not os.path.isdir(id_folder):
         return []
      
      # 3) find attachments
      items = []
      for p in Path(id_folder.replace("\\", "/")).iterdir():
         if p.is_file():
               mime, _ = mimetypes.guess_type(p.name)
               items.append({
                  "name": p.name,
                  "size": p.stat().st_size,
                  "mtime": p.stat().st_mtime,
                  "type": mime or "application/octet-stream",
               })
      return items

   except Exception as e:
      print(f"Error fetching mail attachments: {e}")
      return jsonify({"error": e}), 400

async def get_save_mail_payload(request):
   try:
      if "multipart/form-data" in (request.content_type or ""):
            form = await request.form
            files = await request.files
            payload = json.loads(form.get("payload", "{}"))
            attachments = files.getlist("files")   # list of FileStorage
      else:
         payload = await request.get_json(silent=True) or {}
         attachments = []
   
      id_name = 'INFO' if 'info@designcore.co.in' in payload.get("from") else 'RAJHANS' if 'designcore.rajhans@gmail.com' in payload.get("from") else 'UNKNOWN'
      return {
         "input_object": {
            'id': to_int_or_none(payload.get("id")),
            'mail_id_name': id_name,
            'from_id': payload.get("from"),
            'to_ids': payload.get("to"),
            'cc_ids': payload.get("cc"),
            'bcc_ids': payload.get("bcc"),
            'subject': payload.get("subject"),
            'body': payload.get("body"),
            'projectId': to_int_or_none(payload.get("project")),
            'path': payload.get("path"),
            'is_draft_mail': payload.get("is_draft"),
            'draft_mail_date': datetime.now(),
            'mail_type': 'MAIL',
            'sentById': payload.get("entry_by"),
            'checkById': payload.get("check_by"),
            'is_check': payload.get("is_check"),
            'is_approve': payload.get("is_approve"),
            'remark': payload.get("remark"),
         },
         "attachments": attachments
      }
   except Exception as e:
      print(f"Error getting save mail payload: {e}")
      return jsonify({"error": e}), 400

async def send_mail_to_gmail(id: int):
   try:  
      query = """
         select id, mail_id_name, from_id, to_ids, cc_ids, bcc_ids, subject, body from public.mail_sent where id = $1;
      """
      mail = await fetch_one(query, id)
      attachments = await fetch_sent_mail_attachment_file_paths(id, mail.get("mail_id_name"))
      CID = "mail_compose"
      ASSET_IN_HTML = "assets/images/mail_compose.png"
      INLINE_IMAGE_PATH = "/mnt/data/python-mail/src/shared/assets/mail_compose.png"  # <-- put the real absolute path here
      # INLINE_IMAGE_PATH = "src/shared/assets/mail_compose.png"  # <-- put the real absolute path here

      html_for_email = mail.get("body").replace(ASSET_IN_HTML, f"cid:{CID}")
      
      msg_id = await send_gmail_with_attachments_async(
            email=mail.get("from_id"),
            to=mail.get("to_ids"),
            cc=mail.get("cc_ids"),
            bcc=mail.get("bcc_ids"),
            subject=mail.get("subject"),
            text_body=None,
            html_body=html_for_email,
            attachments=attachments,
            from_display_name='Manish Choksi DesignCore',
            cid_images={CID: INLINE_IMAGE_PATH},
      )
      if "error" in msg_id:
         obj = json.loads(msg_id)
         query = """ UPDATE public.mail_sent SET gmail_remark = $1 WHERE id = $2; """
         error = obj.get("error")
         await execute_one(query, error.get("message"), id)
         return dict(id=None) 
      else:
         return dict(id=msg_id)
      
   except Exception as e:
      print(f"Error sending mail to gmail: {e}")
      return jsonify({"error": e}), 400

async def sent_to_gmail_queue(mail_id):
   try:
      message = await send_mail_to_gmail(mail_id)
      if message.get("id") is None:
         return False
      else:
         query = """
            UPDATE public.mail_sent SET message_id = $1 WHERE id = $2;
         """
         await execute_one(query, message.get("id"), mail_id)
         return True 
   except Exception as e:
      print(f"Error sending to gmail queue: {e}")
      return jsonify({"error": e}), 400


async def fetch_sent_mail_attachment_file_paths(mail_id: int, mail_id_name: str, base_path=config.UPLOAD_MAILS_PATH):
   try:
      # 1) find Base folder
      account_folder = os.path.join(base_path, sanitize_filename(mail_id_name))
      account_folder = os.path.normpath(account_folder)
      if not os.path.exists(account_folder) or not os.path.isdir(account_folder):
         return []
      
      # 2) find ID Folder
      id_folder = os.path.join(account_folder, str(mail_id))
      id_folder = os.path.normpath(id_folder)
      if not os.path.exists(id_folder) or not os.path.isdir(id_folder):
         return []
      
      return [str(p) for p in Path(id_folder.replace("\\", "/")).rglob("*") if p.is_file()]
   
   except Exception as e:
      print(f"Error fetching sent mail attachment file paths: {e}")
      return jsonify({"error": e}), 400

