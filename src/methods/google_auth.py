from google.oauth2.credentials import Credentials
import google.auth.transport.requests

def get_google_access_token(client_id, client_secret, refresh_token):
   creds = Credentials(
      token=None,
      refresh_token=refresh_token,
      token_uri="https://oauth2.googleapis.com/token",
      client_id=client_id,
      client_secret=client_secret,
      scopes=["https://mail.google.com/"],
   )
   request = google.auth.transport.requests.Request()
   creds.refresh(request)
   return creds