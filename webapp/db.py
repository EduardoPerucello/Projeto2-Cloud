# webapp/db.py
import mysql.connector

def get_db():
    # conecta ao MySQL dentro da VM base (192.168.56.10)
    return mysql.connector.connect(
        host='192.168.56.10',
        user='cloud_user',
        password='cloud_pass',
        database='cloud_project',
        connect_timeout=10
    )
