from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import User, StudentProfile, MentorProfile, SupervisorProfile, Background

# Create your tests here.

class RegisterUserTest(APITestCase):
    def test_register_student_success(self):
        url = reverse("user-register")
        data = {
            "role": "student",
            "email": "student1@example.com",
            "first_name": "Alice",
            "last_name": "Nguyen",
            "pg_first_name": "Jane",
            "pg_last_name": "Nguyen",
            "guardian_email": "parent@example.com",
            "school_name": "Sydney High",
            "year_lvl": "11",
            "area_of_interest": "Astrobiology"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertTrue(StudentProfile.objects.filter(user=user).exists())

    def test_register_mentor_success(self):
        # Make sure at least one Background exists
        bg = Background.objects.create(background_desc_unique_field="Physics")

        url = reverse("user-register")
        data = {
            "role": "mentor",
            "email": "mentor1@example.com",
            "first_name": "John",
            "last_name": "Smith",
            "background_id": bg.id,
            "institution": "USYD",
            "mentor_reason": "Support STEM education",
            "max_grp_cnt": 5
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertTrue(MentorProfile.objects.filter(user=user).exists())

    def test_register_supervisor_success(self):
        url = reverse("user-register")
        data = {
            "role": "supervisor",
            "email": "supervisor1@example.com",
            "first_name": "Mary",
            "last_name": "Brown",
            "supervisor_school_name": "Hale School"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertTrue(SupervisorProfile.objects.filter(user=user).exists())

class RegisterUserNegativeTest(APITestCase):
    def test_missing_role_field(self):
        url = reverse("user-register")
        data = {
            "email": "norole@example.com",
            "first_name": "No",
            "last_name": "Role"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)  # should complain about missing role

    def test_invalid_background_id_for_mentor(self):
        url = reverse("user-register")
        data = {
            "role": "mentor",
            "email": "badmentor@example.com",
            "first_name": "Bad",
            "last_name": "Mentor",
            "background_id": 999,  # invalid ID
            "institution": "USYD",
            "mentor_reason": "Testing invalid bg",
            "max_grp_cnt": 3
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("background_id", response.data)  # serializer should complain

    def test_invalid_role_value(self):
        url = reverse("user-register")
        data = {
            "role": "alien",  # not allowed
            "email": "alien@example.com",
            "first_name": "ET",
            "last_name": "PhoneHome"
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
