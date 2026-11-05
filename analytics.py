"""Расчёт показателей для страницы «Аналитика» (сводка для руководства)."""
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime

MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль',
          'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
DOWNTIME_REASONS = ('Неисправность', 'Застревание', 'Остановлен')
# SQL: причина заявки не в лифте: вандализм, пожарная сигнализация. z — таблица заявок
NOISE_TICKET_SQL = """(LOWER(COALESCE(z.Комментарий, '')) LIKE '%вандал%'
                        OR LOWER(COALESCE(z.Комментарий, '')) LIKE '%пож%')"""
# SQL: заявка не считается неисправностью лифта. Сюда же входят ложные заявки: поломка не подтвердилась
FALSE_TICKET_SQL = f"""(LOWER(COALESCE(z.Комментарий, '')) LIKE '%на момент осмотра%'
                        OR LOWER(COALESCE(z.Комментарий, '')) LIKE '%ложн%'
                        OR {NOISE_TICKET_SQL})"""
# Диспетчер пишет или «ложная», или «на момент осмотра»: это одно и то же
INSPECTION_MARKS = ('на момент осмотра', 'ложн')
NOISE_WORDS = ('вандал', 'пож')
# Новая неисправность раньше этого срока после ремонта считается повтором
REPEAT_DAYS = 3
LIFT_PERIODS = (3, 6, 12, 0)  # месяцев, 0: всё время
LIFT_DEFAULT_PERIOD = 12
LIFT_CHART_LABELS = 14  # если месяцев больше, подпись остаётся у каждого второго

# Выводы карточки лифта. Пороги подобраны по журналу: за 12 месяцев вывод есть примерно у четверти лифтов
FINDING_MIN_FAULTS = 10  # при меньшем числе неисправностей о лифте выводов не делаем
FINDING_OFTEN_RATIO = 3  # во сколько раз чаще среднего по городу лифт считается часто ломающимся
FINDING_REPEAT_RATIO = 2
FINDING_QUICK_HOURS = 4  # обычный ремонт не дольше этого считается быстрым
FINDING_ONE_REPAIR_SHARE = 0.5  # доля простоя, которую дал один ремонт
FINDING_ONE_REPAIR_HOURS = 24
FINDING_MIN_COUNT = 5  # меньше стольких одинаковых заявок на закономерность не похоже
FINDING_SHARE = 0.3
FINDING_MANY = 10  # столько одинаковых заявок показываем при любой доле
FINDING_MECHANIC_SHARE = 0.5
# Статус «Сейчас»: последние дни сравниваются с предыдущими. Статус считается на сегодня, по всем годам
STATUS_RECENT_DAYS = 30
STATUS_BASE_DAYS = 180
STATUS_LESS_SHARE = 0.5  # «стало реже»: от обычной частоты осталось не больше этой доли
STATUS_FIXED_EXPECTED = 2  # вывод о тишине пишем, если за такой срок обычно было хотя бы столько заявок
STATUS_LIKELY_FIXED_DAYS = 60  # раньше этого срока пишем «наблюдаем», а не «похоже, устранили»
STATUS_ORDER = {'active': 0, 'less': 1, 'quiet': 2}
ATTENTION_SHOWN = 20  # сколько лифтов блока «На что обратить внимание» видно сразу
MECHANIC_MIN_FAULTS = 50  # на меньшем числе заявок доля перезапусков случайна
MECHANIC_HIGH_RATIO = 3  # доля считается высокой, если она во столько раз больше обычной
MECHANIC_HIGH_SHARE = 0.1  # и не меньше этого: иначе при почти нулевой обычной доле высокими станут все
# В комментарии есть перезапуск, но нет работ и внешней причины (пропало питание и т.п.)
RESTART_WORD = 'перезапуск'
RESTART_EXCEPT = ('замен', 'регулировк', 'ремонт', 'чистк', 'смазк', 'протяжк', 'настройк', 'подтяж',
                  'электроэнерг', 'напряжен', 'скач', 'фаз')
INSPECTION_SHARE = 0.2  # доля ложных заявок среди всех заявок лифта
ERROR_CODE = re.compile(r'(?:авари[яи]|ошибк[аи])\s*№?\s*(\d{1,3})')
NODES = {name: re.compile(pattern) for name, pattern in {
    'двери и приводы дверей': r'двер|створк|привод',
    'замки и контакты': r'замк|замок|контакт',
    'плата и АСУД': r'\bплат|асуд|электроник',
    'пускатели и автоматы': r'пускател|автомат',
    'концевики и датчики': r'концев|датчик',
    'охрана шахты': r'охран|\bош\s*\d{1,2}\s*эт',
    'ловители и натяжное устройство': r'ловител|натяж',
    'кнопки': r'кнопк',
    'канаты, лебёдка, тормоз': r'канат|леб[её]дк|тормоз',
}.items()}
# Месяц считается полным, если заявок в нём хотя бы половина от обычного месяца
COMPLETE_MONTH_SHARE = 0.5
# Меньше стольких ремонтов медиана ни о чём не говорит
MIN_REPAIRS = 5
GROWTH_MIN_TICKETS = 100
# На меньшем числе лифтов процент изменения прыгает от случайных заявок
MIN_COMPARE_LIFTS = 30


def repair_text(seconds):
    """Время ремонта заявки: ещё открыта, ошибка в датах или длительность."""
    if seconds is None:
        return 'Открыта'
    if seconds <= 0:
        return '—'
    return format_duration(seconds / 3600)


def ticket_view(number, date, reason, seconds, comment):
    """Заявка для окна «Заявки лифта»."""
    return {'number': number, 'date': date, 'reason': reason, 'comment': comment or '', 'repair': repair_text(seconds)}


def complete_months(monthly):
    """Месяцы с полными данными. monthly: {(год, месяц): заявок}.

    Последний месяц в базе всегда может быть ещё не закончен, поэтому не считается.
    """
    if not monthly:
        return set()
    threshold = statistics.median(monthly.values()) * COMPLETE_MONTH_SHARE
    last = max(monthly)
    return {key for key, count in monthly.items() if key != last and count >= threshold}


def choose_period(year, complete):
    """Месяцы выбранного года и признак, есть ли с чем сравнивать в прошлом году."""
    months = {m for y, m in complete if y == year}
    common = {m for m in months if (year - 1, m) in complete}
    if common:
        return sorted(common), True
    return sorted(months), False


def period_label(months):
    if not months:
        return ''
    if len(months) == 1:
        return MONTHS[months[0] - 1]
    if months[-1] - months[0] + 1 == len(months):
        return f'{MONTHS[months[0] - 1]}–{MONTHS[months[-1] - 1]}'
    return ', '.join(MONTHS[m - 1] for m in months)


def format_number(value, digits=1):
    return f'{value:.{digits}f}'.replace('.', ',')


def format_duration(hours):
    """1.25 -> «1 ч 15 мин», 0.4 -> «24 мин», 21.6 -> «21 ч 36 мин»."""
    if hours is None:
        return '—'
    minutes = round(hours * 60)
    if minutes < 60:
        return f'{minutes} мин'
    h, m = divmod(minutes, 60)
    return f'{h} ч {m} мин' if m else f'{h} ч'


def _median(values):
    return statistics.median(values) if len(values) >= MIN_REPAIRS else None


def _change(current, previous):
    if not previous:
        return None
    return (current - previous) / previous * 100


def _change_view(change):
    # Знак показывает оценку, а не рост заявок: заявок меньше значит лучше и плюс, больше значит хуже и минус.
    # На чёрно-белом листе смысл передаёт слово, а не цвет
    if change is None:
        return {'text': '—', 'direction': 'none'}
    rounded = round(change, 1)
    if rounded > 0:
        return {'text': f'Хуже: −{format_number(rounded)}%', 'direction': 'up'}
    if rounded < 0:
        return {'text': f'Лучше: +{format_number(abs(rounded))}%', 'direction': 'down'}
    return {'text': 'Без изменений', 'direction': 'none'}


def _downtime_row(name, repairs, over_day_source):
    by_reason = {r: _median(repairs[r]) for r in DOWNTIME_REASONS}
    total = len(over_day_source)
    over_day = sum(hours > 24 for hours in over_day_source)
    return {
        'name': name,
        'fault': format_duration(by_reason['Неисправность']),
        'stuck': format_duration(by_reason['Застревание']),
        'stopped': format_duration(by_reason['Остановлен']),
        'over_day': format_number(over_day / total * 100) + '%' if total else '—',
        'over_day_count': over_day,
        'repairs': total,
    }


def _compare_city(city, counts, lift_counts, year, months):
    """Сравнение города с прошлым годом: те же месяцы и те же лифты.

    Заявки в базу приходили от городов не одновременно, поэтому полноту месяца проверяем для каждого города.
    Состав лифтов менялся, а истории нет, поэтому сравниваются лифты, по которым были заявки в оба года.
    Новые и ушедшие лифты считаются отдельно: они сильно искажают сравнение.
    """
    values = [counts.get((y, m), 0) for y in (year - 1, year) for m in months]
    threshold = statistics.median(values) * COMPLETE_MONTH_SHARE
    used = [m for m in months
            if counts.get((year - 1, m), 0) >= max(threshold, 1) and counts.get((year, m), 0) >= max(threshold, 1)]
    if not used:
        return None

    def collect(y):
        total = Counter()
        for m in used:
            total.update(lift_counts[(y, m)])
        return total

    previous, current = collect(year - 1), collect(year)
    same = set(previous) & set(current)
    if not same:
        return None
    new, gone = set(current) - same, set(previous) - same
    prev_tickets = sum(previous[lift] for lift in same)
    cur_tickets = sum(current[lift] for lift in same)
    change = _change(cur_tickets, prev_tickets)
    return {
        'name': city, 'months': len(used), 'used': used,
        'lifts': len(same),
        'prev_tickets': prev_tickets, 'cur_tickets': cur_tickets,
        'prev_text': format_number(prev_tickets / len(same)), 'cur_text': format_number(cur_tickets / len(same)),
        'new_lifts': len(new), 'new_tickets': sum(current[lift] for lift in new),
        'gone_lifts': len(gone), 'gone_tickets': sum(previous[lift] for lift in gone),
        'change': change, 'view': _change_view(change),
        'unstable': len(same) < MIN_COMPARE_LIFTS,
    }


def build_analytics(tickets, lifts, monthly, year):
    """Считает сводку.

    tickets: строки (город, год, месяц, причина, простой в секундах или None, ложная ли, дом активен ли, id лифта)
    lifts: {город: лифтов в активных домах}
    monthly: {(год, месяц): заявок} за всё время, по нему определяются полные месяцы
    """
    complete = complete_months(monthly)
    months, has_previous = choose_period(year, complete)
    if not months:
        return None
    period = set(months)

    # Заявки и лифты города по месяцам: {город: {(год, месяц): ...}}
    city_counts = defaultdict(lambda: defaultdict(int))
    city_lifts = defaultdict(lambda: defaultdict(Counter))
    current = defaultdict(int)
    on_active = defaultdict(int)
    repairs = defaultdict(lambda: defaultdict(list))
    all_hours = defaultdict(list)
    total_repairs = defaultdict(list)
    open_count = bad_dates = 0

    for city, t_year, month, reason, seconds, is_false, active, lift_id, *_ in tickets:
        if month not in period:
            continue
        city_counts[city][(t_year, month)] += 1
        city_lifts[city][(t_year, month)][lift_id] += 1
        if t_year != year:
            continue
        current[city] += 1
        if active:
            on_active[city] += 1
        if reason not in DOWNTIME_REASONS or is_false:
            continue
        if seconds is None:
            open_count += 1
        elif seconds <= 0:
            bad_dates += 1
        else:
            hours = seconds / 3600
            repairs[city][reason].append(hours)
            total_repairs[reason].append(hours)
            all_hours[city].append(hours)

    # 1. Заявок на один лифт
    per_lift = []
    no_tickets = []
    for city, count in lifts.items():
        if not on_active.get(city):
            if count:
                no_tickets.append(city)
            continue
        if count:
            per_lift.append({'name': city, 'lifts': count, 'tickets': on_active[city],
                             'value': on_active[city] / count})
    per_lift.sort(key=lambda row: row['value'], reverse=True)
    peak = per_lift[0]['value'] if per_lift else 0
    for row in per_lift:
        row['text'] = format_number(row['value'])
        row['bar'] = round(row['value'] / peak * 100, 1) if peak else 0
    lifts_total = sum(row['lifts'] for row in per_lift)
    active_total = sum(row['tickets'] for row in per_lift)
    per_lift_total = active_total / lifts_total if lifts_total else None

    # 2. Сравнение с прошлым годом
    yoy = []
    totals = Counter()
    if has_previous:
        for city in sorted(city_counts):
            row = _compare_city(city, city_counts[city], city_lifts[city], year, months)
            if row:
                yoy.append(row)
                for key in ('lifts', 'prev_tickets', 'cur_tickets', 'new_lifts', 'new_tickets', 'gone_lifts', 'gone_tickets'):
                    totals[key] += row[key]
    yoy.sort(key=lambda row: -row['change'])
    total_change = _change(totals['cur_tickets'], totals['prev_tickets']) if totals['lifts'] else None
    yoy_total = dict(totals)
    yoy_total.update({
        'prev_text': format_number(totals['prev_tickets'] / totals['lifts']) if totals['lifts'] else '—',
        'cur_text': format_number(totals['cur_tickets'] / totals['lifts']) if totals['lifts'] else '—',
        'view': _change_view(total_change),
    })

    # 3. Время ремонта
    downtime = [_downtime_row(city, repairs[city], all_hours[city]) for city in sorted(all_hours)]
    downtime_total = _downtime_row('Все города', total_repairs,
                                   [h for values in all_hours.values() for h in values])
    fault_median = _median(total_repairs['Неисправность'])

    # Выводы одной строкой для руководства
    leader = per_lift[0] if per_lift else None
    growth = [row for row in yoy if row['prev_tickets'] >= GROWTH_MIN_TICKETS and not row['unstable']]
    worst = max(growth, key=lambda row: row['change']) if growth else None
    best = min(growth, key=lambda row: row['change']) if growth else None

    return {
        'year': year,
        'previous_year': year - 1,
        'has_previous': has_previous,
        'period': period_label(months),
        'months_count': len(months),
        'per_lift': per_lift,
        'per_lift_total': format_number(per_lift_total) if per_lift_total is not None else '—',
        'lifts_total': lifts_total,
        'active_total': active_total,
        'no_tickets': sorted(no_tickets),
        'leader': leader,
        'yoy': yoy,
        'yoy_total': yoy_total,
        'all_months': len(months),
        'has_unstable': any(row['unstable'] for row in yoy),
        'min_compare_lifts': MIN_COMPARE_LIFTS,
        'lifts_are_current': not has_previous,
        'worst': worst if worst and worst['change'] > 0 else None,
        'best': best if best and best['change'] < 0 else None,
        'downtime': downtime,
        'downtime_total': downtime_total,
        'fault_median': format_duration(fault_median),
        'open_count': open_count,
        'bad_dates': bad_dates,
        'min_repairs': MIN_REPAIRS,
    }


def _monthly_chart(months, current, previous, name=lambda month: MONTHS[month - 1]):
    """Геометрия столбиков по месяцам для SVG: одна ось, пары столбиков у месяца.

    name: название месяца по его ключу в months.
    """
    width, height = 720, 210
    left, right, top, bottom = 56, 8, 10, 28
    peak = max(list(current.values()) + list(previous.values()) + [1])
    # Круглый верх шкалы, чтобы линии сетки шли по понятным числам
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000)
                if s * 4 >= peak)
    axis_max = step * 4
    plot_h = height - top - bottom
    y = lambda v: top + plot_h - v / axis_max * plot_h
    slot = (width - left - right) / len(months)
    bar = min(slot * 0.34, 26)
    gap = 2
    groups = []
    for i, month in enumerate(months):
        center = left + slot * i + slot / 2
        bars = []
        pair = [('prev', previous.get(month))] if month in previous else []
        pair.append(('cur', current.get(month, 0)))
        total = len(pair) * bar + (len(pair) - 1) * gap
        x = center - total / 2
        for series, value in pair:
            bars.append({'series': series, 'value': value, 'x': round(x, 1), 'y': round(y(value), 1),
                         'w': round(bar, 1), 'h': round(top + plot_h - y(value), 1)})
            x += bar + gap
        groups.append({'label': name(month)[:3], 'name': name(month), 'x': round(center, 1), 'bars': bars})
    grid = [{'y': round(y(step * i), 1), 'label': step * i} for i in range(5)]
    return {'width': width, 'height': height, 'left': left, 'right': width - right, 'axis_y': height - bottom + 16,
            'grid': grid, 'groups': groups}


def build_city(city, tickets, summary, monthly, year):
    """Показатели одного города. summary: результат build_analytics за этот же год.

    tickets: те же строки, что и для build_analytics, с дополнительными полями
    улица, дом, подъезд, тип лифта (из карточки лифта).
    """
    months, _ = choose_period(year, complete_months(monthly))
    period = set(months)
    row = next((r for r in summary['per_lift'] if r['name'] == city), None)
    if row is None:
        return None

    compare = next((r for r in summary['yoy'] if r['name'] == city), None)
    used = set(compare['used']) if compare else set()

    by_month = defaultdict(int)
    prev_by_month = defaultdict(int)
    reasons = defaultdict(int)
    lifts = {}
    repairs = defaultdict(list)
    hours_all = []
    for t_city, t_year, month, reason, seconds, is_false, active, lift_id, street, house, entrance, lift_type in tickets:
        if t_city != city or month not in period:
            continue
        if t_year == year - 1:
            if month in used:
                prev_by_month[month] += 1
            continue
        if t_year != year:
            continue
        by_month[month] += 1
        reasons[reason] += 1
        if reason in DOWNTIME_REASONS and not is_false and seconds and seconds > 0:
            hours = seconds / 3600
            repairs[reason].append(hours)
            hours_all.append(hours)
        if not active:
            continue
        lift = lifts.setdefault(lift_id, {'id': lift_id, 'address': f'{street}, {house}, {entrance}', 'type': lift_type, 'tickets': 0,
                                          'Неисправность': 0, 'Застревание': 0, 'Остановлен': 0})
        lift['tickets'] += 1
        if reason in DOWNTIME_REASONS and not is_false:
            lift[reason] += 1

    worst = sorted(lifts.values(), key=lambda l: (-l['tickets'], l['address']))
    peak = worst[0]['tickets'] if worst else 0
    for position, lift in enumerate(worst, start=1):
        lift['position'] = position
        # Всё остальное, чтобы колонки в сумме давали число заявок
        lift['other'] = lift['tickets'] - sum(lift[r] for r in DOWNTIME_REASONS)
        lift['bar'] = round(lift['tickets'] / peak * 100, 1) if peak else 0
    top = worst[:10]
    top_tickets = sum(l['tickets'] for l in top)

    total = sum(by_month.values())
    reason_rows = sorted(reasons.items(), key=lambda kv: -kv[1])
    reason_peak = reason_rows[0][1] if reason_rows else 0
    reason_view = [{'name': name, 'count': count, 'share': format_number(count / total * 100) + '%',
                    'bar': round(count / reason_peak * 100, 1)} for name, count in reason_rows]

    position = summary['per_lift'].index(row) + 1
    return {
        'city': city,
        'year': year,
        'previous_year': year - 1,
        'period': summary['period'],
        'has_previous': compare is not None,
        'per_lift': row,
        'per_lift_total': summary['per_lift_total'],
        'position': position,
        'cities_count': len(summary['per_lift']),
        'compare': compare,
        'chart': _monthly_chart(months, by_month, {m: prev_by_month[m] for m in sorted(used)}),
        'months_rows': [{'name': MONTHS[m - 1], 'current': by_month[m],
                         'previous': prev_by_month[m] if m in used else None} for m in months],
        'reasons': reason_view,
        'total': total,
        'downtime': _downtime_row(city, repairs, hours_all),
        'downtime_all': summary['downtime_total'],
        'worst': worst,
        'top_share': format_number(top_tickets / row['tickets'] * 100) if row['tickets'] else '0',
        'top_count': len(top),
        'lifts_without_tickets': max(row['lifts'] - len(worst), 0),
    }


def lift_months(period, today, first=None):
    """Календарные месяцы карточки лифта: (год, месяц) по возрастанию, последний — текущий.

    period: число месяцев или 0 (всё время, начиная с месяца first).
    """
    last = today.year * 12 + today.month - 1
    if period:
        start = last - period + 1
    else:
        start = first[0] * 12 + first[1] - 1 if first else last
    return [(index // 12, index % 12 + 1) for index in range(min(start, last), last + 1)]


def _age_text(seconds):
    hours = max(seconds, 0) / 3600
    return f'{int(hours // 24)} дн.' if hours >= 48 else format_duration(hours)


def _month_name(key):
    return f'{MONTHS[key[1] - 1]} {key[0]}'


def _is_inspection(comment):
    """Ложная заявка: «ложная» или «на момент осмотра лифт работал». comment в нижнем регистре."""
    return any(mark in comment for mark in INSPECTION_MARKS) and not any(word in comment for word in NOISE_WORDS)


def _only_restart(comment):
    return RESTART_WORD in comment and not any(word in comment for word in RESTART_EXCEPT)


def _date_text(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y')


def status_period(now):
    """Границы статуса: начало последних дней и начало предыдущих, с которыми они сравниваются."""
    recent_start = now - STATUS_RECENT_DAYS * 86400
    return recent_start, recent_start - STATUS_BASE_DAYS * 86400


def lift_status(last_date, last_end, recent, base, open_date, now):
    """Что с лифтом сейчас.

    Считаются неисправности и ложные заявки: если жители жалуются, тишины нет.
    last_date: дата последней заявки, last_end: когда она или более ранняя закончилась,
    recent и base: заявок за последние дни и за предыдущие, open_date: начало открытой заявки или None.
    Тишина не доказывает ремонт, поэтому «устранили» пишется только как предположение.
    """
    expected = base / STATUS_BASE_DAYS * STATUS_RECENT_DAYS
    if open_date is not None:
        return {'key': 'active', 'title': 'Продолжается', 'short': f'открыта с {_date_text(open_date)}',
                'text': f'Открыта заявка с {_date_text(open_date)}.'}
    last_text = _date_text(last_date)
    if recent and expected and recent <= expected * STATUS_LESS_SHARE:
        return {'key': 'less', 'title': 'Стало реже', 'short': f'последняя {last_text}',
                'text': f'Заявок за {STATUS_RECENT_DAYS} дней: {recent}, раньше примерно {round(expected)} за такой срок. '
                        f'Последняя: {last_text}.'}
    # Долгий ремонт мог закончиться недавно, поэтому тишину считаем от его окончания
    last_end = min(last_end, now)
    days = (now - last_end) // 86400
    if not recent and days >= STATUS_RECENT_DAYS:
        text = f'Последняя заявка закрыта {_date_text(last_end)}, прошло {days} дн.'
        # На таком сроке многие лифты ломаются снова, поэтому сначала только наблюдаем
        if expected >= STATUS_FIXED_EXPECTED:
            text += ' Похоже, причину устранили.' if days >= STATUS_LIKELY_FIXED_DAYS else ' Наблюдаем.'
        return {'key': 'quiet', 'title': 'Давно не ломается', 'short': f'последняя {_date_text(last_end)}', 'text': text}
    return {'key': 'active', 'title': 'Продолжается', 'short': f'последняя {last_text}',
            'text': f'Заявок за {STATUS_RECENT_DAYS} дней: {recent}. Последняя: {last_text}.'}


def _is_pattern(count, total):
    return count >= FINDING_MIN_COUNT and (count / total >= FINDING_SHARE or count >= FINDING_MANY)


def _worker_note(items, several, one):
    """Один механик или разные: текст с фамилией, если больше половины случаев у него."""
    workers = Counter(item['worker'] for item in items if item['worker'])
    top = workers.most_common(1)[0] if workers else None
    if not top:
        return ''
    if len(workers) > 1 and top[1] / len(items) < FINDING_MECHANIC_SHARE:
        return several
    return f'Больше всего таких заявок у механика: {top[0]} ({top[1]} из {len(items)}). {one}'


def _lift_findings(faults, city_average, inspections=()):
    """Выводы по неисправностям лифта за период. Это подсказки, а не заключение.

    faults: неисправности по времени, словари {'number', 'date', 'comment', 'worker', 'seconds', 'closed'}
    city_average: неисправностей на лифт в среднем по городу или None
    inspections: ложные заявки за период, те же словари
    """
    total = len(faults)
    findings = []
    ratio = total / city_average if city_average else None
    hours = [f['seconds'] / 3600 for f in faults if f['closed'] and f['seconds'] > 0]
    usual = statistics.median(hours) if hours else None

    if total >= FINDING_MIN_FAULTS and ratio and ratio >= FINDING_OFTEN_RATIO:
        findings.append({'title': 'Ломался чаще других',
                         'text': f'Неисправностей: {total}, это в {format_number(ratio)} раза больше среднего по городу.'})

    # Как лифт простаивает: один долгий ремонт или много коротких
    downtime = sum(f['seconds'] for f in faults)
    longest = max(faults, key=lambda f: f['seconds'], default=None)
    if (longest and longest['seconds'] / 3600 >= FINDING_ONE_REPAIR_HOURS
            and longest['seconds'] >= downtime * FINDING_ONE_REPAIR_SHARE):
        findings.append({'title': 'Простой из-за одного ремонта',
                         'text': f'Заявка №{longest["number"]} заняла {_age_text(longest["seconds"])}: '
                                 f'это {round(longest["seconds"] / downtime * 100)}% всего простоя. '
                                 'Стоит узнать, что задержало ремонт.'})
    elif (total >= FINDING_MIN_FAULTS and ratio and ratio >= FINDING_REPEAT_RATIO
          and usual is not None and usual <= FINDING_QUICK_HOURS):
        findings.append({'title': 'Ремонты короткие, но поломки повторялись',
                         'text': f'Обычный ремонт занимал {format_duration(usual)}, а неисправностей было много.'})

    # Перезапуск вместо ремонта
    restarts = [f for f in faults if _only_restart(f['comment'])]
    if _is_pattern(len(restarts), total):
        text = f'Закрыты только перезапуском, без ремонта: {len(restarts)} из {total}. '
        text += _worker_note(restarts, 'Закрывали разные механики, поэтому вероятнее причина в самом лифте.',
                             'Стоит разобрать эти случаи с механиком: почему причина не найдена.')
        findings.append({'title': 'Перезапуск вместо ремонта', 'text': text})

    # Жители жалуются, а механик пишет, что лифт работает
    checked = len(inspections)
    all_tickets = total + checked
    if checked >= FINDING_MIN_COUNT and (checked / all_tickets >= INSPECTION_SHARE or checked >= FINDING_MANY):
        last = max(item['date'] for item in inspections)
        text = (f'Ложные заявки: {checked} из {all_tickets}, последняя {_date_text(last)}. '
                'Либо лифт сбоит и к приезду снова работает, либо поломку не отмечают. ')
        text += _worker_note(inspections, 'Отмечали разные механики, поэтому вероятнее, что лифт сбоит время от времени.',
                             'Стоит проверить эти выезды.')
        findings.append({'title': 'Жалобы не подтвердились', 'text': text})

    # Одна и та же поломка: по узлам и кодам ошибок из комментариев
    repeated = Counter()
    last_seen = {}
    for fault in faults:
        names = [name for name, pattern in NODES.items() if pattern.search(fault['comment'])]
        names += [f'ошибка {code}' for code in set(ERROR_CODE.findall(fault['comment']))]
        for name in names:
            repeated[name] += 1
            last_seen[name] = max(last_seen.get(name, 0), fault['date'])
    common = [(name, count) for name, count in repeated.most_common() if _is_pattern(count, total)][:3]
    if common:
        listed = ', '.join(f'{name} ({count}, последняя {_date_text(last_seen[name])})' for name, count in common)
        findings.append({'title': 'Возможно, проблема в этом',
                         'text': f'Чаще всего в комментариях: {listed}. Всего неисправностей: {total}.'})
    return findings


def build_attention(faults, per_lift, activity, now):
    """Лифты с выводами за период страницы аналитики: сначала с большим числом выводов и неисправностей.

    faults: неисправности и ложные заявки за период, строки (id лифта, город, улица, дом, подъезд, тип, дом активен ли,
    номер, дата, дата запуска, комментарий, id механика, механик)
    per_lift: строки раздела «Заявок на один лифт», из них берётся число лифтов города
    activity: {id лифта: аргументы lift_status без now} за все годы
    """
    lifts = {}
    city_faults = Counter()
    for lift_id, city, street, house, entrance, lift_type, active, number, date, closed, comment, _, worker in faults:
        if lift_id is None or not active:
            continue
        lift = lifts.setdefault(lift_id, {
            'id': lift_id, 'city': city, 'type': lift_type,
            'address': ', '.join(str(part) for part in (street, house, entrance) if part),
            'items': [], 'inspections': []})
        comment = (comment or '').lower()
        item = {'number': number, 'date': date, 'comment': comment, 'worker': worker,
                'seconds': max((now if closed is None else closed) - date, 0), 'closed': closed is not None}
        if _is_inspection(comment):
            lift['inspections'].append(item)
        else:
            city_faults[city] += 1
            lift['items'].append(item)

    city_lifts = {row['name']: row['lifts'] for row in per_lift}
    rows = []
    for lift in lifts.values():
        count = city_lifts.get(lift['city'])
        items = lift.pop('items')
        inspections = lift.pop('inspections')
        findings = _lift_findings(items, city_faults[lift['city']] / count if count else None, inspections)
        if findings:
            rows.append({**lift, 'faults': len(items), 'findings': [f['title'] for f in findings],
                         'status': lift_status(*activity[lift['id']], now),
                         'downtime': format_duration(sum(i['seconds'] for i in items) / 3600)})
    # Сначала то, что происходит сейчас. Давно не ломавшиеся не убираем: часть из них возвращается
    rows.sort(key=lambda row: (STATUS_ORDER[row['status']['key']], -len(row['findings']), -row['faults'],
                               row['city'], row['address']))
    for position, row in enumerate(rows, start=1):
        row['position'] = position
    counts = Counter(row['status']['key'] for row in rows)
    return {'rows': rows, 'lifts_with_tickets': len(lifts), 'shown': ATTENTION_SHOWN, 'counts': counts,
            'recent_days': STATUS_RECENT_DAYS}


def build_mechanics(faults):
    """По механикам: доля закрытых только перезапуском и доля ложных заявок. Сначала большая доля перезапусков."""
    mechanics = {}
    for lift_id, *_, comment, worker_id, worker in faults:
        if worker_id is None:
            continue
        row = mechanics.setdefault(worker_id, {'name': worker or '—', 'faults': 0, 'restarts': 0, 'inspections': 0,
                                               'lifts': set()})
        comment = (comment or '').lower()
        row['lifts'].add(lift_id)
        if _is_inspection(comment):
            row['inspections'] += 1
        else:
            row['faults'] += 1
            row['restarts'] += _only_restart(comment)

    rows = [row for row in mechanics.values() if row['faults'] >= MECHANIC_MIN_FAULTS]
    rows.sort(key=lambda row: (-row['restarts'] / row['faults'], row['name']))
    usual = statistics.median(row['restarts'] / row['faults'] for row in rows) if rows else 0
    threshold = max(usual * MECHANIC_HIGH_RATIO, MECHANIC_HIGH_SHARE)
    peak = rows[0]['restarts'] / rows[0]['faults'] if rows else 0
    inspection_share = lambda row: row['inspections'] / (row['faults'] + row['inspections'])
    usual_inspections = statistics.median(inspection_share(row) for row in rows) if rows else 0
    for row in rows:
        share = row['restarts'] / row['faults']
        row['lifts'] = len(row['lifts'])
        row['share'] = format_number(share * 100) + '%'
        row['bar'] = round(share / peak * 100, 1) if peak else 0
        row['high'] = share >= threshold
        row['inspection_share'] = format_number(inspection_share(row) * 100) + '%'
    return {'rows': rows, 'usual': format_number(usual * 100) + '%', 'min_faults': MECHANIC_MIN_FAULTS,
            'usual_inspections': format_number(usual_inspections * 100) + '%',
            'skipped': len(mechanics) - len(rows), 'high_count': sum(row['high'] for row in rows)}


def build_lift(lift, tickets, fleet, months, start, now):
    """Показатели карточки лифта.

    lift: {'id', 'city', 'address', 'type', 'active', 'city_id'}
    tickets: все заявки лифта по возрастанию даты, строки (номер, дата, дата текстом, год, месяц, причина,
    дата запуска, комментарий, механик, ложная ли). Старые нужны, чтобы найти повтор в начале периода.
    fleet: лифты в активных домах, строки (id лифта, id города, неисправностей, секунд простоя) за период
    months: месяцы периода, start: начало периода, now: текущее время (всё в секундах unixtime, кроме months)
    """
    by_month = Counter()
    workers = Counter()
    rows = []
    open_tickets = []
    faults = repeats = downtime = 0
    previous_closed = None
    fault_items = []
    inspection_items = []
    recent_start, base_start = status_period(now)
    recent_count = base_count = 0
    last_date = last_end = open_date = None

    for number, date, date_text, year, month, reason, closed, comment, worker, is_false in tickets:
        fault = reason in DOWNTIME_REASONS and not is_false
        inspection = reason in DOWNTIME_REASONS and _is_inspection((comment or '').lower())
        repeat = fault and previous_closed is not None and 0 <= date - previous_closed <= REPEAT_DAYS * 86400
        if fault:
            previous_closed = closed if closed is not None and closed > date else None
        if fault or inspection:
            last_date = date
            last_end = max(last_end or 0, date, closed or 0)
            recent_count += date >= recent_start
            base_count += base_start <= date < recent_start
            if closed is None and open_date is None:
                open_date = date
        if closed is None:
            open_tickets.append({'number': number, 'date': date_text, 'reason': reason, 'age': _age_text(now - date)})
        if date < start:
            continue
        if inspection:
            inspection_items.append({'date': date, 'worker': worker})
        if fault:
            faults += 1
            repeats += repeat
            # Открытая неисправность считается простоем по текущий момент
            seconds = max((now if closed is None else closed) - date, 0)
            downtime += seconds
            fault_items.append({'number': number, 'date': date, 'comment': (comment or '').lower(), 'worker': worker,
                                'seconds': seconds, 'closed': closed is not None})
            by_month[(year, month)] += 1
            workers[worker or 'не указан'] += 1
        rows.append({'number': number, 'date': date_text, 'reason': reason, 'worker': worker or '—',
                     'repair': repair_text(None if closed is None else closed - date),
                     'comment': comment or '', 'fault': fault, 'repeat': repeat})
    rows.reverse()
    for position, row in enumerate(rows, start=1):
        row['extra'] = position > 20

    chart = _monthly_chart(months, by_month, {}, name=_month_name)
    if len(months) > LIFT_CHART_LABELS:
        for index, group in enumerate(chart['groups']):
            if index % 2:
                group['label'] = ''

    # Сравнение с городом и место среди всех лифтов
    position = lifts_total = city_faults = city_downtime = city_lifts = city_average = None
    if lift['active']:
        lifts_total = len(fleet)
        position = 1 + sum(int(row[2]) > faults for row in fleet)
        peers = [row for row in fleet if row[1] == lift['city_id']]
        city_lifts = len(peers)
        if peers:
            city_average = sum(int(row[2]) for row in peers) / city_lifts
            city_faults = format_number(city_average)
            city_downtime = format_duration(sum(float(row[3]) for row in peers) / city_lifts / 3600)

    peak = max(workers.values(), default=0)
    return {
        **lift,
        'period': f'{_month_name(months[0])} – {_month_name(months[-1])}',
        'faults': faults,
        'repeats': repeats,
        'repeat_days': REPEAT_DAYS,
        'downtime': format_duration(downtime / 3600),
        'position': position,
        'lifts_total': lifts_total,
        'city_faults': city_faults,
        'city_downtime': city_downtime,
        'open_tickets': open_tickets,
        'has_open_fault': any(t['reason'] in DOWNTIME_REASONS for t in open_tickets),
        'findings': _lift_findings(fault_items, city_average, inspection_items),
        'status': (lift_status(last_date, last_end, recent_count, base_count, open_date, now)
                   if last_date is not None else None),
        'recent_days': STATUS_RECENT_DAYS,
        'chart': chart,
        'workers': [{'name': name, 'count': count, 'bar': round(count / peak * 100, 1)}
                    for name, count in sorted(workers.items(), key=lambda kv: (-kv[1], kv[0]))],
        'rows': rows,
    }
