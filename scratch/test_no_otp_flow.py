import unittest
import os
import sys
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database import get_db_connection
from services import auth_service, expense_service

class TestNoOTPAuthFlow(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Clean DB for fresh test run
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM expenses")
        c.execute("DELETE FROM transactions")
        c.execute("DELETE FROM subscriptions")
        c.execute("DELETE FROM financial_goals")
        c.execute("DELETE FROM budget")
        c.execute("DELETE FROM accounts")
        c.execute("DELETE FROM users")
        conn.commit()
        c.close()
        conn.close()

    def test_1_fresh_visitor_redirected_to_login(self):
        """Unauthenticated visitor trying to access dashboard is redirected to /login."""
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/login" in response.headers["Location"])

        # Also check /transactions and /profile
        resp_tx = self.client.get("/transactions", follow_redirects=False)
        self.assertEqual(resp_tx.status_code, 302)
        self.assertTrue("/login" in resp_tx.headers["Location"])

        resp_prof = self.client.get("/profile", follow_redirects=False)
        self.assertEqual(resp_prof.status_code, 302)
        self.assertTrue("/login" in resp_prof.headers["Location"])

    def test_2_direct_registration_no_otp(self):
        """User registers directly without any OTP and is redirected to Dashboard."""
        reg_data = {
            "name": "Padmavathy P",
            "email": "pavi02928@gmail.com",
            "phone": "6383398677",
            "password": "Password123",
            "confirm_password": "Password123"
        }
        response = self.client.post("/register", data=reg_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Account created successfully", response.data)
        self.assertIn(b"Padmavathy P", response.data)
        self.assertIn(b"Dashboard", response.data)

        # Verify in database
        conn = get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT * FROM users WHERE email = 'pavi02928@gmail.com'")
        user = c.fetchone()
        c.close()
        conn.close()
        self.assertIsNotNone(user)
        self.assertEqual(user["name"], "Padmavathy P")
        self.assertEqual(user["phone"], "6383398677")
        self.assertEqual(user["is_verified"], 1)

    def test_3_login_with_email_and_mobile(self):
        """User can log in with either email or mobile number."""
        # Create user
        auth_service.register_user("Alex Morgan", "alex@test.com", "9876543210", "Secret123")

        # Test login via Email
        resp1 = self.client.post("/login", data={"email": "alex@test.com", "password": "Secret123"}, follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"Welcome back, Alex Morgan!", resp1.data)

        # Logout
        self.client.get("/logout")

        # Test login via Mobile
        resp2 = self.client.post("/login", data={"email": "9876543210", "password": "Secret123"}, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b"Welcome back, Alex Morgan!", resp2.data)

    def test_4_user_expense_persistence_and_isolation(self):
        """User A and User B expenses are isolated and persist in DB."""
        user_a, _ = auth_service.register_user("User A", "user_a@test.com", "9876543211", "Pass1234")
        user_b, _ = auth_service.register_user("User B", "user_b@test.com", "9876543212", "Pass1234")

        # User A adds ₹2500 Grocery
        expense_service.add_expense(2500.0, "Food", "Weekly Groceries", "2026-08-21", "UPI", user_id=user_a["id"])

        # User B adds ₹1200 Movie
        expense_service.add_expense(1200.0, "Entertainment", "IMAX Movie", "2026-08-21", "Credit Card", user_id=user_b["id"])

        # Login as User A -> sees only User A expenses
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_a["id"]
            sess["user_name"] = user_a["name"]
            sess["user_email"] = user_a["email"]

        resp_a = self.client.get("/transactions")
        self.assertIn(b"Weekly Groceries", resp_a.data)
        self.assertNotIn(b"IMAX Movie", resp_a.data)

        # Login as User B -> sees only User B expenses
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_b["id"]
            sess["user_name"] = user_b["name"]
            sess["user_email"] = user_b["email"]

        resp_b = self.client.get("/transactions")
        self.assertIn(b"IMAX Movie", resp_b.data)
        self.assertNotIn(b"Weekly Groceries", resp_b.data)

    def test_5_profile_update_without_otp(self):
        """Profile information (including mobile number) updates directly without OTP."""
        user, _ = auth_service.register_user("Initial Name", "initial@test.com", "9876543220", "Pass1234")

        with self.client.session_transaction() as sess:
            sess["user_id"] = user["id"]
            sess["user_name"] = user["name"]
            sess["user_email"] = user["email"]

        update_data = {
            "action_type": "update_info",
            "name": "Updated Name",
            "email": "updated@test.com",
            "phone": "9876543221"
        }
        resp = self.client.post("/profile", data=update_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Profile details updated successfully!", resp.data)
        self.assertIn(b"Updated Name", resp.data)
        self.assertIn(b"9876543221", resp.data)

if __name__ == "__main__":
    unittest.main()
