#!/usr/bin/env python3
"""
Check User Password Script

This script checks and resets user passwords for testing purposes.
"""

import os
import sys
import django

# Setup Django
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from apps.resources.models import RoleAssignmentHistory
from django.utils import timezone

User = get_user_model()

def check_and_reset_user_password(email, new_password='student123'):
    """Check user password and reset if needed"""
    print(f"=== CHECKING PASSWORD FOR {email} ===")
    
    try:
        user = User.objects.get(email=email)
        print(f"✓ User found: {user.email}")
        print(f"  ID: {user.id}")
        print(f"  Is Staff: {user.is_staff}")
        print(f"  Is Active: {user.is_active}")
        print(f"  Date Joined: {user.date_joined}")
        
        # Check current password
        current_password_works = check_password(new_password, user.password)
        print(f"  Current password '{new_password}' works: {current_password_works}")
        
        if not current_password_works:
            print(f"  ✗ Password '{new_password}' doesn't work")
            print(f"  🔧 Resetting password to '{new_password}'...")
            user.set_password(new_password)
            user.save()
            print(f"  ✓ Password reset successfully")
        else:
            print(f"  ✓ Password '{new_password}' is correct")
        
        # Check user's roles
        now = timezone.now()
        active_roles = RoleAssignmentHistory.objects.filter(
            user=user,
            valid_from__lte=now,
            valid_to__isnull=True
        )
        
        print(f"\n🎭 Active Roles:")
        if active_roles:
            for role_hist in active_roles:
                print(f"  - {role_hist.role.role_name}")
        else:
            print("  - No active roles")
        
        # Test login
        print(f"\n🧪 Testing login...")
        from django.test import Client
        client = Client()
        login_success = client.login(email=email, password=new_password)
        print(f"  Login test result: {login_success}")
        
        if login_success:
            print(f"  ✓ Login successful with password '{new_password}'")
        else:
            print(f"  ✗ Login failed with password '{new_password}'")
        
        return login_success
        
    except User.DoesNotExist:
        print(f"✗ User {email} not found in database")
        return False

def main():
    """Main function"""
    if len(sys.argv) > 1:
        email = sys.argv[1]
        password = sys.argv[2] if len(sys.argv) > 2 else 'student123'
        check_and_reset_user_password(email, password)
    else:
        print("Usage: python check_user_password.py <email> [password]")
        print("\nExamples:")
        print("  python check_user_password.py student@test.com")
        print("  python check_user_password.py student@test.com mypassword")
        print("  python check_user_password.py studenttest@gmail.com")

if __name__ == "__main__":
    main()
