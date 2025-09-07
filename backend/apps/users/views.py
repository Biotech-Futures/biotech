from django.shortcuts import render, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework import status
from apps.users.services import auth_service
from apps.users.models import Users
from rest_framework_simplejwt.tokens import RefreshToken


class SendLoginCodeView(APIView):
    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        sent = auth_service.send_login_code(email)
        if sent:
            return Response({"message": "Login code sent"}, status=status.HTTP_200_OK)
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


class VerifyLoginCodeView(APIView):
    def post(self, request):
        email = request.data.get("email")
        code = request.data.get("code")
        if not email or not code:
            return Response({"error": "Email and code are required"}, status=status.HTTP_400_BAD_REQUEST)

        valid = auth_service.verify_login_code(email, code)
        if not valid:
            return Response({"error": "Invalid or expired code"}, status=status.HTTP_400_BAD_REQUEST)

        # At this point user is authenticated → issue tokens
        from apps.users.models import Users
        user = Users.objects.get(email=email)

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            },
            status=status.HTTP_200_OK,
        )

def magic_login(request):
    email = request.GET.get("email")
    code = request.GET.get("code")

    if not email or not code:
        return JsonResponse({"error": "Missing email or code"}, status=400)

    if not auth_service.verify_login_code(email, code):
        return JsonResponse({"error": "Invalid or expired code"}, status=400)

    # User is authenticated → issue JWTs
    user = Users.objects.get(email=email)
    refresh = RefreshToken.for_user(user)

    return JsonResponse(
        {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        },
        status=200,
    )
