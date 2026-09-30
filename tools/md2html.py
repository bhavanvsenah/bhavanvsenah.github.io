#!/usr/bin/env python3
"""Builds an article page from its Markdown source.

    python3 tools/md2html.py articles/about.md

writes articles/about.html next to the source. It reads only the
small subset of Markdown the articles use: # and ## headings, paragraphs, a
> blockquote epigraph, an image followed by its caption in *italics*, a
closing — signature, inline HTML links, **bold**, *italic*, ~~struck-out~~
and `code`. Struck-out words are left out of the page title.

A play also gets speaker lines (**Name.** text, or **Name** *(aside)*. text),
stage directions (a whole paragraph in *italics*) and, in the cast list, an
avatar floated beside each character's description. A cast list is the
section headed «Действующие лица», or any section or whole page that opens
with a character's description: the full name in bold first. Names are
recognised in the modern and in the old spelling alike, «Брат Клод» as well
as «Братъ Клодъ», and shown as written. Web copies of
the avatars are cached in articles/img/avatars/; each copy carries the hash
of the picture it was made from and is rebuilt only when that changes.

All article pages share one stylesheet, article.css next to them, which loads
the fonts from fonts/, so a reader's browser fetches both once for the whole
site. The stylesheet is linked with a version taken from its content
(article.css?v=…), so a browser fetches it anew after every change; rebuild
the pages after changing it. The avatars are linked from articles/img/avatars/, with only their
small outlines embedded; the images are embedded in the page.
"""

import base64
import hashlib
import html
import io
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# Speaker as written in the lines -> (class name, source picture, full name in
# bold in the cast list), both in modern spelling.
AVATARS = {
    'Bhavān': ('bhavan', 'pics/brahman.png', 'Bhavān Vsenaḥ'),
    'Клод': ('klod', 'pics/Claude.png', 'Брат Клод'),
    'Астра': ('astra', 'pics/astra.png', 'Друидесса Астра'),
    'Лама Джамбон': ('lama', 'pics/lama.png', 'Лама Джамбон'),
    'Свами Дебагнатх': ('sadhu', 'pics/sadhu.png', 'Свами Дебагнатх'),
    'Пандит Промптананда': ('pandit', 'pics/brahman.png', 'Пандит Промптананда'),
}
AVATAR_PX = 640  # longest side of the web copy, enough for 8K; the shown size is in article.css
AVATAR_WEBP = {'quality': 86, 'method': 6}
MADE_FROM = 0x010E  # EXIF ImageDescription of the web copy: its source hash and settings
STYLESHEET = 'article.css'  # shared by all article pages, next to them
SHAPE_PX = 160  # the text only needs the avatar's outline, so the shape image is small
MIME = {'.webp': 'image/webp', '.png': 'image/png',
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml'}

SPEAKER = re.compile(
    r'^\*\*(?P<who>[^*]+?)(?P<dot>\.)?\*\*'
    r'(?: \*\((?P<aside>[^)]*)\)\*\.)? (?P<text>.+)$', re.S)
IMAGE = re.compile(r'^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)$')
ITALIC_BLOCK = re.compile(r'^\*(?!\*)(.+)(?<!\*)\*$', re.S)
SIGNATURE = re.compile(r'^— (?P<who>[^\n]{1,60})$')
BOLD_START = re.compile(r'^\*\*(?P<name>[^*]+)\*\*')
CYRILLIC = 'А-Яа-яЁёѢѣІіѲѳѴѵ'  # with the letters of the old spelling
LATIN = 'A-Za-zÀ-ÖØ-öø-ž'  # with accents, as in Irish names: Ó hAltmáin

# The old letters in modern spelling, for comparing names.
MODERN = str.maketrans('ѢѣІіѲѳѴѵЁё', 'ЕеИиФфИиЕе')


def modern(text):
    """Text in modern spelling: no ѣ, і, ѳ, ѵ or ё, and no hard sign closing a word."""
    return re.sub(r'[ъЪ]\b', '', text.translate(MODERN))


# Another full name a character goes by: the lama of the play is a geshe
# in the roster of the artel.
OTHER_NAMES = {'Геше Джамбон': 'Лама Джамбон'}
FULL_NAMES = {modern(name): who for who, (_, _, name) in AVATARS.items()}
FULL_NAMES.update((modern(name), who) for name, who in OTHER_NAMES.items())
SPEAKERS = {modern(who): who for who in AVATARS}


def character(block):
    """The speaker whose description the block is, the full name in bold first; or None."""
    m = BOLD_START.match(block)
    return FULL_NAMES.get(modern(m['name'])) if m else None


# Browsers hyphenate Russian by patterns that know no ѣ or і and leave a word
# with them whole, which opens gaps in justified lines. Such words get soft
# hyphens by the Russian syllable rules (after Khmelev): after й, ь or ъ;
# between vowels; and between consonants, one to the left of two or three
# and two to the left of two.
VOWELS, CONSONANTS, SIGNS = 'аеёиоуыэюяѣіѵ', 'бвгджзклмнпрстфхцчшщѳ', 'йьъ'
LETTERS = VOWELS + CONSONANTS + SIGNS
SYLLABLE_BREAK = re.compile(
    rf'(?<=[{SIGNS}])(?=[{LETTERS}]{{2}})'
    rf'|(?<=[{VOWELS}])(?=[{VOWELS}][{LETTERS}])'
    rf'|(?<=[{VOWELS}][{CONSONANTS}])(?=[{CONSONANTS}][{VOWELS}])'
    rf'|(?<=[{CONSONANTS}][{VOWELS}])(?=[{CONSONANTS}][{VOWELS}])'
    rf'|(?<=[{VOWELS}][{CONSONANTS}])(?=[{CONSONANTS}]{{2}}[{VOWELS}])'
    rf'|(?<=[{VOWELS}][{CONSONANTS}]{{2}})(?=[{CONSONANTS}]{{2}}[{VOWELS}])', re.I)
OLD_LETTER = re.compile('[ѢѣІіѲѳѴѵ]')


def hyphenate(word):
    """Soft hyphens in a word of the old spelling, leaving two letters or more on each side."""
    if not OLD_LETTER.search(word):
        return word  # the browser hyphenates it
    cuts = [m.start() for m in SYLLABLE_BREAK.finditer(word) if 2 <= m.start() <= len(word) - 2]
    return '&shy;'.join(word[a:b] for a, b in zip([0, *cuts], [*cuts, len(word)]))


def typeset(text):
    """Russian typesetting outside tags: short words and dashes keep to the next word,
    words of the old spelling get soft hyphens."""
    parts = re.split(r'(<[^>]+>)', text)
    for i in range(0, len(parts), 2):
        s = parts[i]
        s = re.sub(rf'(?<![^\s(«„])([{CYRILLIC}{LATIN}]{{1,2}}) ', '\\1\u00a0', s)
        s = s.replace(' - ', ' — ')  # a hyphen between spaces is a dash typed by hand
        s = re.sub(r'"([^"<>]*)"', '«\\1»', s)  # straight quotes typed by hand
        s = s.replace(' —', '\u00a0—')
        s = re.sub(r'(\d) %', '\\1\u00a0%', s)
        s = re.sub(r'&(?![#\w]+;)', '&amp;', s)
        s = re.sub(rf'[{CYRILLIC}]+', lambda m: hyphenate(m[0]), s)
        parts[i] = s
    return ''.join(parts)


def inline(text, asides=True):
    text = re.sub(r'`([^`]+)`', lambda m: f'<code>{html.escape(m.group(1))}</code>', text)
    if asides:  # stage directions inside lines; in the cast list (*...*) is plain italics
        text = re.sub(r'\*\((.+?)\)\*', r'<span class="aside">(\1)</span>', text)
        text = re.sub(r'\(\*([^*]+?)\*\)', r'<span class="aside">(\1)</span>', text)  # (*aside*) typed by hand
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
    text = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', text)
    return typeset(text)


def data_uri(data, suffix):
    return f'data:{MIME[suffix]};base64,{base64.b64encode(data).decode()}'


def plain(fragment):
    text = html.unescape(re.sub(r'<[^>]+>', '', fragment)).replace('\u00ad', '')  # no soft hyphens
    return re.sub(r'\s+', ' ', text).strip()


def avatar_copy(slug, source, md_dir):
    """A trimmed, downscaled WebP of the avatar; rebuilt when the source or the settings change.

    Git does not keep file times, so after a pull a copy can look older than
    its source; the copy is compared with the source by hash instead."""
    src = ROOT / source
    out = md_dir / 'img' / 'avatars' / f'{slug}.webp'
    made_from = f'sha256={hashlib.sha256(src.read_bytes()).hexdigest()} px={AVATAR_PX} webp={AVATAR_WEBP}'
    stale = True
    if out.exists():
        with Image.open(out) as im:
            stale = im.getexif().get(MADE_FROM) != made_from
    if stale:
        out.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert('RGBA')
        im = im.crop(im.getchannel('A').getbbox())
        im.thumbnail((AVATAR_PX, AVATAR_PX), Image.LANCZOS)
        exif = Image.Exif()
        exif[MADE_FROM] = made_from
        im.save(out, 'WEBP', exif=exif, **AVATAR_WEBP)
    with Image.open(out) as im:
        shape = im.copy()
        size = im.size
    shape.thumbnail((SHAPE_PX, SHAPE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    shape.save(buf, 'WEBP', quality=60, method=6)
    # The picture is linked, so the browser caches it; its small outline stays
    # in the page, so the text wraps around the figure before the picture loads.
    return out.relative_to(md_dir).as_posix(), data_uri(buf.getvalue(), '.webp'), size


def image_size(src, md_dir):
    with Image.open(md_dir / src) as im:
        return im.size


def render(md, md_dir):
    blocks = [b.strip() for b in re.split(r'\n[ \t]*\n', md) if b.strip()]
    out, title, description = [], '', ''
    act, placed, spoke, section, in_cast = 0, set(), set(), False, False

    play = any(b.startswith('## Действие') for b in blocks)
    casts = 0

    def open_cast():
        """A cast list's section; on a page that is not a play, a roster."""
        nonlocal casts
        casts += 1
        out.append(f'<section class="{"cast" if play else "cast roster"}" id="cast{"" if casts == 1 else f"-{casts}"}">')

    def opens_cast(j):
        """Whether block j describes a character: the full name in bold first."""
        return j < len(blocks) and character(blocks[j]) is not None

    def close_section():
        nonlocal section
        if section:
            out.append('</section>')
            section = False

    i = 0
    while i < len(blocks):
        b = blocks[i]
        i += 1

        if b.startswith('# '):
            title = plain(re.sub(r'<del>.*?</del>', '', inline(b[2:])))
            out.append(f'<h1>{inline(b[2:])}</h1>')
            if i < len(blocks) and ITALIC_BLOCK.match(blocks[i]) and not blocks[i].startswith('**'):
                out.append(f'<p class="genre">{inline(ITALIC_BLOCK.match(blocks[i]).group(1))}</p>')
                i += 1
            if opens_cast(i):  # a page that is itself a cast list
                open_cast()
                section = in_cast = True
            continue

        if b.startswith('## '):
            close_section()
            heading = b[3:]
            in_cast = heading.startswith('Действующие лица') or opens_cast(i)
            if heading.startswith('Действие'):
                act += 1
                out.append(f'<section class="act" id="act-{act}">')
            elif in_cast:
                open_cast()
            else:
                out.append('<section>')
            section = True
            out.append(f'<h2>{inline(heading)}</h2>')
            continue

        if b.startswith('>'):
            lines = [re.sub(r'^>\s?', '', l) for l in b.split('\n')]
            paras = [p for p in '\n'.join(lines).split('\n\n') if p.strip()]
            inner = []
            for p in paras:
                m = ITALIC_BLOCK.match(p)
                if m:
                    inner.append(f'<p class="source">{inline(m.group(1))}</p>')
                else:
                    inner.append('<p>' + '<br>\n'.join(inline(l) for l in p.split('\n')) + '</p>')
            out.append('<blockquote class="epigraph">\n' + '\n'.join(inner) + '\n</blockquote>')
            continue

        m = IMAGE.match(b)
        if m:
            src, alt = m['src'], m['alt']
            w, h = image_size(src, md_dir)
            # Natural size at the standard 16px root, growing with the page on big screens.
            path = md_dir / src
            fig = [f'<figure>\n<img src="{data_uri(path.read_bytes(), path.suffix.lower())}" alt="{html.escape(alt)}" width="{w}" height="{h}" '
                   f'style="width: {w / 16:g}rem" loading="lazy" decoding="async">']
            if i < len(blocks) and ITALIC_BLOCK.match(blocks[i]):
                fig.append(f'<figcaption>{inline(ITALIC_BLOCK.match(blocks[i]).group(1))}</figcaption>')
                i += 1
            out.append('\n'.join(fig) + '\n</figure>')
            continue

        persona = character(b) if in_cast else None
        if persona:
            slug, source, _ = AVATARS[persona]
            placed.add(persona)
            src, shape, (w, h) = avatar_copy(slug, source, md_dir)
            name = html.escape(BOLD_START.match(b)['name'])  # as written on this page
            out.append(
                f'<p class="persona {slug}"><img class="avatar" src="{src}" alt="{name}" '
                f'width="{w}" height="{h}" style="shape-outside: url({shape})" decoding="async">'
                f'{inline(b, asides=False)}</p>')
            continue

        m = SPEAKER.match(b)
        who = SPEAKERS.get(modern(m['who'])) if m else None
        if who:
            spoke.add(who)
            slug = AVATARS[who][0]
            label = f'<span class="who">{m["who"]}{"." if m["dot"] else ""}</span>'
            if m['aside']:
                label += f' <span class="aside">({inline(m["aside"])})</span>.'
            out.append(f'<p class="line {slug}">{label} {inline(m["text"])}</p>')
            continue

        if b.startswith('**TL;DR**'):
            description = plain(inline(b[len('**TL;DR**'):]))
            out.append(f'<p class="tldr">{inline(b)}</p>')
            continue

        m = ITALIC_BLOCK.match(b)
        if m and not b.startswith('**'):
            out.append(f'<p class="remark">{inline(m.group(1))}</p>')
            continue

        m = SIGNATURE.match(b)
        if m:
            out.append(f'<p class="signature">— {inline(m["who"])}</p>')
            continue

        out.append(f'<p>{inline(b)}</p>')

    close_section()
    missing = spoke - placed  # characters of other pages need not be in this one's cast
    if missing:
        print('speaks but is not in the cast list, no avatar:', ', '.join(sorted(missing)), file=sys.stderr)
    if not description:  # without a TL;DR, the subtitle or the first paragraph describes the page
        first = next((plain(x) for x in out if x.startswith(('<p>', '<p class="genre">'))), '')
        description = first if len(first) <= 200 else first[:first.rfind(' ', 0, 200)] + '…'
    return title, description, '\n'.join(out)


PAGE = '''<!DOCTYPE html>
<!-- Built by tools/md2html.py from {source}. Edit the Markdown, not this file. -->
<html lang="ru">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="dark">
    <meta name="theme-color" content="#0f0c0a">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <link rel="icon" href="../favicon.ico" sizes="32x32">
    <link rel="icon" href="../favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="../apple-touch-icon.png">
    <link rel="stylesheet" href="{stylesheet}">
  </head>
  <body>
    <main class="article">
{body}
    </main>
  </body>
</html>
'''


class Balance(HTMLParser):
    """Fails on unclosed or stray tags, so a broken page is never written."""
    VOID = {'br', 'img', 'meta', 'link', 'hr', 'input'}

    def __init__(self):
        super().__init__()
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise SystemExit(f'unbalanced </{tag}> near line {self.getpos()[0]}')


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    source = Path(sys.argv[1]).resolve()
    if not (source.parent / STYLESHEET).exists():
        raise SystemExit(f'{STYLESHEET} not found next to {source.name}')
    title, description, body = render(source.read_text(encoding='utf-8'), source.parent)
    version = hashlib.sha256((source.parent / STYLESHEET).read_bytes()).hexdigest()[:8]
    page = PAGE.format(source=source.name, title=html.escape(title),
                       description=html.escape(description), body=body,
                       stylesheet=f'{STYLESHEET}?v={version}')
    checker = Balance()
    checker.feed(page)
    if checker.stack:
        raise SystemExit(f'unclosed tags: {checker.stack}')
    leftovers = re.findall(r'\*\*|~~|(?<![\w/])\*\w', re.sub(r'<[^>]+>', '', body))
    if leftovers:
        raise SystemExit(f'Markdown left unconverted: {leftovers[:5]}')
    target = source.with_suffix('.html')
    target.write_text(page, encoding='utf-8')
    shown = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target  # a draft kept elsewhere
    print(f'{shown}: {len(page) // 1024} KB')


if __name__ == '__main__':
    main()
