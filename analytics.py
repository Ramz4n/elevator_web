"""Расчёт показателей для страницы «Аналитика» (сводка для руководства)."""
import statistics
from collections import Counter, defaultdict

MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль',
          'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
DOWNTIME_REASONS = ('Неисправность', 'Застревание', 'Остановлен')
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
    """1.25 -> «1 ч 15 мин», 0.4 -> «24 мин», 21.6 -> «22 ч»."""
    if hours is None:
        return '—'
    minutes = round(hours * 60)
    if minutes < 60:
        return f'{minutes} мин'
    if hours >= 10:
        return f'{round(hours)} ч'
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


def _monthly_chart(months, current, previous):
    """Геометрия столбиков по месяцам для SVG: одна ось, пары столбиков у месяца."""
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
        groups.append({'label': MONTHS[month - 1][:3], 'name': MONTHS[month - 1], 'x': round(center, 1), 'bars': bars})
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
