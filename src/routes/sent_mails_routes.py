from quart import Blueprint, request, jsonify
from src.methods.sent_mails.sent_mail_helper import fetch_compose_mail_from_list

sent_mail_bp = Blueprint("sent_mail_bp", __name__)


@sent_mail_bp.route("/sent/compose-mail/from-list", methods=["GET"])
async def get_compose_mail_from_list():
   try:
      mails = await fetch_compose_mail_from_list()
      return jsonify(mails), 200
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400
