from django.shortcuts import render, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.permissions import AllowAny
from . import auth_service
from apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken


class SendLoginCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    def post(self, request):
        email = request.data.get("email")
        # edbert: Added redirect_url parameter to support frontend callback
        redirect_url = request.data.get("redirect_url")
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        # edbert: Pass redirect_url to auth service
        sent = auth_service.send_login_code(email, redirect_url)
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
        from apps.users.models import User
        user = User.objects.get(email=email)

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
    user = User.objects.get(email=email)
    refresh = RefreshToken.for_user(user)

    # edbert: Redirect to frontend with tokens as URL parameters instead of returning JSON
    from django.conf import settings
    frontend_callback = getattr(settings, 'MAGIC_LINK_REDIRECT_URL', 'http://localhost:5173/#/auth/callback')

    # edbert: Add tokens as query parameters for frontend to capture
    redirect_url = f"{frontend_callback}?access_token={str(refresh.access_token)}&refresh_token={str(refresh)}&user_id={user.id}&email={user.email}&first_name={user.first_name}&last_name={user.last_name}"

    return redirect(redirect_url)


@require_http_methods(["GET"])
def test_email_template(request):
    """
    Test view to preview the login email template in browser
    Access at: /services/test-email/
    """
    # Sample data for template testing
    context = {
        "MAGIC_LINK": "https://biotechfutures.org/auth/magic?email=test@example.com&code=123456",
        "OTP_CODE": "123456",
        "EXPIRY_MINUTES": 10,
        "First_Name": "John"
    }

    # Render the email template
    try:
        html_content = render_to_string("emails/login.html", context)
        return HttpResponse(html_content, content_type="text/html")
    except Exception as e:
        return HttpResponse(
            f"<h1>Template Error</h1><p>Error rendering template: {str(e)}</p>",
            content_type="text/html"
        )

#to be deleted.
@require_http_methods(["GET"])
def test_email_preview(request):
    """
    Preview email template with customizable parameters
    Access at: /services/test-email-preview/
    """
    # Get parameters from URL or use defaults
    first_name = request.GET.get('first_name', 'John')
    email = request.GET.get('email', 'test@example.com')
    otp_code = request.GET.get('otp_code', '123456')
    expiry_minutes = request.GET.get('expiry_minutes', '10')

    context = {
        "MAGIC_LINK": f"https://biotechfutures.org/auth/magic?email={email}&code={otp_code}",
        "OTP_CODE": otp_code,
        "EXPIRY_MINUTES": expiry_minutes,
        "First_Name": first_name
    }

    try:
        html_content = render_to_string("emails/login.html", context)

        # Wrap in a preview container
        preview_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Email Template Preview</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .preview-header {{ background: #f0f0f0; padding: 15px; margin-bottom: 20px; border-radius: 5px; }}
                .preview-controls {{ margin-bottom: 20px; }}
                .preview-controls input {{ margin: 5px; padding: 8px; }}
                .preview-controls button {{ background: #007cba; color: white; padding: 8px 15px; border: none; border-radius: 3px; cursor: pointer; }}
                .email-preview {{ border: 1px solid #ddd; padding: 0; }}
            </style>
        </head>
        <body>
            <div class="preview-header">
                <h1>🧪 Email Template Preview</h1>
                <p>Preview of login.html template with current variables</p>
            </div>

            <div class="preview-controls">
                <form method="get">
                    <input type="text" name="first_name" placeholder="First Name" value="{first_name}">
                    <input type="email" name="email" placeholder="Email" value="{email}">
                    <input type="text" name="otp_code" placeholder="OTP Code" value="{otp_code}" maxlength="6">
                    <input type="number" name="expiry_minutes" placeholder="Expiry Minutes" value="{expiry_minutes}">
                    <button type="submit">Update Preview</button>
                </form>
            </div>

            <div class="email-preview">
                {html_content}
            </div>
        </body>
        </html>
        """

        return HttpResponse(preview_html, content_type="text/html")

    except Exception as e:
        return HttpResponse(
            f"<h1>Template Error</h1><p>Error rendering template: {str(e)}</p>",
            content_type="text/html"
        )