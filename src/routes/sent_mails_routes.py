from datetime import datetime
from quart import Blueprint, json, request, jsonify
from src.methods.sent_mails.sent_mails_methods import fetch_sent_draft_mails, save_draft_mail
from src.methods.sent_mails.sent_mail_helper import fetch_compose_mail_from_list, to_int_or_none

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
      user_id = request.args.get("user_id", type=int)
      mail_id_name = request.args.get("mail_id_name")
      mail_of = request.args.get("mail_of")
      approval_mails = await fetch_sent_approval_mails(user_id, mail_id_name, mail_of)
      return jsonify(approval_mails), 200
   except Exception as e:
      print(f"Error fetching sent mails: {e}")
      return jsonify({"error": e}), 400


@sent_mail_bp.route("/sent/compose-mail/save-draft-mail", methods=["POST"])
async def store_mail_draft():
   try:
      if "multipart/form-data" in (request.content_type or ""):
            form = await request.form
            files = await request.files
            payload = json.loads(form.get("payload", "{}"))
            attachments = files.getlist("files")   # list of FileStorage
      else:
         payload = await request.get_json(silent=True) or {}
         attachments = []

      id_name = 'INFO' if 'info@designcore.co.in' in payload.get("from") else 'RAJHANS' if 'designcore.rajhans@gmail.com' in payload.get("from") else 'UNKNOWN'
      input_object = {
         'id': to_int_or_none(payload.get("id")),
         'mail_id_name': id_name,
         'from_id': payload.get("from"),
         'to_ids': payload.get("to"),
         'cc_ids': payload.get("cc"),
         'bcc_ids': payload.get("bcc"),
         'subject': payload.get("subject"),
         'body': payload.get("body"),
         'projectId': to_int_or_none(payload.get("project")),
         'path': payload.get("path"),
         'is_draft_mail': True,
         'draft_mail_date': datetime.now(),
         'mail_type': 'MAIL',
         'sentById': payload.get("entry_by")
      }
      return await save_draft_mail(input_object, attachments)
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
      print(payload.get('mail_ids'))
      return jsonify({"message": "Draft mails removed"}), 200
   except Exception as e:
      print(f"Error saving draft mail: {e}")
      return jsonify({"error": e}), 400
