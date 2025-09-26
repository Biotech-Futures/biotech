# sync_role_groups.py
# This Django management command ensures that for every business role defined in the Roles model,
# there is a corresponding auth Group object. It loops through all role names in Roles,
# and uses get_or_create to make sure each role has a matching Group (avoiding duplicates).
# After syncing, it prints a success message to the console.from django.core.management.base import BaseCommand
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.resources.models import Roles

class Command(BaseCommand):
  help = "Ensure a Django auth Group exists for each Business Role (student, admin, supervisor, mentor)"

  def handle(self, *args, **kwargs):
    for role in Roles.objects.values_list('role_name', flat=True):
      Group.objects.get_or_create(name=role)
    self.stdout.write(self.style.SUCCESS("Role groups synced"))