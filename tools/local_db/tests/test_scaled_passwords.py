"""Real password compatibility checks for large local fixture populations."""
import os
import unittest
from unittest.mock import patch

from django.contrib.auth.hashers import check_password, identify_hasher, is_password_usable
from generator import _synthetic_role_password_hash


class SyntheticPasswordTests(unittest.TestCase):
    def test_role_overrides_keep_standard_django_passwords(self):
        with patch.dict(os.environ, {
            'LOCAL_DB_LOGIN_PASSWORD': 'fallback-demo',
            'LOCAL_DB_ADMIN_PASSWORD': 'admin123',
            'LOCAL_DB_STUDENT_PASSWORD': 'student123',
        }):
            for role, password in [('admin', 'admin123'), ('student', 'student123')]:
                encoded = _synthetic_role_password_hash(role)
                self.assertEqual(identify_hasher(encoded).algorithm, 'pbkdf2_sha256')
                self.assertTrue(check_password(password, encoded))
                self.assertFalse(check_password('incorrect-demo-password', encoded))

    def test_fallback_and_fresh_salts_are_preserved(self):
        with patch.dict(os.environ, {'LOCAL_DB_LOGIN_PASSWORD': 'fallback-demo'}):
            for role in ['mentor', 'supervisor']:
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop(f'LOCAL_DB_{role.upper()}_PASSWORD', None)
                    first = _synthetic_role_password_hash(role)
                    second = _synthetic_role_password_hash(role)
                self.assertNotEqual(first, second)
                self.assertTrue(check_password('fallback-demo', first))
                self.assertTrue(check_password('fallback-demo', second))

    def test_blank_password_remains_unusable(self):
        with patch.dict(os.environ, {'LOCAL_DB_STUDENT_PASSWORD': ''}):
            self.assertFalse(is_password_usable(_synthetic_role_password_hash('student')))


if __name__ == '__main__':
    unittest.main()
