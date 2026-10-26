#!/usr/bin/env python3
"""Импорт закоммиченного свитка Маккона; Git push выполняется отдельно."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess

from catalog_discovery import sync as sync_catalog_discovery

ROOT = Path(__file__).resolve().parent.parent
BOOK = 'Маккон-2005_Грамматика-и-хрестоматия'
OUTPUT = ROOT / 'celts/McCone-2005-ru.html'
RECEIPT = ROOT / 'celts/McCone-2005-ru.publication.json'
STATUS = 'Альфа-версия — перевод не завершён.'


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def publication_units(document):
    # Include numbered units and standalone letter sections such as XII.A,
    # but not grouping headings (I.A, XII.B) with numbered children.
    headings = re.findall(r'<h[23][^>]*id="([ivx]+-(?:[a-z]\d*|\d+))"', document)
    return [unit for unit in headings if not (
        re.fullmatch(r'[ivx]+-[a-z]', unit)
        and any(re.fullmatch(re.escape(unit) + r'\d+', child) for child in headings)
    )]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-repo', type=Path, default=ROOT.parent / 'LGE')
    parser.add_argument('--revision', default='HEAD', help='Только зафиксированная версия исходника')
    parser.add_argument('--date', default=datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    datetime.date.fromisoformat(args.date)
    revision = git(args.source_repo, 'rev-parse', '--verify', args.revision + '^{commit}').decode().strip()
    raw = git(args.source_repo, 'show', f'{revision}:{BOOK}/build/McCone-2005-ru.html')
    original = raw.decode('utf-8')
    if not original.lower().startswith('<!doctype html>') or '<main id="translation">' not in original:
        raise SystemExit('Исходник не является мастер-свитком Маккона')
    # Do not publish stale HTML: each embedded MD digest must match that commit.
    digests = re.findall(r'<!-- MD ([0-9][0-9]-[a-z-]+\.md) SHA256 ([a-f0-9]{64}) -->', original)
    if not digests:
        raise SystemExit('Нет проверяемых ссылок на исходные Markdown')
    for name, expected in digests:
        source = git(args.source_repo, 'show', f'{revision}:{BOOK}/{name}')
        if hashlib.sha256(source).hexdigest() != expected:
            raise SystemExit(f'Свиток устарел относительно {name}; сначала пересоберите и закоммитьте его')
    if re.search(r'file://|/home/|/tmp/|localhost|127\.0\.0\.1', original):
        raise SystemExit('В свитке найден локальный адрес или путь')
    marker = '<p class="edition-scope">'
    if original.count(marker) != 1:
        raise SystemExit('Не найдена единственная отметка неполноты перевода')
    published = original.replace(marker, marker + STATUS + ' ', 1)
    published = published.replace('</head>', '<meta name="description" content="Ким Маккон. Русский научный перевод грамматики и хрестоматии древнеирландского языка. Альфа-версия, перевод не завершён."></head>', 1)
    # All scholarly content and navigation resources remain byte-identical.
    if published.split('<main id="translation">', 1)[1] != original.split('<main id="translation">', 1)[1]:
        raise SystemExit('При импорте изменился текст книги')
    data = published.encode('utf-8')
    units = publication_units(original)
    receipt = {
        'work': 'Kim McCone, A First Old Irish Grammar and Reader (2005)',
        'status': STATUS, 'published_date': args.date,
        'source_revision': revision, 'source_sha256': hashlib.sha256(raw).hexdigest(),
        'published_sha256': hashlib.sha256(data).hexdigest(),
        'markdown': dict(digests), 'units': units,
    }
    receipt_bytes = (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode()
    catalog = json.loads((ROOT / 'celts.json').read_text())
    matches = [b for c in catalog['categories'] for b in c['books'] if b.get('id') == 'mccone-2005']
    if len(matches) != 1 or matches[0].get('href') != 'celts/McCone-2005-ru.html':
        raise SystemExit('Некорректная запись Маккона в каталоге')
    if matches[0].get('status') != STATUS.lower().rstrip('.'):
        raise SystemExit('Маккон должен сохранять альфа-статус незавершённого перевода')
    index_path = ROOT / 'index.html'
    index = index_path.read_text()
    pattern = r'(<section[^>]+data-catalog="celts"[\s\S]*?<time datetime=")[^"]+(">)[^<]+(</time>)'
    months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    date = datetime.date.fromisoformat(args.date)
    label = f'{date.day} {months[date.month - 1]} {date.year}'
    updated_index, count = re.subn(pattern, lambda m: m[1] + args.date + m[2] + label + m[3], index, count=1)
    if count != 1:
        raise SystemExit('Не найдена дата кельтского каталога')
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != data or not RECEIPT.exists() or RECEIPT.read_bytes() != receipt_bytes or index != updated_index:
            raise SystemExit('Публикация отсутствует или не совпадает с выбранной версией')
        sync_catalog_discovery(check=True)
        print(f'Публикация актуальна: {len(units)} подразделов; SHA256 {receipt["published_sha256"]}')
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(data)
        RECEIPT.write_bytes(receipt_bytes)
        index_path.write_text(updated_index)
        sync_catalog_discovery()
        print(f'{OUTPUT}: {len(units)} подразделов; {STATUS}')


if __name__ == '__main__':
    main()
