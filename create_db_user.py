"""
Создаёт пользователя MariaDB для подключения САЙТА к БД и записывает его
логин/пароль в .env (DB_USER, DB_PASSWORD). Запускать через create_db_user.bat.

Логин и пароль генерируются случайно. Права только на чтение (SELECT) на базы
DB_NAME_SITE и DB_NAME_JOURNAL из .env. Админ-пароль MariaDB вводится вручную
и нигде не сохраняется.
"""
import os
import re
import secrets
import sys
from getpass import getpass

import mariadb
from dotenv import dotenv_values

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1')


def ask(prompt, default=''):
    answer = input(f"{prompt} [{default}]: " if default else f"{prompt}: ").strip()
    return answer or default


def write_env(values):
    """Меняет/добавляет переменные в .env, остальные строки не трогает."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    pending = dict(values)
    out = []
    for line in lines:
        key = line.split('=', 1)[0].strip()
        if '=' in line and not line.lstrip().startswith('#') and key in pending:
            out.append(f"{key}={pending.pop(key)}")
        else:
            out.append(line)
    out.extend(f"{k}={v}" for k, v in pending.items())
    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.write("\n".join(out) + "\n")


def main():
    env = dotenv_values(ENV_PATH)
    db_host = env.get('DB_HOST') or 'localhost'
    db_port = int(env.get('DB_PORT') or 3306)
    databases = [d for d in (env.get('DB_NAME_SITE'), env.get('DB_NAME_JOURNAL')) if d]
    if not databases:
        sys.exit("В .env не заданы DB_NAME_SITE / DB_NAME_JOURNAL.")
    for d in databases:
        if not re.fullmatch(r'[A-Za-z0-9_]+', d):
            sys.exit(f"Недопустимое имя базы в .env: {d}")

    current = env.get('DB_USER') or ''
    if current and not current.startswith('['):
        if ask(f"В .env уже есть DB_USER={current}. Создать нового и заменить? (y/N)", 'N').lower() != 'y':
            sys.exit("Отменено, .env не изменён.")

    print(f"Сервер БД: {db_host}:{db_port}")
    admin_user = ask("Админ-логин MariaDB", "root")
    admin_password = getpass("Админ-пароль MariaDB: ")

    # откуда сайт будет подключаться: на том же ПК, что и БД -> localhost
    default_scope = 'localhost' if db_host.lower() in LOCAL_HOSTS else '%'
    scope = ask("С какого хоста подключается сайт (localhost / IP / маска вида 192.168.0.%)", default_scope)
    if not re.fullmatch(r'[A-Za-z0-9_.%:\-]{1,60}', scope):
        sys.exit("Недопустимый хост.")

    user = 'site_' + secrets.token_hex(4)
    password = secrets.token_urlsafe(24)  # алфавит A-Za-z0-9_- -> безопасно для SQL и .env

    try:
        conn = mariadb.connect(host=db_host, port=db_port, user=admin_user,
                               password=admin_password, connect_timeout=5)
    except mariadb.Error as e:
        sys.exit(f"Не удалось подключиться к MariaDB: {e}")

    try:
        cur = conn.cursor()
        cur.execute(f"CREATE USER '{user}'@'{scope}' IDENTIFIED BY '{password}'")
        for d in databases:
            cur.execute(f"GRANT SELECT ON `{d}`.* TO '{user}'@'{scope}'")
        cur.execute("FLUSH PRIVILEGES")
        conn.commit()
    except mariadb.Error as e:
        sys.exit(f"Не удалось создать пользователя (нужны права администратора): {e}")
    finally:
        conn.close()

    write_env({'DB_USER': user, 'DB_PASSWORD': password})
    print(f"\nГотово. Пользователь {user}@{scope}, права SELECT на: {', '.join(databases)}.")
    print(f"DB_USER и DB_PASSWORD записаны в {ENV_PATH}")
    print("Перезапустите сайт (restart.bat), чтобы он подхватил новые данные.")


if __name__ == '__main__':
    main()
