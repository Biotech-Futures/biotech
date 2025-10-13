Meeting Minutes
Project: Biotech Futures
 Date: 10/10
 Time: 10AM
 Location: Zoom Meeting
 Facilitator: William Nixon
 Note taker: Edbert Tien Suwandi
 Attendees: Archie, Workstream 1 reps, Workstream 3 reps
Agenda
Cloud database setup status


Demo of current database configuration


Dependency alignment across workstreams


Discussion Summary
The database is now hosted and operational on Microsoft Azure.


Archie presented a short demo showing how the database is set up and how connections are managed.


Workstream 1 requested an update to requirements.txt to remove duplicated dependencies that overlap with Workstream 3.

Each workstream showed their current progress.


Decisions
Confirmed Azure as the hosting platform for the database.


Agreed to clean and standardize requirements.txt to avoid duplicate and conflicting packages across workstreams.


Action Items
Audit dependencies


Owner: Workstream 1 with input from Workstream 3


Task: Identify and remove duplicate entries in requirements.txt. Consolidate versions where overlap exists.



Update repository


Owner: Workstream 1


Task: Commit cleaned requirements.txt, run build to verify, and open a PR for review by Workstream 3.



Document Azure database setup


Owner: Archie


Task: Share environment details, connection strings handling, access controls, and backup strategy in the project wiki.



Add CI check for dependency duplicates


Owner: DevOps


Task: Add a pipeline step that flags duplicate or conflicting Python dependencies.





Risks and Mitigations
Risk: Version conflicts between workstreams leading to runtime errors.
 Mitigation: Lock versions using a single source of truth and run integration tests after dependency changes.



Next Meeting
When: 17/10





