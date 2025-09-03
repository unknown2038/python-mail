import asyncio
from datetime import datetime
import imaplib
import os
from pathlib import Path
import shutil
from quart import jsonify

import config
from database.db_pool import execute_one, execute_one_returning, executemany, fetch_all, fetch_one
from src.methods.sent_mails.sent_mail_helper import fetch_sent_mail_attachment_file_paths, save_sent_mail_attachments, sent_to_gmail_queue, to_int_or_none


async def fetch_sent_draft_mails(user_id, mail_id_name):
   try:
      query = """
         select 
            sm.id, sm.mail_id_name, sm.mail_type, sm.from_id, sm.to_ids, sm.cc_ids, sm.bcc_ids, sm.subject, sm.body, sm.is_draft_mail, sm.draft_mail_date::date as draft_create_date, sm.path,
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
      mails = await fetch_all(query, True, mail_id_name, user_id)
      return [dict(r) for r in mails]
   except Exception as e:
      print(f"Error fetching sent draft mails: {e}")
      return jsonify({"error": e}), 400

async def fetch_sent_approval_mails(mail_id_name, date_filter):
   try:
      query = """
         select 
            sm.id, sm.mail_id_name, sm.from_id, sm.to_ids, sm.cc_ids, sm.bcc_ids, sm.subject, sm.body, sm.path, sm."createdAt"::date as entry_date, sm.status,sm.approval_rejection_date, sm.approval_rejection_remark, sm.mail_type, 
            (checkerDetails.first_name || ' ' || checkerDetails.last_name) AS check_by_name, checker.id as check_by_id, 
            (ejd.first_name || ' ' || ejd.last_name) AS entry_by_name, e.id as entry_by_id, 
            p.id as project_id, (p.project_name || ' - ' || pcd.first_name || ' ' || pcd.last_name) as project_name
            from public.mail_sent sm 
            left join public.projects p 
            on p.id = sm."projectId"
            left join public.project_client_details pcd
            on pcd.id = p."projectClientId"
            left join public.employees e
            on e.id = sm."sentById"
            left join public.employee_job_details ejd
            on ejd.id = e."detailsId"
            left join public.employees checker
            on checker.id = sm."checkById"
            left join public.employee_job_details checkerDetails
            on checkerDetails.id = checker."detailsId"
         where sm.is_draft_mail = false
            and sm.status = 'In Queue'
            and sm.mail_id_name = $1
            and sm."createdAt"::date = $2
         order by sm."createdAt" DESC;
         """
      mails = await fetch_all(query, mail_id_name, date_filter)
      return [dict(r) for r in mails]
   except Exception as e:
      print(f"Error fetching sent mail approval list: {e}")
      return jsonify({"error": e}), 400

async def save_draft_mail(input_object, attachments):
   try:
      mail_id = None
      if input_object.get("id"):
         # Update the draft mail
         query = """
            update public.mail_sent set 
               mail_id_name = $1, 
               from_id = $2, 
               to_ids = $3, 
               cc_ids = $4, 
               bcc_ids = $5, 
               subject = $6, 
               body = $7, 
               is_draft_mail = $8, 
               draft_mail_date = $9, 
               path = $10, 
               "projectId" = $11,
               "sentById" = $12, 
               mail_type = $13
            where id = $14
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
            input_object.get("mail_type"),
            input_object.get("id"))
         
         if len(attachments) > 0:
            await save_sent_mail_attachments(input_object, mail_id, attachments)
         else:
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

async def fetch_draft_mail_by_id(mail_id):
   try:
      query = """
         select 
            sm.id, sm.mail_id_name, sm.from_id, sm.to_ids, sm.cc_ids, sm.bcc_ids, sm.subject, sm.body, sm.path,p.id as project_id, e.id as entry_by
            from public.mail_sent sm 
            left join public.projects p 
            on p.id = sm."projectId"
            left join public.project_client_details pcd
            on pcd.id = p."projectClientId"
            left join public.employees e
            on e.id = sm."sentById"
         where sm.id = $1;
      """
      mail = await fetch_one(query, mail_id)
      return dict(mail)
   except Exception as e:
      print(f"Error fetching draft mail by id: {e}")
      return jsonify({"error": e}), 400
   
async def remove_sent_draft_mails(mail_ids):
   try:
      find_query = """
         SELECT mail_id_name, id FROM public.mail_sent WHERE id = ANY($1::bigint[]);
      """
      data = await fetch_all(find_query, mail_ids)
      for d in data:
         await remove_sent_mail_attachments(d.get("id"), d.get("mail_id_name"))
         
      query = """
         DELETE FROM public.mail_sent WHERE id = ANY($1::bigint[]);
      """
      await execute_one(query, mail_ids)
      return jsonify({"message": "Draft mails removed Successfully" }), 200
   except Exception as e:
      print(f"Error removing draft mails: {e}")
      return jsonify({"error": e}), 400

async def remove_sent_mail_attachments(mail_id, mail_id_name):
   try:
      mail_folder = Path(os.path.join(config.UPLOAD_MAILS_PATH, mail_id_name, str(mail_id)).replace("\\", "/"))
      if Path(mail_folder).exists():
         shutil.rmtree(Path(mail_folder))
      return jsonify({"message": "Sent mail attachments removed Successfully" }), 200
   except Exception as e:
      print(f"Error removing sent mail attachments: {e}")
      return jsonify({"error": e}), 400

async def check_mail(input_object, attachments):
   try:
      query = """
         update public.mail_sent set 
            mail_id_name = $1, 
            from_id = $2, 
            to_ids = $3, 
            cc_ids = $4, 
            bcc_ids = $5, 
            subject = $6, 
            body = $7, 
            is_draft_mail = $8, 
            draft_mail_date = $9, 
            path = $10, 
            "projectId" = $11,
            "sentById" = $12, 
            mail_type = $13
         where id = $14
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
         input_object.get("mail_type"),
         input_object.get("id"))
      
      if len(attachments) > 0:
         await save_sent_mail_attachments(input_object, mail_id, attachments)

      if input_object.get("is_approve"):
         status = await sent_to_gmail_queue(input_object.get("id"))
         if status:
            query = """
               update public.mail_sent set 
                  "checkById" = $1, 
                  approval_rejection_date = $2,
                  approval_rejection_remark = $3,
                  status = $4
               where id = $5
               returning id;
            """
            mail_id = await execute_one_returning(query, 
               input_object.get("checkById"),
               datetime.now(),
               input_object.get("remark"),
               'Approved',
               input_object.get("id"))
            
            return jsonify({"message": "Mail approved successfully" }), 200
         else:
            remark_query = """
               select gmail_remark from public.mail_sent where id = $1
            """
            remark = await fetch_one(remark_query, input_object.get("id"))
            return jsonify({"message": remark.get("gmail_remark") }), 200
      else:
         query = """
            update public.mail_sent set 
               "checkById" = $1, 
               approval_rejection_date = $2,
               approval_rejection_remark = $3,
               status = $4
            where id = $5
            returning id;
         """
         mail_id = await execute_one_returning(query, 
            input_object.get("checkById"),
            datetime.now(),
            input_object.get("remark"),
            'Rejected',
            input_object.get("id"))
         return jsonify({"message": "Mail rejected successfully" }), 200
   
   except Exception as e:
      print(f"Error checking mail: {e}")
      return jsonify({"error": e}), 400

