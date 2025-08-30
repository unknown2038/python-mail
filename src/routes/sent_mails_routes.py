from quart import Blueprint, request, jsonify
from src.methods.sent_mails.sent_mails_methods import fetch_sent_draft_mails
from src.methods.sent_mails.sent_mail_helper import fetch_compose_mail_from_list

sent_mail_bp = Blueprint("sent_mail_bp", __name__)



@sent_mail_bp.route("/sent/sent-draft-mails", methods=["GET"])
async def get_sent_draft_mails():
   try:
      user_id = request.args.get("user_id", type=int)
      mail_id_name = request.args.get("mail_id_name")
      mail_of = request.args.get("mail_of")
      draft_mails = await fetch_sent_draft_mails(user_id, mail_id_name, mail_of)
      return jsonify(draft_mails), 200
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/sent-approval-mails", methods=["GET"])
async def get_sent_approval_mails():
   try:
      mails = await fetch_compose_mail_from_list()
      return jsonify(mails), 200
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400
   

@sent_mail_bp.route("/sent/compose-mail/from-list", methods=["GET"])
async def get_compose_mail_from_list():
   try:
      mails = await fetch_compose_mail_from_list()
      return jsonify(mails), 200
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400

