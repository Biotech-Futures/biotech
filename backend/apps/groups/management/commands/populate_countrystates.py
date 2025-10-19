from django.core.management.base import BaseCommand
from django.core.management import call_command
from apps.groups.models import Countries, CountryStates
from apps.groups.management.resources.get_countrystates import statesMap
from apps.groups.management.commands import populate_countries
from django.db import transaction

class Command(BaseCommand):
  help = "Auto import supported States into the CountryStates table"

  def handle(self, *args, **kwargs):
    total_created = 0
    total_updated = 0

    # run populate countries first
    call_command('populate_countries')
    
    with transaction.atomic():
      for country_name, states in statesMap.items():
        country = Countries.objects.filter(country_name=country_name).first()
        if not country:
          self.stdout.write(self.style.WARNING(f"Skipping {country_name}: country not found"))
          continue
        created = 0
        updated = 0
        for state, short_name in states.items():
          _, was_created = CountryStates.objects.update_or_create(country=country, state_name=state, defaults={"state_name_SHORT_FORM": short_name})
          if was_created:
            created += 1
            total_created += 1
          else:
            updated += 1
            total_updated += 1
        self.stdout.write(self.style.SUCCESS(
                    f"{country_name}: {created} states created, {updated} states updated"
                ))
      self.stdout.write(self.style.SUCCESS(
            f"Total: {total_created} created, {total_updated} updated"
        ))
        