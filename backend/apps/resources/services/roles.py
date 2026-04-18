from django.utils import timezone
from django.contrib.auth.models import Group
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.resources.models import Roles, RoleAssignmentHistory
import logging

logger = logging.getLogger(__name__)


def _ensure_group(slug: str) -> Group:
    """Ensure a Django auth Group exists with the given name (mirrors role slug)."""
    return Group.objects.get_or_create(name=slug)[0]


@transaction.atomic
def create_role(slug: str) -> Roles:
    """
    Creates a new role and corresponding Django group.

    Args:
        slug: Unique role slug (matches `roles.slug` in the target schema).

    Returns:
        Roles: The created role instance

    Raises:
        ValidationError: If role already exists or name is invalid
    """
    slug = (slug or "").strip()
    if not slug:
        raise ValidationError("Role slug cannot be empty.")

<<<<<<< Updated upstream
    if Roles.objects.filter(slug__iexact=slug).exists():
        raise ValidationError(f"Role '{slug}' already exists.")

    role = Roles.objects.create(slug=slug)
=======
  # Check if role already exists (case-insensitive)
  if Roles.objects.filter(slug__iexact=role_name).exists():
    raise ValidationError(f"Role '{role_name}' already exists.")

  # Create the role
  role = Roles.objects.create(slug=role_name)
>>>>>>> Stashed changes

    _ensure_group(slug)

    logger.info(f"Created new role: {slug} (ID: {role.id})")
    return role


@transaction.atomic
def grant_role(user, role: Roles, start=None, revoke_others=True, force=False):
<<<<<<< Updated upstream
    """
    Grants a role to a user, with duplicate role handling and optionally revoking other active roles.

    Args:
        user (User): the user to grant the role
        role (Roles): the role object in our business domain
        start (dateTime): the start of the new role. defaults to Now
        revoke_others (bool): if True, revokes all other active roles. if False, allows multiple roles.
        force (bool): if True, bypasses duplicate role checks and forces assignment
    Returns:
        dict: Information about what was done
    """
    start = start or timezone.now()

    current_active_roles = RoleAssignmentHistory.objects.filter(
        user=user,
        valid_to__isnull=True,
    )

    existing_same_role = current_active_roles.filter(role=role)

    result = {
        "granted_role": role.slug,
        "revoked_roles": [],
        "had_existing": current_active_roles.exists(),
        "duplicate_role": existing_same_role.exists(),
        "action_taken": None,
    }

    if existing_same_role.exists() and not force:
        existing_same_role.update(valid_to=start)
        result["action_taken"] = "updated_existing_role"
        result["message"] = f"Updated existing {role.slug} role assignment (extended duration)"
        return result

    if revoke_others:
        other_assignments = current_active_roles.exclude(role=role)

        for assignment in other_assignments:
            result["revoked_roles"].append(assignment.role.slug)
            assignment.valid_to = start
            assignment.save()

            try:
                group = Group.objects.get(name=assignment.role.slug)
                user.groups.remove(group)
            except Group.DoesNotExist:
                pass
    else:
        RoleAssignmentHistory.objects.filter(
            user=user,
            role=role,
            valid_to__isnull=True,
        ).update(valid_to=start)

    RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=start)

    group = _ensure_group(role.slug)
    user.groups.add(group)

    result["action_taken"] = "created_new_role"
    result["message"] = f"Granted new {role.slug} role"

    return result
=======
  """
  Grants a role to a user, with duplicate role handling and optionally revoking other active roles.
  
  Args:
    user (User): the user to grant the role
    role (Roles): the role object in our business domain
    start (dateTime): the start of the new role. defaults to Now
    revoke_others (bool): if True, revokes all other active roles. if False, allows multiple roles.
    force (bool): if True, bypasses duplicate role checks and forces assignment
  Returns:
    dict: Information about what was done
  """
  start = start or timezone.now()
  
  # Get current active roles before changes
  current_active_roles = RoleAssignmentHistory.objects.filter(
      user=user, 
      valid_to__isnull=True
        # ).values_list('role__role_name', flat=True)
  )
  
  # Check if user already has this exact role active
  existing_same_role = current_active_roles.filter(role=role)
  
  result = {
      'granted_role': role.slug,
      'revoked_roles': [],
      'had_existing': current_active_roles.exists(),
      'duplicate_role': existing_same_role.exists(),
      'action_taken': None
  }
  
  if existing_same_role.exists() and not force:
    # User already has this role - update the valid_to date instead of creating duplicate
    existing_same_role.update(valid_to=start)
    result['action_taken'] = 'updated_existing_role'
    result['message'] = f"Updated existing {role.slug} role assignment (extended duration)"
    return result
  
  if revoke_others:
        # Revoke ALL other active roles (not just the same role)
    # active_assignments = RoleAssignmentHistory.objects.filter(
    #     user=user, 
    #     valid_to__isnull=True
    # ).exclude(role=role)
    # Revoke ALL other active roles
    other_assignments = current_active_roles.exclude(role=role)
    
    for assignment in other_assignments:
        result['revoked_roles'].append(assignment.role.slug)
        # Close the role assignment
        assignment.valid_to = start
        assignment.save()
        
        # Remove from Django groups
        try:
            group = Group.objects.get(name=assignment.role.slug)
            user.groups.remove(group)
        except Group.DoesNotExist:
            pass
  else:
    # Only close the same role if it exists
    RoleAssignmentHistory.objects.filter(
        user=user, 
        role=role, 
        valid_to__isnull=True
    ).update(valid_to=start)

  # Create new role assignment
  RoleAssignmentHistory.objects.create(user=user, role=role, valid_from=start)
  
  # Add to Django group
  group = _ensure_group(role.slug)
  user.groups.add(group)
  
  result['action_taken'] = 'created_new_role'
  result['message'] = f"Granted new {role.slug} role"
  
  return result
>>>>>>> Stashed changes


@transaction.atomic
def revoke_role(user, role: Roles, end=None):
<<<<<<< Updated upstream
=======
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
    group = Group.objects.get(name=role.slug)
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
          default_role = Roles.objects.get(slug='basic_user')
          grant_role(user, default_role, start=end)
      except Roles.DoesNotExist:
          # Log this situation as it indicates a configuration issue
          logger.error(f"Default role 'basic_user' not found when revoking role for user {user.id}")

def ensure_user_has_role(user): ##JUST FOR DEFAULT ROLES =====> JUST AN ADDITIONAL FUNCTION 
>>>>>>> Stashed changes
    """
    Revokes a specific role from a user.
    """
    end = end or timezone.now()

    RoleAssignmentHistory.objects.filter(
        user=user,
        role=role,
        valid_to__isnull=True,
    ).update(valid_to=end)

    try:
        group = Group.objects.get(name=role.slug)
        user.groups.remove(group)
    except Group.DoesNotExist:
        pass

    has_other_roles = RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=end,
        valid_to__isnull=True,
    ).exclude(role=role).exists()

    if not has_other_roles:
        try:
            default_role = Roles.objects.get(slug="basic_user")
            grant_role(user, default_role, start=end)
        except Roles.DoesNotExist:
            logger.error(f"Default role 'basic_user' not found when revoking role for user {user.id}")


def ensure_user_has_role(user):
    """Ensures user always has some role assigned."""
    now = timezone.now()
    has_active_role = RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now,
        valid_to__isnull=True,
    ).exists()

    if not has_active_role:
<<<<<<< Updated upstream
        default_role = Roles.objects.get(slug="basic_user")
        grant_role(user, default_role, start=now)
=======
        default_role = Roles.objects.get(slug='basic_user')  # Setting to default role 


>>>>>>> Stashed changes
