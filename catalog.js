'use strict';

// Fills each catalogue from <name>.json at start-up. A file is a list of
// books: { "author": "...", "title": "...", "from": "...", "status": "...",
// "href": "..." }; "from" names the languages translated from.
// "href", when given, is the page of the text, <name>/<text>.html; its title
// becomes a button with the route <name>/<text>, which app.js opens in the
// reader.
{
  // Russian typesetting: a one- or two-letter word stays on the line with the next one.
  const tie = (text) => String(text).replace(/(^|[\s(«])([А-Яа-яЁё]{1,2}) /g, '$1$2\u00a0');

  const line = (tag, className, text) => {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = tie(text);
    return element;
  };

  const note = (list, text) => {
    list.replaceChildren(line('li', 'catalog-note', text));
  };

  const render = (list, books) => {
    if (!Array.isArray(books)) throw new Error('ожидался список книг');
    if (!books.length) {
      note(list, 'Здесь пока нет переводов.');
      return;
    }
    list.replaceChildren(
      ...books.map((book) => {
        const item = document.createElement('li');
        item.className = 'book';
        const title = line('h3', 'title', book.title ?? '');
        if (book.href) {
          const open = document.createElement('button');
          open.type = 'button';
          open.dataset.route = book.href.replace(/\.html$/, '');
          open.textContent = title.textContent;
          title.replaceChildren(open);
        }
        if (book.author) item.append(line('p', 'author', book.author));
        item.append(title);
        if (book.from) item.append(line('p', 'from', book.from));
        if (book.status) item.append(line('p', 'status', book.status));
        return item;
      }),
    );
  };

  for (const catalog of document.querySelectorAll('.catalog')) {
    const file = `${catalog.dataset.catalog}.json`;
    const list = catalog.querySelector('.books');
    // A catalogue changes without a new address, so the browser asks the
    // server every time instead of trusting its cache; an unchanged file
    // costs a short "not modified".
    fetch(file, { cache: 'no-cache' })
      .then((response) => {
        if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
        return response.json();
      })
      .then((books) => render(list, books))
      .catch((error) => {
        note(
          list,
          location.protocol === 'file:'
            ? `Каталог не загрузился: страница открыта как файл, а браузер не даёт читать ${file} с диска. Откройте её через serve.sh.`
            : `Каталог не загрузился (${error.message}).`,
        );
      });
  }
}
