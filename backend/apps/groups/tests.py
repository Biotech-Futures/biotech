from django.test import TestCase
from datetime import date, datetime
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.apps import apps as dj_apps

from .models import Countries

# Create your tests here.


class CountriesApiTests(TestCase):
    

    def setUp(self):
        self.client = APIClient()
        self.list_url = reverse('countries-list')
        self.admin_user = get_user_model().objects.create_user(
            email="myemail1@gmail.com", password='adminpass', is_staff=True
        )
        self.normal_user = get_user_model().objects.create_user(
            email="myemail2@gmail.com", password='userpass', is_staff=False
        )
        self.country1 = Countries.objects.create(country_name='Australia')
        self.country2 = Countries.objects.create(country_name='Brazil')

    def test_list_countries_anyone(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertIn('Australia', [c['country_name'] for c in response.data])

    def test_retrieve_country_anyone(self):
        url = reverse('countries-detail', args=[self.country1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['country_name'], 'Australia')

    def test_create_country_admin_only(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.list_url, {'country_name': 'Global'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Countries.objects.filter(
            country_name='Global').exists())

    def test_create_country_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(self.list_url, {'country_name': 'RANDOM_COUNTRY'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Countries.objects.filter(
            country_name='RANDOM_COUNTRY').exists())

    def test_create_country_unauthenticated_forbidden(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.list_url, {'country_name': 'Japan'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Countries.objects.filter(
            country_name='Japan').exists())
