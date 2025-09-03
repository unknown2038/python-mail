from datetime import datetime
from quart import jsonify
from src.methods.receive_mails.receive_mails_methods import fetch_gmail_mails
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def cron_fetch_job():
   try:
      print("Gmail mail fetch started at", datetime.now())
      date_obj = datetime.now()
      date_str = date_obj.strftime("%Y-%m-%d")   # "2025-09-03"
      if date_str:
         date_filter = date_obj.strftime("%d-%b-%Y")  # "03-Sep-2025"
         await fetch_gmail_mails(date_filter)
         print("Gmail mail fetch completed at", datetime.now())
         return jsonify({"message": "Mails imported successfully"}), 200
      else:
         print("Cron job failed")
         return jsonify({"error": "Failed to import mails"}), 500
   except Exception as e:
      print(f"Error in cron job: {e}")


def init_scheduler():
   scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")  # set your TZ if needed
   # run every 5 minutes
   print("Scheduler started")
   scheduler.add_job(cron_fetch_job, "interval", minutes=5)
   scheduler.start()