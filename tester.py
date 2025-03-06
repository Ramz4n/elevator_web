import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import mariadb
import json
from contextlib import closing
from werkzeug.security import check_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
from flask_login import LoginManager, UserMixin, login_required, login_user, current_user, logout_user
from wtforms import StringField, SubmitField, TextAreaField, BooleanField, PasswordField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm
from flask_ipban import IpBan
import pymemcache
from flask_caching import Cache
from db_manager import DataBaseManager
from datetime import datetime

UPLOAD_FOLDER = 'static'
load_dotenv()
db_table_name = os.getenv("DB_NAME1")
db_password = os.getenv("DB_PASSWORD1")
db_user = os.getenv("DB_USER")
db_port = os.getenv("DB_PORT")
db_host = os.getenv("DB_HOST")
tester = Flask(__name__, static_folder='static')
tester.debug = True
tester.config['ENV'] = 'production'
tester.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
tester.config[
    'SQLALCHEMY_DATABASE_URI'] = f'mariadb+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_table_name}'
tester.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
tester.config['SQLALCHEMY_POOL_SIZE'] = 20  # Увеличить размер пула соединений
tester.config['SQLALCHEMY_MAX_OVERFLOW'] = 0  # Запретить переполнение пула
tester.config['SQLALCHEMY_CONNECT_TIMEOUT'] = 30  # Установить время ожидания соединения
tester.config['SQLALCHEMY_POOL_RECYCLE'] = 3600  # Сбрасывать соединения каждые 3600 секунд (1 час)

client = pymemcache.Client('192.168.10.204:8080')

login_manager = LoginManager(tester)
login_manager.init_app(tester)
login_manager.login_view = 'login'
login_manager.login_message = 'Введите Логин и Пароль'

secret_key = os.urandom(24)
tester.config['SECRET_KEY'] = secret_key
db = SQLAlchemy(tester)
ip_ban = IpBan(tester)

# Настройки блокировки IP
tester.config['BANNED_IPS'] = set()
cache = Cache(tester, config={'CACHE_TYPE': 'simple'})


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


@tester.route('/', methods=['GET', 'POST'])
@tester.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(username=form.username.data).first()
        if user:
            # Check the hash
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                print(form.username.data)
                session['access'] = user.access
                # return render_template('general.html')
                return redirect(url_for('base'))
            else:
                ip_address = request.remote_addr
                tester.config['BANNED_IPS'].add(ip_address)
                ip_ban.add(ip_address)
                return 'Ошибка входа. Ваш IP-адрес заблокирован'
        else:
            ip_address = request.remote_addr
            tester.config['BANNED_IPS'].add(ip_address)
            ip_ban.add(ip_address)
            print(request.remote_addr)
            print('Неверно х2')
            flash("Неверный Логин или Пароль")

    return render_template('login.html', form=form)


class Users(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer(), primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(162), nullable=False, unique=True)
    access = db.Column(db.Integer, nullable=False, unique=True)


@tester.route('/logout/')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('login'))


@tester.route('/base', methods=['GET', 'POST'])
# @cache.cached(timeout=10)
@login_required
def base():
    if request.method == 'GET':
        image_value = request.args.get('image_value')
        city = request.args.get('city')
        with open(f'vostok.json', 'r') as file:
            data = json.loads(file.read())
        session['table_name'] = data['table_name']
        session['config_file'] = "vostok"
        table_name = session.get('table_name')
        current_month_index = int((datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.now(tz=None)).strftime("%Y"))
        config_file = session.get('config_file')
        db_manager = DataBaseManager(config_file)
        with closing(db_manager.connect()) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT g.Город FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                group by Город 
                                order by Город''')
            data8 = cursor.fetchall()
            cities = [city[-1] for city in data8]
            town = cities[0]
            # КОЛ-ВО ЛИФТОВ ВЫБРАННОГО ГОРОДА
            cursor.execute((f'''SELECT count(z.id)
                                FROM lifts z
                                JOIN doma d ON z.id_дом = d.id
                                JOIN street s ON d.id_улица = s.id
                                JOIN goroda g ON s.id_город = g.id
                                where Город="{town}"'''))
            data1 = cursor.fetchall()
            # ЗАСТРЕВАНИЯ В МЕСЯЦ ГОРОДА
            cursor.execute((f'''SELECT count(Причина) FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                where not LOWER(Комментарий) like "%ложная%" 
                                AND Причина="Застревание" AND Город="{town}" 
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ? AND NOT pc_id is NULL'''),
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data3 = cursor.fetchall()
            # НЕИСПРАВНОСТИ ЗА МЕСЯЦ ГОРОДА
            cursor.execute((f'''SELECT count(Причина) FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                WHERE Город='{town}' and not LOWER(Комментарий) LIKE '%скачок%' 
                                AND not LOWER(Комментарий) LIKE '%электр%'
                                AND not LOWER(Комментарий) LIKE '%вандал%' 
                                AND not LOWER(Комментарий) LIKE '%пож%'
                                AND not LOWER(Комментарий) like '%ложная%' and Причина IN ('Неисправность', 'Остановлен')
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL'''),
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data4 = cursor.fetchall()
            # ОСТАНОВЛЕННЫЕ ЗА МЕСЯЦ
            cursor.execute((f'''SELECT count(Причина) FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                where Причина="Остановлен" and z.дата_запуска is Null 
                                AND Город="{town}" 
                                AND not lower(Комментарий) like '%ложн%' 
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ? AND NOT pc_id is NULL'''),
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data5 = cursor.fetchall()
            # ЛИНЕЙНЫЕ В МЕСЯЦ ГОРОДА
            cursor.execute(f'''SELECT COUNT(z.Причина) 
                                FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                WHERE z.Причина = ? AND z.Дата_запуска IS NULL 
                                AND g.Город = ? AND NOT pc_id IS NULL''', ("Линейная", town))
            data6 = cursor.fetchall()
            # ТЕКУЩИЕ ЗАЯВКИ
            cursor.execute((f'''SELECT count(*) FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                WHERE Дата_запуска is NULL 
                                AND not Причина in ("Линейная", "Остановлен") 
                                AND Город="{town}" AND NOT pc_id is NULL'''),
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data14 = cursor.fetchall()
            # ЛОЖНЫЕ ТЕКУЩЕГО МЕСЯЦА
            cursor.execute((f'''SELECT count(Комментарий) FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                WHERE Город='{town}' AND LOWER(Комментарий) like '%ложная%' 
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL'''),
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data7 = cursor.fetchall()

            if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                procent1 = '%.1f' % ((data3[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
            else:
                procent1 = '0'
            if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                procent2 = '%.1f' % ((data4[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
            else:
                procent2 = '0'
            if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                procent3 = '%.1f' % ((data7[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
            else:
                procent3 = '0'
            # ГРАФИК ОБРАЩЕНИЙ ЛИНЕЙНЫЙ
            cursor.execute(f'''SELECT 
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                FROM {table_name} z
                                JOIN doma d ON z.id_дом = d.id
                                JOIN street s ON d.id_улица = s.id
                                JOIN goroda g ON s.id_город = g.id
                                WHERE Город = "{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) AND NOT pc_id is NULL;''')
            data9 = cursor.fetchall()
            # ГРАФИК ЗАСТРЕВАНИЙ СТОЛБЧАТЫЙ
            for i in range(11):
                cursor.execute(f'''SELECT 
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                    FROM {table_name} z 
                                    JOIN doma d ON z.id_дом = d.id
                                    JOIN street s ON d.id_улица = s.id
                                    JOIN goroda g ON s.id_город = g.id
                                    WHERE 
                                    Город = "{town}"
                                    AND Причина = 'Застревание' 
                                    AND NOT LOWER(Комментарий) LIKE '%ложная%'
                                    AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
            data10 = cursor.fetchall()
            # ГРАФИК НЕИСПРАВНОСТЕЙ СТОЛБЧАТЫЙ
            for i in range(11):
                cursor.execute(f'''SELECT 
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                    FROM {table_name} z 
                                    JOIN doma d ON z.id_дом = d.id
                                    JOIN street s ON d.id_улица = s.id
                                    JOIN goroda g ON s.id_город = g.id
                                    WHERE 
                                    Город = "{town}"
                                    AND Причина IN ('Неисправность', 'Остановлен')
                                    AND NOT LOWER(Комментарий) LIKE '%электр%'
                                    AND NOT LOWER(Комментарий) LIKE '%скачок%'
                                    AND NOT LOWER(Комментарий) LIKE '%ложная%'
                                    AND NOT LOWER(Комментарий) LIKE '%вандал%'
                                    AND NOT LOWER(Комментарий) LIKE '%пож%'
                                    AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
            data12 = cursor.fetchall()

            # ГРАФИК ЛОЖНЫХ СТОЛБЧАТЫЙ
            for i in range(11):
                cursor.execute(f'''SELECT 
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                    COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                    FROM {table_name} z 
                                    JOIN goroda g ON z.id_город = g.id
                                    WHERE 
                                    Город = "{town}"
                                    AND LOWER(Комментарий) LIKE '%ложная%'
                                    AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
            data13 = cursor.fetchall()
            cursor.execute((f'''SELECT 
                                COUNT(CASE WHEN z.id AND MONTH(FROM_UNIXTIME(Дата_заявки)) = MONTH(CURDATE()) THEN 1 END) AS vsego,
                                COUNT(CASE WHEN Причина = 'Остановлен' and z.дата_запуска is Null THEN 1 END) AS stopped,
                                COUNT(CASE WHEN Причина = 'Линейная' and z.Дата_запуска is Null THEN 1 END) AS lineynaya
                                FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                WHERE Город = "{town}" AND NOT pc_id is NULL'''))
            query = cursor.fetchall()
        return render_template(f'vostok.html',
                               data1=data1,
                               data2=query,
                               data3=data3,
                               data4=data4,
                               data5=data5,
                               data6=data6,
                               data7=data7,
                               data8=cities,
                               town=town,
                               data9=data9[0],
                               data10=data10,
                               data12=data12,
                               data13=data13,
                               data14=data14,
                               procent1=procent1,
                               procent2=procent2,
                               procent3=procent3)
    elif request.method == 'POST':
        config_file = session.get('config_file')
        data = request.get_json()
        table_name = session.get('table_name')
        db_manager = DataBaseManager(config_file)
        selected_city = data.get('selectedCity')
        month_list = data.get('monthList')
        town = selected_city
        current_month_index = int((datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.now(tz=None)).strftime("%Y"))
        with closing(db_manager.connect()) as connection:
            cursor = connection.cursor()
            # ВЫБОР ГОРОДА
            # ЭТО ЕСЛИ ВЫБРАЛИ НА САЙТЕ "ВСЕ ГОРОДА"
            if selected_city == 'all':
                # ВСЕГО ЗАЯВОК, ОСТАНОВКИ, ЛИНЕЙНЫЕ
                cursor.execute((f'''SELECT 
                                    COUNT(CASE WHEN z.id AND MONTH(FROM_UNIXTIME(Дата_заявки)) = ? THEN 1 END) AS vsego,
                                    COUNT(CASE WHEN Причина = 'Остановлен' and z.дата_запуска is Null THEN 1 END) AS stopped,
                                    COUNT(CASE WHEN Причина = 'Линейная' and z.Дата_запуска is Null THEN 1 END) AS lineynaya
                                    FROM {table_name} z WHERE NOT pc_id IS NULL'''), (month_list,))
                query = cursor.fetchall()
                # КОЛ-ВО ЛИФТОВ ВЫБРАННОГО ГОРОДА
                cursor.execute(f'''SELECT count(z.id)
                                    FROM lifts z
                                    JOIN doma d ON z.id_дом = d.id
                                    JOIN street s ON d.id_улица = s.id
                                    JOIN goroda g ON s.id_город = g.id''')
                data1 = cursor.fetchall()
                # ТЕКУЩИЕ ЗАЯВКИ
                cursor.execute(f'''SELECT count(*) FROM {table_name} z
                                    WHERE Дата_запуска is NULL 
                                    AND not Причина in ("Линейная", "Остановлен") AND NOT pc_id IS NULL''')
                data14 = cursor.fetchall()
                # ГОДОВАЯ СТАТИСТИКА
                cursor.execute(f'''SELECT
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                    FROM {table_name} z
                                    JOIN doma d ON z.id_дом = d.id
                                    JOIN street s ON d.id_улица = s.id
                                    JOIN goroda g ON s.id_город = g.id
                                    WHERE EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) AND NOT pc_id is NULL;''')
                data9 = cursor.fetchall()
                # ЗАСТРЕВАНИЯ В МЕСЯЦ ГОРОДА
                cursor.execute((f'''SELECT count(Причина) FROM {table_name} z
                                    where not LOWER(Комментарий) like "%ложная%" and Причина="Застревание" 
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ? AND NOT pc_id is NULL'''),
                               (f'{month_list.zfill(2)}', f'{str(current_year_index)}',))
                data3 = cursor.fetchall()
                # НЕИСПРАВНОСТИ ЗА МЕСЯЦ ГОРОДА
                cursor.execute((f'''SELECT count(Причина) FROM {table_name} z
                                    WHERE not LOWER(Комментарий) LIKE '%скачок%' 
                                    AND not LOWER(Комментарий) LIKE '%электр%' and not LOWER(Комментарий) LIKE '%фаз%'
                                    AND not LOWER(Комментарий) LIKE '%вандал%' and not LOWER(Комментарий) LIKE '%пож%'
                                    AND not LOWER(Комментарий) like '%ложная%' and Причина IN ('Неисправность', 'Остановлен')
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL'''),
                               (f'{month_list.zfill(2)}', f'{str(current_year_index)}',))
                data4 = cursor.fetchall()
                # ЛОЖНЫЕ ТЕКУЩЕГО МЕСЯЦА
                cursor.execute((f'''SELECT count(Комментарий) FROM {table_name} z
                                    WHERE LOWER(Комментарий) like '%ложная%' 
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL'''),
                               (f'{month_list.zfill(2)}', f'{str(current_year_index)}',))
                data7 = cursor.fetchall()
                # ПРОЦЕНТЫ В КРУГУ СТАТИСТИКИ
                if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                    procent1 = '%.1f' % ((data3[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
                else:
                    procent1 = '0'
                if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                    procent2 = '%.1f' % ((data4[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
                else:
                    procent2 = '0'
                if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                    procent3 = '%.1f' % ((data7[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
                else:
                    procent3 = '0'

                # СТАТИСТИКА ЗАСТРЕВАНИЙ
                for i in range(11):
                    cursor.execute(f'''SELECT
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                        FROM {table_name} z
                                        JOIN doma d ON z.id_дом = d.id
                                        JOIN street s ON d.id_улица = s.id
                                        JOIN goroda g ON s.id_город = g.id
                                        WHERE Причина = 'Застревание'
                                        AND NOT LOWER(Комментарий) LIKE '%ложная%'
                                        AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
                data10 = cursor.fetchall()
                # ГРАФИК НЕИСПРАВНОСТЕЙ СТОЛБЧАТЫЙ
                for i in range(11):
                    cursor.execute(f'''SELECT
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                        FROM {table_name} z
                                        JOIN doma d ON z.id_дом = d.id
                                        JOIN street s ON d.id_улица = s.id
                                        JOIN goroda g ON s.id_город = g.id
                                        WHERE Причина IN ('Неисправность', 'Остановлен')
                                        AND NOT LOWER(Комментарий) LIKE '%электр%'
                                        AND NOT LOWER(Комментарий) LIKE '%скачок%'
                                        AND NOT LOWER(Комментарий) LIKE '%ложная%'
                                        AND NOT LOWER(Комментарий) LIKE '%вандал%'
                                        AND NOT LOWER(Комментарий) LIKE '%пож%'
                                        AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
                data12 = cursor.fetchall()
                # ГРАФИК ЛОЖНЫХ СТОЛБЧАТЫЙ
                for i in range(11):
                    cursor.execute(f'''SELECT
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                        FROM {table_name} z
                                        JOIN goroda g ON z.id_город = g.id
                                        WHERE LOWER(Комментарий) LIKE '%ложная%'
                                        AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
                data13 = cursor.fetchall()
            # ЭТО ЕСЛИ ВЫБРАЛИ НА САЙТЕ КОНКРЕТНЫЙ ГОРОД
            else:
                cursor.execute((f'''SELECT 
                                    COUNT(CASE WHEN z.id AND MONTH(FROM_UNIXTIME(Дата_заявки)) = ? THEN 1 END) AS vsego,
                                    COUNT(CASE WHEN Причина = 'Остановлен' and z.дата_запуска is Null THEN 1 END) AS stopped,
                                    COUNT(CASE WHEN Причина = 'Линейная' and z.Дата_запуска is Null THEN 1 END) AS lineynaya
                                    FROM {table_name} z
                                    JOIN goroda g ON z.id_город = g.id
                                    WHERE Город = "{town}" AND NOT pc_id IS NULL'''), (month_list,))
                query = cursor.fetchall()
                # КОЛ-ВО ЛИФТОВ ВЫБРАННОГО ГОРОДА
                cursor.execute((f'''SELECT count(z.id)
                                    FROM lifts z
                                    JOIN doma d ON z.id_дом = d.id
                                    JOIN street s ON d.id_улица = s.id
                                    JOIN goroda g ON s.id_город = g.id
                                    where Город="{town}"'''))
                data1 = cursor.fetchall()
                # ТЕКУЩИЕ ЗАЯВКИ
                cursor.execute(f'''SELECT count(*) FROM {table_name} z
                                    JOIN goroda g ON z.id_город = g.id
                                    WHERE Дата_запуска is NULL 
                                    AND not Причина in ("Линейная", "Остановлен") and Город="{town}" AND NOT pc_id is NULL''')
                data14 = cursor.fetchall()
                # ГОДОВАЯ СТАТИСТИКА
                cursor.execute(f'''SELECT
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                    FROM {table_name} z
                                    JOIN doma d ON z.id_дом = d.id
                                    JOIN street s ON d.id_улица = s.id
                                    JOIN goroda g ON s.id_город = g.id
                                    WHERE Город = "{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) AND NOT pc_id is NULL;''')
                data9 = cursor.fetchall()
                # ЗАСТРЕВАНИЯ В МЕСЯЦ ГОРОДА
                cursor.execute((f'''SELECT count(Причина) FROM {table_name} z
                                    JOIN goroda g ON z.id_город = g.id
                                    where not LOWER(Комментарий) like "%ложная%" and Причина="Застревание" 
                                    AND Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ? AND NOT pc_id is NULL'''),
                               (f'{month_list.zfill(2)}', f'{str(current_year_index)}',))
                data3 = cursor.fetchall()
                # НЕИСПРАВНОСТИ ЗА МЕСЯЦ ГОРОДА
                cursor.execute((f'''SELECT count(Причина) FROM {table_name} z
                                    JOIN goroda g ON z.id_город = g.id
                                    WHERE Город='{town}' and not LOWER(Комментарий) LIKE '%скачок%' 
                                    AND not LOWER(Комментарий) LIKE '%электр%' and not LOWER(Комментарий) LIKE '%фаз%'
                                    AND not LOWER(Комментарий) LIKE '%вандал%' and not LOWER(Комментарий) LIKE '%пож%'
                                    AND not LOWER(Комментарий) like '%ложная%' and Причина IN ('Неисправность', 'Остановлен')
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL'''),
                               (f'{month_list.zfill(2)}', f'{str(current_year_index)}',))
                data4 = cursor.fetchall()
                # ЛОЖНЫЕ ТЕКУЩЕГО МЕСЯЦА
                cursor.execute((f'''SELECT count(Комментарий) FROM {table_name} z
                                    JOIN goroda g ON z.id_город = g.id
                                    WHERE Город='{town}' and LOWER(Комментарий) like '%ложная%' 
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                    AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL'''),
                               (f'{month_list.zfill(2)}', f'{str(current_year_index)}',))
                data7 = cursor.fetchall()
                # ПРОЦЕНТЫ В КРУГУ СТАТИСТИКИ
                if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                    procent1 = '%.1f' % ((data3[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
                else:
                    procent1 = '0'
                if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                    procent2 = '%.1f' % ((data4[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
                else:
                    procent2 = '0'
                if data3[0][0] + data4[0][0] + data7[0][0] != 0:
                    procent3 = '%.1f' % ((data7[0][0] / (data3[0][0] + data4[0][0] + data7[0][0])) * 100)
                else:
                    procent3 = '0'

                # СТАТИСТИКА ЗАСТРЕВАНИЙ
                for i in range(11):
                    cursor.execute(f'''SELECT
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                        FROM {table_name} z
                                        JOIN doma d ON z.id_дом = d.id
                                        JOIN street s ON d.id_улица = s.id
                                        JOIN goroda g ON s.id_город = g.id
                                        WHERE
                                        Город = "{town}"
                                        AND Причина = 'Застревание'
                                        AND NOT LOWER(Комментарий) LIKE '%ложная%'
                                        AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
                data10 = cursor.fetchall()
                # ГРАФИК НЕИСПРАВНОСТЕЙ СТОЛБЧАТЫЙ
                for i in range(11):
                    cursor.execute(f'''SELECT
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                        FROM {table_name} z
                                        JOIN doma d ON z.id_дом = d.id
                                        JOIN street s ON d.id_улица = s.id
                                        JOIN goroda g ON s.id_город = g.id
                                        WHERE
                                        Город = "{town}"
                                        AND Причина IN ('Неисправность', 'Остановлен')
                                        AND NOT LOWER(Комментарий) LIKE '%электр%'
                                        AND NOT LOWER(Комментарий) LIKE '%скачок%'
                                        AND NOT LOWER(Комментарий) LIKE '%ложная%'
                                        AND NOT LOWER(Комментарий) LIKE '%вандал%'
                                        AND NOT LOWER(Комментарий) LIKE '%пож%'
                                        AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
                data12 = cursor.fetchall()
                # ГРАФИК ЛОЖНЫХ СТОЛБЧАТЫЙ
                for i in range(11):
                    cursor.execute(f'''SELECT
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 4 THEN 1 END) AS April,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 5 THEN 1 END) AS May,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 6 THEN 1 END) AS June,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 7 THEN 1 END) AS July,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 8 THEN 1 END) AS August,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 9 THEN 1 END) AS September,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 10 THEN 1 END) AS October,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 11 THEN 1 END) AS November,
                                        COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                                        FROM {table_name} z
                                        JOIN goroda g ON z.id_город = g.id
                                        WHERE
                                        Город = "{town}"
                                        AND LOWER(Комментарий) LIKE '%ложная%'
                                        AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE()) AND NOT pc_id is NULL;''')
                data13 = cursor.fetchall()

            # ЛИНЕЙНЫЕ В МЕСЯЦ ГОРОДА
            cursor.execute(f'''SELECT count(Причина) FROM {table_name} z
                                JOIN goroda g ON z.id_город = g.id
                                where Причина="Линейная" and z.Дата_запуска is Null and Город="{town}" AND NOT pc_id IS NULL''')
            data6 = cursor.fetchall()

    return jsonify({'data1': data1,
                    'vsego': query[0][0],
                    'stopped': query[0][1],
                    'lineynaya': query[0][2],
                    'data3': data3,
                    'data4': data4,
                    'data6': data6,
                    'data7': data7,
                    'data9': data9,
                    'data10': data10,
                    'data12': data12,
                    'data13': data13,
                    'data14': data14,
                    'procent1': procent1,
                    'procent2': procent2,
                    'procent3': procent3})


@tester.route('/_postbutton', methods=['POST'])
@login_required
def _postbutton():
    data = request.get_json()
    city = data.get('city')
    adres = data.get('adres')
    date1 = data.get('date1')
    date2 = data.get('date2')
    print(city)
    print(adres)
    print(date1)
    print(date2)
    return jsonify({'city': city, 'adres': adres, 'date1': date1, 'date2': date2})


@tester.route('/_get_city_for_poisk', methods=['POST'])
@login_required
def _get_city_for_poisk():
    data = request.get_json()
    town = data.get('city')
    db_file = session.get('db_file', 'osp.json')
    with open(f'{db_file}', 'r') as file:
        data = json.loads(file.read())
    host = data['db_host']
    user = data['db_user']
    password = data['db_password']
    port = data['db_port']
    database = data['db_name']
    try:
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT s.улица, d.номер as дом, p.номер as Подъезд
                                FROM lifts z
                                JOIN padik p ON z.id_подъезд = p.id  
                                JOIN doma d ON z.id_дом = d.id
                                JOIN street s ON d.id_улица = s.id
                                JOIN goroda g ON s.id_город = g.id
                                WHERE Город='{town}' 
                                GROUP BY s.улица, дом, Подъезд
                                ORDER BY s.улица, дом, Подъезд''')
            adres = cursor.fetchall()
        return jsonify(adres)
    except Exception as e:
        print('Проблема в паспорте:', e)
        return render_template('error.html')


@tester.route('/_passport', methods=['GET', 'POST'])
@login_required
def _passport():
    # ОБРАЩЕНИЯ №0
    current_month_index = int((datetime.now(tz=None)).strftime("%m")) - 1
    current_year_index = int((datetime.now(tz=None)).strftime("%Y"))
    try:
        if request.method == 'GET':
            config_file = session['config_file']
            table_name = session['table_name']
            db_manager = DataBaseManager(config_file)
            town_url = request.args.get('selectedCity')
            with closing(db_manager.connect()) as connection:
                cursor = connection.cursor()
                cursor.execute(f'''SELECT DISTINCT
                                    g.город
                                    FROM passport pa
                                    JOIN lifts li ON pa.id_лифт = li.id
                                    JOIN doma d ON li.`id_дом` = d.id
                                    JOIN street s ON d.`id_улица` = s.id
                                    JOIN goroda g ON s.id_город = g.id''')
                data2 = cursor.fetchall()
                town = [city[0] for city in data2]

                cursor.execute(f'''SELECT z.Номер_заявки,
                                       FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                                       di.фио,
                                       g.город,
                                       concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                                       z.Тип_лифта,
                                       z.Причина,
                                       m.фио,
                                       FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                                       z.Комментарий
                                       FROM {table_name} z
                                       JOIN workers di ON z.id_Диспетчер = di.id
                                       JOIN goroda g ON z.id_город = g.id
                                       JOIN street s ON z.id_улица = s.id
                                       JOIN doma d ON z.id_дом = d.id
                                       JOIN padik p ON z.id_подъезд = p.id
                                       JOIN workers m ON z.id_Механик = m.id
                                       WHERE Город='{request.args.get('selectedCity')}' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?
                                       group by номер_заявки
                                       order by номер_заявки;''',
                               (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
                data0 = cursor.fetchall()
                print(data0)
                cursor.execute(f'''SELECT concat(u.улица, ', ',  d.номер, ', ',  p.`Номер`, ', ',  li.тип_лифта) as Адрес,
                        pa.завод_№ as Заводской_номер,
                          pa.изготовитель as Изготовитель,
                          pa.модель as Модель,
                          pa.год_ввода as Год_ввода,
                          pa.год_изготовления as Год_изготовления,
                          pa.грузопод as Грузоподъемность,
                          pa.этажн as Этажность,
                          pa.кол_во_канатов as Кол_во_канатов,
                          pa.длина_канатов as Длина_канатов,
                          pa.диаметр_канатов as Диаметр_канатов,
                          pa.редуктор_леб as Редуктор_лебедки,
                          pa.двигатель_леб as двигатель_лебедки,
                          pa.шкив_канат as Шкив_канатоведущий,
                          pa.отводной_блок as Отводной_блок,
                          pa.частотник as Частотный_преобразователь,
                          pa.рег_привод_двер as Регулируемый_привод_дверей,
                          pa.нерег_привод_двер as Нерегулируемый_привод_дверей
                      FROM passport pa
                      JOIN lifts li ON pa.id_лифт = li.id
                      JOIN padik p ON li.`id_подъезд` = p.id
                      JOIN doma d ON li.id_дом = d.id
                      JOIN street u ON d.id_улица = u.id
                      JOIN goroda g ON u.`id_город` = g.id''')
                data1 = cursor.fetchall()
            return render_template('_passport.html', data0=data0, town=town, town_url=town_url, data1=data1)
        if request.method == 'POST':
            address = request.get_json()['adresList']
            table_name = session['table_name']
            town = request.get_json()['cityList']
            address = address.split(', ')
            config_file = session['config_file']
            current_year_index = int((datetime.now(tz=None)).strftime("%Y"))
            db_manager = DataBaseManager(config_file)
            # при выборе города меняется улица дом и падик в списке select html======================================
            with closing(db_manager.connect()) as connection:
                cursor = connection.cursor()
                cursor.execute(f'''SELECT concat(s.улица, ', ', d.номер, ', ', p.номер) AS Адрес,                        
                                    pa.завод_№ as Заводской_номер,
                                    pa.изготовитель as Изготовитель,
                                    pa.модель as Модель,
                                    pa.год_ввода as Год_ввода,
                                    pa.год_изготовления as Год_изготовления,
                                    pa.грузопод AS Грузоподъемность,                        
                                    pa.этажн as Этажность,
                                    pa.кол_во_канатов as Кол_во_канатов,
                                    pa.длина_канатов as Длина_канатов,                        
                                    pa.диаметр_канатов as Диаметр_канатов,
                                    pa.редуктор_леб as Редуктор_лебедки,                        
                                    pa.двигатель_леб AS Двигатель_лебедки,
                                    pa.шкив_канат as Шкив_канатоведущий,                        
                                    pa.отводной_блок as Отводной_блок,
                                    pa.частотник as Частотный_преобразователь,                        
                                    pa.рег_привод_двер as Регулируемый_привод_дверей,
                                    pa.нерег_привод_двер as Нерегулируемый_привод_дверей 
                                                    FROM passport pa     
                                                    JOIN lifts li ON pa.id_лифт = li.id
                                                    JOIN padik p ON li.id_подъезд = p.id 
                                                    JOIN doma d ON li.id_дом = d.id 
                                                    JOIN street s ON d.id_улица = s.id 
                                                    JOIN goroda g ON s.`id_город` = g.id   
                                    WHERE g.город = '{town}' and s.улица = '{address[0]}' and d.номер = '{address[1]}' and p.номер = '{address[2]}'
                                                    group by Адрес
                                                    order by Адрес
                                    ''')
                data1 = cursor.fetchall()
                # КОЛИЧЕСТВО ВСЕГО ОБРАЩЕНИЙ ЗА МЕСЯЦ АДРЕСА
                cursor.execute(f'''SELECT z.Номер_заявки,
                                   FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                                   di.фио,
                                   g.город,
                                   concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                                   z.Тип_лифта,
                                   z.Причина,
                                   di.фио,
                                   FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                                   z.Комментарий
                                   FROM zayavki z
                                   JOIN workers di ON z.id_Диспетчер = di.id
                                    JOIN padik p ON z.id_подъезд = p.id 
                                    JOIN doma d ON z.id_дом = d.id 
                                    JOIN street s ON d.id_улица = s.id 
                                    JOIN goroda g ON s.`id_город` = g.id   
                                   WHERE Город="{town}" and s.улица = '{address[0]}' and d.номер = '{address[1]}' 
                                   and p.номер = '{address[2]}' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                   AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL
                                   group by номер_заявки
                                   order by номер_заявки;''',
                               (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
                data0 = cursor.fetchall()
            return jsonify({'data1': data1,
                            'data2': data0,
                            'address': address})
    except Exception as e:
        print('Проблема в паспорте:', e)
        return render_template('error.html')


def get_results_from_db(address, city):
    config_file = session['config_file']
    db_manager = DataBaseManager(config_file)
    with closing(db_manager.connect()) as connection:
        cursor = connection.cursor()
        cursor.execute(f'''SELECT concat(u.улица, ', ',  d.номер, ', ',  p.`Номер`, ', ',  li.тип_лифта) as Адрес
                      FROM passport pa
                      JOIN lifts li ON pa.id_лифт = li.id
                      JOIN padik p ON li.`id_подъезд` = p.id
                      JOIN doma d ON li.id_дом = d.id
                      JOIN street u ON d.id_улица = u.id
                      JOIN goroda g ON u.`id_город` = g.id AND g.Город = "{city}"
                      WHERE LOWER(concat(u.улица, ', ',  d.номер, ', ',  p.`Номер`, ', ',  li.тип_лифта)) LIKE LOWER("%{address}%") AND NOT pc_id is NULL''')
        results = cursor.fetchall()
    return results


@tester.route('/search', methods=['POST'])
def search():
    address = request.get_json()['address']
    city = request.get_json()['city']
    results = get_results_from_db(address, city)
    return jsonify(results)


@tester.route('/_top_bad', methods=['GET', 'POST'])
@login_required
def _top_bad():
    if request.method == 'GET':
        table_name = session['table_name']
        config_file = session['config_file']
        db_manager = DataBaseManager(config_file)
        try:
            with closing(db_manager.connect()) as connection:
                cursor = connection.cursor()
                cursor.execute(f'''SELECT g.город, 
                                    concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес, 
                                    z.Тип_лифта, 
                                    COUNT(concat(s.улица, ', ', d.номер, ', ', p.номер)) as address_count
                                    FROM {table_name} z
                                    JOIN goroda g ON z.id_город = g.id
                                    JOIN street s ON z.id_улица = s.id
                                    JOIN doma d ON z.id_дом = d.id
                                    JOIN padik p ON z.id_подъезд = p.id
                                    WHERE Дата_заявки >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
                                    and (LOWER(Комментарий) not like '%скачок%'  
                                    and LOWER(Комментарий) not like '%напряж%' and LOWER(Комментарий) not like '%фаз%'
                                    and LOWER(Комментарий) not like '%электр%' and LOWER(Комментарий) not like '%свет%')
                                    and (LOWER(Комментарий) not like '%пож%' and LOWER(Комментарий) not LIKE '%вандал%')
                                    AND NOT pc_id is NULL
                                    GROUP BY Адрес, Тип_лифта
                                    ORDER BY address_count DESC
                                    limit 100;''')
                data1 = cursor.fetchall()
            return render_template('_top_bad.html', data1=data1)
        except Exception as e:
            print('Проблема в наихудших:', e)
            return render_template('error.html')
    if request.method == 'POST':
        table_name = session['table_name']
        config_file = session['config_file']
        db_manager = DataBaseManager(config_file)
        data = request.get_json()
        city = data['city']
        adres = data['adres']
        adres = adres.split(', ')
        lift = data['lift']
        try:
            with closing(db_manager.connect()) as connection:
                cursor = connection.cursor()
                cursor.execute(f'''SELECT z.Номер_заявки,
                                      FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                                      di.фио,
                                      g.город,
                                      concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                                      z.Тип_лифта,
                                      z.Причина,
                                      m.фио,
                                      FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                                      z.Комментарий
                                      FROM {table_name} z
                                      JOIN workers di ON z.id_диспетчер = di.id
                                      JOIN goroda g ON z.id_город = g.id
                                      JOIN street s ON z.id_улица = s.id
                                      JOIN doma d ON z.id_дом = d.id
                                      JOIN padik p ON z.id_подъезд = p.id
                                      JOIN workers m ON z.id_механик = m.id
                                   
                                   WHERE Дата_заявки >= UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY))
                                   and (LOWER(Комментарий) not like '%скачок%'  
                                   and LOWER(Комментарий) not like '%напряж%' and LOWER(Комментарий) not like '%фаз%'
                                   and LOWER(Комментарий) not like '%электр%' and LOWER(Комментарий) not like '%свет%')
                                   and (LOWER(Комментарий) not like '%пож%' and LOWER(Комментарий) not LIKE '%вандал%')
                                   AND g.город = ? AND s.`Улица` = ?
                                    AND d.`Номер` = ? AND p.`Номер` = ? AND z.`Тип_лифта` = ? AND NOT pc_id is NULL
                                   limit 100;''', (city, adres[0], adres[1], adres[2], lift))
                query_bd = cursor.fetchall()

                query = []
                for row in query_bd:
                    query.append({
                        'Номер_заявки': row[0],
                        'Дата_заявки': row[1],
                        'Диспетчер': row[2],
                        'Город': row[3],
                        'Адрес': row[4],
                        'Тип_лифта': row[5],
                        'Причина': row[6],
                        'Механик': row[7],
                        'Дата_запуска': row[8],
                        'Комментарий': row[9],
                    })
            return jsonify({'query_bd': query})
        except Exception as e:
            print('Проблема в наихудших:', e)
            return render_template('error.html')


@tester.route('/_obrasch', methods=['GET', 'POST'])
@login_required
def _obrasch():
    # ОБРАЩЕНИЯ №1
    if request.method == 'GET':
        config_file = session['config_file']
        table_name = session['table_name']
        current_year_index = int((datetime.now(tz=None)).strftime("%Y"))
        town = request.args.get('selectedCity')
        month = request.args.get('monthList')
        db_manager = DataBaseManager(config_file)
        if town == 'all':
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''SELECT z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                               AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL
                               group by z.id
                               order by z.id;''',
                                   (f'{month.zfill(2)}', f'{str(current_year_index)}',))
                    data1 = cursor.fetchall()
                return render_template('_obrasch.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в обращениях:', e)
                return render_template('error.html')
        else:
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''SELECT z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE Город='{town}' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                               AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ? AND NOT pc_id is NULL
                               group by z.id
                               order by z.id;''',
                                   (f'{month.zfill(2)}', f'{str(current_year_index)}',))
                    data1 = cursor.fetchall()
                return render_template('_obrasch.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в обращениях:', e)
                return render_template('error.html')


@tester.route('/_tekuschie', methods=['GET', 'POST'])
@login_required
def _tekuschie():
    # ТЕКУЩИЕ ЗАЯВКИ
    if request.method == 'GET':
        config_file = session['config_file']
        table_name = session['table_name']
        town = request.args.get('selectedCity')
        db_manager = DataBaseManager(config_file)
        if town == 'all':
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''SELECT z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE Дата_запуска is NULL and not z.Причина in ("Линейная", "Остановлен") AND NOT pc_id is NULL''')
                    data1 = cursor.fetchall()
                return render_template('_tekuschie.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в обращениях:', e)
                return render_template('error.html')
        else:
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''SELECT z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE Дата_запуска is NULL and not z.Причина in ("Линейная", "Остановлен") and Город="{town}" AND NOT pc_id is NULL''')
                    data1 = cursor.fetchall()
                return render_template('_tekuschie.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в обращениях:', e)
                return render_template('error.html')


@tester.route('/_stat', methods=['GET', 'POST'])
@login_required
def _stat():
    # statistica
    if request.method == 'GET':
        table_name = session['table_name']
        config_file = session['config_file']
        db_manager = DataBaseManager(config_file)
        try:
            with closing(db_manager.connect()) as connection:
                cursor = connection.cursor()
                cursor.execute(f'''SELECT Город,
                                    CASE 
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'January' THEN 'Январь'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'February' THEN 'Февраль'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'March' THEN 'Март'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'April' THEN 'Апрель'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'May' THEN 'Май'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'June' THEN 'Июнь'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'July' THEN 'Июль'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'August' THEN 'Август'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'September' THEN 'Сентябрь'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'October' THEN 'Октябрь'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'November' THEN 'Ноябрь'
                                    WHEN MONTHNAME(FROM_UNIXTIME(Дата_заявки)) = 'December' THEN 'Декабрь'
                                    END AS месяц,
                                    COUNT(*) as всего_заявок,
                                    SUM(CASE WHEN Причина IN ('Остановлен', 'Неисправность') AND not LOWER(Комментарий) like '%ложная%' AND not LOWER(Комментарий) like '%вандал%' AND not LOWER(Комментарий) like '%пож%' THEN 1 ELSE 0 END) as Остановки,
                                    SUM(CASE WHEN Причина = 'Застревание' AND not LOWER(Комментарий) like '%ложная%' AND not LOWER(Комментарий) like '%вандал%' AND not LOWER(Комментарий) like '%пож%' THEN 1 ELSE 0 END) as Застревание,
                                    SUM(CASE WHEN LOWER(Комментарий) like '%ложная%' THEN 1 ELSE 0 END) as всего_ложные,
                                    SUM(CASE WHEN LOWER(Комментарий) like '%вандал%' THEN 1 ELSE 0 END) as вандалка,
                                    SUM(CASE WHEN LOWER(Комментарий) like '%пож%' THEN 1 ELSE 0 END) as пожарка
                                FROM {table_name} z 
                                JOIN goroda g ON z.id_город = g.id
                                WHERE NOT pc_id is NULL
                                GROUP BY Город, месяц
                                order BY Город, Дата_заявки, месяц;''')
                statistic = cursor.fetchall()
            return render_template('_stat.html', statistic=statistic)
        except Exception as e:
            print('Проблема в stat:', e)
            return render_template('error.html')


@tester.route('/_ostanov', methods=['GET', 'POST'])
@login_required
def _ostanov():
    # ОСТАНОВКИ №4
    if request.method == 'GET':
        town = request.args.get('selectedCity')
        config_file = session.get('config_file')
        table_name = session['table_name']
        db_manager = DataBaseManager(config_file)
        if town == 'all':
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''select z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE z.дата_запуска is Null and not LOWER(Комментарий) like 'ложная' and Причина='Остановлен' AND NOT pc_id is NULL
                                GROUP by z.id
                                ORDER by z.id;''')
                    data1 = cursor.fetchall()
                return render_template('_ostanov.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в остановках:', e)
                return render_template('error.html')
        else:
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''select z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE Город='{town}' and z.дата_запуска is Null and not LOWER(Комментарий) like 'ложная' and Причина='Остановлен' AND NOT pc_id is NULL
                                GROUP by z.id
                                ORDER by z.id;''')
                    data1 = cursor.fetchall()
                return render_template('_ostanov.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в остановках:', e)
                return render_template('error.html')


@tester.route('/_lineynie', methods=['GET', 'POST'])
@login_required
def _lineynie():
    # ЛИНЕЙНЫЕ №4
    if request.method == 'GET':
        town = request.args.get('selectedCity')
        config_file = session.get('config_file')
        table_name = session['table_name']
        db_manager = DataBaseManager(config_file)
        if town == 'all':
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''select z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE z.дата_запуска is Null and Причина='Линейная' AND NOT pc_id IS NULL
                                GROUP by z.id
                                ORDER by z.id;''')
                    data1 = cursor.fetchall()
                return render_template('_lineynie.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в остановках:', e)
                return render_template('error.html')
        else:
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''select z.Номер_заявки,
                               FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                               di.фио,
                               g.город,
                               concat(s.улица, ', ', d.номер, ', ', p.номер) as Адрес,
                               z.Тип_лифта,
                               z.Причина,
                               m.фио,
                               FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                               z.Комментарий
                               FROM {table_name} z
                               JOIN workers di ON z.id_Диспетчер = di.id
                               JOIN goroda g ON z.id_город = g.id
                               JOIN street s ON z.id_улица = s.id
                               JOIN doma d ON z.id_дом = d.id
                               JOIN padik p ON z.id_подъезд = p.id
                               JOIN workers m ON z.id_Механик = m.id
                               WHERE Город='{town}' and z.дата_запуска is Null and Причина='Линейная' AND NOT pc_id is NULL
                                GROUP by z.id
                                ORDER by z.id;''')
                    data1 = cursor.fetchall()
                return render_template('_lineynie.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в остановках:', e)
                return render_template('error.html')

@tester.route('/kolvo_lifts', methods=['GET', 'POST'])
@login_required
def kolvo_lifts():
    # КОЛИЧЕСТВО ЛИФТОВ У КОМПАНИИ
    if request.method == 'GET':
        config_file = session['config_file']
        db_manager = DataBaseManager(config_file)
        town = request.args.get('selectedCity')
        if town == 'all':
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''SELECT g.город,
                               s.`улица`,
                               d.`номер`,
                               p.`номер`,
                               Тип_лифта
                               FROM lifts l
                               JOIN padik p ON l.id_подъезд = p.id
                               JOIN doma d ON l.id_дом = d.id
                               JOIN street s ON d.id_улица = s.id
                               JOIN goroda g ON s.id_город = g.id''')
                    data1 = cursor.fetchall()
                return render_template('kolvo_lifts.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в колво-лифтах:', e)
                return render_template('error.html')
        else:
            try:
                with closing(db_manager.connect()) as connection:
                    cursor = connection.cursor()
                    cursor.execute(f'''SELECT g.город,
                               s.`улица`,
                               d.`номер`,
                               p.`номер`,
                               Тип_лифта
                               FROM lifts l
                               JOIN padik p ON l.id_подъезд = p.id
                               JOIN doma d ON l.id_дом = d.id
                               JOIN street s ON d.id_улица = s.id
                               JOIN goroda g ON s.id_город = g.id
                               WHERE город="{town}"''')
                    data1 = cursor.fetchall()
                return render_template('kolvo_lifts.html', data1=data1, town=town)
            except Exception as e:
                print('Проблема в колво-лифтах:', e)
                return render_template('error.html')


# ---------------------------------------------------------------------------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#
# ---------------------------------------------------------------------------------------------------------------------#
# -----------------------------------------------!!!ALARM!!!-----------------------------------------------------------#
def get_db_manager(config_file):
    return DataBaseManager(config_file)


def fetch_addresses(cursor, city):
    cursor.execute(f'''SELECT concat(s.улица, ', ', d.номер, ', ', p.номер, ', ', l.Тип_лифта) as Адрес
                        FROM lifts l
                        JOIN padik p ON l.`id_подъезд` = p.id
                        JOIN doma d ON l.`id_дом` = d.id
                        JOIN street s ON d.`id_улица` = s.id
                        JOIN goroda g ON s.`id_город` = g.id
                        WHERE g.город = '{city}'
                    ''')
    addresses = cursor.fetchall()

    return [address[0] for address in addresses]


def fetch_tickets(cursor, city, addresses=None, start_date=None, end_date=None):
    query = f'''SELECT
                    z.Номер_заявки,
                    FROM_UNIXTIME(z.Дата_заявки, '%d.%m.%Y, %H:%i') AS Дата_заявки,
                    di.фио,
                    g.город,
                    CONCAT(s.улица, ', ', d.номер, ', ', p.номер, ', ', z.Тип_лифта) AS Адрес,
                    z.Причина,
                    m.фио AS Механик,
                    FROM_UNIXTIME(z.Дата_запуска, '%d.%m.%Y, %H:%i') AS Дата_запуска,
                    z.Комментарий
                FROM zayavki z
                JOIN workers di ON z.id_Диспетчер = di.id
                JOIN goroda g ON z.id_город = g.id
                JOIN street s ON z.id_улица = s.id
                JOIN doma d ON z.id_дом = d.id
                JOIN padik p ON z.id_подъезд = p.id
                JOIN workers m ON z.id_Механик = m.id
                WHERE g.город = '{city}' AND NOT pc_id is NULL'''

    if addresses:
        query += f" AND ('{addresses}' = '' OR CONCAT(s.улица, ', ', d.номер, ', ', p.номер, ', ', z.Тип_лифта) like '%{addresses}%')"
    if start_date:
        query += f" AND z.Дата_заявки BETWEEN {start_date}"
        if end_date:
            query += f" AND {end_date}"
        else:
            end_date = int(datetime.now().timestamp())
            query += f" AND {end_date}"
    query += " ORDER BY z.id;"

    cursor.execute(query)

    return cursor.fetchall()


def fetch_cities(cursor):
    cursor.execute("SELECT id, Город FROM goroda GROUP BY Город ORDER BY Город")
    cities_by_id = cursor.fetchall()

    return [city[-1] for city in cities_by_id]


@tester.route('/updateData', methods=['POST'])
@login_required
def updateData():
    if request.method == 'POST':
        config_file = session.get('config_file')
        db_manager = get_db_manager(config_file)

        city = request.get_json()['cityList']

        with closing(db_manager.connect()) as connection:
            cursor = connection.cursor()

            addresses = fetch_addresses(cursor, city)
            tickets = fetch_tickets(cursor, city)

        return jsonify({'tickets': tickets, 'addresses': addresses})


@tester.route('/_search', methods=['GET', 'POST'])
@login_required
def _search():
    config_file = session.get('config_file')
    db_manager = get_db_manager(config_file)

    if request.method == 'GET':
        with closing(db_manager.connect()) as connection:
            cursor = connection.cursor()

            town = fetch_cities(cursor)
            addresses = fetch_addresses(cursor, town[0])

        return render_template('_search.html', town=town, addresses=addresses)

    if request.method == 'POST':
        city = request.form.get('city')
        addresses = request.form.get('addresses')
        start_calendar = request.form.get('start_calendar')
        end_calendar = request.form.get('end_calendar')

        start_date = None
        end_date = None
        if start_calendar:
            try:
                date_obj_start = datetime.strptime(start_calendar, '%Y-%m-%d')
                start_date = int(date_obj_start.timestamp())
            except ValueError:
                start_date = None

        if end_calendar:
            try:
                date_obj_end = datetime.strptime(end_calendar, '%Y-%m-%d')
                end_date = int(date_obj_end.timestamp())
            except ValueError:
                end_date = None

        with closing(db_manager.connect()) as connection:
            cursor = connection.cursor()

            tickets = fetch_tickets(cursor, city, addresses, start_date, end_date)

        return jsonify({'data1': tickets})

    return render_template('_search.html')


@tester.route('/error', methods=['GET', 'POST'])
@login_required
def error():
    return render_template('error.html')


@tester.route('/techteam', methods=['GET', 'POST'])
def techteam():
    return render_template('techteam.html')


@tester.route('/maxim')
def maxim():
    return render_template('maxim.html')


@tester.route('/dmitry')
def dmitry():
    return render_template('dmitry.html')


@tester.route('/roman')
def roman():
    return render_template('roman.html')


@tester.route('/sergey')
def sergey():
    return render_template('sergey.html')


@tester.route('/alexey')
def alexey():
    return render_template('alexey.html')


if __name__ == '__main__':
    from waitress import serve

    # serve(tester, host="10.40.1.40", port=8080, threads=100)
    # TODO DON'T PUSH
    tester.run(debug=True, host='192.168.10.204', port=8080, threaded=True)
