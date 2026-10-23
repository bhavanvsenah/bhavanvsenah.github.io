"""The real catalog must be readable without JS, with no hidden duplicate."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import catalog_discovery as discovery
from check_catalog_reader import catalog_links

BASE = 'https://example.test/'


class CatalogDiscoveryTests(unittest.TestCase):
    def test_plain_html_has_every_published_link_and_no_draft_link(self):
        expected = set()
        output = ''
        for section in discovery.SECTIONS:
            data = json.loads((discovery.ROOT / f'{section}.json').read_text())
            groups = data['categories'] if isinstance(data, dict) else [{'books': data}]
            expected.update(BASE + b['href'] for c in groups for b in c['books'] if b.get('href'))
            output += discovery.render(section)
        self.assertEqual(set(catalog_links(output, BASE)), expected)
        self.assertIn('Книга захватов Ирландии', output)  # Still an announcement.
        self.assertNotIn('<button', output)
        self.assertNotIn('<script', output)
        self.assertNotIn('<noscript', output)

    def test_hidden_workaround_is_not_accepted_by_reader(self):
        hidden = ('<noscript><a href="book.html">Book</a></noscript>'
                  '<script type="application/ld+json">{"url":"book.html"}</script>')
        self.assertEqual(catalog_links(hidden, BASE), {})

    def test_check_rejects_stale_snapshot_and_preserves_surroundings(self):
        with TemporaryDirectory() as directory:
            page = Path(directory) / 'index.html'
            stale = 'before\n'
            for section in discovery.SECTIONS:
                start, end = discovery.markers(section)
                stale += start + '\nstale\n' + end + '\n'
            page.write_text(stale + 'after\n')
            with patch.object(discovery, 'PAGE', page):
                with self.assertRaisesRegex(ValueError, 'устарели'):
                    discovery.sync(check=True)
                discovery.sync()
                discovery.sync(check=True)
            self.assertTrue(page.read_text().startswith('before\n'))
            self.assertTrue(page.read_text().endswith('after\n'))

    def test_text_is_escaped_and_keeps_nbsp(self):
        self.assertEqual(discovery.text('о принятии <текста>'), 'о\u00a0принятии &lt;текста&gt;')
        self.assertIn('&lt;script&gt;', discovery.render_books([{'title': '<script>'}], 'celts'))

    def test_old_locale_sort_is_preserved(self):
        books = [{'title': 'Текст 10'}, {'title': 'Текст 2'}, {'title': 'А'}]
        self.assertEqual([b['title'] for b in discovery.alphabetical(books)], ['А', 'Текст 2', 'Текст 10'])

    def test_invalid_or_missing_target_is_rejected(self):
        for target in ('../private.html', 'dharma/missing.html', 'https://elsewhere.test/book.html'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                discovery.path(target, 'html', 'dharma')


if __name__ == '__main__':
    unittest.main()
