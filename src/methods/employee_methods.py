from database.db_pool import fetch_one, fetch_all

async def fetch_employee_by_id(employee_id):
    try:
        query = """
            SELECT e.id, e.cosec_id, e.role, e.department, ejd.first_name, ejd.last_name  
            FROM public.employees e JOIN public.employee_job_details ejd ON e."detailsId" = ejd.id WHERE e.id = $1 
            """
        row = await fetch_one(query, employee_id)
        if row:
            return {
                "id": row[0],
                "cosec_id": row[1],
                "role": row[2],
                "department": row[3],
                "first_name": row[4],
                "last_name": row[5],
            }
        return None
    except Exception as e:
        print(f"Error fetching employees: {e}")
        return None


async def fetch_employees():
    try:
        query = """
            SELECT id, cosec_id, role, username, department FROM employees ORDER BY id ASC
        """
        rows = await fetch_all(query)

        return [
            {
                "id": row["id"],
                "cosec_id": row["cosec_id"],
                "role": row["role"],
                "username": row["username"],
                "department": row["department"],
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error fetching employees: {e}")
        return []

