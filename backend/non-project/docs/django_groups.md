# django auth + groups

so we've decided to pair our custom user model with django's built-in groups and permissions system. this allows us to leverage django's robust authentication framework while still having the flexibility to define our own user attributes and roles.

`auth.Group` - for django's built-in auth roles. it is only for authorisation (what a user can do), it integrates with django admin/drf.

our 'resources.Roles' which has our domains roles + history tracking is still valid business logic, and what we'll do is **keep our Roles + history and mirroring them to `auth.Group` for request-time checks. so django Groups will be used for quick permission checks, and we'll still have our Roles model for business logic and history tracking and who/when/why.**

## what is `auth.Group`

this is a named bucket of permission (**the important thing is that Users belong to many groups.**), which integrates smoothly with DRF and django admin.

it is easy to check e.g.
```python
if request.user.groups.filter(name='admin').exists():
    # do admin stuff
```

so the design for our project is:
1. we will keep our domain models AS IS (user, roles, roleassignmenthistory, resources and resourcesroles. these are all STILL VALID)
2. mirror each Roles.role_name into a Django `Group`
  - e..g, one-to-one by name "Mentor" "student" "Supervisor" "Admin"
  - seed on startup/migration (meaning automatically create these Group objects in the database if they don't exist)
3. when we assign or end-date a role
  - create a new row or invalidate an existing row in the roleassignmenthistory
  - add/remove the matching `Group` on the yser
  - this gives us instant checks (`user in group`) and immutable history through our existing models.
4. authorise endpoints using DRF permission classes "Admin-only" -> check group `Admin`.
  - or "user must have any role that this resources requires" -> check against ResourceRoles and user groups.