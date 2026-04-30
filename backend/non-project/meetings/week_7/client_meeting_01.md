# Meeting Minutes

_17 Sep 25_

_Subject_: Week 7 Client Meeting  
_Project Name_: P11 - BIOTech Futures Student Mentoring Platform  
_Facilitator_: William Nixon  
_Prepared by_: Marc C  
_Mode_: In-person  
_Date_: 17 Sep 25  
_Time_: 17:00 - 18:00  
_Attendees_: Client (William Nixon); Team — Marc, Minh, David, Archie, Tyler, Edbert  
_Absent_: Marium  

| #   | Agenda Item              | Description/ Comments | Decision/Action | Who? | Items for escalation |
| --- | ------------------------ | --------------------- | --------------- | ---- | -------------------- |
| 1   | What has been completed? | Conducted first client demo: showed initial API endpoints via Postman and Django Admin. Client expressed satisfaction with progress and direction. | Continue iterating on endpoints demoed; schedule next demo after incorporating Qualtrics/Power Automate payloads. | Backend team | N/A |
| 2   | What is in progress? | **Infrastructure:** Azure DB funding/provisioning discussed (free trial expired). **Data Flow:** Walkthrough of Qualtrics → Power Automate → our API; clarified that payload may include a `group` derived from response ID (`R_…`), blank when individual or not grouped. | Proceed with client-funded paid Azure DB instance; team to avoid spending budget on Slack. Map incoming JSON to our models and adjust endpoints accordingly. | Archie (Azure); Marc & Minh (payload mapping) | **Budget approval** for Azure subscription timing |
| 3   | What is working well? | Clear client-owned validation upstream (email/structure checks) reduces backend data-scrubbing; alignment on letting Power Automate standardize outputs before hitting our API. | Document expected request schemas and edge cases; add examples to API docs. | Marc | N/A |
| 4   | What needs improvement? | **Grouping & WS3 hand-off:** Need a holding area for unassigned students and a way to respect “within-school-only” grouping preference. **Identifiers:** When teacher bulk-creates groups, Power Automate appends a group suffix to `R_…` ID; this must be persisted and exposed to WS3. **Access/ops:** Clarify shared credentials flow for Azure during development. | Design “unassigned-students pool” + endpoints for WS3; persist group token (`R_…[_groupN]`) where provided; confirm ops model: temporary shared Azure credentials with client, then rotated post-project. | Marc (spec); Backend (endpoints); Archie (ops) | Dependency on WS3 algorithm delivery/contract |
| 5   | Reminders                | Client to share example JSONs (individual, teacher bulk with groups, bulk without groups incl. one unassigned). Team to confirm whether to store school-restriction preference for grouping. | Request sample payloads from client; update API contracts and Django models accordingly; reflect in drf-spectacular docs. | Minh & Marc (client follow-up), Ed (docs) | N/A |

