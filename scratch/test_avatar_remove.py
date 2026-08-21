import unittest
import os
import sys
import io

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, UPLOAD_AVATAR_FOLDER
from database import get_db_connection
from services import auth_service

class TestAvatarRemovalFlow(unittest.TestCase):
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

    def test_avatar_upload_remove_and_persistence(self):
        """Tests full lifecycle: upload avatar -> verify -> remove avatar -> verify disk/DB -> persist across relogin."""
        # 1. Register user with avatar
        avatar_data = (io.BytesIO(b"fake image data"), "my_photo.jpg")
        reg_data = {
            "name": "Avatar Tester",
            "email": "avatar@test.com",
            "phone": "9876543299",
            "password": "Password123",
            "confirm_password": "Password123",
            "avatar": avatar_data
        }
        resp = self.client.post("/register", data=reg_data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # 2. Check DB has avatar
        conn = get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT id, avatar FROM users WHERE email = 'avatar@test.com'")
        user = c.fetchone()
        c.close()
        conn.close()

        self.assertIsNotNone(user)
        self.assertTrue(user["avatar"].startswith("/static/uploads/avatars/"))
        avatar_filename = os.path.basename(user["avatar"])
        full_disk_path = os.path.join(UPLOAD_AVATAR_FOLDER, avatar_filename)
        self.assertTrue(os.path.exists(full_disk_path), "Uploaded avatar file should exist on disk")

        # 3. Check profile page displays avatar and remove button
        resp_prof = self.client.get("/profile")
        self.assertIn(b"Remove Photo", resp_prof.data)
        self.assertIn(avatar_filename.encode("utf-8"), resp_prof.data)

        # 4. Click Remove Profile Photo (POST /profile/remove-avatar)
        resp_remove = self.client.post("/profile/remove-avatar", follow_redirects=True)
        self.assertEqual(resp_remove.status_code, 200)
        self.assertIn(b"Profile picture removed successfully", resp_remove.data)
        self.assertIn(b"avatarEmoji", resp_remove.data)

        # 5. Check DB avatar is cleared
        conn = get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT avatar FROM users WHERE email = 'avatar@test.com'")
        user_after = c.fetchone()
        c.close()
        conn.close()
        self.assertEqual(user_after["avatar"], "", "Avatar column in DB should be empty string")

        # 6. Check physical file is removed from server disk
        self.assertFalse(os.path.exists(full_disk_path), "Avatar file should be deleted from server filesystem")

        # 7. Refresh profile page -> avatar remains removed
        resp_refresh = self.client.get("/profile")
        self.assertIn(b"avatarEmoji", resp_refresh.data)
        self.assertNotIn(avatar_filename.encode("utf-8"), resp_refresh.data)

        # 8. Log out and log back in -> avatar remains removed
        self.client.get("/logout")
        resp_login = self.client.post("/login", data={"email": "avatar@test.com", "password": "Password123"}, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)

        # Check profile again
        resp_prof_relogin = self.client.get("/profile")
        self.assertIn(b"avatarEmoji", resp_prof_relogin.data)
        self.assertNotIn(avatar_filename.encode("utf-8"), resp_prof_relogin.data)

if __name__ == "__main__":
    unittest.main()
