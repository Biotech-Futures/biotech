"""
Comprehensive tests for resource file uploading functionality.

This module contains tests for various aspects of file upload validation, security, and storage.
"""

import os
import tempfile
from django.test import TestCase
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.resources.models import Resources, ResourceType, Roles, ResourceRoles
from apps.resources.serializers import ResourcesSerializer

User = get_user_model()


class ResourceUploadTests(TestCase):
    """Comprehensive tests for resource file uploading"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        self.regular_user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            first_name='Regular',
            last_name='User'
        )
        
        # Create test roles
        self.mentor_role = Roles.objects.create(role_name='mentor')
        self.student_role = Roles.objects.create(role_name='student')
        self.admin_role = Roles.objects.create(role_name='admin')
        
        # Assign roles to users
        from apps.resources.models import RoleAssignmentHistory
        from django.utils import timezone
        
        now = timezone.now()
        
        # Admin user gets admin role
        RoleAssignmentHistory.objects.create(
            user=self.admin_user,
            role=self.admin_role,
            valid_from=now
        )
        
        # Regular user gets mentor role (so they can upload)
        RoleAssignmentHistory.objects.create(
            user=self.regular_user,
            role=self.mentor_role,
            valid_from=now
        )
        
        # Create resource types (use get_or_create for test compatibility)
        self.document_type, _ = ResourceType.objects.get_or_create(
            type_name='document',
            defaults={'type_description': 'Research documents, reports, protocols, and scientific papers'}
        )
        self.image_type, _ = ResourceType.objects.get_or_create(
            type_name='image',
            defaults={'type_description': 'Microscopy images, gel electrophoresis results, and scientific diagrams'}
        )
        self.video_type, _ = ResourceType.objects.get_or_create(
            type_name='video',
            defaults={'type_description': 'Training videos, lab demonstrations, and scientific presentations'}
        )
        self.guide_type, _ = ResourceType.objects.get_or_create(
            type_name='guide',
            defaults={'type_description': 'Laboratory protocols, standard operating procedures, and training guides'}
        )
        self.template_type, _ = ResourceType.objects.get_or_create(
            type_name='template',
            defaults={'type_description': 'Lab report templates, data collection forms, and protocol templates'}
        )
        
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

    def create_test_file(self, content, filename, content_type='text/plain'):
        """Helper to create test files"""
        return SimpleUploadedFile(filename, content.encode('utf-8'), content_type=content_type)

    # ===== 1. FILE TYPE VALIDATION TESTS =====
    
    def test_valid_file_types_auto_detection(self):
        """Test that valid file types are auto-detected correctly"""
        test_cases = [
            ('document.pdf', 'application/pdf', 'document'),
            ('protocol.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'document'),
            ('data.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'document'),
            ('presentation.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'document'),
            ('lab_guide.txt', 'text/plain', 'document'),
            ('microscopy.png', 'image/png', 'image'),
            ('gel_result.jpg', 'image/jpeg', 'image'),
            ('training.mp4', 'video/mp4', 'video'),
            ('demo.avi', 'video/x-msvideo', 'video'),
        ]
        
        for filename, content_type, expected_type in test_cases:
            with self.subTest(filename=filename):
                test_file = self.create_test_file('test content', filename, content_type)
                
                # Determine resource type based on expected type
                if expected_type == 'document':
                    resource_type_id = self.document_type.id
                elif expected_type == 'image':
                    resource_type_id = self.image_type.id
                elif expected_type == 'video':
                    resource_type_id = self.video_type.id
                else:
                    resource_type_id = self.document_type.id
                
                data = {
                    'resource_name': f'Test {filename}',
                    'resource_description': f'Testing {filename}',
                    'resource_file': test_file,
                    'resource_type_id': resource_type_id,
                    'role_ids': [self.mentor_role.id]
                }
                
                response = self.client.post('/resources/resource-files/', data, format='multipart')
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                
                # Verify auto-detected type
                resource = Resources.objects.get(resource_name=f'Test {filename}')
                self.assertEqual(resource.resource_type.type_name, expected_type)

    def test_invalid_file_types_rejected(self):
        """Test that invalid file types are rejected"""
        invalid_files = [
            ('script.py', 'text/x-python'),
            ('app.js', 'application/javascript'),
            ('style.css', 'text/css'),
            ('index.html', 'text/html'),
            ('database.sql', 'application/sql'),
            ('config.json', 'application/json'),
            ('archive.zip', 'application/zip'),
        ]
        
        for filename, content_type in invalid_files:
            with self.subTest(filename=filename):
                test_file = self.create_test_file('test content', filename, content_type)
                
                data = {
                    'resource_name': f'Test {filename}',
                    'resource_description': f'Testing {filename}',
                    'resource_file': test_file,
                    'resource_type_id': self.document_type.id,
                    'role_ids': [self.mentor_role.id]
                }
                
                response = self.client.post('/resources/resource-files/', data, format='multipart')
                # Should reject invalid file types with validation error
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('resource_file', response.data)

    def test_explicit_resource_type_override(self):
        """Test that explicitly provided resource_type overrides auto-detection"""
        # Upload a .txt file but specify it as a video
        test_file = self.create_test_file('test content', 'protocol.txt', 'text/plain')
        
        data = {
            'resource_name': 'Video Protocol',
            'resource_description': 'This should be a video despite .txt extension',
            'resource_file': test_file,
            'resource_type_id': self.video_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        # Should be rejected due to file type validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('resource_file', response.data)

    # ===== 2. FILE SIZE VALIDATION TESTS =====
    
    def test_normal_file_sizes(self):
        """Test that normal file sizes are accepted"""
        # Test small file
        small_file = self.create_test_file('small content', 'small.txt')
        data = {
            'resource_name': 'Small File',
            'resource_description': 'Testing small file',
            'resource_file': small_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        resource = Resources.objects.get(resource_name='Small File')
        self.assertEqual(resource.file_size, len('small content'))

    def test_empty_file_rejected(self):
        """Test that empty files are rejected"""
        empty_file = self.create_test_file('', 'empty.txt')
        data = {
            'resource_name': 'Empty File',
            'resource_description': 'Testing empty file',
            'resource_file': empty_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        # Empty files should be rejected
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ===== 3. REQUIRED FIELD TESTS =====
    
    def test_missing_resource_name(self):
        """Test that missing resource_name is rejected"""
        test_file = self.create_test_file('test content', 'test.txt')
        data = {
            'resource_description': 'Testing missing name',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('resource_name', response.data)

    def test_missing_resource_description(self):
        """Test that missing resource_description is rejected"""
        test_file = self.create_test_file('test content', 'test.txt')
        data = {
            'resource_name': 'Test Resource',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('resource_description', response.data)

    def test_missing_resource_file(self):
        """Test that missing resource_file is rejected"""
        data = {
            'resource_name': 'Test Resource',
            'resource_description': 'Testing missing file',
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('resource_file', response.data)

    def test_missing_role_ids(self):
        """Test that missing role_ids is allowed (optional field)"""
        test_file = self.create_test_file('test content', 'test.txt')
        data = {
            'resource_name': 'Test Resource',
            'resource_description': 'Testing missing roles',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        # role_ids is optional, so this should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ===== 4. AUTHENTICATION & AUTHORIZATION TESTS =====
    
    def test_no_authentication_rejected(self):
        """Test that requests without authentication are rejected"""
        self.client.force_authenticate(user=None)
        
        test_file = self.create_test_file('test content', 'test.txt')
        data = {
            'resource_name': 'Test Resource',
            'resource_description': 'Testing no auth',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_can_upload(self):
        """Test that regular users can upload files"""
        self.client.force_authenticate(user=self.regular_user)
        
        test_file = self.create_test_file('test content', 'test.txt')
        data = {
            'resource_name': 'User Upload',
            'resource_description': 'Testing user upload',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        resource = Resources.objects.get(resource_name='User Upload')
        self.assertEqual(resource.uploader_user_id, self.regular_user)

    # ===== 5. FILE CONTENT & SECURITY TESTS =====
    
    def test_suspicious_file_extensions(self):
        """Test files with potentially suspicious extensions"""
        suspicious_files = [
            ('script.exe', 'application/octet-stream'),
            ('malware.bat', 'application/octet-stream'),
            ('virus.com', 'application/octet-stream'),
        ]
        
        for filename, content_type in suspicious_files:
            with self.subTest(filename=filename):
                test_file = self.create_test_file('test content', filename, content_type)
                
                data = {
                    'resource_name': f'Test {filename}',
                    'resource_description': f'Testing {filename}',
                    'resource_file': test_file,
                    'resource_type_id': self.document_type.id,
                    'role_ids': [self.mentor_role.id]
                }
                
                response = self.client.post('/resources/resource-files/', data, format='multipart')
                # Should reject suspicious file types with validation error
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('resource_file', response.data)

    def test_long_filename(self):
        """Test files with very long filenames"""
        long_filename = 'a' * 50 + '.txt'  # Long filename (well under 100 char limit)
        test_file = self.create_test_file('test content', long_filename)
        
        data = {
            'resource_name': 'Long Filename Test',
            'resource_description': 'Testing long filename',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        # Should handle long filenames gracefully
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_special_characters_in_filename(self):
        """Test files with special characters in filename"""
        special_filenames = [
            'file with spaces.txt',
            'file-with-dashes.txt',
            'file_with_underscores.txt',
            'file.with.dots.txt',
            'file(with)parentheses.txt',
        ]
        
        for filename in special_filenames:
            with self.subTest(filename=filename):
                test_file = self.create_test_file('test content', filename)
                
                data = {
                    'resource_name': f'Test {filename}',
                    'resource_description': f'Testing {filename}',
                    'resource_file': test_file,
                    'resource_type_id': self.document_type.id,
                    'role_ids': [self.mentor_role.id]
                }
                
                response = self.client.post('/resources/resource-files/', data, format='multipart')
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ===== 6. DATABASE & STORAGE TESTS =====
    
    def test_resource_metadata_stored_correctly(self):
        """Test that resource metadata is stored correctly"""
        test_file = self.create_test_file('test content for metadata', 'metadata.txt')
        
        data = {
            'resource_name': 'Metadata Test',
            'resource_description': 'Testing metadata storage',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        resource = Resources.objects.get(resource_name='Metadata Test')
        
        # Verify metadata
        self.assertEqual(resource.resource_name, 'Metadata Test')
        self.assertEqual(resource.resource_description, 'Testing metadata storage')
        self.assertEqual(resource.file_size, len('test content for metadata'))
        self.assertEqual(resource.content_type, 'text/plain')
        self.assertEqual(resource.uploader_user_id, self.admin_user)
        self.assertIsNotNone(resource.upload_datetime)
        self.assertFalse(resource.deleted_flag)

    def test_resource_roles_assigned_correctly(self):
        """Test that resource roles are assigned correctly"""
        test_file = self.create_test_file('test content', 'roles.txt')
        
        data = {
            'resource_name': 'Roles Test',
            'resource_description': 'Testing role assignment',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id, self.student_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        resource = Resources.objects.get(resource_name='Roles Test')
        assigned_roles = list(resource.resourceroles.values_list('role__role_name', flat=True))
        
        self.assertIn('mentor', assigned_roles)
        self.assertIn('student', assigned_roles)
        self.assertEqual(len(assigned_roles), 2)

    def test_file_url_generation(self):
        """Test that file URLs are generated correctly"""
        test_file = self.create_test_file('test content', 'url_test.txt')
        
        data = {
            'resource_name': 'URL Test',
            'resource_description': 'Testing URL generation',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify URL fields in response
        self.assertIn('resource_file', response.data)
        self.assertIn('file_url', response.data)
        self.assertIsNotNone(response.data['file_url'])
        
        # Verify URL contains expected components
        file_url = response.data['file_url']
        self.assertIn('btfuturesblobstorage.blob.core.windows.net', file_url)
        self.assertTrue(file_url.startswith('https://'))

    def test_serializer_validation_edge_cases(self):
        """Test serializer validation with edge cases"""
        # Test with None values
        serializer = ResourcesSerializer(data={
            'resource_name': None,
            'resource_description': 'Test',
            'role_ids': [1]
        })
        self.assertFalse(serializer.is_valid())
        
        # Test with empty strings
        serializer = ResourcesSerializer(data={
            'resource_name': '',
            'resource_description': '',
            'role_ids': []
        })
        self.assertFalse(serializer.is_valid())
        
        # Test with invalid role IDs
        test_file = self.create_test_file('test content', 'test.txt')
        serializer = ResourcesSerializer(data={
            'resource_name': 'Test',
            'resource_description': 'Test',
            'resource_file': test_file,
            'role_ids': [99999]  # Non-existent role
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('role_ids', serializer.errors)


class ResourceUploadPerformanceTests(TestCase):
    """Performance tests for resource uploading"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            is_staff=True
        )
        self.mentor_role = Roles.objects.create(role_name='mentor')
        self.admin_role = Roles.objects.create(role_name='admin')
        self.document_type = ResourceType.objects.get_or_create(
            type_name='document',
            defaults={'type_description': 'Research documents, reports, protocols, and scientific papers'}
        )[0]
        
        # Assign admin role to admin user
        from apps.resources.models import RoleAssignmentHistory
        from django.utils import timezone
        
        RoleAssignmentHistory.objects.create(
            user=self.admin_user,
            role=self.admin_role,
            valid_from=timezone.now()
        )
        
        self.client.force_authenticate(user=self.admin_user)

    def test_multiple_resources_creation(self):
        """Test creating multiple separate resources (one file per resource)"""
        results = []
        
        # Test creating multiple separate resources, each with one file
        for i in range(3):
            test_file = SimpleUploadedFile(f'resource_{i}.txt', f'content for resource {i}'.encode())
            data = {
                'resource_name': f'Resource {i}',
                'resource_description': f'Testing resource creation {i}',
                'resource_file': test_file,
                'resource_type_id': self.document_type.id,
                'role_ids': [self.mentor_role.id]
            }
            
            response = self.client.post('/resources/resource-files/', data, format='multipart')
            results.append((i, response.status_code))
        
        # Verify all resources were created successfully
        for file_num, status_code in results:
            self.assertEqual(status_code, status.HTTP_201_CREATED, f"Resource {file_num} creation failed")
        
        # Verify all resources were created in database
        self.assertEqual(Resources.objects.filter(resource_name__startswith='Resource ').count(), 3)


class ResourcePermissionTests(TestCase):
    """Comprehensive tests for role-based permissions on resource operations"""
    
    def setUp(self):
        """Set up test data with different user roles"""
        self.client = APIClient()
        
        # Create users with different roles
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
        
        self.supervisor_user = User.objects.create_user(
            email='supervisor@test.com',
            password='testpass123',
            first_name='Supervisor',
            last_name='User'
        )
        
        self.mentor_user = User.objects.create_user(
            email='mentor@test.com',
            password='testpass123',
            first_name='Mentor',
            last_name='User'
        )
        
        self.student_user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            first_name='Student',
            last_name='User'
        )
        
        # Create roles
        self.admin_role = Roles.objects.create(role_name='admin')
        self.supervisor_role = Roles.objects.create(role_name='supervisor')
        self.mentor_role = Roles.objects.create(role_name='mentor')
        self.student_role = Roles.objects.create(role_name='student')
        
        # Assign roles to users
        from apps.resources.models import RoleAssignmentHistory
        from django.utils import timezone
        
        now = timezone.now()
        
        # Admin user gets admin role
        RoleAssignmentHistory.objects.create(
            user=self.admin_user,
            role=self.admin_role,
            valid_from=now
        )
        
        # Supervisor user gets supervisor role
        RoleAssignmentHistory.objects.create(
            user=self.supervisor_user,
            role=self.supervisor_role,
            valid_from=now
        )
        
        # Mentor user gets mentor role
        RoleAssignmentHistory.objects.create(
            user=self.mentor_user,
            role=self.mentor_role,
            valid_from=now
        )
        
        # Student user gets student role
        RoleAssignmentHistory.objects.create(
            user=self.student_user,
            role=self.student_role,
            valid_from=now
        )
        
        # Create resource type
        self.document_type, _ = ResourceType.objects.get_or_create(
            type_name='document',
            defaults={'type_description': 'Research documents, reports, protocols, and scientific papers'}
        )
        
        # Create a test resource for PATCH/DELETE operations
        self.test_resource = Resources.objects.create(
            resource_name='Test Resource for Permissions',
            resource_description='A test resource for permission testing',
            resource_type=self.document_type,
            uploader_user_id=self.admin_user,
            file_size=100,
            content_type='text/plain'
        )

    def create_test_file(self, content, filename, content_type='text/plain'):
        """Helper to create test files"""
        return SimpleUploadedFile(filename, content.encode('utf-8'), content_type=content_type)

    # ===== STUDENT PERMISSION TESTS =====
    
    def test_student_cannot_create_resource(self):
        """Test that students cannot create resources"""
        print("\n=== Testing Student Create Permission (Should FAIL) ===")
        
        self.client.force_authenticate(user=self.student_user)
        
        test_file = self.create_test_file('test content', 'student_test.txt')
        data = {
            'resource_name': 'Student Test Resource',
            'resource_description': 'Testing student create permission',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.student_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        print(f"   Response status: {response.status_code}")
        print(f"   Response data: {response.data}")
        
        # Students should not be able to create resources
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_patch_resource(self):
        """Test that students cannot modify resources"""
        print("\n=== Testing Student PATCH Permission (Should FAIL) ===")
        
        self.client.force_authenticate(user=self.student_user)
        
        data = {
            'resource_name': 'Modified by Student',
            'resource_description': 'This should not be allowed'
        }
        
        response = self.client.patch(f'/resources/resource-files/{self.test_resource.id}/', data)
        print(f"   Response status: {response.status_code}")
        print(f"   Response data: {response.data}")
        
        # Students should not be able to modify resources
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_delete_resource(self):
        """Test that students cannot delete resources"""
        print("\n=== Testing Student DELETE Permission (Should FAIL) ===")
        
        self.client.force_authenticate(user=self.student_user)
        
        response = self.client.delete(f'/resources/resource-files/{self.test_resource.id}/')
        print(f"   Response status: {response.status_code}")
        print(f"   Response data: {response.data}")
        
        # Students should not be able to delete resources
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ===== MENTOR PERMISSION TESTS =====
    
    def test_mentor_can_create_resource(self):
        """Test that mentors can create resources"""
        print("\n=== Testing Mentor Create Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.mentor_user)
        
        test_file = self.create_test_file('mentor test content', 'mentor_test.txt')
        data = {
            'resource_name': 'Mentor Test Resource',
            'resource_description': 'Testing mentor create permission',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.mentor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        print(f"   Response status: {response.status_code}")
        
        # Mentors should be able to create resources
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify resource was created
        resource = Resources.objects.get(resource_name='Mentor Test Resource')
        self.assertEqual(resource.uploader_user_id, self.mentor_user)

    def test_mentor_can_patch_resource(self):
        """Test that mentors can modify resources"""
        print("\n=== Testing Mentor PATCH Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.mentor_user)
        
        data = {
            'resource_name': 'Modified by Mentor',
            'resource_description': 'This should be allowed for mentors'
        }
        
        response = self.client.patch(f'/resources/resource-files/{self.test_resource.id}/', data)
        print(f"   Response status: {response.status_code}")
        
        # Mentors should be able to modify resources
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify resource was modified
        self.test_resource.refresh_from_db()
        self.assertEqual(self.test_resource.resource_name, 'Modified by Mentor')

    def test_mentor_can_delete_resource(self):
        """Test that mentors can delete resources"""
        print("\n=== Testing Mentor DELETE Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.mentor_user)
        
        # Create a resource to delete
        test_resource = Resources.objects.create(
            resource_name='Mentor Delete Test',
            resource_description='A resource to test mentor delete permission',
            resource_type=self.document_type,
            uploader_user_id=self.mentor_user,
            file_size=100,
            content_type='text/plain'
        )
        
        response = self.client.delete(f'/resources/resource-files/{test_resource.id}/')
        print(f"   Response status: {response.status_code}")
        
        # Mentors should be able to delete resources
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify resource was soft deleted
        test_resource.refresh_from_db()
        self.assertTrue(test_resource.deleted_flag)

    # ===== SUPERVISOR PERMISSION TESTS =====
    
    def test_supervisor_can_create_resource(self):
        """Test that supervisors can create resources"""
        print("\n=== Testing Supervisor Create Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.supervisor_user)
        
        test_file = self.create_test_file('supervisor test content', 'supervisor_test.txt')
        data = {
            'resource_name': 'Supervisor Test Resource',
            'resource_description': 'Testing supervisor create permission',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.supervisor_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        print(f"   Response status: {response.status_code}")
        
        # Supervisors should be able to create resources
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_supervisor_can_patch_resource(self):
        """Test that supervisors can modify resources"""
        print("\n=== Testing Supervisor PATCH Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.supervisor_user)
        
        data = {
            'resource_name': 'Modified by Supervisor',
            'resource_description': 'This should be allowed for supervisors'
        }
        
        response = self.client.patch(f'/resources/resource-files/{self.test_resource.id}/', data)
        print(f"   Response status: {response.status_code}")
        
        # Supervisors should be able to modify resources
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_supervisor_can_delete_resource(self):
        """Test that supervisors can delete resources"""
        print("\n=== Testing Supervisor DELETE Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.supervisor_user)
        
        # Create a resource to delete
        test_resource = Resources.objects.create(
            resource_name='Supervisor Delete Test',
            resource_description='A resource to test supervisor delete permission',
            resource_type=self.document_type,
            uploader_user_id=self.supervisor_user,
            file_size=100,
            content_type='text/plain'
        )
        
        response = self.client.delete(f'/resources/resource-files/{test_resource.id}/')
        print(f"   Response status: {response.status_code}")
        
        # Supervisors should be able to delete resources
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # ===== ADMIN PERMISSION TESTS =====
    
    def test_admin_can_create_resource(self):
        """Test that admins can create resources"""
        print("\n=== Testing Admin Create Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.admin_user)
        
        test_file = self.create_test_file('admin test content', 'admin_test.txt')
        data = {
            'resource_name': 'Admin Test Resource',
            'resource_description': 'Testing admin create permission',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.admin_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        print(f"   Response status: {response.status_code}")
        
        # Admins should be able to create resources
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_can_patch_resource(self):
        """Test that admins can modify resources"""
        print("\n=== Testing Admin PATCH Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.admin_user)
        
        data = {
            'resource_name': 'Modified by Admin',
            'resource_description': 'This should be allowed for admins'
        }
        
        response = self.client.patch(f'/resources/resource-files/{self.test_resource.id}/', data)
        print(f"   Response status: {response.status_code}")
        
        # Admins should be able to modify resources
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_delete_resource(self):
        """Test that admins can delete resources"""
        print("\n=== Testing Admin DELETE Permission (Should PASS) ===")
        
        self.client.force_authenticate(user=self.admin_user)
        
        # Create a resource to delete
        test_resource = Resources.objects.create(
            resource_name='Admin Delete Test',
            resource_description='A resource to test admin delete permission',
            resource_type=self.document_type,
            uploader_user_id=self.admin_user,
            file_size=100,
            content_type='text/plain'
        )
        
        response = self.client.delete(f'/resources/resource-files/{test_resource.id}/')
        print(f"   Response status: {response.status_code}")
        
        # Admins should be able to delete resources
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # ===== UNAUTHENTICATED USER TESTS =====
    
    def test_unauthenticated_user_cannot_create_resource(self):
        """Test that unauthenticated users cannot create resources"""
        print("\n=== Testing Unauthenticated Create Permission (Should FAIL) ===")
        
        self.client.force_authenticate(user=None)
        
        test_file = self.create_test_file('unauth test content', 'unauth_test.txt')
        data = {
            'resource_name': 'Unauthenticated Test Resource',
            'resource_description': 'Testing unauthenticated create permission',
            'resource_file': test_file,
            'resource_type_id': self.document_type.id,
            'role_ids': [self.student_role.id]
        }
        
        response = self.client.post('/resources/resource-files/', data, format='multipart')
        print(f"   Response status: {response.status_code}")
        
        # Unauthenticated users should not be able to create resources
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_patch_resource(self):
        """Test that unauthenticated users cannot modify resources"""
        print("\n=== Testing Unauthenticated PATCH Permission (Should FAIL) ===")
        
        self.client.force_authenticate(user=None)
        
        data = {
            'resource_name': 'Modified by Unauthenticated User',
            'resource_description': 'This should not be allowed'
        }
        
        response = self.client.patch(f'/resources/resource-files/{self.test_resource.id}/', data)
        print(f"   Response status: {response.status_code}")
        
        # Unauthenticated users should not be able to modify resources
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_delete_resource(self):
        """Test that unauthenticated users cannot delete resources"""
        print("\n=== Testing Unauthenticated DELETE Permission (Should FAIL) ===")
        
        self.client.force_authenticate(user=None)
        
        response = self.client.delete(f'/resources/resource-files/{self.test_resource.id}/')
        print(f"   Response status: {response.status_code}")
        
        # Unauthenticated users should not be able to delete resources
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)