import mariadb
import os
from dotenv import load_dotenv

load_dotenv()


class DataBaseManager:
    _pool = None

    def __init__(self, db_name=None):
        self.db_name = db_name or os.getenv('DB_NAME_JOURNAL')

    @classmethod
    def _get_pool(cls, db_name):
        if cls._pool is None:
            cls._pool = mariadb.ConnectionPool(
                pool_name="readonly_pool",
                pool_size=10,
                pool_reset_connection=True,
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST'),
                port=int(os.getenv('DB_PORT', 3306)),
                database=db_name,
                connect_timeout=10,
                read_timeout=30
            )
        return cls._pool

    def connect(self):
        try:
            pool = self._get_pool(self.db_name)
            return pool.get_connection()
        except mariadb.PoolError:
            # Пул занят - создаём временное соединение
            return mariadb.connect(
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST'),
                port=int(os.getenv('DB_PORT', 3306)),
                database=self.db_name,
                connect_timeout=10,
                read_timeout=30
            )