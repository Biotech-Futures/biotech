# Meeting Minutes

_21 Sep 25_

_Subject_: Week 7 Group Meeting  
_Project Name_: P11 - BIOTech Futures Student Mentoring Platform  
_Facilitator_: Marc C  
_Prepared by_: Marc C  
_Mode_: Online  
_Date_: 21 Sep 25  
_Time_: 18:00 - 19:00  
_Attendees_: Marc, Minh, Marium, David, Archie  
_Absent_: Tyler, Edbert  

| #   | Agenda Item              | Description/ Comments | Decision/Action | Who? | Items for escalation |
| --- | ------------------------ | --------------------- | --------------- | ---- | -------------------- |
| 1   | What has been completed? | Reviewed recent PRs (noted: #72, #97, #100). Closed card #17 (bulk import) in favor of using API-driven data creation. Confirmed progress on user/role endpoints, filters, and resources tests. | Merge PRs once at least one peer review each is completed. Move completed cards to new sprint board for reporting. | Reviewers; Marc | N/A |
| 2   | What is in progress? | **Auth & Sessions:** active work on OTP/magic-link replacement; connect auth to Postgres. **DB Schema Plan:** users, roles, groups, consent, certificates; refine student fields. **DB Table Initialisation:** seed using client-provided dummy data via endpoints (no bulk Excel). | Finalise schema updates and seed plan; keep endpoints as source-of-truth for inserts. | Backend team | N/A |
| 3   | What is working well? | Clear task ownership, steady PR throughput, and project board hygiene. Team aligning on phased delivery and keeping discussions action-oriented. | Maintain cadence; continue documenting decisions alongside PRs. | Team | N/A |
| 4   | What needs improvement?  | **API Versioning:** endpoints not yet namespaced (e.g., `/api/v1/…`). **Permissions:** conflicts when testing custom `permission_classes`. **YAML Docs:** drf-spectacular schema needs update after auth changes. | Introduce versioned router (`/api/v1`) and deprecation plan. Isolate permission tests per view; avoid global defaults during tests. Update and deliver `schema.yaml` after specified endpoints are merged. | Archie (permissions), Ed (YAML), Marc (versioning) | N/A |
| 5   | Reminders                | Prepare for Friday all-group sync: bring DB schema and endpoint plan. Track “work left” items and create cards. Ensure Azure/DB provisioning status is communicated. | Create/assign cards for: Chat, group membership endpoints, unassigned-students pool + WS3 endpoints, certificates, resources, workshops/events (stretch), tasks (stretch). | Marc; Assignees | N/A |

### Follow-ups for Client (Will)
- **Parent/Guardian consent source**: Confirm field presence in incoming JSON; until then, default account to **deactivated** and expose endpoint to flip on consent.  
- **Remove redundant model fields**: Drop `has_join_permission` and its DB check constraint; enforce at endpoint/business-logic layer.  
- **Relationship type (student–supervisor)**: Confirm allowable values and when data is provided (during registration vs later).  
- **Student tracks**: Confirmed total as **six** (noted in discussion).

### Decisions & Technical Notes
- **WWCC**: Store **number** and **expiry** only (no document storage). International checks recorded as a boolean-like indicator when applicable.  
- **Docs**: Use **drf-spectacular**; Ed to regenerate and distribute `schema.yaml` once auth/login endpoints stabilise (reference issue to be inserted on PR).  
- **API Versioning**: Adopt `/api/v1` namespace now; plan for `/api/v2` when breaking changes arise.  
- **Repo/Project boards**: Continue card hygiene; move completed Week-7 items into a new sprint for reporting.

### Work Left (tracked as cards)
- **Chat** (phase item)  
- **Groups**: add users to groups; additional group endpoints  
- **Resources**: David to complete remaining endpoints  
- **Unassigned students pool**: design + expose endpoints for **Workstream 3**  
- **Certificates**: endpoints (WWCC and extensible certificate store)  
- **Stretch goals**: Workshops & Events, Tasks

