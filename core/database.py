import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def connectDatabase():
    # Get DataBase informations from client
    username = os.getenv("USERNAME_DB")
    password = os.getenv("PASSWORD_DB")
    hostname = os.getenv("HOSTNAME_DB")
    database = os.getenv("DATABASE_DB")

    # Connect to Data Base
    conn = psycopg2.connect(
        user=username, password=password, host=hostname, port=5432, database=database
    )

    return conn
