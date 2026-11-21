
import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="canteen_management",
        user="postgres",
        password="Vaishnaviraj@123",
        port="5432"
    )
