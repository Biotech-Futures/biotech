from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from .models import Groups, Countries
from .serializers import CountrySerializer

# Create your views here.

class CountryViewSet(viewsets.ModelViewSet):
  queryset = Countries.objects.all()
  serializer_class = CountrySerializer
  
  def get_permissions(self):
    # allow read for anybody and only write for admin
    if self.action in ["list", "retrieve"]:
      return [AllowAny()]
    return [IsAdminUser()] # to check if the user has .is_staff flag