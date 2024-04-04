import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import mariadb
import json
from contextlib import closing
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
from flask_login import LoginManager, UserMixin, login_required, login_user, current_user, logout_user
from wtforms import StringField, SubmitField, TextAreaField, BooleanField, PasswordField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm

#
UPLOAD_FOLDER = 'static'
load_dotenv()
db_table_name = os.getenv("DB_NAME1")
db_password = os.getenv("DB_PASSWORD1")
db_user = os.getenv("DB_USER")
db_port = os.getenv("DB_PORT")
db_host = os.getenv("DB_HOST")
run1 = Flask(__name__, static_folder='static')
run1.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
run1.config[
    'SQLALCHEMY_DATABASE_URI'] = f'mariadb+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_table_name}'
login_manager = LoginManager(run1)
login_manager.init_app(run1)
login_manager.login_view = 'login'

secret_key = os.urandom(24)
run1.config['SECRET_KEY'] = secret_key
db = SQLAlchemy(run1)


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


@run1.route('/', methods=['GET', 'POST'])
@run1.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(username=form.username.data).first()
        if user:
            # Check the hash
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                flash("Успешно!")
                return redirect(url_for('general'))
            else:
                print(user.password, form.password.data)
                flash("Неверный Логин или Пароль")
        else:
            flash("Неверный Логин или Пароль")

    return render_template('login.html', form=form)


class Users(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer(), primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(162), nullable=False, unique=True)


@run1.route('/general', methods=['GET', 'POST'])
@login_required
def general():
    if request.method == 'GET':
        return render_template('general.html')
    if request.method == 'POST':
        print(123)
        return jsonify({'message': 'Вы перешли на страницу general'})


@run1.route('/logout/')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('login'))


@run1.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    host, user, password, port, database, table_name = get_db_config()
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()

            cursor.execute(
                f"SELECT Город FROM {table_name} where DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = {str(current_month_index + 1).zfill(2)} group by Город order by Город desc")
            data8 = cursor.fetchall()
            cities = [city[-1] for city in data8]
            town = cities[0]

            cursor.execute(f'SELECT count(Адрес) FROM {table_name} where Город="{town}"')
            data1 = cursor.fetchall()

            # КОЛИЧЕСТВО ВСЕГО ОБРАЩЕНИЙ ЗА МЕСЯЦ ГОРОДА
            cursor.execute((
                f'SELECT count(id) FROM {table_name} where Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data2 = cursor.fetchall()

            # ЗАСТРЕВАНИЯ В МЕСЯЦ ГОРОДА
            cursor.execute((
                f'SELECT count(Причина) FROM {table_name} where Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data3 = cursor.fetchall()

            # НЕИСПРАВНОСТИ ЗА МЕСЯЦ ГОРОДА
            cursor.execute((
                f'SELECT count(Причина) FROM {table_name} where Комментарий<>"Ложная заявка" and (Причина="Неисправность" or Причина="Остановлен") and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data4 = cursor.fetchall()

            # ОСТАНОВЛЕННЫЕ ЗА МЕСЯЦ
            cursor.execute((
                f'SELECT count(Причина) FROM {table_name} where Причина="Остановлен" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data5 = cursor.fetchall()

            # ОСТАНОВЛЕННЫЕ БОЛЕЕ СУТОК ТЕКУЩЕГО МЕСЯЦА
            cursor.execute(
                f'SELECT count(*) FROM {table_name} WHERE Город="{town}" AND Дата_запуска IS NULL AND (UNIX_TIMESTAMP() - Дата_заявки) >= 86400')
            data6 = cursor.fetchall()

            # ЛОЖНЫЕ ТЕКУЩЕГО МЕСЯЦА
            cursor.execute((
                f'SELECT count(Комментарий) FROM {table_name} where Город="{town}" and Комментарий="Ложная заявка" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
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
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 1 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS January,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 2 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS February,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 3 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS March,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 4 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS April,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 5 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS May,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 6 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS June,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 7 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS July,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 8 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS August,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 9 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS September,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 10 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS October,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 11 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS November,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 12 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS December
            FROM {table_name};''')
            data9 = cursor.fetchall()

            # ГРАФИК ЗАСТРЕВАНИЙ СТОЛБЧАТЫЙ
            for i in range(11):
                cursor.execute(f'''SELECT
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('01.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS January,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('02.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS Febriary,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('03.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS March,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('04.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS April,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('05.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS May,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('06.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS June,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('07.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS July,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('08.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS August,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('09.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS September,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('10.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS October,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('11.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS November,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('12.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS December
                    FROM {table_name}''')
            data10 = cursor.fetchall()

            # ПОДСЧЁТ АДРЕСОВ ХУДШИХ ЛИФТОВ
            cursor.execute(f'''SELECT Адрес, Тип_лифта, count(Адрес) as address_count
                                        FROM {table_name} where Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = {str(current_month_index + 1).zfill(2)}
                                        GROUP BY Адрес, Тип_лифта
                                        ORDER BY address_count DESC 
                                        LIMIT 10;''')
            data_count_address = cursor.fetchall()
        return render_template('index.html', data1=data1,
                               data2=data2,
                               data3=data3,
                               data4=data4,
                               data5=data5,
                               data6=data6,
                               data7=data7,
                               data9=data9,
                               data10=data10,
                               data8=cities,
                               data_count_address=data_count_address,
                               procent1=procent1,
                               procent2=procent2,
                               procent3=procent3)
    if request.method == 'POST':
        selected_city = request.json.get('selectedCity')
        town = selected_city

        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()

            cursor.execute(
                f"SELECT Город FROM {table_name} where DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = {str(current_month_index + 1).zfill(2)} group by Город order by Город desc")
            data8 = cursor.fetchall()
            cities = [city[-1] for city in data8]

            cursor.execute((
                f'SELECT count(id) FROM {table_name} where Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data2 = cursor.fetchall()
            #
            cursor.execute((
                f'SELECT count(Причина) FROM {table_name} where Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data3 = cursor.fetchall()
            #
            cursor.execute((
                f'SELECT count(Причина) FROM {table_name} where Комментарий<>"Ложная заявка" and (Причина="Неисправность" or Причина="Остановлен") and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data4 = cursor.fetchall()
            #
            cursor.execute((
                f'SELECT count(Причина) FROM {table_name} where Причина="Остановлен" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data5 = cursor.fetchall()
            #
            cursor.execute(
                f'''SELECT count(*) FROM {table_name} WHERE Город='{town}' and Комментарий<>'Ложная заявка' and Дата_запуска is NULL and TIMESTAMPDIFF(SECOND, FROM_UNIXTIME(Дата_заявки), NOW()) >= 86400 and Причина='Остановлен' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data6 = cursor.fetchall()
            #
            cursor.execute((
                f'SELECT count(Комментарий) FROM {table_name} where Город="{town}" and Комментарий="Ложная заявка" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? '
                f'AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'),
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

            cursor.execute(f'''SELECT
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 1 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS January,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 2 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS February,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 3 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS March,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 4 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS April,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 5 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS May,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 6 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS June,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 7 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS July,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 8 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS August,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 9 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS September,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 10 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS October,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 11 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS November,
                COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 12 and Город="{town}" AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW()) THEN 1 END) AS December
            FROM {table_name};''')
            data9 = cursor.fetchall()
            for i in range(11):
                cursor.execute(f'''SELECT 
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('01.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS January,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('02.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS Febriary,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('03.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS March,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('04.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS April,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('05.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS May,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('06.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS June,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('07.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS July,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('08.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS August,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('09.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS September,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('10.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS October,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('11.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS November,
                    COUNT(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m.%Y") = CONCAT('12.', YEAR(CURDATE())) and Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" THEN 1 END) AS December
                    FROM {table_name}''')
            data10 = cursor.fetchall()
            cursor.execute(f'''SELECT Адрес, Тип_лифта, count(Адрес) as address_count
                                FROM {table_name} where Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = {str(current_month_index + 1).zfill(2)}
                                GROUP BY Адрес, Тип_лифта
                                ORDER BY address_count DESC 
                                LIMIT 10;
                                ''')
            data_count_address = cursor.fetchall()
    return jsonify({'data2': data2,
                    'data3': data3,
                    'data4': data4,
                    'data5': data5,
                    'data6': data6,
                    'data7': data7,
                    'data9': data9,
                    'data10': data10,
                    'data8': cities,
                    'data_count_address': data_count_address,
                    'procent1': procent1,
                    'procent2': procent2,
                    'procent3': procent3})


@run1.route('/poisk', methods=['GET', 'POST'])
# @login_required
def poisk():
    # ОБРАЩЕНИЯ №0
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        host, user, password, port, database, table_name = get_db_config()
        town_url = request.args.get('selectedCity')
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT Город FROM {table_name}  group by Город order by Город desc")
            data2 = cursor.fetchall()
            town = [city[-1] for city in data2]

            cursor.execute(f'''SELECT Номер_заявки,
                                   FROM_UNIXTIME(Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                                   Диспетчер,
                                   Город,
                                   Адрес,
                                   Тип_лифта,
                                   Причина,
                                   ФИО_механика,
                                   FROM_UNIXTIME(Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                                   Комментарий
                                   FROM {table_name}
                                   WHERE Город='{request.args.get('selectedCity')}' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                   AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data1 = cursor.fetchall()

            cursor.execute(f"SELECT Адрес FROM {table_name} where Город='{town_url}' group by Адрес order by Адрес")
            adres = cursor.fetchall()
            print(adres)

        return render_template('poisk.html', data1=data1, town=town, town_url=town_url, adres=adres)

    if request.method == 'POST':
        host, user, password, port, database, table_name = get_db_config()
        town = request.json.get('selectedCity')
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT Адрес FROM {table_name} where Город='{town}' group by Адрес order by Адрес desc")
            adres = cursor.fetchall()
            cities = [i[-1] for i in adres]
        return jsonify({'cities': cities})


@run1.route('/obrasch', methods=['GET', 'POST'])
# @login_required
def obrasch():
    # ОБРАЩЕНИЯ №1
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        host, user, password, port, database, table_name = get_db_config()
        town = request.args.get('selectedCity')
        print(town)
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT Номер_заявки,
                       FROM_UNIXTIME(Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                       Диспетчер,
                       Город,
                       Адрес,
                       Тип_лифта,
                       Причина,
                       ФИО_механика,
                       FROM_UNIXTIME(Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                       Комментарий
                       FROM {table_name}
                       WHERE Город='{town}' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data1 = cursor.fetchall()
        return render_template('obrasch.html', data1=data1, town=town)


@run1.route('/neispr', methods=['GET', 'POST'])
# @login_required
def neispr():
    # НЕИСПРАВНОСТИ №2
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        host, user, password, port, database, table_name = get_db_config()
        town = request.args.get('selectedCity')
        print(town)
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT Номер_заявки,
                       FROM_UNIXTIME(Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                       Диспетчер,
                       Город,
                       Адрес,
                       Тип_лифта,
                       Причина,
                       ФИО_механика,
                       FROM_UNIXTIME(Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                       Комментарий
                       FROM {table_name}
                       WHERE Город='{town}' and Комментарий<>'Ложная заявка' and Причина='Неисправность' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data1 = cursor.fetchall()
        return render_template('neispr.html', data1=data1, town=town)


@run1.route('/zastrev', methods=['GET', 'POST'])
# @login_required
def zastrev():
    # ЗАСТРЕВАНИЯ №3
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        host, user, password, port, database, table_name = get_db_config()
        town = request.args.get('selectedCity')
        print(town)
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT Номер_заявки,
                       FROM_UNIXTIME(Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                       Диспетчер,
                       Город,
                       Адрес,
                       Тип_лифта,
                       Причина,
                       ФИО_механика,
                       FROM_UNIXTIME(Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                       Комментарий
                       FROM {table_name}
                       WHERE Город='{town}' and Комментарий<>'Ложная заявка' and Причина='Застревание' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data1 = cursor.fetchall()
        return render_template('zastrev.html', data1=data1, town=town)


@run1.route('/ostanov', methods=['GET', 'POST'])
# @login_required
def ostanov():
    # ОСТАНОВКИ №4
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        host, user, password, port, database, table_name = get_db_config()
        town = request.args.get('selectedCity')
        print(town)
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT Номер_заявки,
                       FROM_UNIXTIME(Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                       Диспетчер,
                       Город,
                       Адрес,
                       Тип_лифта,
                       Причина,
                       ФИО_механика,
                       FROM_UNIXTIME(Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                       Комментарий
                       FROM {table_name}
                       WHERE Город='{town}' and Комментарий<>'Ложная заявка' and Причина='Остановлен' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data1 = cursor.fetchall()
        return render_template('ostanov.html', data1=data1, town=town)


@run1.route('/ostanov_more', methods=['GET', 'POST'])
# @login_required
def ostanov_more():
    # ОСТАНОВКИ БОЛЕЕ СУТОК №5
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        host, user, password, port, database, table_name = get_db_config()
        town = request.args.get('selectedCity')
        print(town)
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT Номер_заявки,
                       FROM_UNIXTIME(Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                       Диспетчер,
                       Город,
                       Адрес,
                       Тип_лифта,
                       Причина,
                       ФИО_механика,
                       FROM_UNIXTIME(Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                       Комментарий
                       FROM {table_name}
                       WHERE Город='{town}' and Комментарий<>'Ложная заявка' and Дата_запуска is NULL and TIMESTAMPDIFF(SECOND, FROM_UNIXTIME(Дата_заявки), NOW()) >= 86400 and Причина='Остановлен' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data1 = cursor.fetchall()
            print(data1)
        return render_template('ostanov_more.html', data1=data1, town=town)


@run1.route('/lojnie', methods=['GET', 'POST'])
# @login_required
def lojnie():
    # ЛОЖНЫЕ ЗАЯВКИ №6
    if request.method == 'GET':
        current_month_index = int((datetime.datetime.now(tz=None)).strftime("%m")) - 1
        current_year_index = int((datetime.datetime.now(tz=None)).strftime("%Y"))
        host, user, password, port, database, table_name = get_db_config()
        town = request.args.get('selectedCity')
        print(town)
        with closing(mariadb.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=database)) as connection:
            cursor = connection.cursor()
            cursor.execute(f'''SELECT Номер_заявки,
                       FROM_UNIXTIME(Дата_заявки, '%d.%m.%Y, %H:%i') as Дата_заявки,
                       Диспетчер,
                       Город,
                       Адрес,
                       Тип_лифта,
                       Причина,
                       ФИО_механика,
                       FROM_UNIXTIME(Дата_запуска, '%d.%m.%Y, %H:%i') as Дата_запуска,
                       Комментарий
                       FROM {table_name}
                       WHERE Город='{town}' and Комментарий='Ложная заявка' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                       AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data1 = cursor.fetchall()
        return render_template('lojnie.html', data1=data1, town=town)


def get_db_config():
    with open('config.json', 'r') as file:
        data = json.loads(file.read())
        return data['db_host'], data['db_user'], data['db_password'], data['db_port'], data['db_name'], data[
            'table_name']


if __name__ == '__main__':
    run1.run(debug=True, host='10.40.1.40', port=8080)
