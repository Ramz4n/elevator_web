"""
Скрипт для включения детального логирования кэша

Добавьте этот код в начало функции base() в tester.py
чтобы видеть что происходит с кэшем в реальном времени
"""

# ============= ВАРИАНТ 1: Простое логирование =============

"""
В начало функции base() добавьте:

import time

print("="*60)
print("ЗАГРУЗКА СТРАНИЦЫ /base")
print("="*60)

start_total = time.time()

# Перед каждым запросом к данным:
print("\\n🔍 Получаем data9...")
start = time.time()
data9 = yearly_cache.get_or_fetch(town, 'data9', fetch_data9)
print(f"✅ data9 получен за {time.time() - start:.3f} сек")

# ... аналогично для других данных ...

print(f"\\n⏱️  ИТОГО: страница загружена за {time.time() - start_total:.3f} сек")
print("="*60)
"""

# ============= ВАРИАНТ 2: Детальное логирование =============

"""
Модифицируйте yearly_stats_cache.py:

В функцию get_or_fetch() добавьте логи:

def get_or_fetch(self, town, data_type, fetch_func, year=None):
    # Добавьте в начало:
    import time

    cached = self.get(town, data_type, year)
    if cached is not None:
        print(f"   ✅ КЭШ: {data_type} для '{town}' взят из кэша")
        return cached

    print(f"   🔄 БД:  {data_type} для '{town}' запрашивается из базы...")
    start = time.time()
    fresh_data = fetch_func()
    elapsed = time.time() - start
    print(f"   💾 БД:  Запрос выполнен за {elapsed:.3f} сек, сохраняю в кэш...")

    self.save(town, data_type, fresh_data, year)
    return fresh_data
"""

# ============= ВАРИАНТ 3: Webhook для мониторинга =============

"""
Создайте роут для просмотра статистики кэша:

@tester.route('/cache_stats')
@login_required
def cache_stats():
    from pathlib import Path
    import json

    cache_dir = Path('cache')
    cache_files = list(cache_dir.glob('*.json'))

    stats = {
        'total_files': len(cache_files),
        'total_size': sum(f.stat().st_size for f in cache_files),
        'files': []
    }

    for f in cache_files:
        with open(f, 'r') as file:
            data = json.load(file)
            stats['files'].append({
                'name': f.name,
                'size': f.stat().st_size,
                'cached_month': data.get('cached_month'),
                'last_update': data.get('last_update')
            })

    return jsonify(stats)

# Доступ: http://your-site.com/cache_stats
"""

print(__doc__)
