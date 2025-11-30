"""
Shared service which creates a user object given the required data.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import MultipleObjectsReturned, BadRequest
from django.db import transaction, IntegrityError
from apps.users.models import User, StudentProfile, StudentInterest, AreasOfInterest, SupervisorProfile, RelationshipType, StudentSupervisor, MentorProfile, Background
from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers, generics, permissions, status
from apps.resources.models import Roles, RoleAssignmentHistory
from apps.groups.models import Tracks, Countries, CountryStates
from apps.users.serializers import UserSerializer, UserStatusPatchSerializer
from typing import Dict, Any, Tuple
from apps.groups.services.get_track import *
from django.utils.text import Truncator
import re
import logging
logger = logging.getLogger(__name__)


class UserCreationError(Exception):
  """Base class for user creation errors"""

class InvalidInputError(UserCreationError):
  pass

class UserAlreadyExists(UserCreationError):
  pass

class NonExistentSupervisorError(UserCreationError):
  def __init__(self, supervisor_email: str):
    super().__init__(f"Supervisor '{supervisor_email}' not found in records, aborting student profile creation.") # i believe user rows are still created, just not profiles

# put more error classes in here


def get_relationship_type(supervisor_email: str, guardian_email: str) -> Tuple[RelationshipType, bool]:
  """
  Gets the relationship type
  Args: 
  Returns:
  """
  #TODO: cbbs writing the docs
  supervisor_email = (supervisor_email or "").strip().lower()
  guardian_email = (guardian_email or "").strip().lower()
  if not supervisor_email:
    raise InvalidInputError("Supervisor email must be provided")
  if not guardian_email:
    rel, _ = RelationshipType.objects.get_or_create(relationship_type="Supervisor")
    return rel, False
  if guardian_email == supervisor_email:
    rel, rel_created = RelationshipType.objects.get_or_create(relationship_type="Guardian") #maybe this informs the parent_guardian_flag?
    return rel, True
  else:
    rel, rel_created = RelationshipType.objects.get_or_create(relationship_type="Supervisor")
    return rel, False



def get_supervisor_profile_by_email(email: str) -> SupervisorProfile:
    """
    Resolve a supervisor profile by the supervisor's email on associated user row
    Raises:
      InvalidInputError if email missing/invalid
      NonExistentSupervisorError if no profile found
      InvalidInputError if multiple profiles found (should not happen if email is unique)
    """
    email_norm = (email or "").strip().lower()
    if not email_norm or "@" not in email_norm:
        raise InvalidInputError("Valid supervisor_email is required.")

    try:
        return SupervisorProfile.objects.select_related("user").get(user__email__iexact=email_norm)
    except SupervisorProfile.DoesNotExist:
        raise NonExistentSupervisorError(email_norm)
    except MultipleObjectsReturned:
        raise InvalidInputError(f"Multiple supervisor profiles found for '{email_norm}'")


def register_user(payload: Dict[str, Any], user_type: str) -> Tuple[User, Any]:
  """
  Creates or fetches a user based on input payload.
  Required: email
  Optional: first_name, last_name, country, region, supervisor*, guardian*, interests, school_name, year_level
  user_type (str): The type of user being made: can be "student", "mentor", "supervisor"
  Returns: (user, user_profile) where user_profile is the created/linked profile for the user type.
  """
  {
    "email"
  }
  user_type_raw = (user_type or "").strip().lower();
  if not user_type_raw:
    raise InvalidInputError("User type is required.")
  email = (payload.get('email') or "").strip().lower()
  first_name = (payload.get('first_name') or "").strip().lower().title()
  last_name = (payload.get('last_name') or "").strip().lower().title()
  if not email:
    raise InvalidInputError("Email is required.")
  if not first_name:
    raise InvalidInputError("First name is required.")
  if not last_name:
    raise InvalidInputError("Last name is required.")
  country_name = (payload.get('country_name') or "").strip().lower().title()
  if not country_name:
    raise InvalidInputError("Country name is required.")
  region_name = (payload.get('region_name') or "").strip().lower().title()
  if not region_name:
    raise InvalidInputError("Region name is required.")

  track = None
  state = None
  country = None
  try:
    country = get_supported_country(country_name)
    track = get_supported_track(country_name, region_name)
    state = getattr(track, "state", None) or get_supported_countryState(country_name, region_name)
  except TrackResolutionError as e:
    raise InvalidInputError(str(e))


  User = get_user_model()
  track_state_keyword_args: Dict[str, Any] = {}
  if track:
    track_state_keyword_args["track"] = track
  if state:
    track_state_keyword_args["state"] = state
  user_profile = None
  try:
    with transaction.atomic():
      new_user = User.objects.create(email=email,
                          first_name=first_name,
                          last_name=last_name, 
                          **track_state_keyword_args)
      if user_type_raw == "student":
        student_profile, created = create_student_profile(new_user, payload) 
        user_profile = student_profile

      elif user_type_raw == "supervisor":
        supervisor_profile, created = create_supervisor_profile(new_user, payload)
        user_profile = supervisor_profile
      elif user_type_raw == "mentor":
        mentor_profile, created = create_mentor_profile(new_user, payload)
        user_profile = mentor_profile
      else:
        raise InvalidInputError(f"Unsupported user_type: '{user_type_raw}'")
  except IntegrityError:
    raise UserAlreadyExists(f"User with email '{email}' already exists.")

  # Return the created user and the associated profile (if any)
  return new_user, user_profile
  
  
def create_student_profile(user: User, payload: Dict[str, Any]) -> Tuple[StudentProfile, bool]:
  """
  Creates the appropriate student profile for a student user.

  Args:
    payload (Dict[str, Any]): {
      'pg_first_name': str,
      'pg_last_name': str,
      'supervisor_email': str,
      'interest': str,
      'school_name': str,
      'year_level': str
    }

  Returns:
    studentProfile (StudentProfile): The student profile
    created (bool): if profile was created

  Raises:
    InvalidInputError: If required fields are missing or invalid.
  """

  pg_first_name = (payload.get('pg_first_name') or "").strip()
  pg_last_name = (payload.get('pg_last_name') or "").strip()
  guardian_email = (payload.get('guardian_email') or "").strip().lower()
  supervisor_email = (payload.get('supervisor_email') or "").strip().lower()
  interest_value = (payload.get('interest') or "").strip()  
  school_name = (payload.get('school_name') or "").strip()
  year_level_value = payload.get('year_level')

  pg_first_name = pg_first_name.lower().title() if pg_first_name else ""
  pg_last_name = pg_last_name.lower().title() if pg_last_name else ""

  if not pg_first_name or not pg_last_name:
    raise InvalidInputError("Parent/guardian details required to create student profile.")

  if supervisor_email and '@' not in supervisor_email:
    raise InvalidInputError("Invalid supervisor email.")

  if not interest_value:
    raise InvalidInputError("Interests needed for a student profile.")
  interest_value = interest_value.title()
  interest = AreasOfInterest.objects.filter(interest_desc__iexact=interest_value).first()
  if not interest:
    interest = AreasOfInterest.objects.create(interest_desc=interest_value) #TODO: cant be bothered, but StudentInterest M2M table is kind of created weirdly. We have the StudentProfile having a singular "interest" field, which is an interest from AreasOfInterest, but there is a M2M table for StudentInterest? who even uses this. anyway, we only support a single interest here unfortunately. low prio

  if not school_name:
    raise InvalidInputError("School name is required.")
  if year_level_value is None or str(year_level_value).strip() == "":
    raise InvalidInputError("Year level is required.")
  try:
    year_level = int(str(year_level_value).strip())
  except (TypeError, ValueError):
    raise InvalidInputError("Year level must be an integer.")
  if year_level < 0:
    raise InvalidInputError("Year level must be non-negative.")

  # get or create supervisor profile
  try:
    supervisor_profile = get_supervisor_profile_by_email(supervisor_email)
  except NonExistentSupervisorError:
    # Automatically create a supervisor user and profile when not present
    logger.info("Supervisor '%s' not found; creating new supervisor user and profile.", supervisor_email)
    User = get_user_model()
    # Derive a reasonable first/last name if not provided in payload
    sup_first_name = (payload.get('supervisor_first_name') or "").strip()
    sup_last_name = (payload.get('supervisor_last_name') or "").strip()
    if not sup_first_name or not sup_last_name:
      raise InvalidInputError(f"Attempted to create a new supervisor from student registration, however name details were missing - first name: {sup_first_name}, last name: {sup_last_name}")

    country_name = (payload.get('country_name') or "").strip().lower().title()
    if not country_name:
      raise InvalidInputError("Country name is required.")
    region_name = (payload.get('region_name') or "").strip().lower().title()
    if not region_name:
      raise InvalidInputError("Region name is required.")
    track = None
    state = None
    try:
      track = get_supported_track(country_name, region_name)
      state = getattr(track, "state", None) or get_supported_countryState(country_name, region_name)
    except TrackResolutionError as e:
      raise InvalidInputError(str(e))
    track_state_keyword_args: Dict[str, Any] = {}
    if track:
      track_state_keyword_args["track"] = track
    if state:
      track_state_keyword_args["state"] = state

    # get or create the sueprvisor
    try:
      sup_user, created_user = User.objects.get_or_create(
        email=supervisor_email,
        defaults={
          "first_name": sup_first_name,
          "last_name": sup_last_name,
          **track_state_keyword_args,
        },
      )
    except IntegrityError:
      # edge case if user was created concurrently
      sup_user = User.objects.filter(email__iexact=supervisor_email).first()
      if not sup_user:
        raise InvalidInputError(f"Failed to resolve supervisor user '{supervisor_email}' after concurrency retry.")

    # ensure supervisor exists
    supervisor_profile, _ = create_supervisor_profile(sup_user, payload)
  
  rel_type = None
  parent_is_guardian = False
  try:
    rel_type, parent_is_guardian = get_relationship_type(supervisor_email, guardian_email)
  except Exception as e:
    raise InvalidInputError(f"Could not resolve studentsupervisor relationship type: {e}")
    
  
  
  student_profile_creation_args = {
    "pg_first_name": pg_first_name or None,
    "pg_last_name": pg_last_name or None,
    "parent_guardian_flag": parent_is_guardian, 
    "supervisor": supervisor_profile,
    "interest": interest,
    "school_name": school_name,
    "year_lvl": year_level_value, #chose to use the string instead of the converted int because the field is a charfield in the model
    #TODO: implement has_join_permission and joinperm_responseID
  }

  student_profile = created = None
  try:
    with transaction.atomic():
      student_profile, created = StudentProfile.objects.get_or_create(user=user, defaults=student_profile_creation_args)
      ss, ss_created = StudentSupervisor.objects.get_or_create(student_user=student_profile, supervisor_user=supervisor_profile, defaults={"relationship_type": rel_type})
      # if link exists but the rel type updates...
      if not ss_created and ss.relationship_type_id != rel_type.pk:
        ss.relationship_type = rel_type
        ss.save(update_fields=["relationship_type"])
      return student_profile, created
  except Exception as e:
    raise InvalidInputError(f"Failed to create student profile: {e}")


def create_supervisor_profile(user: User, payload: Dict[str, Any]) -> SupervisorProfile:
  """
  Creates supervisor profile
  Args:
    user (User): User object to be attached to a supervisor profile
    school_name (str): School name
  Returns:
    supervisor (SupervisorProfile): the profile of the supervisor
  """
  school_name = (payload.get("school_name") or "").strip()
  if not school_name:
    raise InvalidInputError("School name requried for supervisor") 
  school_name = school_name.title()
  supervisor_profile = created = None
  try:
    with transaction.atomic():
      supervisor, created = SupervisorProfile.objects.get_or_create(
        user=user,
        defaults={"school_name": school_name}
      )
      return supervisor, created
  except Exception as e:
    raise InvalidInputError(f"Failed to create supervisor profile: {e}")
  

def create_mentor_profile(user: User, payload: Dict[str, Any]) -> Tuple[MentorProfile, bool]:
  """
  Function which creates an associated mentor profile for a user
  Args:
    user (User): The associated user objects
    payload (Dict[str, any]): payload of information
  Returns:
    mentor_profile, created (Tuple[MentorProfile, bool]): The associated mentor profile and if one was created"""
  background_desc_raw = (payload.get('background') or "").strip()
  if not background_desc_raw:
    raise InvalidInputError("Background needed for mentor profile.")
  background_desc_raw = background_desc_raw.title()
  background = Background.objects.filter(background_desc_unique_field__iexact=background_desc_raw).first()
  if not background:
    background = Background.objects.create(background_desc_unique_field=background_desc_raw)
  
  institution_raw = (payload.get("institution") or "").strip()
  if not institution_raw:
    raise InvalidInputError("Instituiton needed for mentor profile")
  institution = Truncator(institution_raw).chars(254) # truncates with ... (ellipsis)

  mentor_reason_raw = (payload.get("mentor_reason") or "").strip()
  if not mentor_reason_raw:
    raise InvalidInputError("Mentor reason needed for mentor profile")
  mentor_reason = Truncator(mentor_reason_raw).chars(254) # truncates with ... (ellipsis)

  max_group_count = (payload.get("max_group_count") or None)
  if isinstance(max_group_count, str):
    try:
      max_group_count = int(max_group_count.strip())
    except ValueError:
      raise InvalidInputError(f"Max Group Count is an invalid value: {max_group_count}")
  
  mentor_profile_creation_args = {
    "background": background,
    "institution": institution,
    "mentor_reason": mentor_reason,
    "max_grp_cnt": max_group_count
  }

  mentor_profile = created = None
  try:
    with transaction.atomic():
      mentor_profile, created = MentorProfile.objects.get_or_create(user=user, defaults=mentor_profile_creation_args)
      return mentor_profile, created
  except Exception as e:
    raise InvalidInputError(f"Failed to create mentor profile: {e}")

  
  

