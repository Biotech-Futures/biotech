# Announcements API - Postman Testing Guide

## 📥 Import the Collection

1. Open Postman
2. Click **Import** button
3. Select `Announcements_API_Postman_Collection.json`
4. Collection will appear in your sidebar

---

## ⚙️ Setup Variables

Before testing, update these collection variables with your actual credentials:

1. Click on the collection name
2. Go to **Variables** tab
3. Update the following:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `base_url` | Your backend URL | `http://localhost:8000` |
| `admin_email` | Admin user email | `admin@example.com` |
| `admin_password` | Admin password | `yourpassword` |
| `student_email` | Student user email | `student@example.com` |
| `student_password` | Student password | `password123` |
| `mentor_email` | Mentor user email | `mentor@example.com` |
| `mentor_password` | Mentor password | `password123` |
| `announcement_id` | ID for update/delete tests | `1` (update after creating) |

---

## 🧪 Test Sequence

### **Phase 1: Basic CRUD (Run as Admin)**

1. **List All Announcements** - Should return empty array initially
2. **Create Announcement - All Users** - Creates announcement for everyone
3. **Create Announcement - Students Only** - Creates student-specific announcement
4. **Create Announcement - With External Link** - Tests external link field
5. **Create Announcement - With Internal Route** - Tests internal route field
6. **Retrieve Single Announcement** - Get details of created announcement
   - **⚠️ Update `announcement_id` variable** with ID from step 2 response
7. **Update Announcement Title** - Modify announcement
8. **Update - Pin Announcement** - Pin to top
9. **Delete Announcement** - Soft delete

---

### **Phase 2: Validation Tests**

10. **Create - INVALID (Both Links)** - Should return 400 error
    - Tests validation: Cannot set both external_link and internal_route

---

### **Phase 3: Permission Tests**

11. **Create as Student (Should Fail)** - Should return 403 Forbidden
    - Tests: Only admins can create announcements

---

### **Phase 4: Filtering Tests**

12. **List with Search Filter** - Search by keyword
13. **List with Audience Filter (Admin Only)** - Filter by audience type
14. **List as Student (Filtered)** - Should only see 'all' + 'student' announcements
15. **List as Mentor (Filtered)** - Should only see 'all' + 'mentor' announcements

---

### **Phase 5: Ordering Tests**

16. **Verify Pinned Ordering** - Pinned announcements should appear first

---

## 🎯 Expected Results

### ✅ **Successful Responses**

**List (GET /announcements/v1/):**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Welcome to BIOTech Futures 2025",
      "summary": "We are excited to announce...",
      "author": {
        "id": 1,
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin@example.com",
        "author_name": "Admin User"
      },
      "author_name": "Admin User",
      "date": "2025-01-15T10:00:00Z",
      "created_datetime": "2025-01-15T10:00:00Z",
      "audience": "all",
      "external_link": null,
      "internal_route": null,
      "is_pinned": true
    }
  ]
}
```

**Create (POST /announcements/v1/):**
```json
{
  "id": 1,
  "title": "Welcome to BIOTech Futures 2025",
  "summary": "We are excited to announce...",
  ...
}
```

**Retrieve (GET /announcements/v1/{id}/):**
```json
{
  "id": 1,
  "title": "...",
  "summary": "...",
  "content": "Full announcement content here...",
  "author": {...},
  ...
}
```

**Update (PATCH /announcements/v1/{id}/):**
```json
{
  "id": 1,
  "title": "Updated: Welcome to BIOTech Futures 2025",
  ...
}
```

**Delete (DELETE /announcements/v1/{id}/):**
```json
{
  "message": "Announcement 'Welcome to BIOTech Futures 2025' has been deleted."
}
```

---

### ❌ **Error Responses**

**Validation Error (400):**
```json
{
  "external_link": [
    "Cannot set both external_link and internal_route. Choose one."
  ],
  "internal_route": [
    "Cannot set both external_link and internal_route. Choose one."
  ]
}
```

**Permission Denied (403):**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**Not Found (404):**
```json
{
  "detail": "Not found."
}
```

---

## 🔍 Audience Filtering Logic

| User Role | Sees Announcements With Audience |
|-----------|----------------------------------|
| **Student** | `all`, `student` |
| **Mentor** | `all`, `mentor` |
| **Supervisor** | `all`, `supervisor` |
| **Admin** | `all`, `admin` (or ALL if is_staff) |

---

## 📋 Test Checklist

- [ ] List returns paginated results
- [ ] Create sets author automatically
- [ ] Create validates external_link vs internal_route
- [ ] Retrieve returns full content field
- [ ] Update works for admin/author only
- [ ] Delete is soft delete (deleted_flag=True)
- [ ] Search filters by title, summary, author
- [ ] Audience filtering works for each role
- [ ] Pinned announcements appear first
- [ ] Non-admin users cannot create
- [ ] Author can update their own announcements
- [ ] Admin can update any announcement

---

## 🚀 Quick Start

1. Import collection
2. Update variables (especially emails/passwords)
3. Run requests 1-9 in sequence (as admin)
4. After step 2, copy the `id` from response and update `announcement_id` variable
5. Test permissions with requests 11-13 (switch auth credentials)
6. Verify filtering with requests 14-16

---

## 💡 Tips

- **Use Collection Runner** to run all tests automatically
- **Enable auto-save responses** to compare results
- **Check test results** in the Test Results tab (some requests have assertions)
- **Monitor Console** (View → Show Postman Console) for detailed request/response logs
- **Use Pre-request Scripts** to dynamically set variables if needed

---

## 🐛 Troubleshooting

**401 Unauthorized:**
- Check that Basic Auth credentials are correct
- Verify user exists in database
- Ensure user has correct role

**403 Forbidden:**
- Verify user has admin role (for create/update/delete)
- Check that non-admin users can only read

**400 Bad Request:**
- Check request body matches expected format
- Verify required fields are present
- Check validation rules (e.g., both links cannot be set)

**CSRF Token errors:**
- Use Basic Auth (doesn't require CSRF)
- Or get CSRF token from cookies and add to headers

---

## ✅ Success Criteria

All tests should pass with expected status codes:
- ✅ GET requests return 200
- ✅ POST requests return 201
- ✅ PATCH requests return 200
- ✅ DELETE requests return 204
- ✅ Permission failures return 403
- ✅ Validation errors return 400
