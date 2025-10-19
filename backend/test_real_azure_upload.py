#!/usr/bin/env python
"""
Test script that uses the actual Django server to upload files to Azure.
This bypasses the test client and makes real HTTP requests.
"""

import os
import sys
import django
import requests
import json

# Setup Django
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import User
from apps.resources.models import Resources, ResourceType, Roles, RoleAssignmentHistory
from storages.backends.azure_storage import AzureStorage
from django.utils import timezone


def setup_test_data():
    """Set up test data in production database"""
    print("==========================================")
    print("Setting up test data...")
    
    # Create test users
    admin_user, _ = User.objects.get_or_create(
        email='admin@test.com',
        defaults={
            'is_staff': True,
            'first_name': 'Admin',
            'last_name': 'User'
        }
    )
    admin_user.set_password('testpass123')
    admin_user.save()
    
    # Create test roles
    mentor_role, _ = Roles.objects.get_or_create(role_name='mentor')
    admin_role, _ = Roles.objects.get_or_create(role_name='admin')
    
    # Assign roles to users
    now = timezone.now()
    RoleAssignmentHistory.objects.get_or_create(
        user=admin_user,
        role=admin_role,
        defaults={'valid_from': now}
    )
    
    # Create resource types
    document_type, _ = ResourceType.objects.get_or_create(
        type_name='document',
        defaults={'type_description': 'Research documents, reports, protocols, and scientific papers'}
    )
    
    return {
        'admin_user': admin_user,
        'mentor_role': mentor_role,
        'document_type': document_type
    }


def test_upload_via_server():
    """Test uploading files via the actual Django server"""
    print("==========================================")
    print("Testing Upload via Django Server")
    print("==========================================")
    
    # Setup test data
    test_data = setup_test_data()
    
    # Server URL (assuming Django server is running on localhost:8000)
    base_url = "http://localhost:8000"
    
    # First, get CSRF token
    print("==========================================")
    print("Getting CSRF token...")
    try:
        response = requests.get(f"{base_url}/admin/login/")
        if response.status_code != 200:
            print(f"ERROR: Failed to get CSRF token: {response.status_code}")
            return
        
        # Extract CSRF token from response
        csrf_token = None
        for line in response.text.split('\n'):
            if 'csrfmiddlewaretoken' in line and 'value=' in line:
                csrf_token = line.split('value="')[1].split('"')[0]
                break
        
        if not csrf_token:
            print("ERROR: Could not extract CSRF token")
            return
        
        print(f"SUCCESS: Got CSRF token: {csrf_token[:20]}...")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to Django server. Please start the server with:")
        print("   python manage.py runserver")
        return
    except Exception as e:
        print(f"ERROR: Error getting CSRF token: {e}")
        return
    
    # Login to get session
    print("==========================================")
    print("Logging in...")
    login_data = {
        'username': 'admin@test.com',
        'password': 'testpass123',
        'csrfmiddlewaretoken': csrf_token
    }
    
    session = requests.Session()
    session.cookies.update(response.cookies)
    
    try:
        login_response = session.post(f"{base_url}/admin/login/", data=login_data)
        if login_response.status_code != 200:
            print(f"ERROR: Login failed: {login_response.status_code}")
            return
        
        print("SUCCESS: Logged in successfully")
        
    except Exception as e:
        print(f"ERROR: Login error: {e}")
        return
    
    # Test multiple file uploads using Basic Authentication
    print("==========================================")
    print("Testing multiple file uploads with Basic Auth...")
    
    # Create resource types for testing
    image_type, _ = ResourceType.objects.get_or_create(
        type_name='image',
        defaults={'type_description': 'Microscopy images, gel electrophoresis results, and scientific diagrams'}
    )
    video_type, _ = ResourceType.objects.get_or_create(
        type_name='video',
        defaults={'type_description': 'Training videos, lab demonstrations, and scientific presentations'}
    )
    guide_type, _ = ResourceType.objects.get_or_create(
        type_name='guide',
        defaults={'type_description': 'Laboratory protocols, standard operating procedures, and training guides'}
    )
    template_type, _ = ResourceType.objects.get_or_create(
        type_name='template',
        defaults={'type_description': 'Lab report templates, data collection forms, and protocol templates'}
    )
    
    # Test cases for different file types
    test_cases = [
        # Document files
        ('test_real_azure_document.pdf', 'application/pdf', 'Real Azure PDF Document', test_data['document_type']),
        ('test_real_azure_document.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Real Azure Word Document', test_data['document_type']),
        ('test_real_azure_document.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Real Azure Excel Spreadsheet', test_data['document_type']),
        ('test_real_azure_document.txt', 'text/plain', 'Real Azure Text Document', test_data['document_type']),
        
        # Image files
        ('test_real_azure_image.png', 'image/png', 'Real Azure PNG Image', image_type),
        ('test_real_azure_image.jpg', 'image/jpeg', 'Real Azure JPEG Image', image_type),
        ('test_real_azure_image.gif', 'image/gif', 'Real Azure GIF Image', image_type),
        
        # Video files
        ('test_real_azure_video.mp4', 'video/mp4', 'Real Azure MP4 Video', video_type),
        ('test_real_azure_video.avi', 'video/x-msvideo', 'Real Azure AVI Video', video_type),
        
        # Guide files
        ('test_real_azure_guide.pdf', 'application/pdf', 'Real Azure PDF Guide', guide_type),
        ('test_real_azure_guide.txt', 'text/plain', 'Real Azure Text Guide', guide_type),
        
        # Template files
        ('test_real_azure_template.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Real Azure Word Template', template_type),
        ('test_real_azure_template.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Real Azure Excel Template', template_type),
    ]
    
    # Use Basic Authentication
    auth = ('admin@test.com', 'testpass123')
    
    uploaded_resources = []
    failed_uploads = []
    
    for filename, content_type, description, resource_type in test_cases:
        print(f"==========================================")
        print(f"Uploading: {filename}")
        
        # Create test file content
        test_content = f"This is a test {description} uploaded to Azure blob storage via real Django server"
        
        # Prepare multipart form data
        files = {
            'resource_file': (filename, test_content, content_type)
        }
        
        data = {
            'resource_name': f'Real Azure Test - {description}',
            'resource_description': f'Testing real upload to Azure via Django server - {description}',
            'resource_type_id': resource_type.id,
            'role_ids': [test_data['mentor_role'].id]
        }
        
        try:
            upload_response = requests.post(
                f"{base_url}/resources/resource-files/",
                files=files,
                data=data,
                auth=auth
            )
            
            print(f"   Upload response: {upload_response.status_code}")
            
            if upload_response.status_code == 201:
                print(f"   SUCCESS: {filename} uploaded successfully!")
                
                # Get the created resource
                resource = Resources.objects.get(resource_name=f'Real Azure Test - {description}')
                uploaded_resources.append(resource)
                
            else:
                print(f"   ERROR: {filename} upload failed: {upload_response.text}")
                failed_uploads.append((filename, upload_response.status_code, upload_response.text))
                
        except Exception as e:
            print(f"   ERROR: {filename} upload error: {e}")
            failed_uploads.append((filename, 'Exception', str(e)))
    
    # Summary of uploads
    print("==========================================")
    print("UPLOAD SUMMARY")
    print("==========================================")
    print(f"SUCCESS: {len(uploaded_resources)} files uploaded")
    print(f"FAILED: {len(failed_uploads)} files failed")
    
    if failed_uploads:
        print("\nFailed uploads:")
        for filename, status, error in failed_uploads:
            print(f"   • {filename}: {status} - {error}")
    
    # Check Azure storage for uploaded files
    if uploaded_resources:
        print("==========================================")
        print("VERIFYING AZURE STORAGE")
        print("==========================================")
        
        azure_storage = AzureStorage()
        azure_files = []
        missing_files = []
        
        for resource in uploaded_resources:
            if azure_storage.exists(resource.resource_file.name):
                azure_files.append(resource.resource_file.name)
                print(f"   ✓ {resource.resource_name}: {resource.resource_file.name}")
            else:
                missing_files.append(resource.resource_file.name)
                print(f"   ✗ {resource.resource_name}: {resource.resource_file.name} (MISSING)")
        
        print(f"\n   Azure Summary:")
        print(f"   ✓ Files in Azure: {len(azure_files)}")
        print(f"   ✗ Files missing: {len(missing_files)}")
        
        # Interactive cleanup
        print("==========================================")
        while True:
            try:
                response = input("Are you done checking Azure? Should I delete the test files now? (y/n): ").strip().lower()
                
                if response in ['yes', 'y']:
                    print("==========================================")
                    print("Starting cleanup...")
                    
                    deleted_count = 0
                    for resource in uploaded_resources:
                        try:
                            if azure_storage.exists(resource.resource_file.name):
                                azure_storage.delete(resource.resource_file.name)
                                print(f"   ✓ Deleted from Azure: {resource.resource_file.name}")
                            resource.delete()
                            print(f"   ✓ Deleted from database: {resource.resource_name}")
                            deleted_count += 1
                        except Exception as e:
                            print(f"   ✗ Failed to delete {resource.resource_name}: {e}")
                    
                    print(f"Cleanup completed: {deleted_count} files deleted")
                    break
                    
                elif response in ['no', 'n']:
                    print("==========================================")
                    print("Test files preserved. You can run cleanup later with:")
                    print("python checking_tools/check_blob_storage.py --delete-all")
                    break
                else:
                    print("Please enter 'y' or 'n'")
            except (EOFError, KeyboardInterrupt):
                print("==========================================")
                print("Test files preserved (interactive input not available)")
                break


def main():
    """Main test function"""
    print("==========================================")
    print("Testing Real Azure Upload via Django Server")
    print("==========================================")
    
    test_upload_via_server()


if __name__ == '__main__':
    main()
