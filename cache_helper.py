"""
Модуль для кэширования статистики по месяцам
Кэширует данные за завершенные месяцы, текущий месяц всегда считает заново
"""
import json
import os
from datetime import datetime
from pathlib import Path


class MonthlyStatsCache:
    """Кэш для месячной статистики"""

    def __init__(self, cache_dir='cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year

    def _get_cache_key(self, town, data_type, month, year):
        """Генерирует ключ для кэша"""
        town_safe = town if town else 'all'
        return f"{town_safe}_{data_type}_{year}_{month:02d}"

    def _get_cache_file(self, cache_key):
        """Возвращает путь к файлу кэша"""
        return self.cache_dir / f"{cache_key}.json"

    def _is_past_month(self, month, year):
        """Проверяет является ли месяц завершенным"""
        if year < self.current_year:
            return True
        if year == self.current_year and month < self.current_month:
            return True
        return False

    def get_cached_data(self, town, data_type, month, year):
        """
        Получает данные из кэша если месяц завершен
        Возвращает None если данных нет в кэше или это текущий месяц
        """
        # Текущий месяц никогда не кэшируем
        if not self._is_past_month(month, year):
            return None

        cache_key = self._get_cache_key(town, data_type, month, year)
        cache_file = self._get_cache_file(cache_key)

        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка чтения кэша {cache_key}: {e}")
                return None
        return None

    def save_to_cache(self, town, data_type, month, year, data):
        """
        Сохраняет данные в кэш только если месяц завершен
        """
        # Текущий месяц не кэшируем
        if not self._is_past_month(month, year):
            return False

        cache_key = self._get_cache_key(town, data_type, month, year)
        cache_file = self._get_cache_file(cache_key)

        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения кэша {cache_key}: {e}")
            return False

    def get_yearly_data(self, town, data_type, year, fetch_callback):
        """
        Получает данные за весь год
        Использует кэш для завершенных месяцев, fetch_callback для текущего

        fetch_callback: функция которая получает данные из БД
                       принимает (month, year) возвращает значение
        """
        yearly_data = {}

        for month in range(1, 13):
            # Пробуем получить из кэша
            cached_value = self.get_cached_data(town, data_type, month, year)

            if cached_value is not None:
                yearly_data[month] = cached_value
            else:
                # Получаем из БД
                fresh_value = fetch_callback(month, year)
                yearly_data[month] = fresh_value

                # Сохраняем в кэш если месяц завершен
                self.save_to_cache(town, data_type, month, year, fresh_value)

        return yearly_data

    def clear_cache(self, town=None, data_type=None):
        """Очищает кэш (опционально только для определенного города/типа)"""
        pattern = "*"
        if town:
            town_safe = town if town else 'all'
            pattern = f"{town_safe}_*"
        if data_type:
            pattern = f"*_{data_type}_*"

        for cache_file in self.cache_dir.glob(f"{pattern}.json"):
            try:
                cache_file.unlink()
            except Exception as e:
                print(f"Ошибка удаления {cache_file}: {e}")

    def clean_old_years(self, keep_years=2):
        """Удаляет кэш за старые годы (оставляет только последние N лет)"""
        min_year = self.current_year - keep_years

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                # Парсим имя файла: town_datatype_year_month.json
                parts = cache_file.stem.split('_')
                if len(parts) >= 3:
                    year = int(parts[-2])
                    if year < min_year:
                        cache_file.unlink()
                        print(f"Удален старый кэш: {cache_file.name}")
            except Exception as e:
                print(f"Ошибка при очистке {cache_file}: {e}")


# Глобальный экземпляр кэша
stats_cache = MonthlyStatsCache()
