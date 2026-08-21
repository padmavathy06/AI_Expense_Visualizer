import unittest
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database import get_db_connection
from services import auth_service

class TestSEOAndBranding(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_1_robots_txt_public_and_private_rules(self):
        """robots.txt allows public pages, protects private pages, and links to sitemap."""
        resp = self.client.get("/robots.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("text/plain" in resp.content_type)
        content = resp.data.decode("utf-8")
        
        # Public allows
        self.assertIn("Allow: /", content)
        self.assertIn("Allow: /login", content)
        self.assertIn("Allow: /register", content)
        self.assertIn("Allow: /static/", content)
        
        # Private disallows
        self.assertIn("Disallow: /transactions", content)
        self.assertIn("Disallow: /accounts", content)
        self.assertIn("Disallow: /subscriptions", content)
        self.assertIn("Disallow: /goals", content)
        self.assertIn("Disallow: /analytics", content)
        self.assertIn("Disallow: /ai-insights", content)
        self.assertIn("Disallow: /profile", content)
        self.assertIn("Disallow: /api/", content)
        
        # Sitemap link pointing to Render domain
        self.assertIn("Sitemap: https://expense-visualizer-app.onrender.com/sitemap.xml", content)

    def test_2_sitemap_xml_structure(self):
        """sitemap.xml includes public pages with priority & changefreq, excluding private pages."""
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue("application/xml" in resp.content_type)
        content = resp.data.decode("utf-8")
        
        self.assertIn("<loc>https://expense-visualizer-app.onrender.com/</loc>", content)
        self.assertIn("<loc>https://expense-visualizer-app.onrender.com/login</loc>", content)
        self.assertIn("<loc>https://expense-visualizer-app.onrender.com/register</loc>", content)
        self.assertNotIn("/transactions", content)
        self.assertNotIn("/profile", content)
        self.assertNotIn("/accounts", content)

    def test_3_login_page_branding_and_seo(self):
        """Login page has exact title, prominent branding, tagline, meta description, keywords, Open Graph & JSON-LD."""
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")

        # 1. Exact Title
        self.assertIn("<title>AI Expense Visualizer | AI-Powered Expense Tracker</title>", content)
        
        # 2. Prominent Branding & Tagline
        self.assertIn("AI Expense Visualizer", content)
        self.assertIn("Track, analyze and understand your expenses with AI.", content)
        
        # 3. Meta Description & Keywords
        self.assertIn('name="description" content="AI Expense Visualizer is an AI-powered expense tracker that helps users track, analyze, visualize, and understand their personal expenses."', content)
        self.assertIn('name="keywords" content="AI Expense Visualizer, AI expense tracker, expense tracker, personal expense tracker, expense management, expense analytics, AI financial insights, spending analysis"', content)
        
        # 4. Canonical URL (Points to Render URL)
        self.assertIn('<link rel="canonical" href="https://expense-visualizer-app.onrender.com/login">', content)
        
        # 5. Open Graph Metadata
        self.assertIn('property="og:title" content="AI Expense Visualizer | AI-Powered Expense Tracker"', content)
        self.assertIn('property="og:description" content="Track, analyze and understand your expenses with AI."', content)
        self.assertIn('property="og:image" content="https://expense-visualizer-app.onrender.com/static/img/og-preview.png"', content)
        
        # 6. Twitter Card
        self.assertIn('name="twitter:card" content="summary_large_image"', content)
        
        # 7. JSON-LD Schema.org Structured Data
        self.assertIn('"@context": "https://schema.org"', content)
        self.assertIn('"@type": "WebApplication"', content)
        self.assertIn('"name": "AI Expense Visualizer"', content)

    def test_4_register_page_branding_and_seo(self):
        """Register page contains exact title, branding, tagline, and canonical URL."""
        resp = self.client.get("/register")
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")

        self.assertIn("<title>Create Account | AI Expense Visualizer | AI-Powered Expense Tracker</title>", content)
        self.assertIn("AI Expense Visualizer", content)
        self.assertIn("Track, analyze and understand your expenses with AI.", content)
        self.assertIn('<link rel="canonical" href="https://expense-visualizer-app.onrender.com/register">', content)

    def test_5_private_dashboard_has_noindex_tag(self):
        """Authenticated dashboard has robots noindex protection to protect private data."""
        # Clean & create user
        user, _ = auth_service.register_user("SEO Tester", "seotester@test.com", "9876543201", "Password123")
        with self.client.session_transaction() as sess:
            sess["user_id"] = user["id"]
            sess["user_name"] = user["name"]
            sess["user_email"] = user["email"]

        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        content = resp.data.decode("utf-8")
        self.assertIn('<meta name="robots" content="noindex, nofollow">', content)
        self.assertIn("Dashboard | AI Expense Visualizer | AI-Powered Expense Tracker", content)

if __name__ == "__main__":
    unittest.main()
