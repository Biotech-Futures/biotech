from django.core.management.base import BaseCommand
from apps.groups.models import Countries
from apps.groups.management.resources.get_countries import countriesMap
from django.db import transaction

class Command(BaseCommand):
  help = "Auto import a list of countries into the Countries table"

  def handle(self, *args, **kwargs):
    created = 0
    updated = 0
    
    with transaction.atomic():
      for country, short in countriesMap.items():
        _, was_created = Countries.objects.update_or_create(country_name=country, 
                                                        defaults={"country_name_SHORT_FORM": short})
        if was_created:
          created += 1
        else:
          updated += 1
      self.stdout.write(self.style.SUCCESS(f"{created} new countries synced to DB, {updated} countries updated."))