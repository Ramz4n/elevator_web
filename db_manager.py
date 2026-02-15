import mariadb
import os
from dotenv import load_dotenv

load_dotenv()


class DataBaseManager:
    def __init__(self, db_name=None):
        self.db_name = db_name or os.getenv('DB_NAME_JOURNAL')

    def connect(self):
        return mariadb.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', 3306)),
            database=self.db_name)