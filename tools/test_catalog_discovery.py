"""Focused checks for the generated, non-rendered catalog snapshot."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import catalog_discovery as discovery


class CatalogDiscoveryTests(unittest.TestCase):
    def test_only_published_catalog_entries_are_exposed(self):
        books = discovery.published_books()
        self.assertEqual(
            [book['href'] for _, book in books],
            ['celts/McCone-2005-ru.html', 'dharma/Toh3971_Trisharanasaptati.html'],
        )
        output = discovery.render()
        self.assertNotIn('Книга захватов Ирландии', output)
        for _, book in books:
            self.assertIn('href="/' + book['href'] + '"', output)
            self.assertIn(discovery.BASE + book['href'], output)
        structured = output.split('<script type="application/ld+json" id="published-catalog-data">', 1)[1].split('</script>', 1)[0]
        entries = json.loads(structured)['mainEntity']['itemListElement']
        self.assertEqual([item['item']['url'] for item in entries],
                         [discovery.BASE + book['href'] for _, book in books])

    def test_check_rejects_stale_snapshot_and_update_preserves_surroundings(self):
        with TemporaryDirectory() as directory:
            page = Path(directory) / 'index.html'
            page.write_text('before\n' + discovery.START + '\nstale\n' + discovery.END + '\nafter\n')
            with patch.object(discovery, 'PAGE', page):
                with self.assertRaisesRegex(ValueError, 'устарел'):
                    discovery.sync(check=True)
                discovery.sync()
                discovery.sync(check=True)
            result = page.read_text()
            self.assertTrue(result.startswith('before\n'))
            self.assertTrue(result.endswith('\nafter\n'))


if __name__ == '__main__':
    unittest.main()
