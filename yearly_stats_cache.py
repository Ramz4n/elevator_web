"""
Кэширование годовых статистик
Простой вариант - кэшируем весь результат, но умно обновляем только при изменениях
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path


class YearlyStatsCache:
    """Кэш для годовой статистики"""

    def __init__(self, cache_dir='cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_key(self, town, data_type, year):
        """Генерирует ключ кэша"""
        town_safe = town if town else 'all_cities'
        return f"yearly_{town_safe}_{data_type}_{year}"

    def _get_cache_file(self, cache_key):
        """Путь к файлу кэша"""
        return self.cache_dir / f"{cache_key}.json"

    def _should_recalculate(self, cached_data):
        """
        Проверяет нужно ли пересчитывать данные

        Пересчитываем если:
        1. Текущий месяц в кэше не совпадает с реальным
        2. Данные за текущий месяц могли измениться
        """
        current_month = datetime.now().month
        cached_month = cached_data.get('cached_month')

        # Если кэш создан в другом месяце - нужно пересчитать
        if cached_month != current_month:
            return True

        # Проверяем время последнего обновления
        # Если прошло больше N минут - обновляем текущий месяц
        last_update = cached_data.get('last_update')
        if last_update:
            from datetime import datetime, timedelta
            last_update_time = datetime.fromisoformat(last_update)
            # Обновляем каждые 30 минут для текущего месяца
            if datetime.now() - last_update_time > timedelta(minutes=30):
                return True

        return False

    def get(self, town, data_type, year=None):
        """Получает данные из кэша"""
        if year is None:
            year = datetime.now().year

        cache_key = self._get_cache_key(town, data_type, year)
        cache_file = self._get_cache_file(cache_key)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)

            # Для текущего года проверяем нужно ли обновить
            if year == datetime.now().year:
                if self._should_recalculate(cached_data):
                    return None  # Нужно пересчитать

            return cached_data.get('data')

        except Exception as e:
            print(f"Ошибка чтения кэша {cache_key}: {e}")
            return None

    def save(self, town, data_type, data, year=None):
        """Сохраняет данные в кэш"""
        if year is None:
            year = datetime.now().year

        cache_key = self._get_cache_key(town, data_type, year)
        cache_file = self._get_cache_file(cache_key)

        cached_data = {
            'data': data,
            'cached_month': datetime.now().month,
            'last_update': datetime.now().isoformat(),
            'year': year
        }

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения кэша {cache_key}: {e}")
            return False

    def invalidate(self, town=None, data_type=None, year=None):
        """Удаляет кэш"""
        if year is None:
            year = datetime.now().year

        if town and data_type:
            # Удаляем конкретный кэш
            cache_key = self._get_cache_key(town, data_type, year)
            cache_file = self._get_cache_file(cache_key)
            if cache_file.exists():
                cache_file.unlink()
        else:
            # Удаляем все по паттерну
            pattern = f"yearly_*_{year}.json"
            for cache_file in self.cache_dir.glob(pattern):
                cache_file.unlink()

    def get_or_fetch(self, town, data_type, fetch_func, year=None):
        """
        Универсальная функция: получить из кэша или выполнить запрос

        Args:
            town: город
            data_type: тип данных (data9, data10 и т.д.)
            fetch_func: функция которая выполняет запрос к БД
            year: год (по умолчанию текущий)

        Returns:
            Данные из кэша или результат fetch_func
        """
        # Пытаемся получить из кэша
        cached = self.get(town, data_type, year)
        if cached is not None:
            return cached

        # Если в кэше нет - выполняем запрос
        fresh_data = fetch_func()

        # Сохраняем в кэш
        self.save(town, data_type, fresh_data, year)

        return fresh_data


# Глобальный экземпляр
yearly_cache = YearlyStatsCache()
