# from django.shortcuts import render
# from rest_framework import viewsets
# from rest_framework.permissions import IsAuthenticated
# from .models import Roles, RoleAssignmentHistory
# from .serializers import RoleSerializer, RoleAssignmentHistorySerializer

# from django.db.models import Q
# from datetime import datetime
# from django.utils import timezone
# from django.utils.dateparse import parse_date
# from rest_framework import permissions

# class RoleViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = Roles.objects.all().order_by('role_name')
#     serializer_class = RoleSerializer
#     permission_classes = [IsAuthenticated]
#     ordering = ['role_name']
#     http_method_names = ["get", "post", "patch", "delete", "head", "options"]

#     def get_permissions(self):
#         if self.request.method in ("POST", "PATCH", "DELETE"):
#             return [IsAdminUser()]
#         return [IsAuthenticated()]

from rest_framework import mixins, pagination, permissions, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from urllib.parse import urlparse
from .models import Roles, RoleAssignmentHistory, Resources, ResourceAudience, ResourceLabel
from .serializers import (
    RoleSerializer,
    RoleAssignmentHistorySerializer,
    ResourceAccessSerializer,
    ResourceLabelSerializer,
    ResourcePublicDetailSerializer,
    ResourcePublicListSerializer,
    ResourcesSerializer,
    ResourceTypeSerializer,
)
from django.db.models import Q
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone
from datetime import datetime
from django.core.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from config.errors import (
    RoleNotFound,
    UserAndRoleIdRequired,
    UserHasActiveRoles,
    UserNotFound,
)
from .services.roles import revoke_role, grant_role, create_role
from django.contrib.auth import get_user_model
from apps.audit.services import log_audit_event
from django.http import HttpResponseRedirect, StreamingHttpResponse
import requests
from apps.common.storage import serve_managed_file
from .rbac import (
    can_access_resource_file,
    can_manage_resource_file,
    filter_resources_for_user,
)
from .models import ResourceType
from .permissions import IsResourceAdmin
from .services.storage import (
    RESOURCE_FILE_SERVICE,
    is_external_storage_key,
    is_managed_storage_key,
)
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class RoleViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.CreateModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    """
    GET    /.../roles/           (list)
    GET    /.../roles/{id}/      (retrieve)
    POST   /.../roles/           (create)
    PATCH  /.../roles/{id}/      (partial update)
    DELETE /.../roles/{id}/      (destroy)
    """
    queryset = Roles.objects.all().order_by("role_name")
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.request.method in ("POST", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsResourceAdmin()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            role = create_role(serializer.validated_data['role_name'])
            response_serializer = self.get_serializer(role)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RoleAssignmentHistoryViewSet(mixins.UpdateModelMixin,
                                   viewsets.ReadOnlyModelViewSet):
    serializer_class = RoleAssignmentHistorySerializer

    def get_permissions(self):
        if self.action in ('grant_role', 'revoke_role', 'partial_update'):
            return [IsAuthenticated(), IsResourceAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = (RoleAssignmentHistory.objects
              .select_related("user", "role")
              .all())

        p = self.request.query_params
        user_id = p.get("user_id")
        role_id = p.get("role_id")
        v_from_s = p.get("valid_from")
        v_to_s = p.get("valid_to")

        if user_id:
            qs = qs.filter(user_id=user_id)
        if role_id:
            qs = qs.filter(role_id=role_id)

        v_from = parse_date(v_from_s) if v_from_s else None
        v_to = parse_date(v_to_s) if v_to_s else None
        if v_from:
            v_from = timezone.make_aware(datetime.combine(v_from, datetime.min.time()))
        if v_to:
            v_to = timezone.make_aware(datetime.combine(v_to, datetime.min.time()))

        if v_from and not v_to:
            qs = qs.filter(Q(valid_to__isnull=True) | Q(valid_to__gte=v_from))
        if v_to and not v_from:
            qs = qs.filter(valid_from__lte=v_to)
        if v_from and v_to:
            qs = qs.filter(
                Q(valid_to__isnull=True) | Q(valid_to__gte=v_from),
                Q(valid_from__lte=v_to),
            )

        return qs.order_by("user_id", "role_id", "valid_from")

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.valid_to and instance.valid_to < timezone.now():
            return Response(
                {"detail": "Cannot modify a closed assignment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsResourceAdmin])
    def grant_role(self, request):
        user_id = request.data.get('user_id')
        role_id = request.data.get('role_id')
        start_date = request.data.get('start')
        revoke_others = request.data.get('revoke_others', True)
        force = request.data.get('force', False)

        if not user_id or not role_id:
            raise UserAndRoleIdRequired()

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            raise UserNotFound() from exc

        try:
            role = Roles.objects.get(id=role_id)
        except Roles.DoesNotExist as exc:
            raise RoleNotFound() from exc

        if start_date:
            start_date = parse_datetime(start_date)

        if not force:
            active_roles = RoleAssignmentHistory.objects.filter(
                user=user,
                valid_to__isnull=True
            ).exclude(role=role)

            if active_roles.exists() and not revoke_others:
                raise UserHasActiveRoles(
                    [assignment.role.role_name for assignment in active_roles]
                )

        result = grant_role(user, role, start=start_date, revoke_others=revoke_others, force=force)

        response_data = {
            "message": result.get('message', f"Role '{role.role_name}' granted to user '{user.email}'"),
            "action_taken": result.get('action_taken'),
            "details": {
                "user_id": user.id,
                "role_id": role.id,
                "start_time": start_date or timezone.now(),
                "user_groups": list(user.groups.values_list('name', flat=True)),
                "granted_role": result['granted_role'],
                "revoked_roles": result['revoked_roles'],
                "had_existing_roles": result['had_existing'],
                "duplicate_role": result.get('duplicate_role', False)
            }
        }

        if result['revoked_roles']:
            response_data["warning"] = f"Revoked existing roles: {', '.join(result['revoked_roles'])}"

        if result.get('duplicate_role') and not force:
            response_data["info"] = "User already had this role - extended the duration instead of creating duplicate"

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsResourceAdmin])
    def revoke_role(self, request):
        user_id = request.data.get('user_id')
        role_id = request.data.get('role_id')
        end_date = request.data.get('end')

        if not user_id or not role_id:
            raise UserAndRoleIdRequired()

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            raise UserNotFound() from exc

        try:
            role = Roles.objects.get(id=role_id)
        except Roles.DoesNotExist as exc:
            raise RoleNotFound() from exc

        if end_date:
            end_date = parse_datetime(end_date)

        revoke_role(user, role, end=end_date)

        return Response(
            {
                "message": f"Role '{role.role_name}' revoked from user '{user.email}'",
                "details": {
                    "user_id": user.id,
                    "role_id": role.id,
                    "end_time": end_date or timezone.now(),
                    "user_groups": list(user.groups.values_list('name', flat=True))
                }
            },
            status=status.HTTP_200_OK
        )


class ResourcesPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_page_size(self, request):
        if self.page_size_query_param:
            if hasattr(request, 'query_params'):
                page_size = request.query_params.get(self.page_size_query_param)
            else:
                page_size = request.GET.get(self.page_size_query_param)

            if page_size is not None:
                try:
                    page_size = int(page_size)
                    if page_size > 0:
                        return min(page_size, self.max_page_size)
                except (KeyError, ValueError):
                    pass
        return self.page_size


class ResourcesViewSet(mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.CreateModelMixin,
                       mixins.UpdateModelMixin,
                       mixins.DestroyModelMixin,
                       viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = ResourcesPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    queryset = Resources.objects.select_related('uploaded_by', 'track').prefetch_related('audiences__role', 'audiences__track', 'labels').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ResourcePublicListSerializer
        if self.action == 'retrieve':
            return ResourcePublicDetailSerializer
        return ResourcesSerializer

    def get_queryset(self):
        user = self.request.user

        if not user or not user.is_authenticated:
            return Resources.objects.none()

        queryset = Resources.objects.filter(
            deleted_at__isnull=True
        ).select_related('uploaded_by', 'track').prefetch_related('audiences__role', 'audiences__track', 'labels')

        if self.action == 'list':
            queryset = filter_resources_for_user(queryset, user)

        queryset = self._apply_filters(queryset)
        return queryset.order_by('-uploaded_at')

    def _apply_filters(self, queryset):
        params = self.request.query_params

        uploader_id = self._parse_int_param(params, 'uploader_id')
        if uploader_id is not None:
            queryset = queryset.filter(uploaded_by_id=uploader_id)

        role = params.get('role')
        if role:
            queryset = queryset.filter(audiences__role__role_name__icontains=role)

        track_id = self._parse_int_param(params, 'track_id')
        if track_id is not None:
            queryset = queryset.filter(
                Q(track_id=track_id) | Q(audiences__track_id=track_id)
            )

        resource_type = params.get('type')
        if resource_type:
            queryset = queryset.filter(type__type_name__iexact=resource_type)

        label_id = self._parse_int_param(params, 'label_id')
        if label_id is not None:
            queryset = queryset.filter(labels__id=label_id)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )

        since = self._parse_date_param(params, 'since')
        if since:
            queryset = queryset.filter(uploaded_at__date__gte=since)

        until = self._parse_date_param(params, 'until')
        if until:
            queryset = queryset.filter(uploaded_at__date__lte=until)

        if since and until and until < since:
            raise DRFValidationError({"until": "until must be on or after since."})

        order = params.get('order', 'newest')
        if order not in ('newest', 'oldest', 'name'):
            raise DRFValidationError({"order": "order must be one of: newest, oldest, name."})
        if order == 'oldest':
            queryset = queryset.order_by('uploaded_at')
        elif order == 'name':
            queryset = queryset.order_by('name')
        elif order == 'newest':
            queryset = queryset.order_by('-uploaded_at')

        return queryset

    @staticmethod
    def _parse_int_param(params, name):
        raw = params.get(name)
        if raw in (None, ''):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise DRFValidationError({name: f"{name} must be an integer."}) from exc

    @staticmethod
    def _parse_date_param(params, name):
        raw = params.get(name)
        if raw in (None, ''):
            return None
        parsed = parse_date(raw)
        if parsed is None:
            raise DRFValidationError({name: f"{name} must be an ISO date (YYYY-MM-DD)."})
        return parsed

    def get_permissions(self):
        if self.action in ['assign_role', 'remove_role']:
            return [IsAuthenticated(), IsResourceAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        track = self._requested_track_for_write()
        if not can_manage_resource_file(self.request.user, track=track):
            raise PermissionDenied("You do not have permission to manage resource files in this scope.")
        resource = serializer.save(uploaded_by=self.request.user)
        log_audit_event(
            actor=self.request.user,
            entity_type="resource",
            entity_id=resource.id,
            action="create",
            after_state=ResourcesSerializer(resource).data,
        )

    def perform_update(self, serializer):
        resource = self.get_object()
        track = self._requested_track_for_write(instance=resource)
        if not can_manage_resource_file(self.request.user, resource=resource, track=track):
            raise PermissionDenied("You do not have permission to manage resource files in this scope.")
        before_state = ResourcesSerializer(resource).data
        resource = serializer.save()
        log_audit_event(
            actor=self.request.user,
            entity_type="resource",
            entity_id=resource.id,
            action="update",
            before_state=before_state,
            after_state=ResourcesSerializer(resource).data,
        )

    def _serialize_public_resource(self, resource):
        return ResourcePublicDetailSerializer(resource, context={"request": self.request})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            self._serialize_public_resource(serializer.instance).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(self._serialize_public_resource(serializer.instance).data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_access_resource_file(request.user, instance):
            return Response({"detail": "You do not have access to this resource."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_manage_resource_file(request.user, resource=instance):
            return Response({"detail": "You do not have permission to manage this resource."}, status=status.HTTP_403_FORBIDDEN)
        before_state = ResourcesSerializer(instance).data
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])
        log_audit_event(
            actor=request.user,
            entity_type="resource",
            entity_id=instance.id,
            action="soft_delete",
            before_state=before_state,
            after_state=ResourcesSerializer(instance).data,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _build_access_payload(self, resource):
        # Resource access is explicit so the frontend can stop guessing whether a resource is
        # directly downloadable, opens as an external page, or is not yet wired to storage.
        storage_key = (resource.storage_key or "").strip()
        external_url = self._validated_external_resource_url(storage_key)
        invalid_external_url = bool(storage_key) and is_external_storage_key(storage_key) and external_url is None
        mime_type = (resource.file_mime_type or "").lower()
        body_html = None
        if not storage_key:
            access_mode = "unavailable"
            detail = "This resource does not have a configured storage target yet."
        elif invalid_external_url:
            access_mode = "unavailable"
            detail = "This resource has an invalid external URL."
        elif external_url and resource.kind == Resources.ResourceKind.PAGE:
            access_mode = "external_page"
            detail = None
        elif external_url and resource.kind == Resources.ResourceKind.FILE:
            access_mode = "external_file"
            detail = None
        elif (
            resource.kind == Resources.ResourceKind.PAGE
            and mime_type == "text/html"
            and is_managed_storage_key(storage_key)
        ):
            access_mode = "inline_html"
            body_html, detail = self._read_inline_html_body(resource)
        else:
            access_mode = "managed_file" if resource.kind == Resources.ResourceKind.FILE else "managed_page"
            detail = None

        serializer = ResourcePublicListSerializer(resource, context={"request": self.request})
        resource_data = serializer.data
        return {
            "resource_id": resource.id,
            "kind": resource.kind,
            "storage_status": resource_data["storage_status"],
            "access_mode": access_mode,
            "access_url": resource_data["access_url"],
            "download_url": resource_data["download_url"],
            "external_url": external_url,
            "file_name": resource_data["file_name"],
            "file_mime_type": resource.file_mime_type,
            "file_size": resource.file_size,
            "body_html": body_html,
            "detail": detail,
        }

    def _read_inline_html_body(self, resource):
        # Returns (body_html, detail). On any failure, body is None and detail
        # explains so the client can show a fallback message instead of a 500.
        max_bytes = getattr(settings, "RESOURCE_INLINE_HTML_MAX_BYTES", 2 * 1024 * 1024)
        if resource.file_size and resource.file_size > max_bytes:
            return None, "Rich-text content is too large to inline."
        try:
            with RESOURCE_FILE_SERVICE.open(resource.storage_key) as fp:
                raw = fp.read(max_bytes + 1)
        except Exception as exc:
            # Azure's ResourceNotFoundError is an HttpResponseError, not OSError,
            # so the narrower catch let missing-blob reads bubble up as a 500.
            logger.warning("Failed to read inline HTML for resource %s: %s", resource.pk, exc)
            return None, "Rich-text content could not be loaded."
        if len(raw) > max_bytes:
            return None, "Rich-text content is too large to inline."
        try:
            return raw.decode("utf-8", errors="replace"), None
        except UnicodeDecodeError as exc:
            logger.warning("Failed to decode inline HTML for resource %s: %s", resource.pk, exc)
            return None, "Rich-text content could not be decoded."

    def _validated_external_resource_url(self, storage_key: str | None):
        value = (storage_key or "").strip()
        if not is_external_storage_key(value):
            return None
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            return None
        return value

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def access(self, request, pk=None):
        resource = self.get_object()
        if not can_access_resource_file(request.user, resource):
            return Response({"detail": "You do not have access to this resource."}, status=status.HTTP_403_FORBIDDEN)

        payload = self._build_access_payload(resource)
        return Response(ResourceAccessSerializer(payload).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def download(self, request, pk=None):
        resource = self.get_object()
        if not can_access_resource_file(request.user, resource):
            return Response({"detail": "You do not have access to this resource."}, status=status.HTTP_403_FORBIDDEN)

        payload = self._build_access_payload(resource)
        external_url = payload["external_url"]
        # ``force=1`` query param: proxy the file bytes through us so the
        # browser sees a ``Content-Disposition: attachment`` header and
        # actually saves the file. Without it, an external resource just
        # 302-redirects to the upstream URL — and the browser's
        # ``<a download>`` hint is ignored cross-origin, so the file ends up
        # opening inline instead of downloading. The force path is opt-in so
        # callers that just want a preview still get the cheap redirect.
        force = (request.query_params.get("force") or "").lower() in {"1", "true", "yes"}
        if external_url and payload["access_mode"] in {"external_file", "external_page"}:
            if not force:
                return HttpResponseRedirect(external_url)
            try:
                upstream = requests.get(external_url, stream=True, timeout=10)
            except requests.RequestException as exc:
                return Response(
                    {"detail": f"Upstream resource could not be fetched: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            if upstream.status_code >= 400:
                return Response(
                    {"detail": f"Upstream resource returned HTTP {upstream.status_code}."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            file_name = payload.get("file_name") or resource.name or "resource"
            mime_type = (
                resource.file_mime_type
                or upstream.headers.get("content-type")
                or "application/octet-stream"
            )
            response = StreamingHttpResponse(
                upstream.iter_content(chunk_size=64 * 1024),
                content_type=mime_type,
            )
            response["Content-Disposition"] = f'attachment; filename="{file_name}"'
            content_length = upstream.headers.get("content-length")
            if content_length:
                response["Content-Length"] = content_length
            return response
        if payload["access_mode"] == "unavailable":
            return Response(
                {"detail": payload["detail"]},
                status=status.HTTP_409_CONFLICT,
            )

        storage_key = (resource.storage_key or "").strip()
        return serve_managed_file(
            resolve_url=RESOURCE_FILE_SERVICE.resolve_url,
            open_file=RESOURCE_FILE_SERVICE.open,
            storage_key=storage_key,
            filename=payload["file_name"] or resource.name,
            mime_type=resource.file_mime_type,
            size=resource.file_size,
            as_attachment=resource.kind == Resources.ResourceKind.FILE,
            on_open_failure_detail="The stored file could not be opened for download.",
        )

    def _requested_track_for_write(self, instance=None):
        track_id = self.request.data.get("track")
        group_id = self.request.data.get("group")

        if track_id not in (None, ""):
            return track_id

        if group_id not in (None, ""):
            from apps.groups.models import Groups

            group = Groups.objects.only("id", "track_id").filter(pk=group_id).first()
            if group is not None:
                return group.track_id

        if instance is not None:
            if instance.track_id:
                return instance.track_id
            if instance.group_id:
                return instance.group.track_id

        return None

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsResourceAdmin])
    def assign_role(self, request, pk=None):
        resource = self.get_object()
        role_id = request.data.get('role_id')

        if not role_id:
            return Response(
                {"error": "role_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            role = Roles.objects.get(id=role_id)

            if ResourceAudience.objects.filter(resource=resource, role=role, track__isnull=True).exists():
                return Response(
                    {"error": "Role is already assigned to this resource"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            ResourceAudience.objects.create(resource=resource, role=role)

            return Response({
                "message": f"Role '{role.role_name}' assigned to resource '{resource.name}'",
                "resource_id": resource.id,
                "resource_name": resource.name,
                "role_id": role.id
            }, status=status.HTTP_201_CREATED)

        except Roles.DoesNotExist:
            return Response(
                {"error": "Role not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['delete'], permission_classes=[IsAuthenticated, IsResourceAdmin])
    def remove_role(self, request, pk=None):
        resource = self.get_object()
        role_id = request.data.get('role_id')

        if not role_id:
            return Response(
                {"error": "role_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            role = Roles.objects.get(id=role_id)
            resource_role = ResourceAudience.objects.get(resource=resource, role=role, track__isnull=True)
            role_name = role.role_name
            resource_role.delete()

            return Response({
                "message": f"Role '{role_name}' removed from resource '{resource.name}'"
            }, status=status.HTTP_200_OK)

        except Roles.DoesNotExist:
            return Response(
                {"error": "Role not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except ResourceAudience.DoesNotExist:
            return Response(
                {"error": "Role is not assigned to this resource"},
                status=status.HTTP_404_NOT_FOUND
            )


class ResourceTypeViewSet(mixins.ListModelMixin,
                          mixins.RetrieveModelMixin,
                          viewsets.GenericViewSet):
    queryset = ResourceType.objects.all().order_by("type_name")
    serializer_class = ResourceTypeSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]


class ResourceLabelViewSet(mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           viewsets.GenericViewSet):
    """Read-only labels with a `resource_count` that respects the caller's audience.

    The count is the number of live resources visible to *this* user that carry
    the label, so the UI sidebar shows the same numbers Chronus does.
    """
    serializer_class = ResourceLabelSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return ResourceLabel.objects.none()

        visible = filter_resources_for_user(
            Resources.objects.filter(deleted_at__isnull=True),
            user,
        )
        # ``filter_resources_for_user`` may add a join to the audiences table,
        # which makes ``Count('resources')`` double-count. Restrict the count
        # to visible IDs.
        from django.db.models import Count, Q

        visible_ids = list(visible.values_list('id', flat=True).distinct())
        return (
            ResourceLabel.objects.annotate(
                resource_count=Count(
                    'resources',
                    filter=Q(resources__id__in=visible_ids),
                    distinct=True,
                )
            )
            .order_by('name')
        )
