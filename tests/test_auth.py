import unittest
from types import SimpleNamespace

from bdh_sdk import is_admin


def req(**user):
    base = {"is_authenticated": True, "is_active": True, "is_staff": True}
    return SimpleNamespace(user=SimpleNamespace(**{**base, **user}))


class IsAdminTests(unittest.TestCase):
    def test_active_signed_in_staff_is_admin(self):
        self.assertTrue(is_admin(req()))

    def test_anyone_else_is_not(self):
        for user in ({"is_staff": False}, {"is_active": False}, {"is_authenticated": False}):
            with self.subTest(**user):
                self.assertFalse(is_admin(req(**user)))

    def test_request_without_user_is_not(self):
        self.assertFalse(is_admin(SimpleNamespace()))
        self.assertFalse(is_admin(SimpleNamespace(user=None)))


if __name__ == "__main__":
    unittest.main()
