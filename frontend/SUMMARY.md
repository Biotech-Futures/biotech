## BIOTech Futures Mentoring Portal Frontend Summary (Requirement Audit)

**Date:** 2026-03-17

### Basis and Scope

- **Requirement Specification:** `CS17_BIOTech_Futures_-_Mentoring_Portal.pdf`
- **Frontend Codebase:** `\frontend\src\`
- **Note:** This summary focuses exclusively on "Completed vs. Pending (including specific gaps)" in the frontend. It does not evaluate backend implementation.

------

### Completed Features (Currently Available/Implemented)

- **Core Infrastructure:** Established using **Vue 3 + Vite + Pinia + Vue Router**. Development, build, testing, formatting, and ESLint workflows are fully functional.
- **Main Layout & Navigation:** Implementation of the top bar, sidebar, notification panel, and conditional layout logic (e.g., hiding main layout on the Login page) within `App.vue`.
- **Authentication Flow:**
  - **UI & Requests:** Email Magic Link + 6-digit OTP process implemented in `LoginPage.vue`.
  - **State Management:** Callback page handles token reception and session establishment in `AuthCallbackPage.vue`.
  - **Persistence:** Login state managed via Pinia with localStorage persistence and Route Guards for access control (`auth.ts` + `router/index.ts`).
- **Page Scaffolding:** Frameworks for Dashboard, Groups, Group Detail, Events, Resources, Announcements, Profile, and Admin pages are present and accessible.
- **Resource List Integration:** `ResourcesPage.vue` successfully calls `fetchResources()` to pull data, supporting search and type filtering.
- **API Encapsulation:** `resourcesAPI.ts` includes CRUD and type interfaces for resources (though not yet fully utilized by the UI).

------

### Pending Features (Gaps and Details)

#### 1. Role-Based Access Control (RBAC)

- **Requirement:** Full permission system for Students, Mentors, Supervisors, Regional Admins, and Global Admins.
- **Current State:** Frontend only performs basic checks for "Admin menu visibility." Granular page permissions, data visibility, and action-based authorization for other roles are not yet implemented.
- **Impact:** Fails to meet the "Role-Based Access Control" delivery requirement.

#### 2. Group & Mentor Collaboration (UI/Mock Only)

- Group lists and detail pages currently rely on **mock data** (`src/data/mock.ts`).
- **Plan & Discussion features in Group Details are local state only:**
  - Tasks and messages cannot be persisted to the backend.
  - Data is lost upon refresh; no integration with real member/mentor data.
- **Group Chat & Document Sharing:**
  - The discussion area only supports local messages; the attachment button lacks upload logic.
  - Missing file lists, download functionality, and permission controls.

#### 3. Automated Mentor Matching & Reassignment

- **Requirement:** Automated matching and reassignment based on specific business rules.
- **Current State:** The frontend lacks any UI, workflow entry points, or configuration pages. No integration with matching APIs exists.

#### 4. Admin Dashboard (Demo Layer Only)

- Admin pages currently display mock users and mock group data.
- **Missing Critical Capabilities:**
  - Bulk group creation and configuration.
  - Mentor reassignment workflows.
  - Filtered bulk communication (Email/In-app) for specific user segments.
  - Authentic data Import/Export workflows.

#### 5. Events & Announcements Integration

- **Events:** Pages use mock data; "Create" and "Register" logic are currently `alert()` placeholders.
- **Announcements:** Mock data only; supports local search but lacks API integration and detail pages.

#### 6. Profile & Settings Persistence

- The Profile page uses a mock user. "Save" and "Cancel" actions only trigger pop-up notifications.
- **Gap:** No actual API updates, backend data synchronization, or server-side validation.

#### 7. Resource Management (Read-Only)

- While listing and display are functional, the following are missing:
  - **Resource Upload:** The frontend button lacks logic.
  - **Edit/Delete:** APIs are encapsulated but not connected to the UI.
  - **Visibility Limits:** Currently shows tags only; no permission-based filtering is enforced.

#### 8. Routing & Page Placeholders

- The `/groups` route currently reuses `DashboardPage`; a dedicated Group List page is not yet implemented.
- The `/resources/:id` route redirects to `ResourcesPage`; a dedicated Resource Detail page is missing.

------

### Conclusion

The frontend currently provides a **"Demonstrable Product Framework and Authentication Flow,"** but core business logic remains driven by mocks and UI-only interactions. To meet the goal of a **"Production-grade platform with full functional delivery"** as outlined in the PDF, the following priorities must be addressed:

1. **Real Data Integration:** Connect Groups, Events, Announcements, Users, and Profiles to the backend.
2. **Permissions (RBAC):** Implement a robust role-based visibility and action system.
3. **Collaboration Tools:** Finalize Group Chat and File Sharing persistence.
4. **Admin Workflows:** Build the Matching, Grouping, and Bulk Communication tools.
5. **Resource Management:** Complete the Upload/Edit/Delete cycle with permission filters.