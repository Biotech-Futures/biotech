# Create your views here.
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from .models import MentorCertificate
from .serializers import (
    MentorCertificateSerializer,
    MentorCertificateCreateSerializer,
    MentorCertificateUpdateSerializer,
    AdminCertificateUpdateSerializer,
)
from .permissions import CertificatePermission
from apps.common.rbac import get_active_role_name
from apps.common.role_names import ROLE_MENTOR, ROLE_SUPERVISOR
from config.errors import AdminVerificationRequired


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

    # Active-role lookup is intentionally delegated to apps.common.rbac
    # so this viewset stays consistent with the rest of the RBAC stack.

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
        role_name = get_active_role_name(user)

        if not role_name:
            return queryset.none()  # No active role = no access

        # Mentors can only see their own certificates
        if role_name == ROLE_MENTOR:
            if hasattr(user, 'mentorprofile'):
                return queryset.filter(mentor_profile=user.mentorprofile)
            return queryset.none()

        # Supervisors can see certificates of mentors they oversee
        if role_name == ROLE_SUPERVISOR:
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
        role_name = get_active_role_name(user)

        if role_name == ROLE_MENTOR:
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
            raise AdminVerificationRequired()
        
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
            raise AdminVerificationRequired()
        
        certificate = self.get_object()
        certificate.verified = False
        certificate.save(update_fields=['verified'])
        
        serializer = self.get_serializer(certificate)
        return Response(serializer.data)
