from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction

from apps.groups.models import Countries, CountryStates, Tracks

class Command(BaseCommand):
    help = "Populate supported Tracks (AUS-<STATE>, BRA, GLO) based on existing Countries and CountryStates."

    def handle(self, *args, **kwargs):
        # Ensure prerequisite data exists
        call_command("populate_countries")
        call_command("populate_countrystates")

        total_created = 0
        total_updated = 0

        with transaction.atomic():
            # Australia: one track per state using short form (e.g., AUS-NSW)
            au = Countries.objects.filter(
                country_name__iexact="Australia").first()
            if not au:
                self.stdout.write(self.style.WARNING(
                    "Australia not found; skipping AUS-* tracks."))
            else:
                au_created = 0
                au_updated = 0
                au_states = CountryStates.objects.filter(country=au)
                for state in au_states:
                    short = (state.state_name_SHORT_FORM or "").strip().upper()
                    if not short:
                        # Fallback to upper of state_name if short missing
                        short = (state.state_name or "").strip().upper()
                    track_name = f"AUS-{short}"
                    _, was_created = Tracks.objects.update_or_create(
                        track_name=track_name,
                        defaults={"state": state},
                    )
                    if was_created:
                        au_created += 1
                        total_created += 1
                    else:
                        au_updated += 1
                        total_updated += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Australia: {au_created} tracks created, {au_updated} tracks updated"
                ))

            # Brazil: single track 'BRA' anchored to any Brazil state (prefer 'Distrito Federal')
            br = Countries.objects.filter(
                country_name__iexact="Brazil").first()
            if not br:
                self.stdout.write(self.style.WARNING(
                    "Brazil not found; skipping BRA track."))
            else:
                br_state = (
                    CountryStates.objects.filter(
                        country=br, state_name__iexact="Distrito Federal").first()
                    or CountryStates.objects.filter(country=br).first()
                )
                if not br_state:
                    self.stdout.write(self.style.WARNING(
                        "No states for Brazil; skipping BRA track."))
                else:
                    _, was_created = Tracks.objects.update_or_create(
                        track_name="BRA",
                        defaults={"state": br_state},
                    )
                    if was_created:
                        total_created += 1
                        self.stdout.write(self.style.SUCCESS(
                            "Brazil: 1 track created"))
                    else:
                        total_updated += 1
                        self.stdout.write(self.style.SUCCESS(
                            "Brazil: 1 track ensured/updated"))

            # Global: single track 'GLO' anchored to any non-Australia/Brazil state if available
            glo_state = (
                CountryStates.objects.exclude(country__country_name__in=[
                                              "Australia", "Brazil"]).first()
            )
            if not glo_state:
                self.stdout.write(
                    self.style.WARNING(
                        "No non-Australia/Brazil states available; skipping GLO track.\n"
                        "To create GLO, add at least one CountryStates for a non-AU/BR country and re-run."
                    )
                )
            else:
                _, was_created = Tracks.objects.update_or_create(
                    track_name="GLO",
                    defaults={"state": glo_state},
                )
                if was_created:
                    total_created += 1
                    self.stdout.write(self.style.SUCCESS(
                        "Global: 1 track created (GLO)"))
                else:
                    total_updated += 1
                    self.stdout.write(self.style.SUCCESS(
                        "Global: 1 track ensured/updated (GLO)"))

        self.stdout.write(self.style.SUCCESS(
            f"Tracks sync completed. Total: {total_created} created, {total_updated} updated."
        ))
