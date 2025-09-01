import asyncio
from datetime import datetime
import imaplib
from quart import jsonify

from database.db_pool import execute_one, execute_one_returning, fetch_all
from src.methods.sent_mails.sent_mail_helper import save_sent_mail_attachments, to_int_or_none
from src.methods.employee_methods import fetch_employee_by_id


async def fetch_sent_draft_mails(user_id, mail_id_name, mail_of):
   try:
      query = """
         select 
            sm.id, sm.mail_id_name, sm.from_id, sm.to_ids, sm.cc_ids, sm.bcc_ids, sm.subject, sm.body, sm.is_draft_mail, sm.draft_mail_date::date as draft_create_date, sm.path,
            (ejd.first_name || ' ' || ejd.last_name) AS sent_by_name, e.id as sent_by_id, p.id as project_id, (p.project_name || ' - ' || pcd.first_name || ' ' || pcd.last_name) as project_name
            from public.mail_sent sm 
            left join public.projects p 
            on p.id = sm."projectId"
            left join public.project_client_details pcd
            on pcd.id = p."projectClientId"
            left join public.employees e
            on e.id = sm."sentById"
            left join public.employee_job_details ejd
            on ejd.id = e."detailsId"
         where sm.is_draft_mail = $1
            and sm.mail_id_name = $2
            and e.id = $3
         order by sm.draft_mail_date asc;
      """
      mails = await fetch_all(query, (mail_of == 'Draft'), mail_id_name, user_id)
      return [dict(r) for r in mails]
   except Exception as e:
      print(f"Error fetching sent draft mails: {e}")
      return jsonify({"error": e}), 400


async def fetch_sent_approval_mails(user_id, mail_id_name, mail_of):
   try:
      return []
   except Exception as e:
      print(f"Error fetching sent approval mails: {e}")
      return jsonify({"error": e}), 400


async def save_draft_mail(input_object, attachments):
   try:
      
      if input_object.get("id"):
         # Update the draft mail
         pass
      else:
         # Save the draft mail
         query = """
            insert into public.mail_sent (mail_id_name, from_id, to_ids, cc_ids, bcc_ids, subject, body, is_draft_mail, draft_mail_date, path, "projectId","sentById", mail_type)
            values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            returning id;
         """
         mail_id = await execute_one_returning(query, 
            input_object.get("mail_id_name"), 
            input_object.get("from_id"), 
            input_object.get("to_ids"), 
            input_object.get("cc_ids"), 
            input_object.get("bcc_ids"), 
            input_object.get("subject"), 
            input_object.get("body"), 
            input_object.get("is_draft_mail"), 
            input_object.get("draft_mail_date"), 
            input_object.get("path"), 
            input_object.get("projectId"), 
            input_object.get("sentById"), 
            input_object.get("mail_type"))
         
         if len(attachments) > 0:
            await save_sent_mail_attachments(input_object, mail_id, attachments)
         else:
            pass

      return jsonify({"message": "Draft mail saved successfully"}), 200
   except Exception as e:
      print(f"Error saving draft mail: {e}")
      return jsonify({"error": e}), 400