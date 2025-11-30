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
    python check_role_status.py --all        # Show all users and their roles
    python check_role_status.py --credentials # Show user credentials for API testing
    python check_role_status.py               # Show available roles

Examples:
    python check_role_status.py 1             # Check user with ID 1
    python check_role_status.py 5             # Check user with ID 5
    python check_role_status.py --all        # Show all users and their roles
    python check_role_status.py --credentials # Show credentials for Postman testing

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
# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
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

def show_all_users_and_roles():
    """Show all users and their current roles"""
    print(f"\n=== ALL USERS AND THEIR ROLES ===")
    
    users = User.objects.all().order_by('id')
    total_users = users.count()
    
    print(f"Total users: {total_users}")
    print("=" * 80)
    
    for user in users:
        print(f"\n👤 User ID {user.id}: {user.email}")
        print(f"   Name: {user.first_name} {user.last_name}")
        print(f"   Staff: {user.is_staff} | Active: {user.is_active}")
        
        # Current Django Groups
        groups = user.groups.all()
        if groups:
            group_names = [group.name for group in groups]
            print(f"   Django Groups: {', '.join(group_names)}")
        else:
            print(f"   Django Groups: None")
        
        # Current Active Roles
        active_roles = RoleAssignmentHistory.objects.filter(
            user=user, 
            valid_from__lte=timezone.now(),
            valid_to__isnull=True
        )
        
        if active_roles:
            role_names = [role_hist.role.role_name for role_hist in active_roles]
            print(f"   Active Roles: {', '.join(role_names)}")
        else:
            print(f"   Active Roles: None")
        
        # Total role assignments (including historical)
        total_assignments = RoleAssignmentHistory.objects.filter(user=user).count()
        print(f"   Total Role Assignments: {total_assignments}")
        
        print("-" * 80)
    
    # Summary statistics
    print(f"\n📊 SUMMARY STATISTICS:")
    
    # Users with active roles
    users_with_roles = User.objects.filter(
        roleassignmenthistory__valid_from__lte=timezone.now(),
        roleassignmenthistory__valid_to__isnull=True
    ).distinct().count()
    
    # Users with Django groups
    users_with_groups = User.objects.filter(groups__isnull=False).distinct().count()
    
    # Staff users
    staff_users = User.objects.filter(is_staff=True).count()
    
    print(f"   Users with active roles: {users_with_roles}")
    print(f"   Users with Django groups: {users_with_groups}")
    print(f"   Staff users: {staff_users}")
    print(f"   Regular users: {total_users - staff_users}")
    
    # Role distribution
    print(f"\n🎭 ROLE DISTRIBUTION:")
    role_stats = RoleAssignmentHistory.objects.filter(
        valid_from__lte=timezone.now(),
        valid_to__isnull=True
    ).values('role__role_name').annotate(
        count=models.Count('user', distinct=True)
    ).order_by('-count')
    
    for stat in role_stats:
        print(f"   {stat['role__role_name']}: {stat['count']} users")

def show_user_credentials():
    """Show user credentials for API testing"""
    print(f"\n=== USER CREDENTIALS FOR API TESTING ===")
    print("Use these credentials in Postman or curl for API testing:")
    print("=" * 80)
    
    users = User.objects.all().order_by('id')
    
    for user in users:
        # Get user's active roles for context
        active_roles = RoleAssignmentHistory.objects.filter(
            user=user, 
            valid_from__lte=timezone.now(),
            valid_to__isnull=True
        )
        
        role_names = [role_hist.role.role_name for role_hist in active_roles]
        roles_str = ', '.join(role_names) if role_names else 'No roles'
        
        # Map known test passwords
        test_passwords = {
            'admin@admin.com': 'admin123',
            'test@gmail.com': 'test123',
            'student@test.com': 'student123',
            'admin@test.com': 'admin123',
            'student@gmail.com': 'student123',
        }
        
        password = test_passwords.get(user.email, '[Unknown - check Django admin]')
        
        print(f"\n👤 User ID {user.id}: {user.email}")
        print(f"   Name: {user.first_name} {user.last_name}")
        print(f"   Email: {user.email}")
        print(f"   Password: {password}")
        print(f"   Staff: {user.is_staff} | Active: {user.is_active}")
        print(f"   Roles: {roles_str}")
        print("-" * 80)
    
if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            show_all_users_and_roles()
        elif sys.argv[1] == "--credentials":
            show_user_credentials()
        else:
            try:
                user_id = int(sys.argv[1])
                check_user_roles(user_id)
            except ValueError:
                print("Error: Please provide a valid user ID or use --all or --credentials")
                print("Usage: python check_role_status.py <user_id>")
                print("       python check_role_status.py --all")
                print("       python check_role_status.py --credentials")
    else:
        print("Usage: python check_role_status.py <user_id>")
        print("       python check_role_status.py --all")
        print("       python check_role_status.py --credentials")
        print("\nAvailable roles:")
        list_all_roles()