#!/usr/bin/env python3
"""Keep the non-rendered discovery block on the home page in sync with catalogs."""

import argparse
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'index.html'
BASE = 'https://bhavanvsenah.github.io/'
START = '<!-- BEGIN GENERATED CATALOG DISCOVERY -->'
END = '<!-- END GENERATED CATALOG DISCOVERY -->'
PATH = re.compile(r'^(celts|dharma)/[A-Za-z0-9_-]+\.html$')


def published_books():
    found = []
    seen = set()
    for section in ('celts', 'dharma'):
        data = json.loads((ROOT / f'{section}.json').read_text(encoding='utf-8'))
        groups = data['categories'] if isinstance(data, dict) else [
            {'title': 'Дхарма', 'books': data}
        ]
        for group in groups:
            for book in group['books']:
                path = book.get('href')
                if not path:
                    continue  # An announcement is not a published text.
                if not isinstance(path, str) or not PATH.fullmatch(path) or not path.startswith(section + '/'):
                    raise ValueError(f'Некорректный адрес опубликованного текста: {path!r}')
                if path in seen or not (ROOT / path).is_file():
                    raise ValueError(f'Повторный или отсутствующий текст: {path}')
                if not isinstance(book.get('title'), str) or not book['title'].strip():
                    raise ValueError(f'Нет названия текста: {path}')
                seen.add(path)
                found.append((group['title'], book))
    return found


def render():
    books = published_books()
    entries = [
        {
            '@type': 'ListItem',
            'position': number,
            'item': {
                '@type': 'CreativeWork',
                'name': book['title'],
                'url': BASE + book['href'],
                **({'author': book['author']} if book.get('author') else {}),
            },
        }
        for number, (_, book) in enumerate(books, 1)
    ]
    data = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': 'Опубликованные тексты',
        'url': BASE,
        'mainEntity': {'@type': 'ItemList', 'itemListElement': entries},
    }
    # A title containing </script> must never terminate the script element.
    encoded = json.dumps(data, ensure_ascii=False, indent=2).replace('<', '\\u003c')
    lines = [
        START,
        '    <script type="application/ld+json" id="published-catalog-data">',
        encoded,
        '    </script>',
        '    <noscript>',
        '      <nav aria-label="Опубликованные тексты">',
        '        <h2>Опубликованные тексты</h2>',
        '        <ul>',
    ]
    for _, book in books:
        title = html.escape(book['title'], quote=True)
        author = html.escape(book.get('author', ''), quote=True)
        label = f'{author} — {title}' if author else title
        lines.append(f'          <li><a href="/{book["href"]}">{label}</a></li>')
    lines += ['        </ul>', '      </nav>', '    </noscript>', END]
    return '\n'.join(lines)


def sync(check=False):
    page = PAGE.read_text(encoding='utf-8')
    if page.count(START) != 1 or page.count(END) != 1:
        raise ValueError('На главной странице должен быть один служебный блок каталога')
    before, remainder = page.split(START, 1)
    _, after = remainder.split(END, 1)
    updated = before + render() + after
    if updated != page:
        if check:
            raise ValueError('Служебный каталог устарел; запустите tools/catalog_discovery.py')
        PAGE.write_text(updated, encoding='utf-8')
        print('index.html: служебный каталог обновлён')
    else:
        print('index.html: служебный каталог актуален')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    sync(parser.parse_args().check)
