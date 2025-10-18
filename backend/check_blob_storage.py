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
    
    args = parser.parse_args()
    
    if not any([args.check_connection, args.list_all, args.resource_id]):
        parser.print_help()
        return
    
    checker = BlobStorageChecker()
    
    if args.check_connection:
        checker.check_connection()
    
    if args.list_all:
        checker.list_all_blobs()
    
    if args.resource_id:
        checker.check_resource(args.resource_id)


if __name__ == '__main__':
    main()
