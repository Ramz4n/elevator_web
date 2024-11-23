import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import mariadb
import json
from contextlib import closing


def index_osp():
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
                f'''SELECT g.Город FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = {str(current_month_index + 1).zfill(2)}
                group by Город order by Город desc''')
            data8 = cursor.fetchall()
            cities = [city[-1] for city in data8]
            town = cities[0]

            # КОЛИЧЕСТВО ВСЕГО ОБРАЩЕНИЙ ЗА МЕСЯЦ ГОРОДА
            cursor.execute((
                f'''SELECT count(z.id) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data2 = cursor.fetchall()

            # ЗАСТРЕВАНИЯ В МЕСЯЦ ГОРОДА
            cursor.execute((
                f'''SELECT count(Причина) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data3 = cursor.fetchall()

            # НЕИСПРАВНОСТИ ЗА МЕСЯЦ ГОРОДА
            cursor.execute((
                f'''SELECT count(Причина) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Комментарий<>"Ложная заявка" and (Причина="Неисправность" or Причина="Остановлен") and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data4 = cursor.fetchall()

            # ОСТАНОВЛЕННЫЕ ЗА МЕСЯЦ
            cursor.execute((
                f'''SELECT count(Причина) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Причина="Остановлен" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data5 = cursor.fetchall()

            # ОСТАНОВЛЕННЫЕ БОЛЕЕ СУТОК ТЕКУЩЕГО МЕСЯЦА
            cursor.execute(f'''SELECT count(*) FROM {table_name} z
                            JOIN goroda g ON z.id_город = g.id
                            WHERE Город='{town}' and Комментарий<>'Ложная заявка' 
                            and Дата_запуска is NULL and TIMESTAMPDIFF(SECOND, FROM_UNIXTIME(Дата_заявки), NOW()) >= 86400 
                            and Причина='Остановлен' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                            AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data6 = cursor.fetchall()

            # ЛОЖНЫЕ ТЕКУЩЕГО МЕСЯЦА
            cursor.execute((
                f'''SELECT count(Комментарий) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Город="{town}" and Комментарий="Ложная заявка" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
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
            FROM {table_name} z 
            JOIN goroda g ON z.id_город = g.id;''')
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
                    FROM {table_name} z JOIN goroda g ON z.id_город = g.id''')
            data10 = cursor.fetchall()

            # ПОДСЧЁТ АДРЕСОВ ХУДШИХ ЛИФТОВ
            cursor.execute(f'''SELECT Город, concat(u.улица, ',', d.номер, ',', p.номер) as Адрес, Тип_лифта, 
                                        count(concat(u.улица, ',', d.номер, ',', p.номер)) as address_count
                                        FROM {table_name} z
                                        JOIN goroda g ON z.id_город = g.id
                                        JOIN street u ON z.id_улица = u.id
                                        JOIN doma d ON z.id_дом = d.id
                                        JOIN padik p ON z.id_подъезд = p.id
                                        where DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = {str(current_month_index + 1).zfill(2)}
                                        GROUP BY u.`улица`, d.`номер`, p.`номер`, Тип_лифта
                                        ORDER BY address_count DESC 
                                        LIMIT 10;''')
            data_count_address = cursor.fetchall()
        return render_template('index.html',
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
        host, user, password, port, database, table_name = get_db_config()
        selected_city = request.json.get('selectedCity')
        town = selected_city
        print("или сюда залетает")
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
                f'''SELECT g.Город FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = {str(current_month_index + 1).zfill(2)} 
                group by Город order by Город desc''')
            data8 = cursor.fetchall()
            cities = [city[-1] for city in data8]

            cursor.execute((
                f'''SELECT count(z.id) FROM {table_name}
                JOIN goroda g ON z.id_город = g.id
                where Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data2 = cursor.fetchall()
            #
            cursor.execute((
                f'''SELECT count(Причина) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Комментарий<>"Ложная заявка" and Причина="Застревание" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data3 = cursor.fetchall()
            #
            cursor.execute((
                f'''SELECT count(Причина) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Комментарий<>"Ложная заявка" and (Причина="Неисправность" or Причина="Остановлен") 
                and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data4 = cursor.fetchall()
            #
            cursor.execute((
                f'''SELECT count(Причина) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Причина="Остановлен" and Город="{town}" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ? 
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
                (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data5 = cursor.fetchall()
            #
            cursor.execute(f'''SELECT count(*) FROM {table_name} z
                                        JOIN goroda g ON z.id_город = g.id
                                        WHERE Город='{town}' and Комментарий<>'Ложная заявка' 
                                        and Дата_запуска is NULL and TIMESTAMPDIFF(SECOND, FROM_UNIXTIME(Дата_заявки), NOW()) >= 86400 
                                        and Причина='Остановлен' and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%m') = ?
                                        AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), '%Y') = ?;''',
                           (f'{str(current_month_index + 1).zfill(2)}', f'{str(current_year_index)}',))
            data6 = cursor.fetchall()
            #
            cursor.execute((
                f'''SELECT count(Комментарий) FROM {table_name} z
                JOIN goroda g ON z.id_город = g.id
                where Город="{town}" and Комментарий="Ложная заявка" and DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = ?
                AND DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%Y") = ?'''),
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
            FROM {table_name} z JOIN goroda g ON z.id_город = g.id;''')
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
                    FROM {table_name} z JOIN goroda g ON z.id_город = g.id;''')
            data10 = cursor.fetchall()
            cursor.execute(f'''SELECT Город, concat(u.улица, ',', d.номер, ',', p.номер) as Адрес, Тип_лифта, 
                                                    count(concat(u.улица, ',', d.номер, ',', p.номер)) as address_count
                                                    FROM {table_name} z
                                                    JOIN goroda g ON z.id_город = g.id
                                                    JOIN street u ON z.id_улица = u.id
                                                    JOIN doma d ON z.id_дом = d.id
                                                    JOIN padik p ON z.id_подъезд = p.id
                                                    where DATE_FORMAT(FROM_UNIXTIME(Дата_заявки), "%m") = {str(current_month_index + 1).zfill(2)}
                                                    GROUP BY u.`улица`, d.`номер`, p.`номер`, Тип_лифта
                                                    ORDER BY address_count DESC 
                                                    LIMIT 10;''')
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


def get_db_config():
    with open('ospmitol.json', 'r') as file:
        data = json.loads(file.read())
        return data['db_host'], data['db_user'], data['db_password'], data['db_port'], data['db_name'], data[
            'table_name']
