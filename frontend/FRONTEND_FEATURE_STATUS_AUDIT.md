# BIOTech Futures Frontend Status Audit

Date: 2026-03-22  
Scope: Frontend-only audit (Vue app in `frontend/src`) against:
- `C:\Users\QINCH\Desktop\COMP5703\Requirement.txt`
- `C:\Users\QINCH\Desktop\COMP5703\CS17_BIOTech_Futures_-_Mentoring_Portal.pdf`

## 1. Frontend Framework Snapshot

- Stack: Vue 3 + Vite + Pinia + Vue Router (+ TypeScript support)
- Current app structure includes pages for:
  - Login / Auth callback
  - Dashboard
  - Group detail
  - Events
  - Resources
  - Announcements
  - Profile
  - Admin

## 2. Requirement Coverage Summary

| Requirement Area | Current Status | Notes |
|---|---|---|
| Passwordless login (single-use code) | **Partially Complete** | Login page sends and verifies code via API. Flow is implemented in frontend. |
| Authentication & route protection | **Partially Complete** | Auth store + route guard exist, but authorization is not fully role-based. |
| Full RBAC (student/mentor/supervisor/local admin/global admin) | **Not Complete** | No full route/action-level permission matrix; admin check is limited. |
| Role-tailored dashboard/navigation | **Partially Complete** | Role-based UI variants exist, but most displayed business data is mock/local. |
| Group chat (real-time) + file sharing | **Not Complete** | Discussion UI exists, but no API/websocket/file upload integration. |
| Notifications for key updates | **Not Complete** | No backend-driven notification system implemented. |
| Resource library with role-based access + upload/version control | **Partially Complete** | Resource list is API-backed; upload/version control and role enforcement are incomplete. |
| Mentor matching algorithm + admin override | **Not Complete** | No matching workflow UI/API integration in frontend. |
| Progress tracking (assign plan + mark tasks complete) | **Partially Complete** | Plan/task UI exists, but is local-only and not persisted. |
| User profile update (interests/location/contact preferences) | **Partially Complete** | UI exists, but uses mock user and demo save only. |
| Event listing + registration + external integration (e.g., Humanitix) | **Partially Complete** | Events page exists with mock list and demo register behavior. |
| Admin user filtering/search and operational workflows | **Partially Complete** | Filter/search UI exists, but data is mock and core workflows are not connected. |

## 3. Completed Features (Frontend Implemented)

## 3.1 API-Integrated Features

- Passwordless login request:
  - `POST /services/send-login-code/`
  - File: `src/views/LoginPage.vue`
- OTP verification:
  - `POST /services/verify-login-code/`
  - File: `src/views/LoginPage.vue`
- Authenticated user fetch:
  - `GET /api/v1/users/me/`
  - File: `src/stores/auth.ts`
- Resource list fetch:
  - `GET /resources/resource-files/`
  - Files: `src/utils/resourcesAPI.ts`, `src/views/ResourcesPage.vue`

## 3.2 Core Frontend Structure Completed

- Global layout + sidebar/header navigation: `src/App.vue`
- Routing and auth guard: `src/router/routes.ts`, `src/router/index.ts`
- Auth state persistence (localStorage hydration): `src/stores/auth.ts`
- Main page scaffolding for Dashboard, Group, Events, Resources, Announcements, Profile, Admin: `src/views/*.vue`

## 4. Implemented in Frontend but Using Mock/Local Data (Not Real API Data)

| Feature | Current Data Source | Evidence |
|---|---|---|
| Dashboard cards, summaries, previews | `mockGroups`, `mockResources`, `mockAnnouncements` + local arrays | `src/views/DashboardPage.vue`, `src/data/mock.ts` |
| Group identity/details | `mockGroups` | `src/views/GroupDetailPage.vue` |
| Group plan milestones/tasks | Local component state (`tasks`) | `src/views/GroupDetailPage.vue` |
| Group discussion messages | Local component state (`messages`) | `src/views/GroupDetailPage.vue` |
| Events listing/content | `mockEvents` | `src/views/EventsPage.vue`, `src/data/mock.ts` |
| Event registration action | `alert(...)` placeholder | `src/views/EventsPage.vue` |
| Event creation action | `alert('Create Event (demo)')` | `src/views/EventsPage.vue` |
| Announcements list/search | `mockAnnouncements` | `src/views/AnnouncementsPage.vue`, `src/data/mock.ts` |
| Admin user table and stats | `mockUsers`, `mockGroups`, hardcoded counters | `src/views/AdminPage.vue`, `src/data/mock.ts` |
| Profile data and save behavior | `mockUsers[0]` + demo alert | `src/views/ProfilePage.vue` |
| Resource "open" action | `alert(...)` placeholder | `src/views/ResourcesPage.vue` |
| Resource/event cover images | Local `localStorage` only | `src/views/ResourcesPage.vue`, `src/views/EventsPage.vue` |
| Resource type catalog helper | Hardcoded list (not endpoint) | `src/utils/resourcesAPI.ts` (`fetchResourceTypes`) |

## 5. Not Implemented or Incomplete Features (Against Requirements)

- Full RBAC enforcement across pages/actions (including local/global admin distinctions)
- Route-level authorization for non-admin roles and restricted actions
- Backend-connected group chat persistence / real-time messaging
- File upload/download in group discussion
- Notification system for key updates
- Mentor allocation/reallocation UI workflow integration
- Admin bulk group formation workflow
- Admin bulk communication workflow
- Profile update API integration (save currently demo only)
- Event management API integration (create/register/filter workflows are mostly UI/demo)
- Humanitix (or equivalent) real integration
- Resource upload/edit/delete wiring in UI (API helpers exist, UI not connected)
- Resource version control workflow
- Guaranteed role-based resource visibility enforcement in frontend logic
- Dedicated group list page (`/groups` currently points to detail component)
- Dedicated resource detail page (`/resources/:id` currently reuses list page)
- Contact administrator route/page (`/contact`) is referenced in UI but not routed

## 6. Practical Interpretation

The frontend is currently a **solid functional shell + partial API integration**:
- Real API integration exists mainly for **authentication** and **resource listing**.
- Many core business features are present as **UI prototypes** but still depend on **mock/local/demo logic**.
- The project is **not yet production-ready** for the full CS17 Phase II deliverable scope described in the PDF.

---

## 7. Incremental Update (2026-04-12)

This section records changes observed after the 2026-03-22 snapshot.

### 7.1 Newly Integrated Backend APIs (Since 2026-03-22)

#### A. Dashboard data APIs (newly wired in frontend)

The dashboard now issues parallel API requests on page load (`loadDashboardData` with `Promise.all` in `src/views/DashboardPage.vue`).

| Feature Slice | Endpoint | Method | Frontend Integration Point | Runtime Behavior |
|---|---|---|---|---|
| Dashboard summary cards | `/api/v1/dashboard/summary/` | GET | `loadSummary()` in `src/views/DashboardPage.vue` | Uses API response; falls back to local derived values on failure |
| My groups overview | `/api/v1/groups/my/` | GET | `loadGroups()` | Uses API response; falls back to `mockGroups` on failure |
| Dashboard resources preview | `/api/v1/resources/` | GET | `loadResources()` | Uses API response; falls back to `mockResources` on failure |
| Dashboard announcements preview | `/api/v1/announcements/` | GET | `loadAnnouncements()` | Uses API response; falls back to `mockAnnouncements` on failure |
| Upcoming events preview | `/api/v1/events/upcoming/` | GET | `loadEvents()` | Uses API response; falls back to `mockEvents` on failure |
| Admin workflow summary | `/api/v1/admin/workflow/summary/` | GET | `loadAdminWorkflow()` | Admin-only request path; uses hardcoded fallback metrics on failure |
| Progress snapshot | `/api/v1/dashboard/progress/` | GET | `loadProgress()` | Uses API response; falls back to default snapshot on failure |
| Action center | `/api/v1/dashboard/action-center/` | GET | `loadActionCenter()` | Uses API response; falls back to role-based local builders |
| Checklist | `/api/v1/dashboard/checklist/` | GET | `loadChecklist()` | Uses API response; falls back to role-based local builders |

#### B. Authentication/session APIs (newly expanded usage)

| Feature Slice | Endpoint | Method | Frontend Integration Point | Runtime Behavior |
|---|---|---|---|---|
| Logout session invalidation | `/services/logout/` | POST | `logout()` in `src/stores/auth.ts` (triggered by app logout actions) | Calls backend logout then clears local auth state |
| App bootstrap current-user sync (expanded flow) | `/api/v1/users/me/` | GET | `initializeAuth()` called in `src/main.ts` before mount | Hydrates local cache, then synchronizes with backend session |

#### C. API hooks present but not fully activated in page flow

| Endpoint | Method | Status |
|---|---|---|
| `/api/v1/public/biotech-showcase/` | GET | Loader function exists in dashboard (`loadBiotechShowcase`) but is not currently included in the main dashboard loading sequence (`Promise.all` list) |

### 7.2 Other Frontend Changes (Non-API or Partial-API)

#### A. Dashboard architecture and UX enhancements

- Dashboard was significantly expanded in layout/interaction complexity (hero area, role-aware sections, action center/checklist composition, fallback builders).
- Data loading now follows an API-first pattern with graceful per-module fallback rather than mock-only rendering.
- Multiple dashboard blocks still initialize with local mock seed values and degrade to mock/defaults on fetch failure.

#### B. Authentication lifecycle improvements

- Frontend bootstrap now awaits auth initialization before routing/mount, improving session consistency at first render.
- Auth callback flow explicitly calls `fetchUserData()` then redirects based on session availability.

#### C. Resource page behavior upgrades

- Resource list page has explicit loading/error/empty states and retry action.
- Resource list is API-backed (`fetchResources`) with frontend transformation for display.
- Resource card "open" action remains placeholder (`alert(...)`), and upload button is still UI-only (no upload API wiring in page flow).

### 7.3 Still Mock/Demo or Not Fully Connected (Current)

The following areas remain primarily local/mock/demo despite frontend UI availability:

- Events page list source remains `mockEvents`; register/create actions are still alert/demo placeholders.
- Announcements page list/search remains `mockAnnouncements`.
- Admin page table/stats remain `mockUsers` + `mockGroups` + hardcoded counters.
- Profile page still uses mock user data; save remains demo-only.
- Group detail page (group info, plan/tasks, discussion messages) remains local/mock state.
- Resource API helper has CRUD functions (`create/update/delete/fetch by id`), but those workflows are not wired into current page actions.
- Resource type helper (`fetchResourceTypes`) is still hardcoded and not backed by an endpoint.

### 7.4 Updated Practical Interpretation (Post-Update)

Compared with 2026-03-22, frontend backend-integration scope has expanded from:
- Authentication + resource listing

to:
- Authentication/session lifecycle + resource listing + dashboard multi-endpoint aggregation.

However, a large part of operational workflows (events, profile editing persistence, admin operations, group collaboration workflows) remains mock/demo or partially connected, so end-to-end production readiness is still incomplete.
