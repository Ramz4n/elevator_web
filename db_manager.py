import mariadb
import json


class DataBaseManager:
    def __init__(self, config_file):
        with open(f'{config_file}.json', 'r') as file:
            self.config = json.loads(file.read())

    def connect(self):
        return mariadb.connect(
            user=self.config['db_user'],
            password=self.config['db_password'],
            host=self.config['db_host'],
            port=self.config['db_port'],
            database=self.config['db_name'])