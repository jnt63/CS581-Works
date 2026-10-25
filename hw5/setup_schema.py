#!/usr/bin/env python3
"""HW5 Database Schema Setup Script."""
import os
import pymysql
DB_HOST = os.environ.get('DB_HOST', '')
DB_USER = os.environ.get('DB_USER', '')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME = os.environ.get('DB_NAME', '')
SQL_FILE_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def create_schema():
    #check for file
    if not os.path.exists(SQL_FILE_PATH):
        raise FileNotFoundError(f"cant find SQL schema file at {SQL_FILE_PATH}")

    # read from schema.sql
    with open(SQL_FILE_PATH, 'r') as f:
        sql_commands = f.read().split(';')

    # Connect to MySQL
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True
    )

    with conn.cursor() as cursor:
        print(f"Executing schema definitions from {SQL_FILE_PATH}...")
        for command in sql_commands:
            stmt = command.strip()
            if stmt:  # Ignore empty lines/trailing semicolons
                cursor.execute(stmt)

    conn.close()
    print("Database schema successfully configured!")


if __name__ == '__main__':
    create_schema()