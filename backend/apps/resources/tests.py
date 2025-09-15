"""
COMPREHENSIVE TEST SUITE FOR ROLE ASSIGNMENT SERIALIZERS

This file contains unit tests for all serializers in the resources app,
specifically focusing on role assignment functionality with date validity.

Test Structure:
1. BaseTestCase - Sets up common test data used across all test classes
2. UserSerializerTest - Tests basic user data serialization
3. RoleSerializerTest - Tests role data serialization
4. RoleAssignmentHistorySerializerTest - Tests reading role assignments with nested data
5. RoleAssignmentCreateSerializerTest - Tests creating new role assignments with validation

Each test class inherits from BaseTestCase to get pre-created test objects.
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User
from .models import RoleAssignmentHistory, Roles
from apps.users.models import Users
from apps.groups.models import Tracks, CountryStates, Countries
from .serializers import (
    UserSerializer,
    RoleSerializer,
    RoleAssignmentHistorySerializer,
    RoleAssignmentCreateSerializer
)


class BaseTestCase(TestCase):
    """
    BASE TEST CASE CLASS

    This class sets up common test data that all other test classes need.
    It creates a complete hierarchy of related objects:
    Country -> State -> Track -> User, plus a Role object.

    This setup method runs before each individual test method,
    ensuring each test starts with fresh, consistent data.
    """
    def setUp(self):
        # Create geographical hierarchy (Country -> State)
        # This mimics the real application structure where users belong to states/countries
        self.country = Countries.objects.create(country_name="Test Country")
        self.state = CountryStates.objects.create(
            state_name="Test State",
            country=self.country
        )

        # Create a track (program/course) that belongs to the state
        # Tracks represent different mentoring programs in different locations
        self.track = Tracks.objects.create(
            track_name="Test Track",
            state=self.state
        )

        # Create a test user with all required relationships
        # This user will be used in role assignment tests
        self.user = Users.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@test.com",
            status=True,              # Active user
            track=self.track,         # Belongs to the test track
            state=self.state          # Lives in the test state
        )

        # Create a test role that can be assigned to users
        # This represents roles like "Mentor", "Admin", "Student", etc.
        self.role = Roles.objects.create(role_name="Test Role")


class UserSerializerTest(BaseTestCase):
    """
    USER SERIALIZER TESTS

    These tests verify that the UserSerializer correctly converts User model
    instances into JSON-serializable Python dictionaries.

    The UserSerializer is used when we need to display user information
    in API responses, particularly in nested serializers like RoleAssignmentHistory.
    """

    def test_user_serialization(self):
        """
        TEST: Basic user data serialization

        This test verifies that a User object is correctly converted to a dictionary
        with the expected field values. It checks that all the basic user information
        (id, names, email) is properly serialized.
        """
        # Create a serializer instance with our test user
        serializer = UserSerializer(self.user)
        # Get the serialized data (Python dictionary)
        data = serializer.data

        # Verify each field is correctly serialized
        self.assertEqual(data['id'], self.user.id)
        self.assertEqual(data['first_name'], 'John')
        self.assertEqual(data['last_name'], 'Doe')
        self.assertEqual(data['email'], 'john.doe@test.com')

    def test_user_serialization_fields(self):
        """
        TEST: Verify only expected fields are included

        This test ensures that the serializer only includes the fields we want
        and doesn't accidentally expose sensitive or unnecessary data like
        passwords, internal status flags, etc.
        """
        serializer = UserSerializer(self.user)
        data = serializer.data

        # Define exactly which fields should be present in the serialized data
        expected_fields = {'id', 'first_name', 'last_name', 'email'}
        # Verify that the serialized data contains exactly these fields, no more, no less
        self.assertEqual(set(data.keys()), expected_fields)

    def test_multiple_users_serialization(self):
        """
        TEST: Serializing multiple users at once

        This test verifies that the serializer works correctly when serializing
        a list of users (using many=True parameter). This is common when
        returning lists of users in API endpoints.
        """
        # Create a second test user with different data
        user2 = Users.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@test.com",
            status=False,  # Different status to test variety
            track=self.track,
            state=self.state
        )

        # Create a list of users and serialize them all at once
        users = [self.user, user2]
        serializer = UserSerializer(users, many=True)  # many=True enables list serialization
        data = serializer.data

        # Verify we get a list with the correct number of items
        self.assertEqual(len(data), 2)
        # Verify the data for each user is correct
        self.assertEqual(data[0]['first_name'], 'John')
        self.assertEqual(data[1]['first_name'], 'Jane')


class RoleSerializerTest(BaseTestCase):
    """
    ROLE SERIALIZER TESTS

    These tests verify that the RoleSerializer correctly converts Role model
    instances into JSON data. Roles represent different user types in the system
    like "Mentor", "Admin", "Student", etc.

    The RoleSerializer is used in API responses and nested within other serializers.
    """

    def test_role_serialization(self):
        """
        TEST: Basic role data serialization

        Verifies that a Role object is correctly converted to a dictionary
        with the expected id and role_name fields.
        """
        # Serialize the test role
        serializer = RoleSerializer(self.role)
        data = serializer.data

        # Verify the serialized data matches the original role
        self.assertEqual(data['id'], self.role.id)
        self.assertEqual(data['role_name'], 'Test Role')

    def test_role_serialization_fields(self):
        """
        TEST: Verify only expected fields are included

        Ensures the serializer only exposes the intended fields (id, role_name)
        and doesn't accidentally include internal or sensitive data.
        """
        serializer = RoleSerializer(self.role)
        data = serializer.data

        # Define the exact fields that should be present
        expected_fields = {'id', 'role_name'}
        # Verify no extra or missing fields
        self.assertEqual(set(data.keys()), expected_fields)

    def test_multiple_roles_serialization(self):
        """
        TEST: Serializing multiple roles at once

        Tests the serializer's ability to handle lists of roles,
        which is useful for API endpoints that return all available roles.
        """
        # Create a second role for testing
        role2 = Roles.objects.create(role_name="Admin Role")

        # Serialize multiple roles at once
        roles = [self.role, role2]
        serializer = RoleSerializer(roles, many=True)
        data = serializer.data

        # Verify we get correct data for both roles
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['role_name'], 'Test Role')
        self.assertEqual(data[1]['role_name'], 'Admin Role')


class RoleAssignmentHistorySerializerTest(BaseTestCase):
    """
    ROLE ASSIGNMENT HISTORY SERIALIZER TESTS

    These tests verify the RoleAssignmentHistorySerializer, which is used to
    READ existing role assignments. This serializer includes nested user and role
    data, and calculates whether the assignment is currently active.

    This serializer is used when displaying lists of role assignments,
    showing who has what roles and when those assignments are/were valid.
    """

    def setUp(self):
        """
        Set up test data specific to role assignment history tests.

        In addition to the base test data, this creates an actual role assignment
        that we can use to test the serializer behavior.
        """
        super().setUp()  # Get the base test data (user, role, etc.)

        # Create a timestamp for when the role assignment starts
        self.valid_from = timezone.now()

        # Create an active role assignment (valid_to=None means it's ongoing)
        self.role_assignment = RoleAssignmentHistory.objects.create(
            user=self.user,           # Assign the role to our test user
            role=self.role,           # Assign our test role
            valid_from=self.valid_from,  # Started now
            valid_to=None             # No end date = currently active
        )

    def test_role_assignment_serialization(self):
        """
        TEST: Basic role assignment serialization

        This test verifies that a RoleAssignmentHistory object is correctly
        serialized with all expected fields, including nested user and role data.
        """
        # Serialize the role assignment
        serializer = RoleAssignmentHistorySerializer(self.role_assignment)
        data = serializer.data

        # Verify basic fields are correct
        self.assertEqual(data['id'], self.role_assignment.id)

        # Verify nested user data is included and correct
        self.assertEqual(data['user']['id'], self.user.id)

        # Verify nested role data is included and correct
        self.assertEqual(data['role']['id'], self.role.id)

        # Verify the calculated 'is_active' field (should be True since valid_to is None)
        self.assertEqual(data['is_active'], True)

    def test_nested_user_and_role_serialization(self):
        """
        TEST: Nested serializer data inclusion

        This test specifically verifies that the nested UserSerializer and RoleSerializer
        are working correctly within the RoleAssignmentHistorySerializer.
        Instead of just getting user_id and role_id, we get full user and role objects.
        """
        serializer = RoleAssignmentHistorySerializer(self.role_assignment)
        data = serializer.data

        # Verify that nested objects are included (not just IDs)
        self.assertIn('user', data)
        self.assertIn('role', data)

        # Verify the nested user object contains detailed user information
        self.assertEqual(data['user']['first_name'], 'John')
        self.assertEqual(data['user']['last_name'], 'Doe')

        # Verify the nested role object contains detailed role information
        self.assertEqual(data['role']['role_name'], 'Test Role')

    def test_is_active_method_true(self):
        """
        TEST: is_active field calculation (True case)

        This tests the custom SerializerMethodField 'is_active'.
        When valid_to is None, it means the role assignment is ongoing/active.
        The get_is_active method should return True in this case.
        """
        serializer = RoleAssignmentHistorySerializer(self.role_assignment)
        data = serializer.data

        # Since our role assignment has valid_to=None, it should be active
        self.assertTrue(data['is_active'])

    def test_is_active_method_false(self):
        """
        TEST: is_active field calculation (False case)

        This tests the custom SerializerMethodField 'is_active' when the
        role assignment has an end date (valid_to is not None).
        When valid_to has a value, it means the role assignment has ended,
        so is_active should return False.
        """
        # Modify the role assignment to have an end date (making it inactive)
        self.role_assignment.valid_to = timezone.now() + timedelta(days=1)
        self.role_assignment.save()

        # Serialize the now-inactive role assignment
        serializer = RoleAssignmentHistorySerializer(self.role_assignment)
        data = serializer.data

        # Since valid_to is now set, the assignment should be considered inactive
        self.assertFalse(data['is_active'])

    def test_serialization_fields(self):
        """
        TEST: Verify all expected fields are present

        This test ensures that the serializer includes all the fields we expect
        and no unexpected ones. This is important for API consistency and security.

        Expected fields:
        - id: The unique identifier of the role assignment
        - user: Nested user object with user details
        - role: Nested role object with role details
        - valid_from: When the role assignment started
        - valid_to: When the role assignment ended (or None if ongoing)
        - is_active: Calculated field indicating if assignment is currently active
        """
        serializer = RoleAssignmentHistorySerializer(self.role_assignment)
        data = serializer.data

        # Define all fields that should be present in the serialized data
        expected_fields = {'id', 'user', 'role', 'valid_from', 'valid_to', 'is_active'}

        # Verify the serialized data contains exactly these fields
        self.assertEqual(set(data.keys()), expected_fields)


class RoleAssignmentCreateSerializerTest(BaseTestCase):
    """
    ROLE ASSIGNMENT CREATE SERIALIZER TESTS

    This is the most important test class as it tests the RoleAssignmentCreateSerializer,
    which is used to CREATE new role assignments via the POST API endpoint.

    This serializer includes extensive validation:
    - Validates that user_id and role_id exist in the database
    - Validates that valid_from is not in the past
    - Validates that valid_to is after valid_from (if provided)
    - Handles the creation of new RoleAssignmentHistory records

    These tests cover both successful creation and all possible validation failures.
    """

    def setUp(self):
        """
        Set up test data specific to role assignment creation tests.

        Creates future timestamps for testing date validation logic.
        We use future dates to avoid "past date" validation errors.
        """
        super().setUp()  # Get the base test data

        # Create timestamps in the future for valid test data
        # valid_from is 1 hour from now (future, so it should be valid)
        self.valid_from = timezone.now() + timedelta(hours=1)
        # valid_to is 30 days from now (well after valid_from)
        self.valid_to = timezone.now() + timedelta(days=30)

    def test_valid_serialization(self):
        """
        TEST: Valid data should pass validation

        This is the "happy path" test - when all data is correct,
        the serializer should validate successfully.
        This test uses valid user_id, role_id, and future timestamps.
        """
        # Create a dictionary of valid input data
        data = {
            'user_id': self.user.id,        # Valid user ID from setUp
            'role_id': self.role.id,        # Valid role ID from setUp
            'valid_from': self.valid_from,  # Future timestamp (valid)
            'valid_to': self.valid_to       # Future timestamp after valid_from
        }

        # Create serializer with the test data
        serializer = RoleAssignmentCreateSerializer(data=data)

        # Verify that the serializer considers this data valid
        self.assertTrue(serializer.is_valid())

    def test_create_role_assignment(self):
        """
        TEST: Successful creation of role assignment

        This test verifies that when valid data is provided, the serializer
        not only validates correctly but also creates the actual database record
        with the correct relationships and field values.
        """
        # Prepare valid input data
        data = {
            'user_id': self.user.id,
            'role_id': self.role.id,
            'valid_from': self.valid_from,
            'valid_to': self.valid_to
        }

        # Create and validate the serializer
        serializer = RoleAssignmentCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Save the serializer to create the actual database record
        role_assignment = serializer.save()

        # Verify the created record has correct relationships
        # Note: user_id becomes a User object, role_id becomes a Role object
        self.assertEqual(role_assignment.user, self.user)
        self.assertEqual(role_assignment.role, self.role)

        # Verify the timestamps are correctly stored
        self.assertEqual(role_assignment.valid_from, self.valid_from)
        self.assertEqual(role_assignment.valid_to, self.valid_to)

    def test_invalid_user_id(self):
        """
        TEST: Invalid user_id should fail validation

        This tests the custom validate_user_id method in the serializer.
        When a non-existent user_id is provided, the serializer should
        reject the data with a specific error message.
        """
        # Use a user ID that doesn't exist in the database
        data = {
            'user_id': 99999,              # Non-existent user ID
            'role_id': self.role.id,       # Valid role ID
            'valid_from': self.valid_from, # Valid timestamp
            'valid_to': self.valid_to      # Valid timestamp
        }

        serializer = RoleAssignmentCreateSerializer(data=data)

        # The serializer should reject this data
        self.assertFalse(serializer.is_valid())

        # Verify that the error is specifically for the user_id field
        self.assertIn('user_id', serializer.errors)

        # Verify the exact error message matches what we expect
        self.assertEqual(str(serializer.errors['user_id'][0]), "User does not exist")

    def test_invalid_role_id(self):
        """
        TEST: Invalid role_id should fail validation

        This tests the custom validate_role_id method in the serializer.
        When a non-existent role_id is provided, the serializer should
        reject the data with a specific error message.
        """
        # Use a role ID that doesn't exist in the database
        data = {
            'user_id': self.user.id,       # Valid user ID
            'role_id': 99999,              # Non-existent role ID
            'valid_from': self.valid_from, # Valid timestamp
            'valid_to': self.valid_to      # Valid timestamp
        }

        serializer = RoleAssignmentCreateSerializer(data=data)

        # The serializer should reject this data
        self.assertFalse(serializer.is_valid())

        # Verify that the error is specifically for the role_id field
        self.assertIn('role_id', serializer.errors)

        # Verify the exact error message matches what we expect
        self.assertEqual(str(serializer.errors['role_id'][0]), "Role does not exist")

    def test_past_valid_from_date(self):
        """
        TEST: Past valid_from date should fail validation

        This tests the custom validate method that prevents creating role assignments
        that supposedly started in the past. This business rule ensures that all
        role assignments are created for current or future dates only.
        """
        # Create a timestamp in the past (1 hour ago)
        past_date = timezone.now() - timedelta(hours=1)

        data = {
            'user_id': self.user.id,
            'role_id': self.role.id,
            'valid_from': past_date,      # Past timestamp (invalid)
            'valid_to': self.valid_to     # Future timestamp (valid)
        }

        serializer = RoleAssignmentCreateSerializer(data=data)

        # The serializer should reject this data
        self.assertFalse(serializer.is_valid())

        # Date validation errors appear in 'non_field_errors' because they
        # involve multiple fields or overall object validation
        self.assertIn('non_field_errors', serializer.errors)

        # Verify the specific error message
        self.assertEqual(str(serializer.errors['non_field_errors'][0]), "valid_from cannot be in the past")

    def test_valid_to_before_valid_from(self):
        """
        TEST: valid_to before valid_from should fail validation

        This tests the logical validation that an end date (valid_to) must be
        after the start date (valid_from). A role assignment cannot end before
        it begins - this would be logically impossible.
        """
        data = {
            'user_id': self.user.id,
            'role_id': self.role.id,
            'valid_from': self.valid_from,                    # Future start date
            'valid_to': self.valid_from - timedelta(hours=1) # End date BEFORE start date
        }

        serializer = RoleAssignmentCreateSerializer(data=data)

        # This should fail validation due to impossible date logic
        self.assertFalse(serializer.is_valid())

        # Date range validation errors appear in 'non_field_errors'
        self.assertIn('non_field_errors', serializer.errors)

        # Verify the specific error message for this validation rule
        self.assertEqual(str(serializer.errors['non_field_errors'][0]), "valid_to must be after valid_from")

    def test_valid_to_equal_valid_from(self):
        """
        TEST: valid_to equal to valid_from should fail validation

        This tests the edge case where the end date equals the start date.
        Our business logic requires that valid_to must be AFTER valid_from,
        not equal to it. A role assignment that starts and ends at the same
        moment would have zero duration, which doesn't make business sense.
        """
        data = {
            'user_id': self.user.id,
            'role_id': self.role.id,
            'valid_from': self.valid_from,  # Start date
            'valid_to': self.valid_from     # End date SAME as start date
        }

        serializer = RoleAssignmentCreateSerializer(data=data)

        # This should fail because valid_to must be AFTER (not equal to) valid_from
        self.assertFalse(serializer.is_valid())

        # Verify the error appears in the correct location
        self.assertIn('non_field_errors', serializer.errors)

        # Verify we get the same error message as the "before" case
        # because the validation logic is "valid_to must be after valid_from"
        self.assertEqual(str(serializer.errors['non_field_errors'][0]), "valid_to must be after valid_from")

    def test_optional_valid_to(self):
        """
        TEST: valid_to field should be optional

        This tests that role assignments can be created without an end date
        (valid_to=None), which represents ongoing/permanent role assignments.
        This is a common use case - many role assignments don't have predetermined
        end dates.
        """
        # Create data without the valid_to field
        data = {
            'user_id': self.user.id,
            'role_id': self.role.id,
            'valid_from': self.valid_from  # Only start date, no end date
        }

        serializer = RoleAssignmentCreateSerializer(data=data)

        # This should be valid - valid_to is optional
        self.assertTrue(serializer.is_valid())

        # Create the actual role assignment
        role_assignment = serializer.save()

        # Verify that valid_to is None (indicating an ongoing assignment)
        self.assertIsNone(role_assignment.valid_to)

    def test_serialization_fields(self):
        """
        TEST: Verify expected fields in validated data

        This test ensures that after validation, the serializer's validated_data
        contains exactly the fields we expect. This is important for security
        and consistency - we want to make sure no unexpected fields are accepted
        and no expected fields are missing.
        """
        # Create complete test data with all fields
        data = {
            'user_id': self.user.id,
            'role_id': self.role.id,
            'valid_from': self.valid_from,
            'valid_to': self.valid_to
        }

        serializer = RoleAssignmentCreateSerializer(data=data)

        # Validate the data first
        self.assertTrue(serializer.is_valid())

        # Define exactly which fields should be in the validated data
        expected_fields = {'user_id', 'role_id', 'valid_from', 'valid_to'}

        # Verify that validated_data contains exactly these fields
        # This ensures the serializer doesn't accept extra fields or lose expected ones
        self.assertEqual(set(serializer.validated_data.keys()), expected_fields)
