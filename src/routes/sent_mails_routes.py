from datetime import datetime
import os
from pathlib import Path
from quart import Blueprint, json, request, jsonify, send_file
import config
from src.methods.sent_mails.sent_mail_google import fetch_mail_creds
from src.methods.sent_mails.sent_mails_methods import check_mail, check_wp_mail, fetch_draft_mail_by_id, fetch_sent_approval_mails, fetch_sent_draft_mails, fetch_sent_record_mails, fetch_whatsapp_mail_by_id, remove_sent_draft_mails, save_draft_mail, save_whatsapp_mail
from src.methods.sent_mails.sent_mail_helper import fetch_compose_mail_from_list, fetch_mail_attachments, get_save_mail_payload, save_whatsapp_mail_payload, to_int_or_none

sent_mail_bp = Blueprint("sent_mail_bp", __name__)


@sent_mail_bp.route("/sent/sent-draft-mails", methods=["GET"])
async def get_sent_draft_mails():
   try:
      user_id = request.args.get("user_id", type=int)
      mail_id_name = request.args.get("mail_id_name")
      draft_mails = await fetch_sent_draft_mails(user_id, mail_id_name)
      return jsonify(draft_mails), 200
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/sent-approval-mails", methods=["GET"])
async def get_sent_approval_mails():
   try:
      mail_id_name = request.args.get("mail_id_name")
      date_str = request.args.get("date")  # Expecting format: YYYY-MM-DD
      
      if date_str:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
            approval_mails = await fetch_sent_approval_mails(mail_id_name, date_filter)
            return jsonify(approval_mails), 200
      else:
         return jsonify({"error": "No date provided"}), 400
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/sent-record-mails", methods=["GET"])
async def get_sent_record_mails():
   try:
      mail_id_name = request.args.get("mail_id_name")
      user_id = request.args.get("user_id")
      date_str = request.args.get("date")  # Expecting format: YYYY-MM-DD
      
      if date_str:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
            record_mails = await fetch_sent_record_mails(mail_id_name, date_filter, user_id)
            return jsonify(record_mails), 200
      else:
         return jsonify({"error": "No date provided"}), 400
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/compose-mail/save-draft-mail", methods=["POST"])
async def store_mail_draft():
   try:
      input_data = await get_save_mail_payload(request)
      return await save_draft_mail(input_data["input_object"], input_data["attachments"])
   except Exception as e:
      print(f"Error saving draft mail: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/compose-mail/from-list", methods=["GET"])
async def get_compose_mail_from_list():
   try:
      mails = await fetch_compose_mail_from_list()
      return jsonify(mails), 200
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/compose-mail/remove-draft-mails", methods=["POST"])
async def remove_draft_mails():
   try:
      payload = await request.get_json(silent=True) or {}
      mail_ids = [int(x) for x in (payload.get("mail_ids") or []) if isinstance(x, (int, str)) and str(x).strip().lstrip("+-").isdigit()]
      return await remove_sent_draft_mails(mail_ids)
   except Exception as e:
      print(f"Error saving draft mail: {e}")
      return jsonify({"error": e}), 400
   
@sent_mail_bp.route("/sent/compose-mail/edit-mail-compose", methods=["GET"])
async def edit_draft_mails():
   try:
      mail_id = request.args.get("id", type=int)
      compose_mail = await fetch_draft_mail_by_id(mail_id)
      attachments = await fetch_mail_attachments(mail_id, compose_mail.get("mail_id_name"))
      compose_mail["attachments"] = attachments
      return jsonify(compose_mail), 200
   except Exception as e:
      print(f"Error saving draft mail: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/compose-mail/each-attachment", methods=["GET"])
async def get_each_attachment():
   try:
      mail_id = request.args.get("id")
      mail_id_name = request.args.get("mail_id_name")
      file_name = request.args.get("file_name")
      base_path = config.UPLOAD_MAILS_PATH
      file_path = Path(os.path.join(base_path, mail_id_name, mail_id, file_name).replace("\\", "/"))

      if not file_path.exists() or not file_path.is_file():
         return None
      return await send_file(file_path, as_attachment=False)
   except Exception as e:
      print(f"Error sending attachment: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/check-mail", methods=["POST"])
async def check_sent_mail():
   try:
      input_data = await get_save_mail_payload(request)
      return await check_mail(input_data["input_object"], input_data["attachments"])
   except Exception as e:
      print(f"Error checking sent mail: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/whatsapp-mail/save-whatsapp-mail", methods=["POST"])
async def store_whatsapp_mail():
   try:
      input_data = await save_whatsapp_mail_payload(request)
      print(input_data)
      return await save_whatsapp_mail(input_data["input_object"], input_data["attachments"])
   except Exception as e:
      print(f"Error saving draft mail: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/whatsapp-mail/edit-whatsapp-compose", methods=["GET"])
async def get_whatsapp_mail():
   try:
      mail_id = request.args.get("id", type=int)
      compose_mail = await fetch_whatsapp_mail_by_id(mail_id)
      attachments = await fetch_mail_attachments(mail_id, 'WHATSAPP')
      compose_mail["attachments"] = attachments
      return jsonify(compose_mail), 200
   except Exception as e:
      print(f"Error fetching whatsapp mail: {e}")
      return jsonify({"error": e}), 400

@sent_mail_bp.route("/sent/whatsapp-mail/check-whatsapp-mail", methods=["POST"])
async def check_whatsapp_mail():
   try:
      input_data = await save_whatsapp_mail_payload(request)
      print(input_data)
      return await check_wp_mail(input_data["input_object"], input_data["attachments"])
   except Exception as e:
      print(f"Error checking sent mail: {e}")
      return jsonify({"error": e}), 400