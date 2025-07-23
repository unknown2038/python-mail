import pytz
import email.utils


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
      
      # Safely extract HTML and plain parts
      html_part = mail_content.get_body('html')
      plain_part = mail_content.get_body('plain')

      html_content = html_part.get_content() if html_part else ''
      plain_content = plain_part.get_content() if plain_part else ''

      # Convert date to IST (if exists)
      date_header = mail_content.get('Date')
      ist_date = convert_email_date_to_ist(date_header) if date_header else None
      
      attachment_count = 0
      for part in mail_content.walk():
         content_disposition = str(part.get("Content-Disposition") or "")
         if "attachment" in content_disposition.lower():
               attachment_count += 1
   
      return {
         "mail_id": username,
         "mail_id_name": name,
         "is_self_sent_mail": is_sent,
         "from_id": mail_content.get('From') or None,
         "to_ids": split_emails(mail_content.get('To')),
         "cc_ids": split_emails(mail_content.get('Cc')),
         "bcc_ids": split_emails(mail_content.get('Bcc')),
         "subject": mail_content.get('Subject') or '',
         "html":html_content,
         "body": plain_content,
         "message_id": mail_content['Message-ID'] or '',
         "receive_date": ist_date,
         "in_reply_to": None if not mail_content.get('In-Reply-To') or mail_content.get('In-Reply-To').strip() in ("", "<>") else mail_content.get('In-Reply-To').strip(),
         "references": None if not mail_content.get('References') or mail_content.get('References').strip() in ("", "<>") else mail_content.get('References').strip(),
         "attachments": attachment_count,
      }
   except Exception as e:
      print(f"Error while making mail object: {e}")
      return None
