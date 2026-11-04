// Окно со списком заявок лифта: страница города в аналитике и «Проблемные лифты».
// Комментарии пишут люди, поэтому текст вставляется только через textContent.
window.TicketsDialog = (function () {
  var dialog, title, sub, body;
  var requestId = 0;

  function ensure() {
    if (dialog) return;
    dialog = document.createElement('dialog');
    dialog.className = 'tickets-dialog';
    dialog.setAttribute('aria-labelledby', 'ticketsTitle');

    var head = document.createElement('div');
    head.className = 'tickets-head';
    var heading = document.createElement('div');
    title = document.createElement('h3');
    title.id = 'ticketsTitle';
    sub = document.createElement('div');
    sub.className = 'tickets-sub';
    heading.appendChild(title);
    heading.appendChild(sub);

    var close = document.createElement('button');
    close.className = 'tickets-close';
    close.type = 'button';
    close.setAttribute('aria-label', 'Закрыть');
    close.textContent = '×';
    close.addEventListener('click', function () { dialog.close(); });
    head.appendChild(heading);
    head.appendChild(close);

    body = document.createElement('div');
    body.className = 'tickets-body';
    dialog.appendChild(head);
    dialog.appendChild(body);

    // Клик по затемнению вокруг окна тоже закрывает его
    dialog.addEventListener('click', function (e) {
      if (e.target === dialog) dialog.close();
    });
    document.body.appendChild(dialog);
  }

  function render(tickets, columns) {
    body.textContent = '';
    if (!tickets.length) {
      body.textContent = 'Заявок нет';
      return;
    }
    var table = document.createElement('table');
    table.className = 'tickets-table';
    var headRow = table.createTHead().insertRow();
    columns.forEach(function (column) {
      var th = document.createElement('th');
      th.textContent = column.label;
      headRow.appendChild(th);
    });
    var tbody = table.createTBody();
    tickets.forEach(function (ticket) {
      var row = tbody.insertRow();
      columns.forEach(function (column) {
        var cell = row.insertCell();
        var value = ticket[column.key];
        cell.textContent = (value === null || value === undefined || value === '') ? '—' : value;
        cell.dataset.label = column.label;
        if (column.nowrap) cell.classList.add('tickets-nowrap');
        if (column.wide) cell.classList.add('tickets-wide');
      });
    });
    body.appendChild(table);
  }

  // options: title, columns [{key, label, nowrap, wide}], load() -> Promise со списком заявок, subtitle(tickets) -> строка
  function open(options) {
    ensure();
    var current = ++requestId;
    title.textContent = options.title;
    sub.textContent = '';
    body.textContent = 'Загрузка...';
    if (!dialog.open) dialog.showModal();
    options.load()
      .then(function (tickets) {
        if (current !== requestId) return;
        sub.textContent = options.subtitle(tickets);
        render(tickets, options.columns);
      })
      .catch(function () {
        if (current === requestId) body.textContent = 'Не удалось загрузить заявки. Обновите страницу и попробуйте ещё раз.';
      });
  }

  // Ответ сервера с ошибкой не должен выглядеть как пустой список
  function json(response) {
    if (!response.ok) throw new Error(response.status);
    return response.json();
  }

  return { open: open, json: json };
})();
