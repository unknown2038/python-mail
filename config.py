HOST = "127.0.0.1"
PORT = 83
DEBUG = True

DATABASE_HOST = "10.254.254.242"
# DATABASE_HOST = "115.96.27.93"
DATABASE_PORT = 5432
DATABASE_NAME = "designcore_execution"
DATABASE_USER = "root"
DATABASE_PASSWORD = "URMANISH123"

RECEIVE_FOLDER_PATH = '/mnt/backup/Upload/New_Mail'
UPLOAD_MAILS_PATH = '/mnt/backup/Upload/New_Sent_Mail'


GMAIL_SIZE_LIMIT_BYTES = 24 * 1024 * 1024  # ~24 MB raw limit

TOKEN_URI = "https://oauth2.googleapis.com/token"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"