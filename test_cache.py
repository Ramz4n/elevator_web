#!/usr/bin/env python3
"""
Скрипт для тестирования кэширования
Запуск: python test_cache.py
"""

import time
from yearly_stats_cache import yearly_cache


def mock_db_query():
    """Имитация медленного запроса к БД"""
    print("    🔄 Выполняется 'запрос к БД'...")
    time.sleep(2)  # Имитация медленного запроса
    return [
        (10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65)  # Данные за 12 месяцев
    ]


def test_cache_performance():
    """Тест производительности кэша"""
    print("\n" + "="*60)
    print("ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ КЭШИРОВАНИЯ")
    print("="*60)

    town = "Москва"
    data_type = "test_data"

    # Очистим кэш перед тестом
    yearly_cache.invalidate(town, data_type)
    print("\n✅ Кэш очищен")

    # Тест 1: Первый запрос (без кэша)
    print("\n📊 ТЕСТ 1: Первый запрос (создание кэша)")
    print("-" * 60)
    start = time.time()
    data1 = yearly_cache.get_or_fetch(town, data_type, mock_db_query)
    time1 = time.time() - start
    print(f"    ⏱️  Время: {time1:.3f} секунд")
    print(f"    📦 Данные: {data1}")

    # Тест 2: Повторный запрос (из кэша)
    print("\n📊 ТЕСТ 2: Повторный запрос (из кэша)")
    print("-" * 60)
    start = time.time()
    data2 = yearly_cache.get_or_fetch(town, data_type, mock_db_query)
    time2 = time.time() - start
    print(f"    ⏱️  Время: {time2:.3f} секунд")
    print(f"    📦 Данные: {data2}")

    # Тест 3: Еще раз из кэша
    print("\n📊 ТЕСТ 3: Третий запрос (тоже из кэша)")
    print("-" * 60)
    start = time.time()
    data3 = yearly_cache.get_or_fetch(town, data_type, mock_db_query)
    time3 = time.time() - start
    print(f"    ⏱️  Время: {time3:.3f} секунд")
    print(f"    📦 Данные: {data3}")

    # Результаты
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ")
    print("="*60)
    print(f"Первый запрос (без кэша):  {time1:.3f} сек")
    print(f"Второй запрос (из кэша):   {time2:.3f} сек  🚀 Ускорение: {time1/time2:.0f}x")
    print(f"Третий запрос (из кэша):   {time3:.3f} сек  🚀 Ускорение: {time1/time3:.0f}x")

    if time2 < 0.1:
        print("\n✅ ОТЛИЧНО! Кэш работает идеально!")
    elif time2 < time1 / 2:
        print("\n✅ ХОРОШО! Кэш работает и ускоряет запросы")
    else:
        print("\n⚠️  ВНИМАНИЕ! Кэш может работать неправильно")

    print("="*60)


def test_cache_files():
    """Проверка файлов кэша"""
    import os
    from pathlib import Path

    print("\n" + "="*60)
    print("ПРОВЕРКА ФАЙЛОВ КЭША")
    print("="*60)

    cache_dir = Path('cache')

    if not cache_dir.exists():
        print("❌ Папка cache/ не существует!")
        print("   Создаю папку...")
        cache_dir.mkdir()
        print("✅ Папка cache/ создана")
        return

    cache_files = list(cache_dir.glob('*.json'))

    print(f"\n📁 Папка кэша: {cache_dir.absolute()}")
    print(f"📊 Файлов в кэше: {len(cache_files)}")

    if cache_files:
        print("\n📄 Список файлов кэша:")
        total_size = 0
        for f in cache_files:
            size = f.stat().st_size
            total_size += size
            print(f"   - {f.name} ({size:,} байт)")

        print(f"\n💾 Общий размер кэша: {total_size:,} байт ({total_size/1024:.2f} KB)")

        # Покажем содержимое одного файла
        if cache_files:
            import json
            sample_file = cache_files[0]
            print(f"\n📋 Содержимое файла {sample_file.name}:")
            with open(sample_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                print(json.dumps(content, indent=2, ensure_ascii=False)[:500] + "...")
    else:
        print("📭 Кэш пуст. Файлы будут создаваться при первом использовании.")

    print("="*60)


def test_with_real_db():
    """Тест с реальной БД (если доступна)"""
    print("\n" + "="*60)
    print("ТЕСТ С РЕАЛЬНОЙ БАЗОЙ ДАННЫХ")
    print("="*60)

    try:
        from db_manager import DataBaseManager
        from contextlib import closing
        import json

        # Загружаем конфиг
        with open('vostok.json', 'r') as f:
            config_data = json.loads(f.read())

        db_manager = DataBaseManager('vostok')
        table_name = config_data['table_name']

        print("✅ Подключение к БД установлено")
        print(f"📊 Таблица: {table_name}")

        with closing(db_manager.connect()) as connection:
            cursor = connection.cursor()

            town = "Москва"  # Замените на реальный город из вашей БД

            # Функция запроса
            def fetch_real_data():
                print("    🔄 Выполняется реальный запрос к БД...")
                cursor.execute(f'''SELECT
                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 1 THEN 1 END) AS January,
                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 2 THEN 1 END) AS February,
                    COUNT(CASE WHEN EXTRACT(MONTH FROM FROM_UNIXTIME(Дата_заявки)) = 3 THEN 1 END) AS March
                    FROM {table_name} z
                    JOIN doma d ON z.id_дом = d.id
                    JOIN street s ON d.id_улица = s.id
                    JOIN goroda g ON s.id_город = g.id
                    WHERE Город = %s
                    AND EXTRACT(YEAR FROM FROM_UNIXTIME(Дата_заявки)) = YEAR(NOW())
                    AND NOT pc_id IS NULL
                    LIMIT 1;''', (town,))
                return cursor.fetchall()

            # Очистим кэш
            yearly_cache.invalidate(town, 'real_test')

            # Первый запрос
            print("\n1️⃣ Первый запрос (к БД):")
            start = time.time()
            data1 = yearly_cache.get_or_fetch(town, 'real_test', fetch_real_data)
            time1 = time.time() - start
            print(f"   ⏱️  Время: {time1:.3f} сек")
            print(f"   📦 Результат: {data1}")

            # Второй запрос
            print("\n2️⃣ Второй запрос (из кэша):")
            start = time.time()
            data2 = yearly_cache.get_or_fetch(town, 'real_test', fetch_real_data)
            time2 = time.time() - start
            print(f"   ⏱️  Время: {time2:.3f} сек")
            print(f"   📦 Результат: {data2}")

            print(f"\n🚀 Ускорение: {time1/time2:.0f}x раз!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("   (Это нормально если БД не доступна или конфиг не настроен)")

    print("="*60)


def main():
    """Главная функция"""
    print("\n" + "="*60)
    print(" 🧪 ТЕСТИРОВАНИЕ СИСТЕМЫ КЭШИРОВАНИЯ")
    print("="*60)

    # Тест 1: Производительность
    test_cache_performance()

    # Тест 2: Файлы кэша
    test_cache_files()

    # Тест 3: Реальная БД (опционально)
    try_real_db = input("\n❓ Протестировать с реальной БД? (y/n): ").lower()
    if try_real_db == 'y':
        test_with_real_db()

    print("\n✅ Тестирование завершено!\n")


if __name__ == "__main__":
    main()
