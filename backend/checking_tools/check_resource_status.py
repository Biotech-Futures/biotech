#!/usr/bin/env python3
"""
Resource Status Checker 

This script provides comprehensive resource status checking for the Django Resource Management system.
It examines resource details, access permissions, upload history, and role-based visibility.

What it checks:
1. Resource Details
   - Basic resource information (name, description, upload date)
   - Uploader information
   - Deletion status and history

2. Resource Access Permissions
   - Which roles can access this resource
   - Role-based visibility settings
   - Access control configuration

3. Resource History & Status
   - Upload and deletion timestamps
   - Current status (active/deleted)
   - Resource lifecycle information

4. User Resource Access
   - What resources a user can access based on their roles
   - Resource visibility for specific users
   - Permission verification

Usage:
    python check_resource_status.py <resource_id>     # Check specific resource
    python check_resource_status.py user <user_id>    # Check user's accessible resources
    python check_resource_status.py                   # Show available resources

Examples:
    python check_resource_status.py 1                 # Check resource with ID 1
    python check_resource_status.py user 5           # Check resources accessible to user 5
    python check_resource_status.py                  # List all resources

This tool is useful for:
- Debugging resource access issues
- Verifying role-based permissions work correctly
- Understanding resource visibility and access control
- Troubleshooting resource management problems
- Auditing resource permissions
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.resources.models import Resources, ResourceRoles, Roles, RoleAssignmentHistory
from django.contrib.auth.models import Group

User = get_user_model()

def check_resource_details(resource_id):
    """Check detailed information for a specific resource"""
    try:
        resource = Resources.objects.get(id=resource_id)
        print(f"\n=== RESOURCE STATUS FOR ID {resource_id} ===")
        
        # 1. Basic Resource Information
        print(f"\n1. RESOURCE DETAILS:")
        print(f"   ID: {resource.id}")
        print(f"   Name: {resource.resource_name or 'No name provided'}")
        print(f"   Description: {resource.resource_description}")
        print(f"   Upload Date: {resource.upload_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Status: {'DELETED' if resource.deleted_flag else 'ACTIVE'}")
        if resource.deleted_datetime:
            print(f"   Deleted Date: {resource.deleted_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 2. Uploader Information
        print(f"\n2. UPLOADER INFORMATION:")
        uploader = resource.uploader_user_id
        print(f"   Uploader ID: {uploader.id}")
        print(f"   Uploader Email: {uploader.email}")
        print(f"   Uploader Name: {uploader.first_name} {uploader.last_name}")
        print(f"   Is Staff: {uploader.is_staff}")
        print(f"   Is Active: {uploader.is_active}")
        
        # 3. Resource Access Permissions (Role-based)
        print(f"\n3. ACCESS PERMISSIONS:")
        resource_roles = ResourceRoles.objects.filter(resource=resource)
        if resource_roles:
            print("   Roles that can access this resource:")
            for rr in resource_roles:
                print(f"   - {rr.role.role_name} (ID: {rr.role.id})")
        else:
            print("   - No specific role restrictions (accessible to all authenticated users)")
        
        # 4. Resource Status Summary
        print(f"\n4. STATUS SUMMARY:")
        if resource.deleted_flag:
            print("   ⚠️  RESOURCE IS DELETED")
            print(f"   Deleted on: {resource.deleted_datetime}")
        else:
            print("   ✅ RESOURCE IS ACTIVE")
            print(f"   Uploaded: {resource.upload_datetime}")
            if resource_roles:
                print(f"   Access Level: Role-restricted ({len(resource_roles)} roles)")
            else:
                print("   Access Level: Public (all authenticated users)")
                
    except Resources.DoesNotExist:
        print(f"Resource with ID {resource_id} not found")

def check_user_accessible_resources(user_id):
    """Check what resources a user can access based on their roles"""
    try:
        user = User.objects.get(id=user_id)
        print(f"\n=== ACCESSIBLE RESOURCES FOR USER {user_id} ({user.email}) ===")
        
        # 1. User's Current Roles
        print(f"\n1. USER'S CURRENT ROLES:")
        active_roles = RoleAssignmentHistory.objects.filter(
            user=user, 
            valid_from__lte=timezone.now(),
            valid_to__isnull=True
        )
        if active_roles:
            user_role_names = []
            for role_hist in active_roles:
                role_name = role_hist.role.role_name
                user_role_names.append(role_name)
                print(f"   - {role_name} (since {role_hist.valid_from.strftime('%Y-%m-%d')})")
        else:
            print("   - No active roles")
            user_role_names = []
        
        # 2. Accessible Resources
        print(f"\n2. ACCESSIBLE RESOURCES:")
        accessible_resources = []
        
        # Get all active (non-deleted) resources
        all_resources = Resources.objects.filter(deleted_flag=False)
        
        for resource in all_resources:
            # Check if resource has role restrictions
            resource_roles = ResourceRoles.objects.filter(resource=resource)
            
            if not resource_roles:
                # No role restrictions - accessible to all authenticated users
                accessible_resources.append(resource)
                print(f"   ✅ {resource.resource_name or f'Resource {resource.id}'} (Public)")
            else:
                # Check if user has any of the required roles
                required_role_names = [rr.role.role_name for rr in resource_roles]
                if any(role in user_role_names for role in required_role_names):
                    accessible_resources.append(resource)
                    matching_roles = [role for role in user_role_names if role in required_role_names]
                    print(f"   ✅ {resource.resource_name or f'Resource {resource.id}'} (Roles: {', '.join(matching_roles)})")
                else:
                    print(f"   ❌ {resource.resource_name or f'Resource {resource.id}'} (Missing roles: {', '.join(required_role_names)})")
        
        # 3. Summary
        print(f"\n3. ACCESS SUMMARY:")
        print(f"   Total Resources: {len(all_resources)}")
        print(f"   Accessible to User: {len(accessible_resources)}")
        print(f"   Restricted: {len(all_resources) - len(accessible_resources)}")
        
        if not user_role_names:
            print("   ⚠️  User has no active roles - can only access public resources")
        
    except User.DoesNotExist:
        print(f"User with ID {user_id} not found")

def list_all_resources():
    """List all available resources with basic info"""
    print(f"\n=== ALL RESOURCES ===")
    resources = Resources.objects.all().order_by('-upload_datetime')
    
    if not resources:
        print("   No resources found")
        return
    
    for resource in resources:
        status = "DELETED" if resource.deleted_flag else "ACTIVE"
        name = resource.resource_name or f"Resource {resource.id}"
        
        # Get role restrictions
        resource_roles = ResourceRoles.objects.filter(resource=resource)
        if resource_roles:
            role_names = [rr.role.role_name for rr in resource_roles]
            access_info = f"Roles: {', '.join(role_names)}"
        else:
            access_info = "Public"
        
        print(f"   ID {resource.id}: {name} ({status}) - {access_info}")
        print(f"      Uploaded: {resource.upload_datetime.strftime('%Y-%m-%d %H:%M')} by {resource.uploader_user_id.email}")

def show_resource_statistics():
    """Show overall resource statistics"""
    print(f"\n=== RESOURCE STATISTICS ===")
    
    total_resources = Resources.objects.count()
    active_resources = Resources.objects.filter(deleted_flag=False).count()
    deleted_resources = Resources.objects.filter(deleted_flag=True).count()
    
    print(f"   Total Resources: {total_resources}")
    print(f"   Active Resources: {active_resources}")
    print(f"   Deleted Resources: {deleted_resources}")
    
    # Role-based access statistics
    public_resources = Resources.objects.filter(
        deleted_flag=False,
        resourceroles__isnull=True
    ).distinct().count()
    
    role_restricted_resources = Resources.objects.filter(
        deleted_flag=False,
        resourceroles__isnull=False
    ).distinct().count()
    
    print(f"   Public Resources: {public_resources}")
    print(f"   Role-Restricted Resources: {role_restricted_resources}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "user" and len(sys.argv) > 2:
            user_id = int(sys.argv[2])
            check_user_accessible_resources(user_id)
        else:
            resource_id = int(sys.argv[1])
            check_resource_details(resource_id)
    else:
        print("Usage:")
        print("  python check_resource_status.py <resource_id>     # Check specific resource")
        print("  python check_resource_status.py user <user_id>    # Check user's accessible resources")
        print("  python check_resource_status.py                   # Show all resources")
        print("\nAvailable resources:")
        list_all_resources()
        show_resource_statistics()
