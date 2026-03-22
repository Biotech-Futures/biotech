# Workstream 2 – Back-End Core Services & APIs 

*Lead deliverable:* Scalable, secure, cloud-hosted core system with public/private APIs. 

*Key tasks:* 
- Implement passwordless login service (email code, short expiry). 
- Build user management and role-based permissions. 
- Design database schema for users, groups, resources, and messages. 
- Implement Tracks and group structures. 
- Create chat service (native or integrated provider). 
- Implement resource library storage with role-based access. 
- Build API endpoints for: 
  - Profile import/export (Airtable integration). 
  - Group and message retrieval. 
  - Resource retrieval and upload. 
- Account activation/deactivation functions. 

*Integration points:* 
- Supplies APIs to Workstream 1 (UI) and Workstream 3 (admin automation). 
- Connects to Airtable for profile sync if required. 
- Humanitix

# Technical Considerations 
*Hosting:* Azure (see code repository) 
*Database:* PostgreSQL (see code repository) 
*Authentication:* Passwordless email code system with token expiry. 
*Security:* HTTPS, role-based access, secure file uploads, audit logging. 
*Scalability:* Modular architecture to allow microservice expansion. 
*Accessibility:* WCAG 2.1 AA compliance where feasible. 


# Entire Project MVP (All Workstream 1: front end, Workstream 2: backend and APIs, Workstream 3: Algorithm)
The MVP will include: 
- Web-based interface accessible on desktop and mobile browsers. 
- Passwordless login via short-expiry, single-use email code. 
- Role-based access control for: 
  1. Student 
  2. Mentor 
  3. Supervisor 
  4. Administrator 
- Tracks for regions: AUS–NSW, AUS–QLD, AUS–VIC, AUS–WA, Brazil, Global. 
- Mentoring groups with: 
  - Chat functionality (document sharing enabled). 
  - Document storage per group. 
- Administrator functions: 
  - Automated student team formation and mentor assignment via algorithm. 
  - Group reassignment tools (single and bulk) with automated email triggers. 
  - Account status management (active/deactivated). 
- Resource library with admin-only content creation and role-based visibility. 
- Integration points for Airtable synchronisation (profiles) and Humanitix (events). 
- API support for importing/exporting user data. 

## Stretch goals (delivered if capacity allows): 
- Connection plan tool to guide mentoring. 
- Embedded video conferencing. 
- Calendar integration for meeting scheduling. 
- Advanced analytics dashboards. 

 

 