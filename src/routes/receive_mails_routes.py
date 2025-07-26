from flask import Blueprint, request, jsonify
from src.methods.receive_mails.receive_mail_helper import assign_mails_to_project
from src.methods.receive_mails.receive_mails_methods import fetch_mail_creds, fetch_mail_from_gmail, fetch_receive_mails
from datetime import datetime


receive_mail_bp = Blueprint("receive_mail_bp", __name__)

@receive_mail_bp.route("/receive-mails", methods=["GET"])
async def get_receive_mails():
    try:
        user_id = request.args.get("user_id", type=int)
        mail_id_name = request.args.get("mail_id_name")
        is_self_sent = request.args.get("is_self_sent")
        date_str = request.args.get("date")  # Expecting format: YYYY-MM-DD
        if date_str:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
            receive_mails = await fetch_receive_mails(user_id, mail_id_name, date_filter, is_self_sent)
            return jsonify(receive_mails), 200
        
        # await fetch_mail_creds()
        # return jsonify({"message": "Mails fetched successfully"}), 200       
    except Exception as e:
        print(f"Error fetching receive mails: {e}")
        return jsonify({"error": e}), 400

@receive_mail_bp.route("/assign-project-to-mails", methods=["POST"])
async def assign_project_to_mails():
    try:
        # Parse JSON body
        data = request.get_json()  # Flask async support
        project_ids = data.get("project_ids")
        mail_ids = data.get("mail_ids", [])
        # Validate inputs
        if not isinstance(project_ids, list) or not all(isinstance(i, int) for i in project_ids):
            return jsonify({"error": "project_id must be an integer"}), 400
        if not isinstance(mail_ids, list) or not all(isinstance(i, int) for i in mail_ids):
            return jsonify({"error": "mail_ids must be a list of integers"}), 400

        response = await assign_mails_to_project(project_ids, mail_ids)
        if response:
            return jsonify({"message": "Mails assigned successfully"}), 200
        else:
            return jsonify({"error": "Failed to assign mails to project"}), 500
    except Exception as e:
        print(f"Error assigning mails: {e}")
        return jsonify({"error": str(e)}), 500

# await fetch_mail_creds()