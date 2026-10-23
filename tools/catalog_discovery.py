#!/usr/bin/env python3
"""Build the real home-page catalogs from JSON, with crawlable HTML links."""

import argparse
import html
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'index.html'
SECTIONS = ('celts', 'dharma')
SITE_URL = 'https://bhavanvsenah.github.io/'


def markers(section):
    return (f'<!-- BEGIN GENERATED CATALOG {section} -->',
            f'<!-- END GENERATED CATALOG {section} -->')


def text(value):
    """Keep the existing non-breaking-space typography, then HTML-escape."""
    tied = re.sub(r'(^|[\s(«])([А-Яа-яЁё]{1,2}) ',
                  lambda m: m[1] + m[2] + '\u00a0', str(value))
    return html.escape(tied, quote=True)


def alphabetical(books):
    if len(books) < 2:
        return books
    # Match the old browser's Russian/numeric ordering exactly.
    code = """
const fs = require('node:fs');
const books = JSON.parse(fs.readFileSync(0, 'utf8'));
const c = new Intl.Collator('ru', {sensitivity:'base', numeric:true});
books.sort((a,b) => c.compare(a.sortAuthor || a.author || a.title,
                             b.sortAuthor || b.author || b.title) ||
                    c.compare(a.title,b.title));
process.stdout.write(JSON.stringify(books));
"""
    result = subprocess.check_output(['node', '-e', code], input=json.dumps(books).encode())
    return json.loads(result)


def path(value, extension, section):
    if value is None or value == '':
        return ''
    if not isinstance(value, str) or not re.fullmatch(
            rf'{section}/[A-Za-z0-9_-]+\.{extension}', value):
        raise ValueError(f'Некорректный адрес {extension}: {value!r}')
    if not (ROOT / value).is_file():
        raise ValueError(f'Нет опубликованного файла: {value}')
    return value


def render_books(books, section):
    if not isinstance(books, list):
        raise ValueError('Ожидался список книг')
    if not books:
        return '<li class="catalog-note">Здесь пока нет переводов.</li>'
    items = []
    for book in alphabetical(books):
        if not isinstance(book.get('title'), str) or not book['title'].strip():
            raise ValueError('Нет названия книги')
        href = path(book.get('href'), 'html', section)
        title = text(book['title'])
        if href:
            title = f'<a href="{SITE_URL}{href}">{title}</a>'
        body = ''.join(f'<p class="{field}">{text(book[field])}</p>'
                       for field in ('author',) if book.get(field))
        body += f'<h3 class="title">{title}</h3>'
        body += ''.join(f'<p class="{field}">{text(book[field])}</p>'
                        for field in ('from', 'status') if book.get(field))
        options = []
        for key, label in (('html', 'HTML'), ('pdf', 'PDF'), ('fb2', 'FB2')):
            url = href if key == 'html' else path(book.get('formats', {}).get(key), key, section)
            if url:
                action = 'Читать' if key == 'html' else 'Скачать'
                aria = html.escape(f'{action} «{book["title"]}» в {label}', quote=True)
                download = '' if key == 'html' else f' download="{url.split("/")[-1]}"'
                options.append(f'<a class="format" href="{SITE_URL}{url}"{download} aria-label="{aria}">{label}</a>')
            else:
                options.append(f'<span class="format unavailable" title="{label} пока недоступен">'
                               f'{label}<span class="visually-hidden"> (пока недоступен)</span></span>')
        formats = '<div class="book-formats"><p class="formats-label">Форматы</p>'
        formats += '<div class="formats">' + ''.join(options) + '</div></div>'
        items.append(f'<li class="book"><div class="book-text">{body}</div>{formats}</li>')
    return '\n'.join(items)


def render(section):
    data = json.loads((ROOT / f'{section}.json').read_text(encoding='utf-8'))
    start, end = markers(section)
    if isinstance(data, list):
        listing = '<ul class="books" role="list">\n' + render_books(data, section) + '\n</ul>'
    else:
        ids = set()
        categories = []
        for number, category in enumerate(data['categories'], 1):
            cid = category['id']
            if not re.fullmatch(r'[a-z][a-z0-9-]*', cid) or cid in ids:
                raise ValueError(f'Некорректная или повторная рубрика: {cid}')
            ids.add(cid)
            summary = (f'<summary><span class="category-number" aria-hidden="true">{number:02d}</span>'
                       f'<span class="category-title">{text(category["title"])}</span>'
                       f'<span class="category-count">{text(str(len(category["books"])) + " изд.")}</span></summary>')
            content = '<div class="category-content"><ul class="books" role="list">'
            content += render_books(category['books'], section) + '</ul></div>'
            categories.append(f'<li class="catalog-category"><details id="{section}-{cid}">'
                              f'{summary}{content}</details></li>')
        listing = '<ul class="books catalog-categories" role="list">\n'
        listing += '\n'.join(categories) if categories else '<li class="catalog-note">Здесь пока нет переводов.</li>'
        listing += '\n</ul>'
    return start + '\n' + listing + '\n' + end


def sync(check=False):
    page = PAGE.read_text(encoding='utf-8')
    updated = page
    for section in SECTIONS:
        start, end = markers(section)
        if updated.count(start) != 1 or updated.count(end) != 1:
            raise ValueError(f'Должен быть один блок каталога {section}')
        before, remainder = updated.split(start, 1)
        _, after = remainder.split(end, 1)
        updated = before + render(section) + after
    if updated != page:
        if check:
            raise ValueError('Каталоги устарели; запустите tools/catalog_discovery.py')
        PAGE.write_text(updated, encoding='utf-8')
        print('index.html: HTML-каталоги обновлены')
    else:
        print('index.html: HTML-каталоги актуальны')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    sync(parser.parse_args().check)
