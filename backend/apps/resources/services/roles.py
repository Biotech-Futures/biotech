from django.utils import timezone
from django.contrib.auth.models import Group
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.resources.models import Roles, RoleAssignmentHistory
import logging

logger = logging.getLogger(__name__)

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
def create_role(role_name: str) -> Roles:
  """
  Creates a new role and corresponding Django group.

  Args:
    role_name (str): Name of the role to create

  Returns:
    Roles: The created role instance

  Raises:
    ValidationError: If role already exists or name is invalid
  """
  # Validate role name
  role_name = (role_name or "").strip()
  if not role_name:
    raise ValidationError("Role name cannot be empty.")

  # Check if role already exists (case-insensitive)
  if Roles.objects.filter(role_name__iexact=role_name).exists():
    raise ValidationError(f"Role '{role_name}' already exists.")

  # Create the role
  role = Roles.objects.create(role_name=role_name)

  # Create corresponding Django group for permissions
  _ensure_group(role_name)

  logger.info(f"Created new role: {role_name} (ID: {role.id})")
  return role

@transaction.atomic
def grant_role(user, role: Roles, start=None, end=None, revoke_others=True, force=False):
  """
  Grants a role to a user, with duplicate role handling and optionally revoking other active roles.
  
  Args:
    user (User): the user to grant the role
    role (Roles): the role object in our business domain
    start (dateTime): the start of the new role. defaults to Now
    end (dateTime): the end of the new role. If None, role is indefinite (no expiration)
    revoke_others (bool): if True, revokes all other active roles. if False, allows multiple roles.
    force (bool): if True, bypasses duplicate role checks and forces assignment
  Returns:
    dict: Information about what was done
  """
  start = start or timezone.now()
  
  # Validate end date is after start date
  if end and end <= start:
    raise ValidationError(
      f"End date ({end}) must be after start date ({start}). "
      f"Cannot create a role that has already expired."
    )
  
  # Get current active roles before changes
  # Active = started AND (no end date OR end date in future)
  from django.db.models import Q
  now = timezone.now()
  current_active_roles = RoleAssignmentHistory.objects.filter(
      user=user,
      valid_from__lte=start  # Use the start parameter, not 'now', to check at grant time
  ).filter(
      Q(valid_to__isnull=True) | Q(valid_to__gt=start)  # Either indefinite OR expires after start
  )
  
  # Check if user already has this exact role active
  existing_same_role = current_active_roles.filter(role=role)
  
  result = {
      'granted_role': role.role_name,
      'revoked_roles': [],
      'had_existing': current_active_roles.exists(),
      'duplicate_role': existing_same_role.exists(),
      'action_taken': None,
      'replaced_role': False
  }
  
  # If user already has this exact role, close it (will be replaced with new assignment)
  if existing_same_role.exists() and not force:
    existing_same_role.update(valid_to=start)
    result['replaced_role'] = True
    result['action_taken'] = 'replaced_existing_role'
    # Continue to create new role assignment (don't return early!)
  
  if revoke_others:
        # Revoke ALL other active roles (not just the same role)
    # active_assignments = RoleAssignmentHistory.objects.filter(
    #     user=user, 
    #     valid_to__isnull=True
    # ).exclude(role=role)
    # Revoke ALL other active roles
    other_assignments = current_active_roles.exclude(role=role)
    
    for assignment in other_assignments:
        # Skip if the role was deleted
        if not assignment.role:
            # Still close the assignment
            assignment.valid_to = start
            assignment.save()
            continue
            
        result['revoked_roles'].append(assignment.role.role_name)
        # Close the role assignment
        assignment.valid_to = start
        assignment.save()
        
        # Remove from Django groups
        try:
            group = Group.objects.get(name=assignment.role.role_name)
            user.groups.remove(group)
        except Group.DoesNotExist:
            pass
  else:
    # Only close the same role if it exists and is still active
    RoleAssignmentHistory.objects.filter(
        user=user, 
        role=role,
        valid_from__lte=start
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gt=start)
    ).update(valid_to=start)

  # Create new role assignment with optional end date
  RoleAssignmentHistory.objects.create(
      user=user, 
      role=role, 
      valid_from=start,
      valid_to=end  # Can be None for indefinite roles
  )
  
  # Add to Django group
  group = _ensure_group(role.role_name)
  user.groups.add(group)
  
  # Set appropriate action if not already set
  if not result['action_taken']:
      result['action_taken'] = 'created_new_role'
  
  # Generate message based on what happened
  if result['replaced_role']:
      if end:
          result['message'] = f"Replaced {role.role_name} role - now valid from {start} to {end}"
      else:
          result['message'] = f"Replaced {role.role_name} role - now valid from {start} (indefinite)"
  else:
      if end:
          result['message'] = f"Granted {role.role_name} role from {start} to {end}"
      else:
          result['message'] = f"Granted {role.role_name} role from {start} (indefinite)"
  
  return result


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

  Returns:
    dict: Information about what was revoked

  Raises:
    None. If the group does not exist, the exception is silently ignored.
  """
  from django.db.models import Q
  end = end or timezone.now()

  # Find active assignments for this role and close them
  updated_count = RoleAssignmentHistory.objects.filter(
      user=user, 
      role=role,
      valid_from__lte=end
  ).filter(
      Q(valid_to__isnull=True) | Q(valid_to__gt=end)
  ).update(valid_to=end)

  # remove the group record 
  group_removed = False
  try: 
    group = Group.objects.get(name=role.role_name)
    user.groups.remove(group)
    group_removed = True
  except Group.DoesNotExist:
    logger.warning(f"Group '{role.role_name}' not found when revoking role for user {user.id}")
  
  # Check if user has any other active roles
  has_other_roles = RoleAssignmentHistory.objects.filter(
      user=user,
      valid_from__lte=end
  ).filter(
      Q(valid_to__isnull=True) | Q(valid_to__gt=end)
  ).exclude(role=role).exists()
  
  assigned_default = False
  if not has_other_roles:
      # Assign default role with 1 year duration
      try:
          from datetime import timedelta
          default_role = Roles.objects.get(role_name='basic_user')
          grant_role(user, default_role, start=end, end=end + timedelta(days=365))
          assigned_default = True
      except Roles.DoesNotExist:
          # Log this situation as it indicates a configuration issue
          logger.error(f"Default role 'basic_user' not found when revoking role for user {user.id}")
  
  return {
      'revoked_role': role.role_name,
      'updated_count': updated_count,
      'group_removed': group_removed,
      'assigned_default_role': assigned_default,
      'end_time': end
  }

def ensure_user_has_role(user, duration_days=365): 
    """
    Ensures user always has some role assigned.
    Used for assigning default 'basic_user' role.
    
    Args:
        user (User): The user to check/assign role
        duration_days (int): How long the default role should last (default 365 days)
    """
    from django.db.models import Q
    from datetime import timedelta
    now = timezone.now()
    has_active_role = RoleAssignmentHistory.objects.filter(
        user=user,
        valid_from__lte=now
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gt=now)
    ).exists()
    
    if not has_active_role:
        try:
            default_role = Roles.objects.get(role_name='basic_user')
            grant_role(user, default_role, start=now, end=now + timedelta(days=duration_days))
        except Roles.DoesNotExist:
            logger.error(f"Default role 'basic_user' not found for user {user.id}") 


