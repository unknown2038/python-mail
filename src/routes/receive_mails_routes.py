from flask import Blueprint, request, jsonify
from src.methods.receive_mails.receive_mails_methods import fetch_mail_creds, fetch_mail_from_gmail, fetch_receive_mails
from datetime import datetime


receive_mail_bp = Blueprint("receive_mail_bp", __name__)

@receive_mail_bp.route("/receive-mails", methods=["GET"])
async def get_receive_mails():
    try:
        user_id = request.args.get("user_id", type=int)
        mail_id_name = request.args.get("mail_id_name")
        date_str = request.args.get("date")  # Expecting format: YYYY-MM-DD
        if date_str:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
            receive_mails = await fetch_receive_mails(user_id, mail_id_name, date_filter)
            return jsonify(receive_mails), 200
    except Exception as e:
        print(f"Error fetching receive mails: {e}")
        return jsonify({"error": e}), 400



# await fetch_mail_creds()