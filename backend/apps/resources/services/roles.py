from django.utils import timezone
from django.contrib.auth.models import Group
from django.db import transaction
from apps.resources.models import Roles, RoleAssignmentHistory

# ===============================RBAC ROLES DJANGO GROUP FUNCTIONS===============================
def _ensure_group(role_name: str) -> Group:
  """
  ensures there exists a Django group with given role name.
  Args:
    role_name (str): The name of the role/group to ensure exists.
  Returns:
    Group: The Django Group instance corresponding to the given role name.
  """
  return Group.objects.get_or_create(name=role_name)[0]

@transaction.atomic
def grant_role(user, role: Roles, start=None):
  """
  closes off an existing role and adds a new one to history, then adds to group
  Args:
    user (User): the user to grant the role
    role (Roles): the role object in our business domain
    start (dateTime): the start of the new role. defaults to Now
  Returns:
    None
  """
  start = start or timezone.now()

  # if there an a same role, close open interval
  RoleAssignmentHistory.objects.filter(user=user, role=role, valid_to__isnull=True).update(valid_to=start)

  # then open a new role interval for tracking
  RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=start)
  
  # finally get or create and add to django perm group.
  group = _ensure_group(role.role_name)
  user.groups.add(group)


@transaction.atomic
def revoke_role(user, role: Roles, end=None):
  """
  Revokes a specific role from a user.

  This function updates the role assignment history to set the end date (`valid_to`) for the given role,
  effectively marking the role as revoked. It also removes the corresponding Django group from the user.

  Args:
    user (User): The user from whom the role will be revoked.
    role (Roles): The role to revoke.
    end (datetime, optional): The end date for the role assignment. Defaults to current time.

  Raises:
    None. If the group does not exist, the exception is silently ignored.
  """
  end = end or timezone.now()

  # find the record of the role and close it
  RoleAssignmentHistory.objects.filter(
      user=user, 
      role=role,
      valid_to__isnull=True
  ).update(valid_to=end)

  # remove the group record 
  try: 
    group = Group.objects.get(name=role.role_name)
    user.groups.remove(group)
  except Group.DoesNotExist:
    pass
  
  # Check if user has any other active roles
  has_other_roles = RoleAssignmentHistory.objects.filter(
      user=user,
      valid_from__lte=end,
      valid_to__isnull=True
  ).exclude(role=role).exists()
  
  if not has_other_roles:
      # Assign default role
      try:
          default_role = Roles.objects.get(role_name='basic_user')
          grant_role(user, default_role, start=end)
      except Roles.DoesNotExist:
          # Log this situation as it indicates a configuration issue
          logger.error(f"Default role 'basic_user' not found when revoking role for user {user.id}")

def ensure_user_has_role(user): ##JUST FOR DEFAULT ROLES =====> JUST AN ADDITIONAL FUNCTION 
    """
    Ensures user always has some role assigned
    """
    now = timezone.now()
    has_active_role = RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now,
        valid_to__isnull=True
    ).exists()
    
    if not has_active_role:
        default_role = Roles.objects.get(role_name='basic_user')  # Setting to default role 


