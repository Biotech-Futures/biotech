"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    # API v1 endpoints
    path("api/v1/", include("apps.users.urls")),

    # Legacy URL structure (kept for backwards compatibility)
    path("users/", include("apps.users.urls")),
    path("events/", include("apps.events.urls")),
    path("tasks/", include("apps.tasks.urls")),
    path("groups/", include("apps.groups.urls")),
    path("chat/", include("apps.chat.urls")),
    path("resources/", include("apps.resources.urls")),
    path("integrations/", include("apps.integrations.urls")),
    path("certificates/", include("apps.certificates.urls")),
    path("announcements/", include("apps.announcements.urls")),

    # Services (auth, email, etc)
    path("services/", include("apps.services.urls")),
    path('api-auth/', include('rest_framework.urls')), # for browsable API login

    # Schema and docs
    path('', RedirectView.as_view(url='/api/docs/', permanent=False)),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

]
