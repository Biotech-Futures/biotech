from django.core.management.base import BaseCommand
from apps.groups.models import Countries
from apps.groups.management.resources.get_countries import countriesList

class Command(BaseCommand):
  help = "Auto import a list of countries into the Countries table"

  def handle(self, *args, **kwargs):
    synced_count = 0
    for country in countriesList:
      obj, created = Countries.objects.get_or_create(country_name=country)
      if created:
        synced_count += 1
    self.stdout.write(self.style.SUCCESS(f"{synced_count} new countries synced to DB."))