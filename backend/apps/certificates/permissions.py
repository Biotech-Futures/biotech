"""
Custom permissions for Certificate management
"""
from rest_framework import permissions

from apps.common.rbac import get_active_role_name
from apps.common.role_names import ROLE_MENTOR, ROLE_SUPERVISOR


class CertificatePermission(permissions.BasePermission):
    """
    Custom permission for certificate access based on active roles:
    - Mentors: Can create, read, and update their own certificates (cannot verify)
    - Admins: Full CRUD access to all certificates
    - Supervisors: Read-only access to certificates of mentors they oversee
    - Students: No access

    Active-role resolution is delegated to ``apps.common.rbac.get_active_role_name``
    so role-name comparisons stay in lock-step with the rest of the codebase.
    """

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

        role_name = get_active_role_name(request.user)
        if not role_name:
            return False

        # Mentors can create and manage their own certificates
        if role_name == ROLE_MENTOR:
            # Mentors can POST (create) and GET (list/retrieve)
            if request.method in ['GET', 'POST']:
                return True
            # Mentors can PATCH/PUT their own certificates (checked in has_object_permission)
            if request.method in ['PATCH', 'PUT']:
                return True
            # Mentors cannot DELETE
            return False

        # Supervisors can only read (GET)
        if role_name == ROLE_SUPERVISOR:
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

        role_name = get_active_role_name(request.user)
        if not role_name:
            return False

        # Mentors can read and update ONLY their own certificates
        if role_name == ROLE_MENTOR:
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
        if role_name == ROLE_SUPERVISOR:
            if request.method in permissions.SAFE_METHODS:
                # TODO: Implement logic to check if supervisor oversees this mentor
                # This would require a relationship between supervisors and mentors
                # For now, supervisors can view all mentor certificates
                return True
            return False

        return False

