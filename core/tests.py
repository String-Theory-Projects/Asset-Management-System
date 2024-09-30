from django.test import TestCase
from django.db import connection

from django.contrib.auth import get_user_model
from core.models import *

User = get_user_model()

class DatabaseConnectionTest(TestCase):
    def test_database_connection(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
