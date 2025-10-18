# Mentor Management System

A Django-based mentor-student matching management system for automatically assigning student groups and mentors, with mentor management functionality.

## Project Overview

The system's main features include:
- Import student and mentor data from Excel files
- Automatically group students (based on pre-assigned group numbers and interest matching)
- Automatically assign mentors to groups
- Mentor replacement and account management
- Email notification functionality

## Environment Requirements

- Python 3.8+
- Django 4.2.23
- SQLite database (default)
- Other dependencies listed in `backend/requirements.txt`

## Quick Start

### 1. Environment Setup

```bash
# Clone the project (if from Git repository)
# git clone <repository-url>
# cd COMP5615_xinsheng_demo_mentorManage

# Navigate to backend directory
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Initialization

```bash
# Execute in backend directory
python manage.py migrate

# Create superuser (optional, for Django admin interface)
python manage.py createsuperuser
```

### 3. Import Test Data

```bash
# Import data from Excel file (using test data from project root)
python manage.py import_p11 "../P11 Test User Data.xlsx"
```

### 4. Start Service

```bash
# Start Django development server
python manage.py runserver

# Service will start at http://127.0.0.1:8000
```

## Feature Testing Guide

### 1. Basic Functionality Testing

#### 1.1 Health Check
Visit: http://127.0.0.1:8000/api/health/
Should return: `{"status": "ok", "service": "ws3-backend"}`

#### 1.2 Django Admin Interface
Visit: http://127.0.0.1:8000/admin/
Login with created superuser to view and manage:
- Students
- Mentors
- Student Groups
- Interest Tags

### 2. Core Functionality Testing

#### 2.1 Reset All Groups and Mentor Assignments

Use the `test.py` script in the project root:

```bash
# Execute in project root directory
python test.py
```

Or call the API directly:
```bash
curl -X POST "http://127.0.0.1:8000/api/reset_groups/?mode=delete_all&reset_seq=1"
```

**Function Description**:
- Delete all existing groups
- Clear all mentor assignments
- Reset group ID sequence number

#### 2.2 Auto-group Students

```bash
curl -X POST "http://127.0.0.1:8000/api/auto_group/"
```

**Function Description**:
- First process students with pre-assigned group numbers (from Excel "Group Number" column)
- Then auto-group students without pre-assigned group numbers by interests
- Maximum 5 people per group
- Group by track

#### 2.3 Fallback Grouping (Handle Remaining Students)

```bash
curl -X POST "http://127.0.0.1:8000/api/auto_group_fallback/"
```

**Function Description**:
- Handle students who are still ungrouped
- Prioritize grouping by shared interests
- Secondary grouping by year level and regional proximity

#### 2.4 Assign Mentors

```bash
curl -X POST "http://127.0.0.1:8000/api/assign_mentors/"
```

**Function Description**:
- Automatically assign mentors to groups without mentors
- Matching rules:
  - Must have at least one shared interest
  - Consider mentor capacity limits
  - Match by track priority
  - Consider experience level matching

### 3. Mentor Management Functionality Testing

#### 3.1 Using Web Interface

**Accessing Web Interface**:

Method 1: Direct HTML file access
- Find `frontend/admin.html` in file manager and double-click to open

Method 2: Access through Django server (recommended)

Quick setup steps:
```bash
# 1. Copy frontend file to Django templates directory
cp frontend/admin.html backend/matching/templates/admin_interface.html

# 2. Add to backend/matching/views.py:
def admin_interface(request):
    return render(request, 'admin_interface.html')

# 3. Add to backend/matching/urls.py urlpatterns:
path("admin-interface/", admin_interface, name="admin_interface"),

# 4. Restart Django server
python manage.py runserver
```

Then visit: http://127.0.0.1:8000/api/admin-interface/

This interface provides the following features:

**Replace Single Group Mentor**:
1. Enter group ID and new mentor ID
2. Click "Replacement of mentors and notification"
3. System will send email notifications to relevant parties

**Deactivate Mentor Account**:
1. Enter mentor ID
2. Click "Deactivate the mentorstutor and clear the group"
3. Mentor is marked as inactive, their assigned groups' mentor assignments are cleared

#### 3.2 Using API Interfaces

**Replace Group Mentor**:
```bash
curl -X POST "http://127.0.0.1:8000/api/replace_group_mentor/" \
  -H "Content-Type: application/json" \
  -d '{"group_id": 1, "new_mentor_id": 2}'
```

**Deactivate Mentor**:
```bash
curl -X POST "http://127.0.0.1:8000/api/deactivate_mentor/" \
  -H "Content-Type: application/json" \
  -d '{"mentor_id": 2}'
```

**Bulk Operations Preview** (placeholder functionality):
```bash
curl "http://127.0.0.1:8000/api/bulk_inactive_mentors_preview/"
```

### 4. Complete Workflow Testing

#### 4.1 Complete Reset and Reassignment Workflow

```bash
# 1. Reset all data
python test.py

# 2. Auto-group
curl -X POST "http://127.0.0.1:8000/api/auto_group/"

# 3. Fallback grouping (if needed)
curl -X POST "http://127.0.0.1:8000/api/auto_group_fallback/"

# 4. Assign mentors
curl -X POST "http://127.0.0.1:8000/api/assign_mentors/"
```

#### 4.2 Verify Results

1. **Check Django Admin Interface**:
   - Visit http://127.0.0.1:8000/admin/
   - Check if student groups are created correctly
   - Check if mentor assignments are reasonable

2. **Check API Responses**:
   - Each API call returns detailed execution results
   - Includes number of groups created, mentor assignment information, etc.

## Email Notification Functionality

### Development Environment
In development environment, emails are output to Django console and not actually sent.

### Production Environment
To enable real email sending, set the following environment variables:

```bash
export EMAIL_HOST="smtp.gmail.com"
export EMAIL_PORT="587"
export EMAIL_HOST_USER="your-email@gmail.com"
export EMAIL_HOST_PASSWORD="your-app-password"
export EMAIL_USE_TLS="true"
export DEFAULT_FROM_EMAIL="your-email@gmail.com"
```

## Data Model Description

### Student
- Basic info: name, email, school, year level
- Geographic info: country, region, track
- Interest tags: many-to-many relationship
- Pre-assigned group number: from Excel Group Number column

### Mentor
- Basic info: name, email, institution
- Background info: experience level, professional field
- Geographic info: country, region, track
- Capacity limit: maximum number of groups they can handle
- Active status: whether available

### StudentGroup
- Basic info: group name, track
- Year range: minimum and maximum year levels
- Members: many-to-many relationship
- Interests: union of member interests
- Mentor: foreign key relationship

## Troubleshooting

### Common Issues

1. **Excel Import Failure**:
   - Ensure Excel file path is correct
   - Check if Excel file contains "Students" and "Mentors" worksheets
   - Ensure column names match expected format

2. **API Call Failure**:
   - Check if Django service is running
   - Confirm API endpoint URL is correct
   - Check request format (JSON format, Content-Type, etc.)

3. **Email Sending Failure**:
   - Development environment: check console output
   - Production environment: check SMTP configuration

4. **Database Errors**:
   - Run `python manage.py migrate` to update database
   - Check database file permissions

### Debugging Tips

1. **View Django Logs**:
   - Set `DEBUG = True` in settings.py
   - Check console output for detailed error information

2. **Use Django Shell**:
   ```bash
   python manage.py shell
   ```
   Can interactively test models and queries

3. **Check Database Content**:
   ```bash
   python manage.py dbshell
   ```
   Direct access to SQLite database

## Extended Features

### Bulk Operations (Placeholder Functionality)
The system reserves interfaces for bulk processing inactive mentors, currently returning placeholder data:
- `GET /api/bulk_inactive_mentors_preview/` - Preview inactive mentors
- `POST /api/bulk_replace_inactive_mentors/` - Bulk replace mentors

### Custom Configuration
Can adjust through modifying `backend/core/settings.py`:
- Database configuration
- Email settings
- Other Django settings

## Contributing Guidelines

1. Each workflow uses independent branches
2. Keep commit messages concise and clear
3. Merge to main branch through Pull Request
4. Ensure main branch remains stable and deployable

## License

Please add appropriate license information as needed for the project.
