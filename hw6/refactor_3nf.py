import os
import pymysql
DB_HOST = os.environ.get('DB_HOST', '')
DB_USER = os.environ.get('DB_USER', '')
DB_NAME="web_metadata_db"
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

SQL_3NF_PATH = os.path.join(os.path.dirname(__file__), '3nfschema.sql')
SQL_MIGRATE_PATH=os.path.join(os.path.dirname(__file__), 'migrate.sql')

def create_schema():
    #check for file
    print("starting script")
    if not os.path.exists(SQL_3NF_PATH):
        raise FileNotFoundError(f"cant find SQL schema file at {SQL_3NF_PATH}")

    #read from schema.sql
    with open(SQL_3NF_PATH, 'r') as f:
        sql_3nf_commands = f.read().split(';')

    if not os.path.exists(SQL_MIGRATE_PATH):
        raise FileNotFoundError(f"cant find SQL schema file at {SQL_MIGRATE_PATH}")

    #read from schema.sql
    with open(SQL_MIGRATE_PATH, 'r') as f:
        sql_migrate_commands = f.read().split(';')

    #connect to mysql
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        database=DB_NAME,
        password=DB_PASSWORD,
        autocommit=True
    )

    with conn.cursor() as cursor:
        print(f"Executing schema definitions from {SQL_3NF_PATH}...")
        cursor.execute("SHOW TABLES LIKE %s;", ('old_requests',))
        exists = cursor.fetchone() is not None
        if not exists:
            cursor.execute("RENAME TABLE requests to old_requests;")

        for command in sql_3nf_commands:
            stmt = command.strip() 
            if stmt:  
                cursor.execute(stmt)
                
        for command in sql_migrate_commands:
            stmt = command.strip() 
            if stmt:  
                cursor.execute(stmt)

    conn.close()
    print("Database schema configured")

if __name__ == '__main__':
    create_schema()
