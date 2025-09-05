import traceback
from googleapiclient.http import HttpError
from quart import jsonify
from database.db_pool import fetch_one
import config
import os
import base64
import mimetypes
import asyncio
from typing import Iterable, Tuple, List, Optional, Union
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.header import Header
from email.utils import formataddr, make_msgid
from email import encoders
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from email.mime.image import MIMEImage
from pathlib import Path
import re

# -------------------------------
# Creds fetch (ASYNC) + builders
# -------------------------------


async def fetch_mail_creds(email: str) -> Optional[dict]:
   """
   Returns: {"username","client_id","client_secret","refresh_token","name"} or None
   """
   try:
      query = """
         SELECT username, client_id, client_secret, refresh_token, name
         FROM public.mail_credentials
         WHERE is_active = $1 AND username = $2
      """
      row = await fetch_one(query, True, email)  # (is_active=True, username=email)
      return dict(row) if row else None
   except Exception as e:
      print(f"Error fetching mail creds: {e}")
      return None


def _make_credentials_from_dict(cred: dict) -> Credentials:
   try:
      creds = Credentials(
         None,
         refresh_token=cred["refresh_token"],
         client_id=cred["client_id"],
         client_secret=cred["client_secret"],
         token_uri=config.TOKEN_URI,
      )
      # Blocking refresh – call via asyncio.to_thread
      creds.refresh(Request())
      return creds
   except Exception as e:
      print(f"Error making credentials from dict: {e}")
      return None

def _build_service(creds: Credentials):
   # googleapiclient discovery build is blocking; call via asyncio.to_thread
   return build("gmail", "v1", credentials=creds)


async def gmail_service_from_refresh_async(email: str):
   """
   Async builder: fetch creds (await!), then build the service off-thread.
   """
   cred = await fetch_mail_creds(email)
   if not cred:
      raise ValueError(f"No active Gmail OAuth credentials found for {email}")

   creds = await asyncio.to_thread(_make_credentials_from_dict, cred)
   service = await asyncio.to_thread(_build_service, creds)
   return service


# -------------------------------
# File helpers
# -------------------------------


def _guess_mime_type(path: str) -> Tuple[str, str]:
   ctype, encoding = mimetypes.guess_type(path)
   if ctype is None or encoding is not None:
      ctype = "application/octet-stream"
   maintype, subtype = ctype.split("/", 1)
   return maintype, subtype


def _attach_file(msg: MIMEMultipart, file_path: str):
   maintype, subtype = _guess_mime_type(file_path)
   with open(file_path, "rb") as f:
      part = MIMEBase(maintype, subtype)
      part.set_payload(f.read())
      encoders.encode_base64(part)

   filename = os.path.basename(file_path)
   part.add_header(
      "Content-Disposition",
      "attachment",
      filename=(Header(filename, "utf-8").encode()),
   )
   msg.attach(part)


def _collect_files_sync(
   path_or_paths: Iterable[str],
   include_extensions: Optional[Iterable[str]] = None,
) -> List[str]:
   results: List[str] = []
   if isinstance(path_or_paths, (str, bytes, os.PathLike)):
      path_or_paths = [path_or_paths]  # normalize

   exts = set(e.lower() for e in include_extensions) if include_extensions else None

   for entry in path_or_paths:
      entry = str(entry)
      if os.path.isdir(entry):
         for root, _, files in os.walk(entry):
               for name in files:
                  fp = os.path.join(root, name)
                  if exts and not any(name.lower().endswith(x) for x in exts):
                     continue
                  results.append(fp)
      elif os.path.isfile(entry):
         name = os.path.basename(entry)
         if exts and not any(name.lower().endswith(x) for x in exts):
               continue
         results.append(entry)
      else:
         # silently skip non-existent entries
         continue
   return results


def _build_mime_message_sync(
   *,
   from_display_name: Optional[str],
   to: List[str],
   cc: Optional[List[str]],
   bcc: Optional[List[str]],
   subject: str,
   parent_message_id: str,
   text_body: Optional[str],
   html_body: Optional[str],
   attachments: Optional[List[str]],
   cid_images: Optional[dict] = None,
) -> MIMEMultipart:
   msg = MIMEMultipart("mixed")
   
   if from_display_name:
      # Gmail infers actual address from credentials. Friendly name is OK.
      msg["From"] = formataddr((str(Header(from_display_name, "utf-8")), ""))

   if to:
      msg["To"] = ", ".join(to)
   if cc:
      msg["Cc"] = ", ".join(cc)
   if bcc:
      # Bcc is allowed in MIME; Gmail strips it on delivery to other recipients.
      msg["Bcc"] = ", ".join(bcc)

   msg["Subject"] = str(Header(subject, "utf-8"))
   msg["Message-ID"] = make_msgid()
   if parent_message_id:
      msg["In-Reply-To"] = parent_message_id
      msg["References"] = parent_message_id   

   # Body part (alternative: text + html)
   alt = MIMEMultipart("alternative")
   if html_body or cid_images:
      related = MIMEMultipart("related")

      if html_body:
         related.attach(MIMEText(html_body, "html", "utf-8"))

      if cid_images:
         for cid, img_path in cid_images.items():
               if not os.path.isfile(img_path):
                  raise FileNotFoundError(f"Inline image not found: {img_path}")

               # determine subtype
               ctype, enc = mimetypes.guess_type(img_path)
               maintype, subtype = ("image", "png")
               if ctype and "/" in ctype:
                  m, s = ctype.split("/", 1)
                  if m == "image":
                     maintype, subtype = m, s

               with open(img_path, "rb") as f:
                  data = f.read()

               img = MIMEImage(data, _subtype=subtype)
               img.add_header("Content-ID", f"<{cid}>")  # must be in angle brackets
               img.add_header("Content-Disposition", "inline", filename=os.path.basename(img_path))
               # X-Attachment-Id helps Gmail match cid sometimes
               img.add_header("X-Attachment-Id", cid)
               related.attach(img)

      # Place related into alternative
      alt.attach(related)

   # Attach the alternative block into the mixed top-level
   msg.attach(alt)

   # Attachments
   for fp in attachments or []:
      if os.path.isfile(fp):
         _attach_file(msg, fp)
      else:
         raise FileNotFoundError(f"Attachment not found: {fp}")

   return msg

def _sanitize_error_message(msg: str) -> str:
   patterns = [
      r'("access_token"\s*:\s*")[^"]+(")',
      r'("refresh_token"\s*:\s*")[^"]+(")',
      r'client_secret\s*[:=]\s*\S+',
      r'GOCSPX-[A-Za-z0-9_\-]+',
   ]
   red = msg or ""
   for pat in patterns:
      red = re.sub(pat, '***REDACTED***', red, flags=re.IGNORECASE)
   return red

def _truncate(text: str, limit: int = 2000) -> str:
   if text and len(text) > limit:
      return text[:limit - 10] + "…[trunc]"
   return text

def _send_gmail_sync(service, raw: str) -> str:
   try:
      sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
      
      # Read only the Message-Id header
      meta = service.users().messages().get(
         userId="me",
         id=sent["id"],
         format="metadata",
         metadataHeaders=["Message-Id"]
      ).execute()
      headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
      return headers.get("Message-Id")

   except HttpError as e:
      # Google API error → serialize JSON and save
      try:
         err_content = e.content.decode() if hasattr(e, "content") else str(e)
      except Exception:
         err_content = str(e)
      clean = _truncate(_sanitize_error_message(err_content))
      return clean


   except Exception as e:
      tb = traceback.format_exc(limit=2)
      clean = _truncate(_sanitize_error_message(f"{e} | {tb}"))
      return clean


# -------------------------------
# Async wrappers
# -------------------------------


async def collect_files_async(
   path_or_paths: Union[str, Iterable[str]],
   *,
   include_extensions: Optional[Iterable[str]] = None,
) -> List[str]:
   return await asyncio.to_thread(
      _collect_files_sync, path_or_paths, include_extensions
   )


async def build_mime_message_async(
   *,
   from_display_name: Optional[str],
   to: List[str],
   cc: Optional[List[str]],
   bcc: Optional[List[str]],
   subject: str,
   parent_message_id: str,
   text_body: Optional[str],
   html_body: Optional[str],
   attachments: Optional[List[str]],
   cid_images: Optional[dict] = None,
) -> MIMEMultipart:
   return await asyncio.to_thread(
      _build_mime_message_sync,
      from_display_name=from_display_name,
      to=to,
      cc=cc,
      bcc=bcc,
      subject=subject,
      parent_message_id=parent_message_id,
      text_body=text_body,
      html_body=html_body,
      attachments=attachments,
      cid_images=cid_images,
   )


# -------------------------------
# Public async API (unchanged signature)
# -------------------------------


async def send_gmail_with_attachments_async(
   *,
   email: str,
   to: Iterable[str],
   cc: Optional[Iterable[str]] = None,
   bcc: Optional[Iterable[str]] = None,
   subject: str,
   parent_message_id: str,
   text_body: Optional[str] = None,
   html_body: Optional[str] = None,
   attachments: Optional[Iterable[str]] = None,
   from_display_name: Optional[str] = None,
   cid_images: Optional[dict] = None,
) -> str:
   """
   Build & send an email via Gmail API using credentials looked up by 'email'.
   """
   # 1) Build Gmail service (fetch creds ASYNC, then build off-thread)
   service = await gmail_service_from_refresh_async(email)

   # 2) Prepare lists
   to_list = list(to)
   cc_list = list(cc) if cc else None
   bcc_list = list(bcc) if bcc else None
   att_list = list(attachments) if attachments else None

   # 3) Build MIME off-thread
   msg = await build_mime_message_async(
      from_display_name=from_display_name,
      to=to_list,
      cc=cc_list,
      bcc=bcc_list,
      subject=subject,
      parent_message_id=parent_message_id,
      text_body=text_body,
      html_body=html_body,
      attachments=att_list,
      cid_images=cid_images,
   )

   # 4) Enforce Gmail raw size limit (~35 MB)
   GMAIL_SIZE_LIMIT_BYTES = 35 * 1024 * 1024
   raw_bytes = msg.as_bytes()
   if len(raw_bytes) > GMAIL_SIZE_LIMIT_BYTES:
      raise ValueError(
         f"Raw message is {len(raw_bytes)/1024/1024:.2f} MB; must be <= ~35 MB. "
         f"Split/compress attachments or send multiple emails."
      )

   # 5) Send off-thread
   raw = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")
   msg_id = await asyncio.to_thread(_send_gmail_sync, service, raw)
   return msg_id
