#!/usr/bin/env python3
"""
Role Status Checker 

This script provides comprehensive role status checking for users in the Django RBAC system.
It examines both Django's built-in group system and the custom business logic role tracking.

What it checks:
1. Current Django Groups (Active Permissions)
   - Shows which Django groups the user belongs to
   - These groups control actual permissions in the system
   - Represents what the user can currently do

2. Current Active Roles (Business Logic)
   - Shows active roles from RoleAssignmentHistory table
   - These are the business domain roles (Student, Mentor, etc.)
   - Tracks role assignments with start/end dates

3. Complete Role History
   - Shows all role assignments for the user over time
   - Includes both active and historical roles
   - Displays start and end dates for each role assignment

Usage:
    python check_role_status.py <user_id>     # Check specific user
    python check_role_status.py               # Show available roles

Examples:
    python check_role_status.py 1             # Check user with ID 1
    python check_role_status.py 5             # Check user with ID 5

This tool is useful for:
- Debugging role assignment issues
- Verifying grant/revoke operations worked correctly
- Understanding user permissions and role history
- Troubleshooting RBAC system problems
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.resources.models import Roles, RoleAssignmentHistory
from django.contrib.auth.models import Group

User = get_user_model()

def check_user_roles(user_id):
    """Check all role information for a user"""
    try:
        user = User.objects.get(id=user_id)
        #================DISPLAY ROLE INFORMATION================
        print(f"\n=== ROLE STATUS FOR USER {user_id} ({user.email}) ===")

        #================DISPLAY USER INFORMATION, ONLY FOR DEBUGGING PURPOSES================
        print(f"\n=== ROLE STATUS FOR USER {user_id} ===")
        print(f"Email: {user.email}")
        print(f"First Name: {user.first_name}")
        print(f"Last Name: {user.last_name}")
        print(f"Username: {user.username}")
        print(f"Is Staff: {user.is_staff}")
        print(f"Is Active: {user.is_active}")
        print(f"Date Joined: {user.date_joined}")
        print(f"Last Login: {user.last_login}")
        #================DISPLAY USER INFORMATION, ONLY FOR DEBUGGING PURPOSES================

        # 1. Current Django Groups (active permissions)
        print(f"\n1. CURRENT DJANGO GROUPS (Active Permissions):")
        groups = user.groups.all()
        if groups:
            for group in groups:
                print(f"   - {group.name}")
        else:
            print("   - No groups assigned")
        
        # 2. Current Active Roles (from RoleAssignmentHistory)
        print(f"\n2. CURRENT ACTIVE ROLES (Business Logic):")
        active_roles = RoleAssignmentHistory.objects.filter(
            user=user, 
            valid_from__lte=timezone.now(),  # Role has started
            valid_to__isnull=True  # Role hasn't ended
        )
        if active_roles:
            for role_hist in active_roles:
                print(f"   - {role_hist.role.role_name} (since {role_hist.valid_from})")
        else:
            print("   - No active roles")
        
        # 3. All Role History
        print(f"\n3. ALL ROLE HISTORY:")
        all_roles = RoleAssignmentHistory.objects.filter(user=user).order_by('-valid_from')
        if all_roles:
            for role_hist in all_roles:
                end_date = role_hist.valid_to.strftime('%Y-%m-%d %H:%M') if role_hist.valid_to else 'ACTIVE'
                print(f"   - {role_hist.role.role_name}: {role_hist.valid_from.strftime('%Y-%m-%d %H:%M')} → {end_date}")
        else:
            print("   - No role history")
            
    except User.DoesNotExist:
        print(f"User with ID {user_id} not found")

def list_all_roles():
    """List all available roles"""
    print(f"\n=== ALL AVAILABLE ROLES ===")
    roles = Roles.objects.all()
    for role in roles:
        print(f"   ID {role.id}: {role.role_name}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])
        check_user_roles(user_id)
    else:
        print("Usage: python check_role_status.py <user_id>")
        print("\nAvailable roles:")
        list_all_roles()