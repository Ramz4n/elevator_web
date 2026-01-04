"""
Готовые функции с кэшированием для роута /base

Используйте эти функции вместо прямых SQL запросов
"""
from yearly_stats_cache import yearly_cache


def get_data9_cached(cursor, table_name, town=None):
    """
    График обращений линейный (data9) с кэшированием
    """
    def fetch_func():
        if town:
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
                WHERE Город = %s
                AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW())
                AND NOT pc_id IS NULL;''', (town,))
        else:
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
                COUNT(CASE WHEN MONTH(FROM_UNIXTIME(Дата_заявки)) = 12 THEN 1 END) AS December
                FROM {table_name} z
                JOIN doma d ON z.id_дом = d.id
                JOIN street s ON d.id_улица = s.id
                JOIN goroda g ON s.id_город = g.id
                WHERE EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW())
                AND NOT pc_id IS NULL;''')
        return cursor.fetchall()

    return yearly_cache.get_or_fetch(town, 'data9', fetch_func)


def get_data10_cached(cursor, table_name, town=None):
    """
    График застреваний столбчатый (data10) с кэшированием
    """
    def fetch_func():
        if town:
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
                WHERE Город = %s
                AND Причина = 'Застревание'
                AND NOT (LOWER(Комментарий) LIKE '%ложная%' OR LOWER(Комментарий) LIKE '%на момент%')
                AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE())
                AND NOT pc_id IS NULL;''', (town,))
        else:
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
                AND NOT (LOWER(Комментарий) LIKE '%ложная%' OR LOWER(Комментарий) LIKE '%на момент%')
                AND YEAR(FROM_UNIXTIME(Дата_заявки)) = YEAR(CURDATE())
                AND NOT pc_id IS NULL;''')
        return cursor.fetchall()

    return yearly_cache.get_or_fetch(town, 'data10', fetch_func)


# Добавьте аналогичные функции для data12, data13, data3, data4, data7
# По тому же шаблону
