# Meeting Minutes

_27 Aug 25_

_Subject_: Week 4 Client Meeting  
_Project Name_: P11 - BIOTech Futures Student Mentoring Platform  
_Facilitator_: William Nixon  
_Prepared by_: Marc C  
_Mode_: Hybrid  
_Date_: 27 Aug 25  
_Time_: 16:30 - 17:00  
_Attendees_: Full team and client (William Nixon)  
_Absent_: None  

| #   | Agenda Item              | Description/ Comments | Decision/Action | Who? | Items for escalation |
| --- | ------------------------ | --------------------- | --------------- | ---- | -------------------- |
| 1   | What has been completed? | Alignment on registration/parental consent flow and initial data-handling principles. Confirmed frontend stack already chosen by W1 (Vue + Tailwind) and W2 is progressing DB schema and API plan. | Proceed with DB schema + endpoint plan to support consent states and profile fields discussed. | W2 (Backend) | N/A |
| 2   | What is in progress? | **Compliance & Identity:** Working With Children Check (WWCC) rules; parental consent gating; Qualtrics integration approach. **Infrastructure:** Repo ownership/transfer plan. **Roadmap:** Preparing for all-group meeting (W1, W2, W3). | Finalise schema for: `wwcc_number`, `wwcc_expiry`, `jurisdiction`, `international_clearance_flag` (no document storage). Add `account_status` to support “Pending Guardian Consent.” | Backend + Auth subteam | N/A |
| 3   | What is working well? | Clear division of responsibilities with client providing Qualtrics API format/content; team focuses on our ingestion API. Agreement on creating repo now and transferring ownership at project end. | Draft and send expected payload schema to client (fields + example JSON) for Qualtrics → our API. Create repo under team org with transfer plan noted. | Backend Lead; DevOps | N/A |
| 4   | What needs improvement? | **Profile lifecycle:** handling student→mentor transition across years; avoiding data loss. **Security posture:** explicit encryption standards still to be selected (research-based). **Chat scope:** (not primary here) remains stretch/phase item. | Provisional approach: retain existing user record; on mentor registration, collect additional mentor fields and keep student history (no deletion). Document encryption standards (at-rest + in-transit) based on best practice and include in ADR. | Backend + Security | Confirm with client that “retain + extend profile” is acceptable |
| 5   | Reminders                | Humanitix events workshop is a **stretch goal** (not MVP). Program cadence: 6 weeks, once per year—use to inform roles/eligibility and retention rules. All-group meeting (W1, W2, W3) on **Friday**—bring DB schema and endpoint plan. | Finalise v1 DB schema and endpoint plan; prepare demo test endpoint seeded with client dummy data. | Backend; All streams | None |

