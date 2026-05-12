import os
import django
from django.conf import settings
from django.test import Client
import json

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import User
from apps.services.models import LoginToken

def run_tests():
    print("========================================")
    print("[TEST SCRIPT] INITIALIZING AUTHENTICATION TESTS")
    print("========================================")
    
    # 1. Provision Mock User
    email = "test_auth_user@example.com"
    password = "SuperSecretPassword123!"
    
    user, created = User.objects.get_or_create(email=email)
    user.set_password(password)
    user.save()
    user.activate()
    print(f"Mock User Provisioned: {email}")
    
    client = Client()
    
    # ---------------------------------------------------------
    # TEST 1: PASSWORD LOGIN
    # ---------------------------------------------------------
    print("\n[TEST 1] Password Login Flow")
    response = client.post(
        '/api/v1/auth/login/',
        json.dumps({'email': email, 'password': password}),
        content_type='application/json'
    )
    
    if response.status_code == 200:
        cookies = response.client.cookies
        sessionid = cookies.get('sessionid')
        print("SUCCESS: Password Login Returned 200 OK")
        print(f"SUCCESS: sessionid cookie attached: {bool(sessionid)}")
    else:
        print(f"FAILED: Password Login ({response.status_code}) -> {response.content}")

    client.logout()

    # ---------------------------------------------------------
    # TEST 2: OTP LOGIN
    # ---------------------------------------------------------
    print("\n[TEST 2] OTP Code Flow")
    
    # Generate OTP Code
    resp_send = client.post(
        '/services/send-login-code/',
        json.dumps({'email': email}),
        content_type='application/json'
    )
    
    if resp_send.status_code == 200:
        print("SUCCESS: OTP Code Generated")
        
        # Manually extract the token from DB for test bypass
        token_obj = LoginToken.objects.filter(user=user, used=False).last()
        raw_code = token_obj.token # Normally sent to email
        print(f"   -> DB Intercepted Code: {raw_code}")
        
        # Verify OTP
        resp_verify = client.post(
            '/services/verify-login-code/',
            json.dumps({'email': email, 'code': raw_code}),
            content_type='application/json'
        )
        
        if resp_verify.status_code == 200:
            cookies = resp_verify.client.cookies
            print("SUCCESS: OTP Verified & Logged In")
            print(f"SUCCESS: sessionid cookie attached: {bool(cookies.get('sessionid'))}")
        else:
            print(f"FAILED: OTP Verify ({resp_verify.status_code}) -> {resp_verify.content}")
    else:
        print(f"FAILED: OTP Generate ({resp_send.status_code}) -> {resp_send.content}")

    client.logout()

    # ---------------------------------------------------------
    # TEST 3: MAGIC LINK URL
    # ---------------------------------------------------------
    print("\n[TEST 3] Magic Link Flow")
    
    # Generate a fresh token for magic link test
    token_obj = LoginToken.create_for_user(user)
    
    # Simulate Email Click (GET Request)
    resp_magic = client.get(
        f'/services/magic/',
        {'email': email, 'code': token_obj.token, 'redirect_url': 'http://localhost:5173'}
    )
    
    # We expect a 302 Redirect to the frontend and session injection
    if resp_magic.status_code == 302:
        cookies = resp_magic.client.cookies
        print("SUCCESS: Magic Link redirected properly")
        print(f"SUCCESS: Redirected to: {resp_magic.url}")
        print(f"SUCCESS: sessionid cookie attached: {bool(cookies.get('sessionid'))}")
    else:
        print(f"FAILED: Magic Link ({resp_magic.status_code}) -> {resp_magic.content}")

    # Cleanup
    user.delete()
    print("\nEnvironment cleanup complete.")

if __name__ == '__main__':
    run_tests()
