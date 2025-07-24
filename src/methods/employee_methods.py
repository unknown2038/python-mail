from database.db import get_db_connection


async def fetch_employee_by_id(employee_id):
    conn = await get_db_connection()
    if not conn:
        print("No connection to the database")
        return None
    try:
        row = await conn.fetchrow("""
            SELECT e.id, e.cosec_id, e.role, e.department, ejd.first_name, ejd.last_name  
            FROM public.employees e JOIN public.employee_job_details ejd ON e."detailsId" = ejd.id WHERE e.id = $1 
            """,employee_id)
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


def fetch_employees():
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, cosec_id, role, username, department FROM employees ORDER BY id ASC"
        )
        rows = cur.fetchall()

        employees = []
        for row in rows:
            employees.append(
                {
                    "id": row[0],
                    "cosec_id": row[1],
                    "role": row[2],
                    "username": row[3],
                    "department": row[4],
                }
            )
        return employees
    except Exception as e:
        print(f"Error fetching employees: {e}")
        return []
    finally:
        conn.close()


# def fetch_employee_by_id(employee_id):
#     conn = get_db_connection()
#     if not conn:
#         return None

#     try:
#         cur = conn.cursor()
#         cur.execute(
#             "SELECT id, cosec_id, role, username, department FROM employees WHERE id = %s",
#             (employee_id,),
#         )
#         row = cur.fetchone()

#         if row:
#             return {
#                 "id": row[0],
#                 "cosec_id": row[1],
#                 "role": row[2],
#                 "username": row[3],
#                 "department": row[4],
#             }
#         return None
#     except Exception as e:
#         print(f"Error fetching employee: {e}")
#         return None
#     finally:
#         conn.close()
