"""
URL configuration for btf_backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # API Documentation (OpenAPI)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Authentication endpoints
    path('api/auth/', include('authentication.urls', namespace='authentication')),

    # User profile endpoints
    path('api/users/', include('users.urls', namespace='users')),

    # Admin dashboard endpoints
    path('api/admin/', include('users.admin_urls', namespace='admin_panel')),

    # Group management endpoints
    path('api/groups/', include('groups.urls', namespace='groups')),

    # Resource library endpoints
    path('api/resources/', include('resources.urls', namespace='resources')),

    # Events endpoints
    path('api/events/', include('events.urls', namespace='events')),

    # Announcements endpoints
    path('api/announcements/', include('announcements.urls', namespace='announcements')),

    # Chat endpoints
    path('api/', include(('chat.urls', 'chat'), namespace='chat')),

    # Core endpoints (health, uploads)
    path('api/', include(('core.urls', 'core'), namespace='core')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
