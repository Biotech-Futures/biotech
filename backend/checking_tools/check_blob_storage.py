#!/usr/bin/env python
"""
Azure Blob Storage Checker for Bio Company Resources

This script helps verify that files uploaded to the resources system
are properly stored in Azure blob storage and can be accessed.

Usage:
    python check_blob_storage.py --check-connection
    python check_blob_storage.py --list-all
    python check_blob_storage.py --resource-id 123
"""

import os
import sys
import django
from datetime import datetime
import argparse

# Setup Django environment
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.resources.models import Resources
from storages.backends.azure_storage import AzureStorage
from django.conf import settings


class BlobStorageChecker:
    def __init__(self):
        self.storage = AzureStorage()
        self.container_name = settings.AZURE_CONTAINER
        self.account_name = settings.AZURE_ACCOUNT_NAME
        
    def check_connection(self):
        """Test Azure blob storage connection"""
        print("=== Azure Blob Storage Checker ===")
        print("Testing Azure connection...")
        
        try:
            # Test basic connection
            dirs, files = self.storage.listdir('')
            print(f"✓ Connection successful!")
            print(f"  Account: {self.account_name}")
            print(f"  Container: {self.container_name}")
            
            # Get container info
            try:
                # Try to get container info using the storage backend
                container_info = self.storage.container_client if hasattr(self.storage, 'container_client') else None
                if container_info:
                    properties = container_info.get_container_properties()
                    last_modified = properties.last_modified
                    print(f"  Last Modified: {last_modified}")
                else:
                    print(f"  Note: Container properties not available")
            except Exception as e:
                print(f"  Note: Could not get container properties: {e}")
            
            # Count resources in database
            total_resources = Resources.objects.count()
            resources_with_files = Resources.objects.exclude(resource_file='').count()
            
            print(f"\nResources in DB:")
            print(f"  Total: {total_resources}")
            print(f"  With files: {resources_with_files}")
            print(f"  Without files: {total_resources - resources_with_files}")
            
            return True
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def list_all_blobs(self):
        """List all blobs in the container and check against database"""
        print("=== Azure Blob Storage Checker ===")
        print("Listing all blobs in container...")
        
        try:
            # Get all files from Azure storage
            all_dirs, all_files = self.storage.listdir('')
            
            # Filter for resource files
            resource_files = [f for f in all_files if f.startswith('resources/')]
            
            if not resource_files:
                print("No files found in resources/ folder")
                return
            
            print(f"Found {len(resource_files)} file(s):")
            
            # Get all resources from database
            db_resources = {}
            for resource in Resources.objects.exclude(resource_file=''):
                if resource.resource_file:
                    db_resources[resource.resource_file.name] = resource
            
            total_size = 0
            missing_files = []
            
            for file_path in resource_files:
                # Get file size from storage
                try:
                    file_size = self.storage.size(file_path)
                except:
                    file_size = 0
                
                total_size += file_size
                
                # Check if file exists in database
                if file_path in db_resources:
                    resource = db_resources[file_path]
                    print(f"  • {file_path}")
                    print(f"    Size: {self._format_size(file_size)}")
                    print(f"    Modified: {resource.upload_datetime}")
                    print(f"    ✓ Resource #{resource.id}: {resource.resource_name}")
                else:
                    print(f"  • {file_path}")
                    print(f"    Size: {self._format_size(file_size)}")
                    print(f"    ✗ NOT IN DATABASE (orphaned file)")
            
            print(f"\nTotal storage used: {self._format_size(total_size)}")
            
            # Check for missing files (in DB but not in storage)
            for db_path, resource in db_resources.items():
                if db_path not in resource_files:
                    missing_files.append(db_path)
            
            if missing_files:
                print(f"\n⚠️  Found {len(missing_files)} missing file(s) (in DB but not in storage)")
                for missing in missing_files[:5]:  # Show first 5
                    print(f"    - {missing}")
                if len(missing_files) > 5:
                    print(f"    ... and {len(missing_files) - 5} more")
                                                
        except Exception as e:
            print(f"Error listing blobs: {e}")
            return
    
    def check_resource(self, resource_id):
        """Check a specific resource's file in blob storage"""
        print("=== Azure Blob Storage Checker ===")
        
        try:
            resource = Resources.objects.get(id=resource_id)
        except Resources.DoesNotExist:
            print(f"✗ Resource #{resource_id} not found in database")
            return
        
        print(f"Resource #{resource_id}: {resource.resource_name}")
        print(f"  Description: {resource.resource_description}")
        print(f"  Uploaded by: {resource.uploader_user_id.email if resource.uploader_user_id else 'Unknown'}")
        print(f"  Upload date: {resource.upload_datetime}")
        print()
        
        if not resource.resource_file:
            print("  ✗ No file associated with this resource")
            return
        
        file_path = resource.resource_file.name
        print(f"  File path: {file_path}")
        print(f"  File size: {resource.file_size} bytes")
        print(f"  Content type: {resource.content_type}")
        print()
        
        # Check if file exists in blob storage
        try:
            exists = self.storage.exists(file_path)
            if exists:
                print("✓ File EXISTS in blob storage")
                
                # Get blob properties using Django storage
                try:
                    # Get file size from storage
                    file_size = self.storage.size(file_path)
                    print(f"  Blob size: {file_size} bytes")
                    print(f"  Content type: {resource.content_type}")
                    print(f"  Last modified: {resource.upload_datetime}")
                    print()
                    print("  Download URL:")
                    print(f"  {resource.resource_file.url}")
                    
                except Exception as e:
                    print(f"  Note: Could not get blob properties: {e}")
                    print(f"  Download URL: {resource.resource_file.url}")
            else:
                print("✗ File DOES NOT EXIST in blob storage")
                print("  The database has a reference but the file is missing!")
                
        except Exception as e:
            print(f"✗ Error checking file: {e}")
    
    def delete_file(self, file_path):
        """Delete a specific file from blob storage"""
        print("=== Azure Blob Storage Checker ===")
        print(f"Deleting file: {file_path}")
        
        try:
            # Check if file exists
            if not self.storage.exists(file_path):
                print(f"✗ File does not exist: {file_path}")
                return False
            
            # Delete the file
            self.storage.delete(file_path)
            print(f"✓ File deleted successfully: {file_path}")
            return True
            
        except Exception as e:
            print(f"✗ Error deleting file: {e}")
            return False
    
    def delete_orphaned_files(self):
        """Delete files that exist in blob storage but not in database"""
        print("=== Azure Blob Storage Checker ===")
        print("Finding and deleting orphaned files...")
        
        try:
            # Get all files from Azure storage
            all_dirs, all_files = self.storage.listdir('')
            resource_files = [f for f in all_files if f.startswith('resources/')]
            
            # Get all resources from database
            db_resources = set()
            for resource in Resources.objects.exclude(resource_file=''):
                if resource.resource_file:
                    db_resources.add(resource.resource_file.name)
            
            orphaned_files = []
            for file_path in resource_files:
                if file_path not in db_resources:
                    orphaned_files.append(file_path)
            
            if not orphaned_files:
                print("✓ No orphaned files found")
                return
            
            print(f"Found {len(orphaned_files)} orphaned file(s):")
            for file_path in orphaned_files:
                print(f"  • {file_path}")
            
            # Ask for confirmation
            response = input("\nDo you want to delete these orphaned files? (y/N): ")
            if response.lower() in ['y', 'yes']:
                deleted_count = 0
                for file_path in orphaned_files:
                    if self.storage.delete(file_path):
                        print(f"✓ Deleted: {file_path}")
                        deleted_count += 1
                    else:
                        print(f"✗ Failed to delete: {file_path}")
                
                print(f"\n✓ Deleted {deleted_count} orphaned file(s)")
            else:
                print("Deletion cancelled")
                
        except Exception as e:
            print(f"Error: {e}")
    
    def delete_all_files(self):
        """⚠️ DANGER: Delete ALL files in blob storage (temporary command)"""
        print("=== ⚠️  DANGER: DELETE ALL FILES ⚠️  ===")
        print("This will delete ALL files in your Azure blob storage!")
        print("This action CANNOT be undone!")
        print()
        
        try:
            # Get all files from Azure storage
            all_dirs, all_files = self.storage.listdir('')
            resource_files = [f for f in all_files if f.startswith('resources/')]
            
            if not resource_files:
                print("✓ No files found to delete")
                return
            
            print(f"Found {len(resource_files)} file(s) to delete:")
            for file_path in resource_files:
                print(f"  • {file_path}")
            
            print()
            print("⚠️  WARNING: This will delete ALL files in blob storage!")
            print("⚠️  Make sure you have backups if needed!")
            print()
            
            # Double confirmation
            response1 = input("Type 'DELETE ALL' to confirm (case sensitive): ")
            if response1 != 'DELETE ALL':
                print("Deletion cancelled - confirmation text did not match")
                return
            
            response2 = input("Are you absolutely sure? Type 'YES' to proceed: ")
            if response2 != 'YES':
                print("Deletion cancelled - second confirmation failed")
                return
            
            print("\n🗑️  Deleting all files...")
            deleted_count = 0
            failed_count = 0
            
            for file_path in resource_files:
                try:
                    if self.storage.delete(file_path):
                        print(f"✓ Deleted: {file_path}")
                        deleted_count += 1
                    else:
                        print(f"✗ Failed to delete: {file_path}")
                        failed_count += 1
                except Exception as e:
                    print(f"✗ Error deleting {file_path}: {e}")
                    failed_count += 1
            
            print(f"\n📊 Deletion Summary:")
            print(f"  ✓ Successfully deleted: {deleted_count} files")
            print(f"  ✗ Failed to delete: {failed_count} files")
            print(f"  📁 Total files processed: {len(resource_files)}")
            
            if deleted_count > 0:
                print(f"\n⚠️  {deleted_count} files have been permanently deleted from Azure blob storage!")
                
        except Exception as e:
            print(f"Error: {e}")
    
    def _format_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0.00 MB"
        
        size_mb = size_bytes / (1024 * 1024)
        if size_mb < 1:
            return f"{size_bytes} bytes"
        else:
            return f"{size_mb:.2f} MB"


def main():
    parser = argparse.ArgumentParser(description='Azure Blob Storage Checker for Bio Company Resources')
    parser.add_argument('--check-connection', action='store_true', 
                       help='Test Azure blob storage connection')
    parser.add_argument('--list-all', action='store_true',
                       help='List all blobs in container and check against database')
    parser.add_argument('--resource-id', type=int,
                       help='Check a specific resource ID')
    parser.add_argument('--delete-file', type=str,
                       help='Delete a specific file by path (e.g., "resources/2025/10/16/file.txt")')
    parser.add_argument('--delete-orphaned', action='store_true',
                       help='Delete orphaned files (files in storage but not in database)')
    parser.add_argument('--delete-all', action='store_true',
                       help='⚠️ DANGER: Delete ALL files in blob storage (requires double confirmation)')
    
    args = parser.parse_args()
    
    if not any([args.check_connection, args.list_all, args.resource_id, args.delete_file, args.delete_orphaned, args.delete_all]):
        parser.print_help()
        return
    
    checker = BlobStorageChecker()
    
    if args.check_connection:
        checker.check_connection()
    
    if args.list_all:
        checker.list_all_blobs()
    
    if args.resource_id:
        checker.check_resource(args.resource_id)
    
    if args.delete_file:
        checker.delete_file(args.delete_file)
    
    if args.delete_orphaned:
        checker.delete_orphaned_files()
    
    if args.delete_all:
        checker.delete_all_files()


if __name__ == '__main__':
    main()
