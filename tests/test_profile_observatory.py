import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from public_site_audit import SITE_PROFILES, audit_profile


class ProfileObservatoryTests(unittest.TestCase):
    def test_profile_defines_multiple_routes(self):
        self.assertGreaterEqual(len(SITE_PROFILES['agm']['routes']), 3)
        self.assertGreaterEqual(len(SITE_PROFILES['oee-oracle']['routes']), 3)

    def test_audit_profile_writes_summary_and_route_packets(self):
        responses = {
            'https://example.com/': ('<html><head><title>Home</title></head><body><h1>Home</h1>Alpha <a href="/about">About</a></body></html>', {':status': '200', 'server': 'Vercel', 'content-type': 'text/html'}),
            'https://example.com/about': ('<html><head><title>About</title></head><body><h1>About</h1>Beta</body></html>', {':status': '200', 'server': 'Vercel', 'content-type': 'text/html'}),
        }
        profile = {
            'url': 'https://example.com',
            'markers': ['Alpha'],
            'routes': [
                {'path': '/', 'markers': ['Alpha']},
                {'path': '/about', 'markers': ['Beta']},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch('public_site_audit.Path.home', return_value=root), patch('public_site_audit.fetch_html', side_effect=lambda url: responses[url]):
                outdir, summary = audit_profile('example', profile, workflow='public-site-smoke', lane='deploy')

            self.assertTrue((outdir / 'summary.json').exists())
            data = json.loads((outdir / 'summary.json').read_text())
            self.assertEqual(data['profile'], 'example')
            self.assertEqual(len(data['routes']), 2)
            self.assertEqual(summary['risk_level'], 'low')
            self.assertTrue((outdir / 'routes' / 'root' / 'packet.json').exists())
            self.assertTrue((outdir / 'routes' / 'about' / 'packet.json').exists())


if __name__ == '__main__':
    unittest.main()
