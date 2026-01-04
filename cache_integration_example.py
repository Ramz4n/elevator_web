"""
ПРИМЕР ИНТЕГРАЦИИ КЭШИРОВАНИЯ В tester.py

Добавьте этот код в начало файла tester.py (после импортов):
"""

# ============= ДОБАВИТЬ В НАЧАЛО tester.py =============

from yearly_stats_cache import yearly_cache

# ============= ПРИМЕР ИСПОЛЬЗОВАНИЯ В РОУТЕ /base =============

# БЫЛО (медленно - каждый раз делает запрос):
"""
cursor.execute('''SELECT
    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
    ...
    FROM {table_name} z
    WHERE Город = %s AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW())
    AND NOT pc_id IS NULL;''', (town,))
data9 = cursor.fetchall()
"""

# СТАЛО (быстро - использует кэш для прошлых месяцев):
"""
def fetch_data9():
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
    return cursor.fetchall()

# Используем кэш
data9 = yearly_cache.get_or_fetch(town, 'data9', fetch_data9)
"""

# ============= ПОЛНЫЙ ПРИМЕР ЗАМЕНЫ В РОУТЕ =============

"""
@tester.route('/base', methods=['GET', 'POST'])
@login_required
def base():
    if request.method == 'GET':
        # ... существующий код ...

        with closing(db_manager.connect()) as connection:
            cursor = connection.cursor()

            # ГРАФИК ОБРАЩЕНИЙ ЛИНЕЙНЫЙ (data9)
            if town:
                def fetch_data9():
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
                    return cursor.fetchall()

                # Используем кэш!
                data9 = yearly_cache.get_or_fetch(town, 'data9', fetch_data9)
            else:
                # Аналогично для "все города"
                def fetch_data9_all():
                    cursor.execute(f'''SELECT ... ''')
                    return cursor.fetchall()

                data9 = yearly_cache.get_or_fetch(None, 'data9', fetch_data9_all)

            # Аналогично для data3, data4, data7, data10, data12, data13
            # ...
"""

# ============= КАК ЭТО РАБОТАЕТ =============

"""
1. При первом запросе:
   - fetch_data9() выполняется (делается запрос к БД)
   - Результат сохраняется в кэш
   - Возвращается результат

2. При повторных запросах:
   - Если текущий месяц НЕ изменился И прошло < 30 минут:
     * Данные берутся из кэша (БЫСТРО!)
     * Запрос к БД не делается

   - Если текущий месяц изменился (например был март, стал апрель):
     * Кэш считается устаревшим
     * Делается новый запрос к БД
     * Обновляется кэш

   - Если прошло > 30 минут:
     * Обновляются данные текущего месяца
     * Прошлые месяцы остаются из кэша

3. Преимущества:
   - Прошлые месяцы НИКОГДА не пересчитываются (январь 2024 всегда одинаковый)
   - Текущий месяц обновляется каждые 30 минут
   - Запросы к БД сократятся в 10-100 раз!
"""

# ============= РУЧНАЯ ОЧИСТКА КЭША =============

"""
# Очистить кэш для конкретного города и типа данных
yearly_cache.invalidate(town='Москва', data_type='data9', year=2024)

# Очистить весь кэш за 2024 год
yearly_cache.invalidate(year=2024)

# Очистить всё
import shutil
shutil.rmtree('cache')
os.makedirs('cache')
"""
