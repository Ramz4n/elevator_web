// Таблица страниц со списком заявок: срок открытой заявки и сортировка по заголовкам
(function () {
  const table = document.querySelector('.fixed-header');
  if (!table || !table.tHead) return;
  const tbody = table.tBodies[0];

  const HOUR = 3600;
  const DAY = 24 * HOUR;

  function fillOpenAge(cell) {
    const seconds = Math.max(0, Math.floor(Date.now() / 1000) - Number(cell.dataset.opened));
    cell.textContent = seconds < DAY ? Math.floor(seconds / HOUR) + ' ч' : Math.floor(seconds / DAY) + ' дн.';
    cell.dataset.age = seconds;
  }
  tbody.querySelectorAll('td[data-opened]').forEach(fillOpenAge);

  // Значение ячейки для сравнения. null: значения нет, такие строки всегда внизу
  const READERS = {
    number: function (cell) {
      const value = parseFloat(cell.textContent);
      return Number.isNaN(value) ? null : value;
    },
    // «26.10.2026, 09:15»
    date: function (cell) {
      const m = /^(\d{2})\.(\d{2})\.(\d{4}), (\d{2}):(\d{2})/.exec(cell.textContent.trim());
      return m ? new Date(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]).getTime() : null;
    },
    age: function (cell) {
      return cell.dataset.age === undefined ? null : Number(cell.dataset.age);
    },
    text: function (cell) {
      const value = cell.textContent.trim();
      return value && value !== 'None' ? value : null;
    },
  };

  function clearSortMarks() {
    table.tHead.querySelectorAll('th[aria-sort]').forEach(function (th) { th.removeAttribute('aria-sort'); });
  }
  // Страница «Остановленные» сортирует свою колонку сама и снимает общую отметку
  window.clearSortMarks = clearSortMarks;

  function sortBy(th, ascending) {
    const read = READERS[th.dataset.sort];
    const index = th.cellIndex;
    const direction = ascending ? 1 : -1;
    Array.from(tbody.rows)
      .map(function (row) { return { row: row, value: read(row.cells[index]) }; })
      .sort(function (a, b) {
        if (a.value === null || b.value === null) return (a.value === null) - (b.value === null);
        if (th.dataset.sort === 'text') return direction * a.value.localeCompare(b.value, 'ru');
        return direction * (a.value - b.value);
      })
      .forEach(function (item) { tbody.appendChild(item.row); });
    clearSortMarks();
    th.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
  }

  table.tHead.addEventListener('click', function (event) {
    const th = event.target.closest('th[data-sort]');
    if (!th) return;
    // Срок при первом нажатии показывает сначала самые старые заявки
    const current = th.getAttribute('aria-sort');
    const ascending = current ? current === 'descending' : th.dataset.sort !== 'age';
    sortBy(th, ascending);
  });

  // На страницах открытых заявок сверху те, что ждут дольше всего
  if (document.body.classList.contains('hide-launch-date')) {
    sortBy(table.tHead.querySelector('th[data-sort="age"]'), false);
  }
})();
