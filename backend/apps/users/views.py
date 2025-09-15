from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from django.db import transaction
from rest_framework import serializers, generics, permissions, status
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.pagination import PageNumberPagination
from.models import User
from apps.resources.models import Roles, RoleAssignmentHistory
from .serializers import UserSerializer, UserStatusPatchSerializer, RoleSerializer, RoleAssignmentHistorySerializer

# Create your views here.
#Issue 41
class UsersRetrieveView(generics.RetrieveAPIView):
    queryset = User.objects.select_related("track","state")
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    # renderer_classes = [JSONRenderer]
    renderer_classes = [TemplateHTMLRenderer]
    template_name = "users/details.html"