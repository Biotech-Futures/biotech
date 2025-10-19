#!/usr/bin/env python
"""
Standalone script to clean up test files from Azure blob storage.
This script will delete all files with 'test_oct_19' in the name from both Azure and the database.
"""

import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.resources.models import Resources
from storages.backends.azure_storage import AzureStorage

def cleanup_test_files():
    """Clean up all test files from Azure blob storage and database"""
    print("=== CLEANING UP TEST FILES FROM AZURE BLOB STORAGE ===")
    print()
    
    # Initialize Azure storage
    azure_storage = AzureStorage()
    
    # Get all test resources
    test_resources = Resources.objects.filter(
        resource_name__startswith='Test Oct 19 -'
    )
    
    print(f"Found {test_resources.count()} test resources in database")
    
    if test_resources.count() == 0:
        print("No test files found to clean up.")
        return
    
    # Confirm deletion
    print("\nTest files to be deleted:")
    for resource in test_resources:
        print(f"   • {resource.resource_name} ({resource.resource_file.name if resource.resource_file else 'No file'})")
    
    print(f"\n  WARNING: This will permanently delete {test_resources.count()} test resources and their files from Azure blob storage!")
    confirm = input("Type 'yes' to confirm deletion: ").strip().lower()
    
    if confirm != 'yes':
        print("Deletion cancelled.")
        return
    
    print("\nStarting cleanup...")
    
    deleted_count = 0
    failed_count = 0
    
    for resource in test_resources:
        try:
            # Delete file from Azure blob storage
            if resource.resource_file and azure_storage.exists(resource.resource_file.name):
                azure_storage.delete(resource.resource_file.name)
                print(f"   ✓ Deleted from Azure: {resource.resource_file.name}")
                deleted_count += 1
            else:
                print(f"   ⚠ File not found in Azure: {resource.resource_file.name if resource.resource_file else 'No file'}")
            
            # Delete resource from database
            resource_name = resource.resource_name
            resource.delete()
            print(f"   ✓ Deleted from database: {resource_name}")
            
        except Exception as e:
            print(f"   ✗ Failed to delete {resource.resource_name}: {e}")
            failed_count += 1
    
    print(f"\n=== CLEANUP SUMMARY ===")
    print(f"✓ Files deleted from Azure: {deleted_count}")
    print(f"✗ Failed deletions: {failed_count}")
    print(f"Total test resources processed: {test_resources.count()}")
    
    # Verify cleanup
    print(f"\n=== VERIFICATION ===")
    remaining_test_files = []
    try:
        dirs, files = azure_storage.listdir('')
        remaining_test_files = [f for f in files if f.startswith('resources/') and 'test_oct_19' in f]
        
        if remaining_test_files:
            print(f"⚠ Warning: {len(remaining_test_files)} test files still in Azure:")
            for file_path in remaining_test_files:
                print(f"   • {file_path}")
        else:
            print(f"✓ All test files successfully removed from Azure")
            
    except Exception as e:
        print(f"⚠ Could not verify cleanup: {e}")
    
    # Check database
    remaining_resources = Resources.objects.filter(
        resource_name__startswith='Test Oct 19 -'
    ).count()
    
    if remaining_resources == 0:
        print(f"✓ All test resources successfully removed from database")
    else:
        print(f"⚠ Warning: {remaining_resources} test resources still in database")
    
    print("\n=== CLEANUP COMPLETE ===")

if __name__ == '__main__':
    cleanup_test_files()
