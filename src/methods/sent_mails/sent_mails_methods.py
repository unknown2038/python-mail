import asyncio
import imaplib
from quart import jsonify

from database.db_pool import fetch_all
from src.methods.employee_methods import fetch_employee_by_id


async def fetch_sent_draft_mails(user_id, mail_id_name, mail_of):
   try:
      query = """
         select 
            sm.id, sm.mail_id_name, sm.from_id, sm.to_id, sm.cc_ids, sm.bcc_ids, sm.subject, sm.html, sm.is_draft_mail, sm.draft_mail_date::date as draft_create_date, sm.path,
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