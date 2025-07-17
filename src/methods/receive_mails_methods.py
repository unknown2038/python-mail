import imaplib
from database.db import get_db_connection
from src.methods.employee_methods import fetch_employee_by_id
from src.methods.google_auth import get_google_access_token

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

def fetch_mail_creds():
   conn = get_db_connection()
   if not conn:
      print("No connection to the database")
      return None
   try:
      cur = conn.cursor()
      cur.execute("""
         SELECT username, client_id, client_secret, refresh_token FROM public.mail_credentials WHERE is_active = %s
         """,(True,))
      rows = cur.fetchall()
      creds = []
      if rows:
         for row in rows:
            fetch_mail_from_gmail(row[0], row[1], row[2], row[3])
   except Exception as e:
      print(f"Error fetching mail creds: {e}")
   finally:
      conn.close()



def fetch_mail_from_gmail(username, client_id, client_secret, refresh_token):
   conn = get_db_connection()
   if not username or not client_id or not client_secret or not refresh_token or not conn:
      return None

   try:
      mail_creds = imaplib.IMAP4_SSL('imap.gmail.com', 993)
      access_token = get_google_access_token(client_id, client_secret, refresh_token)
      auth_string = f"user={username}\x01auth=Bearer {access_token.token}\x01\x01"
      mail_creds.authenticate('XOAUTH2', lambda x: auth_string.encode('utf-8'))
   except Exception as e:
      print(f"Error fetching mail from gmail: {e}")

   # try:
      
      # creds = get_google_access_token()
      # service = build('gmail', 'v1', credentials=creds)
      # results = service.users().messages().list(userId='me').execute()
      # messages = results.get('messages', [])
      # return messages
   #    print("fetching mail from gmail")
   # except Exception as e:
   #    print(f"Error fetching mail from gmail: {e}")
   
   
   