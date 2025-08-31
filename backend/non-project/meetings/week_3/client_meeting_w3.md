# Meeting Minutes

_18 Aug 25_

_Subject_: Week 3 Client Meeting  
_Project Name_: P11 - BIOTech Futures Student Mentoring Platform  
_Facilitator_: William Nixon  
_Prepared by_: Marc C  
_Mode_: Hybrid  
_Date_: 20 Aug 25  
_Time_: 17:00 - 18:00  
_Attendees_: Full project team and client (William Nixon)  
_Absent_: None  

| #   | Agenda Item              | Description/ Comments | Decision/Action | Who? | Items for escalation |
| --- | ------------------------ | --------------------- | --------------- | ---- | -------------------- |
| 1   | What has been completed? | Review of role and track structures. Client confirmed mentors/supervisors can belong to multiple groups, mentees only in one. Regions include Brazil, Victoria, Queensland, NSW, and WA. | Structure confirmed. | Team & Client | N/A |
| 2   | What is in progress? | Discussion on registration and data management. Registration handled externally via Qualtrics/PowerResume; our system will consume API data to create profiles. Debate over Airtable vs. custom DB. | Decision: Airtable integration dropped. Use our own DB with UI for non-technical staff. | Team | N/A |
| 3   | What is working well? | Agreement reached on phased roadmap instead of standalone work allocations. Strong clarity on responsibilities and data management. | Team to align work allocations with phased roadmap. | Team | N/A |
| 4   | What needs improvement?  | Clarifications on account lifecycle (active/pending/deactivated), handling login attempts, and role transitions over time. Retention policy confirmed to follow USYD (5 years). | Build audit logs for login attempts (low priority). Incorporate role lifecycle constraints into DB schema. | DB/Backend Team | N/A |
| 5   | Reminders                | Client requests API contracts and DB schema delivered this week. Ensure role allocations are clear (CI/CD, DB, Auth, Azure, Qualtrics). | Allocate final tasks and communicate with client. | Team | Timeline pressure if schema not delivered |
