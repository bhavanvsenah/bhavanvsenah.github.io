#!/usr/bin/env python3
"""Mark the stylesheet, scripts and pictures of index.html with versions of their content.

GitHub Pages lets browsers keep a file for ten minutes, and a reload asks
again only for the page itself, so a fresh index.html could meet yesterday's
styles.css from the cache. Each local stylesheet, script, picture and
icon gets ?v= and the first eight hex digits of its SHA-256: a changed file
gets a new address and is fetched anew. Run after changing styles.css, any script or
any picture of the start page. The article pages get the same mark for
article.css from md2html.py.

Usage: tools/stamp.py [--check]   (--check only reports stale marks)
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / 'index.html'
ASSET = re.compile(r'((?:href|src)=")([\w/-]+\.(?:css|js|png|jpg|webp|svg|ico))(?:\?v=[0-9a-f]*)?(")')


def stamp(match):
    name = match.group(2)
    version = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()[:8]
    return f'{match.group(1)}{name}?v={version}{match.group(3)}'


def main():
    page = PAGE.read_text(encoding='utf-8')
    stamped = ASSET.sub(stamp, page)
    if stamped == page:
        print('index.html: marks are current')
    elif '--check' in sys.argv[1:]:
        raise SystemExit('index.html: marks are stale, run tools/stamp.py')
    else:
        PAGE.write_text(stamped, encoding='utf-8')
        print('index.html: marks updated')


if __name__ == '__main__':
    main()
