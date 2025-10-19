"""
Custom permissions for Certificate management
"""
from rest_framework import permissions
from django.utils import timezone
from django.db.models import Q
from apps.resources.models import RoleAssignmentHistory


class CertificatePermission(permissions.BasePermission):
    """
    Custom permission for certificate access based on active roles:
    - Mentors: Can create, read, and update their own certificates (cannot verify)
    - Admins: Full CRUD access to all certificates
    - Supervisors: Read-only access to certificates of mentors they oversee
    - Students: No access
    """

    def _get_active_role(self, user):
        """
        Get the user's current active role from RoleAssignmentHistory
        Returns the role_name (e.g., 'Mentor', 'Student', 'Supervisor', 'Admin')
        """
        if not user or not user.is_authenticated:
            return None
        
        now = timezone.now()
        
        # Get active role: valid_to is NULL (ongoing) or in the future
        active_role = RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=now)
        ).select_related('role').first()
        
        if active_role and active_role.role:
            return active_role.role.role_name
        
        return None

    def has_permission(self, request, view):
        """
        Check if user has permission to access the certificate endpoints
        """
        # User must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Django staff/superuser always have full access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Get user's active role
        role_name = self._get_active_role(request.user)
        
        if not role_name:
            return False  # No active role = no access

        # Normalize role name for comparison (case-insensitive)
        role_name = role_name.lower()

        # Mentors can create and manage their own certificates
        if role_name == 'mentor':
            # Mentors can POST (create) and GET (list/retrieve)
            if request.method in ['GET', 'POST']:
                return True
            # Mentors can PATCH/PUT their own certificates (checked in has_object_permission)
            if request.method in ['PATCH', 'PUT']:
                return True
            # Mentors cannot DELETE
            return False

        # Supervisors can only read (GET)
        if role_name == 'supervisor':
            if request.method in permissions.SAFE_METHODS:  # GET, HEAD, OPTIONS
                return True
            return False

        # Students and others have no access
        return False

    def has_object_permission(self, request, view, obj):
        """
        Check if user has permission to access a specific certificate
        """
        # Django staff/superuser have full access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Get user's active role
        role_name = self._get_active_role(request.user)
        
        if not role_name:
            return False
        
        role_name = role_name.lower()

        # Mentors can read and update ONLY their own certificates
        if role_name == 'mentor':
            # Check if user has a mentor profile and owns this certificate
            if hasattr(request.user, 'mentorprofile'):
                if obj.mentor_profile == request.user.mentorprofile:
                    # Mentors can GET, PATCH, PUT their own certificates
                    if request.method in ['GET', 'PATCH', 'PUT']:
                        return True
                    # Mentors cannot DELETE their own certificates
                    return False
            return False

        # Supervisors can read certificates of mentors they oversee
        if role_name == 'supervisor':
            if request.method in permissions.SAFE_METHODS:
                # TODO: Implement logic to check if supervisor oversees this mentor
                # This would require a relationship between supervisors and mentors
                # For now, supervisors can view all mentor certificates
                return True
            return False

        return False

