
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAdminUser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from django.db.models import Prefetch
from django.utils import timezone

from .models import NewsletterSubscription
from .serializers import (
    SubscribeRequestSerializer,
    UnsubscribeRequestSerializer,
    ResubscribeRequestSerializer,
    NewsletterSubscriptionSerializer,
)
from apps.resources.models import RoleAssignmentHistory


@extend_schema(
    summary="Subscribe to the newsletter",
    request=SubscribeRequestSerializer,
    responses={200: NewsletterSubscriptionSerializer},
    tags=["Newsletter"],
)
class SubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SubscribeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        user = request.user if request.user and request.user.is_authenticated else None
        if not email and user:
            email = user.email

        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        sub, changed = NewsletterSubscription.subscribe(email=email, user=user)
        out = NewsletterSubscriptionSerializer(sub).data
        out.update({"created_or_updated": changed})
        return Response(out, status=status.HTTP_200_OK)


@extend_schema(
    summary="Unsubscribe from the newsletter",
    request=UnsubscribeRequestSerializer,
    responses={200: {
        "type": "object",
                "properties": {
                    "email": {"type": "string", "nullable": True},
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                }
    }},
    tags=["Newsletter"],
)
class UnsubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UnsubscribeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get("email")
        token = serializer.validated_data.get("token")

        sub, changed = NewsletterSubscription.unsubscribe(
            email=email, token=token)
        # Avoid account enumeration: return generic success even when not found
        return Response({
            "email": (sub.email if sub else email),
            "success": True,
            "message": "If this email was subscribed, it has been unsubscribed.",
        }, status=status.HTTP_200_OK)


@extend_schema(
    summary="Re-subscribe to the newsletter",
    request=ResubscribeRequestSerializer,
    responses={200: NewsletterSubscriptionSerializer},
    tags=["Newsletter"],
)
class ResubscribeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResubscribeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        user = request.user if request.user and request.user.is_authenticated else None
        if not email and user:
            email = user.email

        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        sub, changed = NewsletterSubscription.subscribe(email=email, user=user)
        out = NewsletterSubscriptionSerializer(sub).data
        out.update({"created_or_updated": changed})
        return Response(out, status=status.HTTP_200_OK)


@extend_schema(
    summary="List newsletter subscribers",
    parameters=[
        OpenApiParameter(name="status", description="Filter by status: subscribed or unsubscribed",
                         required=False, type=OpenApiTypes.STR),
        OpenApiParameter(name="q", description="Search by email substring (case-insensitive)",
                         required=False, type=OpenApiTypes.STR),
    ],
    tags=["Newsletter"],
)
class SubscribersListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = NewsletterSubscriptionSerializer
    queryset = NewsletterSubscription.objects.all().order_by("-created_at")

    def get_queryset(self):
        qs = super().get_queryset()
        now = timezone.now()
        # Optimize related lookups for serializer computed fields
        qs = qs.select_related(
            "user",
            "user__state",
            "user__track",
            "user__track__state",
            # OneToOne relations can be select_related as well
            "user__studentprofile",
            "user__mentorprofile",
            "user__supervisorprofile",
        )

        # Compute reverse accessor name dynamically to avoid hardcoding
        try:
            user_fk = RoleAssignmentHistory._meta.get_field(
                "user").remote_field
            # e.g., 'roleassignmenthistory_set' or custom
            accessor_name = user_fk.get_accessor_name()
            prefetch_path = f"user__{accessor_name}"
            qs = qs.prefetch_related(
                Prefetch(
                    prefetch_path,
                    queryset=RoleAssignmentHistory.objects.filter(
                        valid_from__lte=now, valid_to__isnull=True
                    ).select_related("role"),
                    to_attr="active_roles",
                )
            )
        except Exception:
            # Fallback: no role prefetch, serializer will query lazily
            pass
        status_filter = (self.request.query_params.get(
            "status") or "").strip().lower()
        if status_filter == "subscribed":
            qs = qs.filter(is_subscribed=True)
        elif status_filter == "unsubscribed":
            qs = qs.filter(is_subscribed=False)

        q = (self.request.query_params.get("q") or "").strip().lower()
        if q:
            qs = qs.filter(email__icontains=q)
        return qs
