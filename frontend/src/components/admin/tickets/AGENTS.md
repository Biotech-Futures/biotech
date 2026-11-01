# Ticket System: frontend

Vue pages and components for support tickets. The backend, its rules and the API are described in `backend/apps/tickets/AGENTS.md`; read that first. Built by Team 2 (COMP3888, 2026). The agent side used to live in the React `adminweb`; it was moved here at the client's request, and `adminweb` is frozen. **Do not add ticket code to `adminweb`.**

## Map

| Path | What it holds |
|---|---|
| `frontend/src/views/SupportCentrePage.vue` | `/support`: raise an enquiry, help links, "My tickets" |
| `frontend/src/views/TicketDetailPage.vue` | `/support/tickets/:id`: the requester's conversation and reply box |
| `frontend/src/components/support/` | Requester components: form, attachment picker, reply box, timeline, badges |
| `frontend/src/views/admin/tickets/TicketsSection.vue` | `/admin/tickets` shell with the Queue, Audit and Analytics tabs |
| `frontend/src/views/admin/tickets/TicketQueuePage.vue` | Queue; `?ticket=<id>` opens the detail panel |
| `TicketAuditPage.vue`, `TicketAnalyticsPage.vue` | Audit log and analytics |
| `components/admin/tickets/queue/` | Counter cards, filter bar, table, pager, bulk assign |
| `components/admin/tickets/detail/` | Detail panel, triage controls, reply and internal-note composers, timeline, AI screening review |
| `components/admin/tickets/audit/`, `analytics/` | Audit table and analytics tiles |
| `frontend/src/composables/admin/useTicketQueue.ts` | Queue state, filters and snapshot paging |
| `frontend/src/utils/supportAPI.ts` | Requester API |
| `frontend/src/utils/ticketAgentAPI.ts`, `ticketAgentSchema.ts` | Agent API and its zod schemas |
| `frontend/src/utils/ticketTransport.ts` | Fetch wrapper: CSRF, multipart uploads, file downloads |
| `frontend/src/utils/ticketDates.ts` | `ticketTimeZone()` and date formatting |
| `frontend/src/views/SupportAccessPage.vue` | Landing page for a support-role user without queue access |

## Rules

1. **Times:** always format with `ticketDates.ts`. It uses the viewer's Profile time zone, or the browser's zone when the Profile still says UTC. Pass the same zone to `analytics/` and the exports.
2. **Access:** `canWorkTickets` and `isSupportOnly` come from `stores/auth.ts`. A support-only user may only reach `/admin/tickets`, `/profile` and `/support-access` (`router/index.ts`). The "Support" link stays visible when Pages Visibility hides other pages.
3. **Never show internal notes on requester pages.** The API already removes them; do not add fields that could carry them.
4. **Statuses change through the API only.** The reply composer's "Status after sending" and the triage dropdown send the requested status; the backend decides the result.
5. **Attachments:** 5 files, 10 MB each, PDF, PNG, JPG or DOCX. Keep the frontend limits in step with `backend/apps/tickets/services/attachments.py`.
6. **Design:** the screens follow the team designer's two rounds, which the client approved. Dark mode is supported; check contrast in both themes when changing colours.

## Tests

Spec files sit in `__tests__/` folders next to the code (about 57 files). Run `pnpm test:unit --run` or `npm run test:unit -- --run` in `frontend/`. End-to-end: `frontend/e2e/tickets.spec.ts` (7 tests, Chromium only; see `frontend/e2e/README.md`).

## Known gaps

- The AI screening review keeps the "Message under review" label after a decision (`detail/TicketDetailPanel.vue:114-116`).
- There is no delete button; ticket deletion is admin-only through the API.
