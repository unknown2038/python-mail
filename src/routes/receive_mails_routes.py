from flask import Blueprint, request, jsonify
from src.methods.receive_mails_methods import fetch_mail_creds, fetch_mail_from_gmail, fetch_receive_mails

receive_mail_bp = Blueprint("receive_mail_bp", __name__)


@receive_mail_bp.route("/receive-mails", methods=["GET"])
def get_receive_mails():
    user_id = request.args.get("user_id", type=int)
    mail_id_name = request.args.get("mail_id_name")
    fetch_mail_creds()
    return jsonify([]), 200
