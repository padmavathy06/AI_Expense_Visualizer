import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class TestWSGIProductionRoutes(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_robots_txt_status_and_content(self):
        res = self.client.get("/robots.txt", headers={"Host": "expense-visualizer-app.onrender.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "text/plain")
        self.assertIn(b"User-agent: *", res.data)
        self.assertIn(b"Allow: /", res.data)
        self.assertIn(b"Disallow: /transactions", res.data)
        self.assertIn(b"Sitemap: https://expense-visualizer-app.onrender.com/sitemap.xml", res.data)

    def test_sitemap_xml_status_and_content(self):
        res = self.client.get("/sitemap.xml", headers={"Host": "expense-visualizer-app.onrender.com"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/xml")
        self.assertIn(b"<loc>https://expense-visualizer-app.onrender.com/</loc>", res.data)
        self.assertIn(b"<loc>https://expense-visualizer-app.onrender.com/login</loc>", res.data)
        self.assertIn(b"<loc>https://expense-visualizer-app.onrender.com/register</loc>", res.data)

    def test_login_page_canonical(self):
        res = self.client.get("/login", headers={"Host": "expense-visualizer-app.onrender.com"})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'<link rel="canonical" href="https://expense-visualizer-app.onrender.com/login">', res.data)

if __name__ == "__main__":
    unittest.main()
