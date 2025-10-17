# Create your views here.
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db.models import Q
from .models import MentorCertificate
from .serializers import (
    MentorCertificateSerializer,
    MentorCertificateCreateSerializer,
    MentorCertificateUpdateSerializer,
    AdminCertificateUpdateSerializer,
)
from .permissions import CertificatePermission
from apps.resources.models import RoleAssignmentHistory


class MentorCertificateViewSet(mixins.ListModelMixin,
                               mixins.RetrieveModelMixin,
                               mixins.CreateModelMixin,
                               mixins.UpdateModelMixin,
                               mixins.DestroyModelMixin,
                               viewsets.GenericViewSet):
    """
    Certificate Management with Role-Based Access Control:
    
    Mentors:
        - GET /certificates/v1/ -> list their own certificates
        - GET /certificates/v1/{id}/ -> retrieve their own certificate
        - POST /certificates/v1/ -> create their own certificate
        - PATCH /certificates/v1/{id}/ -> update their own certificate
        
    Admins:
        - Full CRUD access to all certificates
        - GET /certificates/v1/?expires_by=YYYY-MM-DD -> audit view with expiry filter
        - Can set 'verified' flag
        
    Supervisors:
        - GET /certificates/v1/ -> list certificates of mentors they oversee
        - GET /certificates/v1/{id}/ -> view specific certificates (read-only)
        
    Students:
        - No access
    """
    queryset = MentorCertificate.objects.select_related(
        "certificate_type", "mentor_profile"
    )
    permission_classes = [CertificatePermission]
    
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
    
    def get_queryset(self):
        """
        Filter queryset based on user role:
        - Admins: see all certificates
        - Mentors: see only their own certificates
        - Supervisors: see certificates of mentors they oversee
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # Django staff/superuser can see all certificates
        if user.is_staff or user.is_superuser:
            # Admin-only filter: expires_by date
            expires_by = self.request.query_params.get('expires_by')
            if expires_by:
                try:
                    expiry_date = parse_date(expires_by)
                    if expiry_date:
                        queryset = queryset.filter(expires_at__lte=expiry_date)
                except (ValueError, TypeError):
                    pass  # Invalid date format, ignore filter
            return queryset
        
        # Get user's active role
        role_name = self._get_active_role(user)
        
        if not role_name:
            return queryset.none()  # No active role = no access
        
        role_name = role_name.lower()
        
        # Mentors can only see their own certificates
        if role_name == 'mentor':
            if hasattr(user, 'mentorprofile'):
                return queryset.filter(mentor_profile=user.mentorprofile)
            return queryset.none()
        
        # Supervisors can see certificates of mentors they oversee
        if role_name == 'supervisor':
            # TODO: Implement logic to filter by supervised mentors
            # For now, return all certificates (adjust based on your supervisor-mentor relationship)
            return queryset
        
        # Default: return empty queryset (students, etc.)
        return queryset.none()
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions and user roles:
        - Create: MentorCertificateCreateSerializer
        - Update (Mentor): MentorCertificateUpdateSerializer
        - Update (Admin): AdminCertificateUpdateSerializer
        - Retrieve/List: MentorCertificateSerializer
        """
        if self.action == 'create':
            return MentorCertificateCreateSerializer
        
        if self.action in ['update', 'partial_update']:
            # Admins can update all fields including 'verified'
            if self.request.user.is_staff or self.request.user.is_superuser:
                return AdminCertificateUpdateSerializer
            # Mentors can only update their certificate details, not 'verified'
            return MentorCertificateUpdateSerializer
        
        return MentorCertificateSerializer
    
    def perform_create(self, serializer):
        """
        When creating a certificate:
        - If user is a mentor (not admin), auto-set mentor_profile to current user
        - Certificate starts as unverified (verified=False by default)
        """
        user = self.request.user
        
        # Django staff/superuser creating certificate (can specify any mentor)
        if user.is_staff or user.is_superuser:
            serializer.save()
            return
        
        # Get user's active role
        role_name = self._get_active_role(user)
        
        if role_name and role_name.lower() == 'mentor':
            # Mentor creating their own certificate
            if hasattr(user, 'mentorprofile'):
                # Auto-set mentor_profile to current user, starts unverified
                serializer.save(mentor_profile=user.mentorprofile, verified=False)
                return
        
        # Fallback (shouldn't reach here due to permissions)
        serializer.save()
    
    @action(detail=True, methods=['post'], permission_classes=[CertificatePermission])
    def verify(self, request, pk=None):
        """
        Admin-only action to verify a certificate.
        POST /certificates/v1/{id}/verify/
        """
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {"detail": "Only admins can verify certificates."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        certificate = self.get_object()
        certificate.verified = True
        certificate.save(update_fields=['verified'])
        
        serializer = self.get_serializer(certificate)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[CertificatePermission])
    def unverify(self, request, pk=None):
        """
        Admin-only action to unverify a certificate.
        POST /certificates/v1/{id}/unverify/
        """
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {"detail": "Only admins can verify certificates."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        certificate = self.get_object()
        certificate.verified = False
        certificate.save(update_fields=['verified'])
        
        serializer = self.get_serializer(certificate)
        return Response(serializer.data)
