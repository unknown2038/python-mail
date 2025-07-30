import re
from flask import Blueprint, request, jsonify
from src.methods.receive_mails.receive_mail_helper import (
    assign_mails_to_project,
    modify_receive_mails,
)
from src.methods.receive_mails.receive_mails_methods import (
    fetch_mail_creds,
    fetch_gmail_mails,
    fetch_receive_mails,
    move_to_trash,
    remove_from_trash,
    search_any_mail,
)
from datetime import datetime


receive_mail_bp = Blueprint("receive_mail_bp", __name__)


@receive_mail_bp.route("/receive/receive-mails", methods=["GET"])
async def get_receive_mails():
    try:
        user_id = request.args.get("user_id", type=int)
        mail_id_name = request.args.get("mail_id_name")
        is_self_sent = request.args.get("is_self_sent")
        mail_of = request.args.get("mail_of")
        date_str = request.args.get("date")  # Expecting format: YYYY-MM-DD
        if date_str:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
            receive_mails = await fetch_receive_mails(
                user_id, mail_id_name, date_filter, is_self_sent, mail_of
            )
            result = modify_receive_mails(receive_mails)
            return jsonify(result), 200
        else:
            return jsonify({"error": "No date provided"}), 400
    except Exception as e:
        print(f"Error fetching receive mails: {e}")
        return jsonify({"error": e}), 400


@receive_mail_bp.route("/receive/mail-creds", methods=["GET"])
async def get_mail_creds():
    try:
        mail_creds = await fetch_mail_creds()
        return jsonify(mail_creds), 200
    except Exception as e:
        print(f"Error fetching mail creds: {e}")
        return jsonify({"error": e}), 400


@receive_mail_bp.route("/receive/assign-project-to-mails", methods=["POST"])
async def assign_project_to_mails():
    try:
        # Parse JSON body
        data = request.get_json()  # Flask async support
        project_ids = data.get("project_ids")
        mail_ids = data.get("mail_ids", [])
        # Validate inputs
        if not isinstance(project_ids, list) or not all(
            isinstance(i, int) for i in project_ids
        ):
            return jsonify({"error": "project_id must be an integer"}), 400
        if not isinstance(mail_ids, list) or not all(
            isinstance(i, int) for i in mail_ids
        ):
            return jsonify({"error": "mail_ids must be a list of integers"}), 400

        response = await assign_mails_to_project(project_ids, mail_ids)
        if response:
            return jsonify({"message": "Mails assigned successfully"}), 200
        else:
            return jsonify({"error": "Failed to assign mails to project"}), 500
    except Exception as e:
        print(f"Error assigning mails: {e}")
        return jsonify({"error": str(e)}), 500


@receive_mail_bp.route("/receive/import-mails-from-gmail", methods=["POST"])
async def import_mails_from_gmail():
    try:
        # Parse JSON body
        data = request.get_json()  # Flask async support
        date_str = data.get("date")  # Expecting format: YYYY-MM-DD
        if date_str:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            date_filter = date_obj.strftime("%d-%b-%Y")
            await fetch_gmail_mails(date_filter)
            return jsonify({"message": "Mails imported successfully"}), 200
        else:
            return jsonify({"error": "Failed to import mails"}), 500
    except Exception as e:
        print(f"Error importing mails: {e}")
        return jsonify({"error": str(e)}), 500

@receive_mail_bp.route("/receive/search-mail", methods=["GET"])
async def search_mail():
    try:
        search_query = request.args.get("search_query")
        user_id = request.args.get("user_id", type=int)
        mail_id_name = request.args.get("mail_id_name")

        receive_mails = await search_any_mail(search_query, user_id, mail_id_name)
        result = modify_receive_mails(receive_mails)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error searching mail: {e}")
        return jsonify({"error": str(e)}), 500

@receive_mail_bp.route("/receive/move-to-trash-mails", methods=["POST"])
async def move_to_trash_mails():
    try:
        data = request.get_json()  # Flask async support
        mail_ids = data.get("mail_ids")
        # Validate inputs
        if not isinstance(mail_ids, list) or not all(
            isinstance(i, int) for i in mail_ids
        ):
            return jsonify({"error": "mail_ids must be a list of integers"}), 400
        
        await move_to_trash(mail_ids)
        return jsonify({"message": "Mails moved to trash successfully"}), 200
    except Exception as e:
        print(f"Error moving mails to trash: {e}")
        return jsonify({"error": str(e)}), 500

@receive_mail_bp.route("/receive/remove-from-trash-mails", methods=["POST"])
async def remove_from_trash_mails():
    try:
        data = request.get_json()  # Flask async support
        mail_ids = data.get("mail_ids")
        # Validate inputs
        if not isinstance(mail_ids, list) or not all(
            isinstance(i, int) for i in mail_ids
        ):
            return jsonify({"error": "mail_ids must be a list of integers"}), 400
        
        await remove_from_trash(mail_ids)
        return jsonify({"message": "Mails moved to trash successfully"}), 200
    except Exception as e:
        print(f"Error moving mails to trash: {e}")
        return jsonify({"error": str(e)}), 500