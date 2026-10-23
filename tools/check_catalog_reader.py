#!/usr/bin/env python3
"""Read a site's catalog and texts using only its base URL and plain HTTP."""

import argparse
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.request import Request, urlopen


class PlainPage(HTMLParser):
    """Deliberately ignore the script/noscript/template discovery workaround."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored = 0
        self.links = []
        self.anchor = None
        self.parts = []
        self.translation = []
        self.in_translation = False
        self.translation_tag = None
        self.translation_nesting = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.ignored += 1
        if self.ignored:
            return
        attrs = dict(attrs)
        if attrs.get('id') == 'translation':
            self.in_translation = True
            self.translation_tag = tag
            self.translation_nesting = 1
        elif self.in_translation and tag == self.translation_tag:
            self.translation_nesting += 1
        if tag == 'a' and attrs.get('href'):
            self.anchor = [attrs['href'], []]

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'template'):
            self.ignored -= 1
            return
        if self.ignored:
            return
        if tag == 'a' and self.anchor is not None:
            href, parts = self.anchor
            self.links.append((href, ' '.join(''.join(parts).split())))
            self.anchor = None
        if self.in_translation and tag == self.translation_tag:
            self.translation_nesting -= 1
            if self.translation_nesting == 0:
                self.in_translation = False

    def handle_data(self, data):
        if self.ignored:
            return
        self.parts.append(data)
        if self.in_translation:
            self.translation.append(data)
        if self.anchor is not None:
            self.anchor[1].append(data)


def catalog_links(source, base):
    page = PlainPage()
    page.feed(source)
    found = {}
    for href, label in page.links:
        url = urldefrag(urljoin(base, href))[0]
        if urlsplit(url).netloc != urlsplit(base).netloc or not urlsplit(url).path.endswith('.html'):
            continue
        if label and url not in found:
            found[url] = label
    return found


def fetch(url):
    request = Request(url, headers={'User-Agent': 'catalog-read-check/1.0'})
    with urlopen(request, timeout=25) as response:
        if response.headers.get_content_type() != 'text/html':
            raise ValueError(f'Не HTML: {url}')
        raw = response.read(10_000_001)
        if len(raw) > 10_000_000:
            raise ValueError(f'Слишком большой ответ: {url}')
        return raw.decode(response.headers.get_content_charset() or 'utf-8')


def main(base):
    links = catalog_links(fetch(base), base)
    if not links:
        raise SystemExit('В обычном HTML главной страницы нет прямых ссылок на тексты')
    for url, label in links.items():
        print(f'\n{label}\n{url}')
        page = PlainPage()
        page.feed(fetch(url))
        content = ' '.join(' '.join(page.translation or page.parts).split())
        if len(content) < 200:
            raise SystemExit(f'Нет читаемого текста: {url}')
        print(content[:700] + '…')
    print(f'\nПрочитано текстов по ссылкам из главной: {len(links)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base_url')
    main(parser.parse_args().base_url)
