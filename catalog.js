'use strict';

// Fills each catalogue from <name>.json at start-up. A file is a list of
// books: { "author": "...", "title": "...", "from": "...", "status": "...",
// "href": "...", "formats": { "pdf": null, "fb2": null } }.
// "from" names the languages translated from. Set a format to the relative
// path of its published file; missing/null formats are plain, unavailable text.
// "href", when given, is the page of the text, <name>/<text>.html; its title
// becomes a button with the route <name>/<text>, which app.js opens in the
// reader.
// A thematic catalogue can instead contain { categories: [
//   { id: "grammar", title: "Грамматики и учебники", books: [...] }
// ] }. sortAuthor is an optional surname-first sorting key, not display text.
{
  const collator = new Intl.Collator('ru', { sensitivity: 'base', numeric: true });
  const alphabetical = (books) => [...books].sort((a, b) =>
    collator.compare(a.sortAuthor || a.author || a.title, b.sortAuthor || b.author || b.title) ||
    collator.compare(a.title, b.title));
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

  const path = (href, extension, section) => {
    if (href == null || href === '') return '';
    if (typeof href !== 'string' ||
        !new RegExp(`^(dharma|celts)/[A-Za-z0-9_-]+\\.${extension}$`).test(href) ||
        !href.startsWith(`${section}/`)) {
      throw new Error(`некорректный путь ${extension}`);
    }
    return href;
  };

  const formats = (book, href, section) => {
    const group = document.createElement('div');
    group.className = 'book-formats';
    group.append(line('p', 'formats-label', 'Форматы'));
    const options = document.createElement('div');
    options.className = 'formats';
    for (const [key, label] of [['html', 'HTML'], ['pdf', 'PDF'], ['fb2', 'FB2']]) {
      const url = key === 'html' ? href : path(book.formats?.[key], key, section);
      let option;
      if (url && key === 'html') {
        option = line('button', 'format', label);
        option.type = 'button';
        option.dataset.route = url.replace(/\.html$/, '');
        option.setAttribute('aria-label', `Читать «${book.title}» в HTML`);
      } else if (url) {
        option = line('a', 'format', label);
        option.href = url;
        option.download = url.split('/').pop();
        option.setAttribute('aria-label', `Скачать «${book.title}» в ${label}`);
      } else {
        option = line('span', 'format unavailable', label);
        option.title = `${label} пока недоступен`;
        option.append(line('span', 'visually-hidden', ' (пока недоступен)'));
      }
      options.append(option);
    }
    group.append(options);
    return group;
  };

  const renderBooks = (list, books, section) => {
    if (!Array.isArray(books)) throw new Error('ожидался список книг');
    if (!books.length) {
      note(list, 'Здесь пока нет переводов.');
      return;
    }
    list.replaceChildren(
      ...alphabetical(books).map((book) => {
        const item = document.createElement('li');
        item.className = 'book';
        const body = document.createElement('div');
        body.className = 'book-text';
        const href = path(book.href, 'html', section);
        const title = line('h3', 'title', book.title ?? '');
        if (href) {
          const open = document.createElement('button');
          open.type = 'button';
          open.dataset.route = href.replace(/\.html$/, '');
          open.textContent = title.textContent;
          title.replaceChildren(open);
        }
        if (book.author) body.append(line('p', 'author', book.author));
        body.append(title);
        if (book.from) body.append(line('p', 'from', book.from));
        if (book.status) body.append(line('p', 'status', book.status));
        item.append(body, formats(book, href, section));
        return item;
      }),
    );
  };

  // Native details keeps keyboard behaviour and find-in-page. Web Animations
  // adds both directions of motion without relying on interpolate-size support.
  const animateDisclosure = (details, content) => {
    const summary = details.querySelector('summary');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    let animation = null;
    let expanded = details.open;
    const finish = () => {
      animation?.cancel();
      animation = null;
      details.open = expanded;
      content.inert = !expanded;
      content.style.removeProperty('overflow');
    };
    summary.addEventListener('click', (event) => {
      if (reduced.matches || !content.animate) return; // native instant fallback
      event.preventDefault();
      const from = details.open ? content.getBoundingClientRect().height : 0;
      const opacity = details.open ? getComputedStyle(content).opacity : 0;
      expanded = !expanded;
      animation?.cancel();
      details.open = true; // keep content present until closing has finished
      content.inert = !expanded;
      content.style.overflow = 'hidden';
      const to = expanded ? content.scrollHeight : 0;
      animation = content.animate([
        { height: `${from}px`, opacity },
        { height: `${to}px`, opacity: expanded ? 1 : 0 },
      ], { duration: 320, easing: 'cubic-bezier(.2,.75,.25,1)' });
      animation.onfinish = finish;
    });
    details.addEventListener('toggle', () => {
      if (!animation) {
        expanded = details.open;
        content.inert = !expanded;
      }
    });
    reduced.addEventListener('change', () => { if (animation) finish(); });
  };

  const render = (list, data, section) => {
    if (Array.isArray(data)) return renderBooks(list, data, section);
    if (!data || !Array.isArray(data.categories)) throw new Error('ожидались рубрики каталога');
    const ids = new Set();
    const categories = data.categories.map((category, index) => {
      if (!category || !/^[a-z][a-z0-9-]*$/.test(category.id) || ids.has(category.id) ||
          typeof category.title !== 'string' || !category.title.trim() || !Array.isArray(category.books)) {
        throw new Error('некорректная рубрика каталога');
      }
      ids.add(category.id);
      const item = line('li', 'catalog-category', '');
      const details = document.createElement('details');
      details.id = `${section}-${category.id}`;
      const summary = document.createElement('summary');
      const number = line('span', 'category-number', String(index + 1).padStart(2, '0'));
      number.setAttribute('aria-hidden', 'true');
      summary.append(number, line('span', 'category-title', category.title),
        line('span', 'category-count', `${category.books.length} изд.`));
      const content = line('div', 'category-content', '');
      const books = line('ul', 'books', '');
      books.setAttribute('role', 'list');
      renderBooks(books, category.books, section);
      content.append(books);
      details.append(summary, content);
      animateDisclosure(details, content);
      item.append(details);
      return item;
    });
    if (!categories.length) return note(list, 'Здесь пока нет переводов.');
    list.classList.add('catalog-categories');
    list.replaceChildren(...categories);
  };

  for (const catalog of document.querySelectorAll('.catalog')) {
    const file = `${catalog.dataset.catalog}.json`;
    const list = catalog.querySelector('.books');
    note(list, 'Загрузка каталога…');
    // A catalogue changes without a new address, so the browser asks the
    // server every time instead of trusting its cache; an unchanged file
    // costs a short "not modified".
    fetch(file, { cache: 'no-cache' })
      .then((response) => {
        if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
        return response.json();
      })
      .then((books) => render(list, books, catalog.dataset.catalog))
      .catch((error) => {
        note(
          list,
          location.protocol === 'file:'
            ? `Каталог не загрузился: браузер не даёт читать ${file} с диска. Откройте сайт по HTTP или HTTPS.`
            : `Каталог не загрузился (${error.message}).`,
        );
      });
  }
}
