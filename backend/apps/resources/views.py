from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Roles, RoleAssignmentHistory
from .serializers import RoleSerializer, RoleAssignmentCreateSerializer, RoleAssignmentHistorySerializer

class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Roles.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['role_name']

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_role(request):
    """
    Assign a role to a user with date validity.

    POST /api/v1/role-assignments/

    Body:
    {
        "user_id": 1,
        "role_id": 2,
        "valid_from": "2024-01-01T00:00:00Z",
        "valid_to": "2024-12-31T23:59:59Z"  // optional
    }
    """
    serializer = RoleAssignmentCreateSerializer(data=request.data)

    if serializer.is_valid():
        role_assignment = serializer.save()

        # Return the created assignment with full details
        response_serializer = RoleAssignmentHistorySerializer(role_assignment)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )