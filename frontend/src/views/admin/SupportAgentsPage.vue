<template>
  <div class="content-area support-agents">
    <!-- The route's guard reads the store's role-name isAdmin, which is not
         what the server checks. These endpoints are IsAdminScoped (an
         AdminScope row), so the page asks the server's own flag. A support
         agent who is not an admin, or an account whose role name says admin
         with no AdminScope behind it, gets an answer instead of a table that
         fails to load, and no request is made for them at all. -->
    <template v-if="!auth.isTicketAdmin">
      <h1 class="support-agents__title">Support agents</h1>
      <p class="support-agents__muted">
        Only administrators can change who works the support queue.
      </p>
    </template>

    <template v-else>
      <div class="support-agents__header">
        <div>
          <h1 ref="heading" class="support-agents__title" tabindex="-1">Support agents</h1>
          <p class="support-agents__muted support-agents__subtitle">
            Everyone here can open the support queue. Administrators can already work it without
            being listed.
          </p>
        </div>
        <!-- Two ways in (the two ways out are in the comment below). The
             client asked for a support agent to be created "similar to how
             they can currently create a new admin user", and that form lives
             on the People page, but this is the screen somebody comes to when
             they think "how do I add a support person?", so the answer has to
             be here too.

             A link rather than a second copy of the dialog: the People editor
             already knows which fields each role needs, and a bespoke form
             here would be a second place to keep that in step. ?role=support
             is the parameter the People page's Users tab reads on arrival
             (AdminUsersView.vue).

             The label names where it goes because that is what it does. It
             opens a filtered list, not a form, and the form behind Add User
             there opens on Student, so a button that only said "Create a
             support agent" promised a step it does not take. Filtering to
             support does not make that list the roster either: a role is not
             queue access, and the paragraph below says so. -->
        <RouterLink
          :to="{ name: 'admin-users', query: { role: 'support' } }"
          class="btn btn-outline support-agents__create"
        >
          Create a support agent on the People page
        </RouterLink>
      </div>

      <!-- And two ways out. This page used to say, as the React one did, that
           removing access was only possible here. It is not: saving a Support
           account with another role on the People page revokes its access
           too (backend services/user.py, the role_moved branch), and
           AdminUserFormSheet.vue warns about that on the People page. Admin
           is the exception, because an administrator works the queue without
           being listed. What stays true is that revoking here never touches
           the role. -->
      <p class="support-agents__muted support-agents__prose">
        Adding someone here gives an existing account access to the queue. Creating a support agent
        makes a new account that has queue access and nothing else. The button above opens the
        People page, where the new account needs Support picked as its role. Revoking access here
        leaves the account's role as it is. On the People page, changing a Support account to
        another role also removes its access, unless the new role is Admin.
      </p>

      <!-- Says out loud what an admin would otherwise have to work out by
           comparing two screens. Granting and revoking queue access never
           touch the account's role, on purpose, so the People page goes on
           listing someone as Support after their access is gone, and someone
           whose role reads Mentor can be on this page and working the queue.
           Neither of those is a stale row waiting to catch up.

           The clause about administrators is load-bearing. They reach the
           queue through their admin access and are never listed here, which
           the heading above already says, so an unqualified "only place"
           would send anyone taking stock of queue access straight past every
           one of them. -->
      <p class="support-agents__muted support-agents__prose">
        The Role column on the People page records what an account is, not whether it can open the
        queue. Apart from administrators, this page is the only place that shows queue access.
      </p>

      <SupportAgentGrant :roster-ids="rosterIds" @granted="loadRoster" />

      <SupportRosterTable
        :agents="agents"
        :loading="rosterLoading"
        :failed="rosterFailed"
        :revoking="revoking"
        @revoke="askToRevoke"
      />

      <ConfirmDialog
        v-model="revokeOpen"
        :title="revokeTitle"
        :message="revokeMessage"
        confirm-label="Revoke access"
        variant="danger"
        :busy="revoking"
        @confirm="confirmRevoke"
      >
        <!-- A failed revoke used to show nothing at all in the React version:
             the dialog closed, the row stayed, and the admin was left to
             guess. The server answers 404 "Support access not found" when
             somebody else got there first.

             tabindex="-1" so confirmRevoke can put focus here after a
             refusal. While the request runs ConfirmDialog disables both of
             its buttons, and a browser drops focus from a button that
             becomes disabled to the page body, outside this dialog. -->
        <p
          v-if="revokeError"
          ref="revokeErrorEl"
          class="support-agents__dialog-error"
          role="alert"
          tabindex="-1"
        >
          {{ revokeError }}
        </p>
      </ConfirmDialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import SupportAgentGrant from '@/components/admin/support-agents/SupportAgentGrant.vue'
import SupportRosterTable from '@/components/admin/support-agents/SupportRosterTable.vue'
import { useAuthStore } from '@/stores/auth'
import { logApiError } from '@/utils/apiError'
import { fetchSupportRoster, revokeSupport, serverMessage } from '@/utils/ticketAgentAPI'
import type { SupportAgent } from '@/utils/ticketAgentSchema'

const auth = useAuthStore()

const heading = ref<HTMLElement | null>(null)

// --- The roster -------------------------------------------------------------

const agents = ref<SupportAgent[]>([])
const rosterLoading = ref(false)
const rosterFailed = ref(false)
const rosterIds = computed(() => agents.value.map((agent) => agent.id))

// A reload after a grant or a revoke can overlap the one before it; only the
// newest answer may paint the table.
let rosterSeq = 0

async function loadRoster() {
  const seq = ++rosterSeq
  rosterLoading.value = true
  rosterFailed.value = false
  try {
    const rows = await fetchSupportRoster()
    if (seq !== rosterSeq) return
    agents.value = rows
  } catch (error) {
    if (seq !== rosterSeq) return
    logApiError('admin.supportAgents.roster', error)
    rosterFailed.value = true
  } finally {
    if (seq === rosterSeq) rosterLoading.value = false
  }
}

// Loads only for the server's admin. The React page ran its queries before
// its own admin check, so a support agent who opened the address still sent
// the roster request and ate a 403; here nothing is sent for them. A watch
// rather than onMounted, so a store that learns the flag after mount (a
// /users/me/ refresh) still gets its roster.
watch(
  () => auth.isTicketAdmin,
  (isTicketAdmin) => {
    if (isTicketAdmin) void loadRoster()
  },
  { immediate: true }
)

// No cache to invalidate after a grant or a revoke. In React both mutations
// invalidated the assignee lists too, because "the assignee dropdowns are
// built from who can work the queue, so they go stale the moment the roster
// changes". In the portal the queue and the detail panel fetch assignees
// fresh when they open (ticketAgentAPI.ts header, T02), so there is no copy
// here to go stale; this page only reloads its own table.

// --- Revoking ---------------------------------------------------------------

const pending = ref<SupportAgent | null>(null)
const revokeOpen = ref(false)
const revoking = ref(false)
const revokeError = ref<string | null>(null)
const revokeErrorEl = ref<HTMLElement | null>(null)
let opener: HTMLElement | null = null
// Set when the dialog closes because the revoke went through: the row, and
// the button that opened the dialog with it, is about to be removed by the
// reload, so focus must not go back there.
let revokedOnClose = false

const revokeTitle = computed(() =>
  pending.value ? `Remove ${pending.value.name} from the support queue?` : ''
)

function askToRevoke(agent: SupportAgent, from: HTMLElement) {
  // Opening the dialog must not be the action itself.
  pending.value = agent
  revokeError.value = null
  opener = from
  revokeOpen.value = true
}

// The consequence an admin would not guess: revoking access does not hand the
// work to anybody. Saying nothing here is how three tickets end up owned by
// someone who can no longer open them.
const revokeMessage = computed(() => {
  const agent = pending.value
  if (!agent) return ''
  const work =
    agent.openTickets > 0
      ? `They still own ${agent.openTickets} ticket${agent.openTickets === 1 ? '' : 's'} that ` +
        'nobody else is working on. Revoking does not hand those to anyone else. They stay in ' +
        "this person's name until somebody reassigns them."
      : 'They will lose access to the support queue. Nothing else about their account changes.'
  // The one part of "nothing else changes" worth spelling out, and in both
  // branches. An admin who checks their work on the People page afterwards
  // reads Support next to a name the server now refuses, and the natural next
  // move is to edit that row, which does nothing.
  return `${work} The role listed for them on the People page does not change.`
})

async function confirmRevoke() {
  const agent = pending.value
  // Reads the live flag: a second press can land before busy is painted.
  if (!agent || revoking.value) return
  revoking.value = true
  revokeError.value = null
  let refused = false
  try {
    await revokeSupport(agent.id)
    revokedOnClose = true
    revokeOpen.value = false
  } catch (error) {
    logApiError('admin.supportAgents.revoke', error)
    revokeError.value = serverMessage(error) ?? 'That person was not removed from the queue.'
    refused = true
  } finally {
    revoking.value = false
  }
  // Reloaded whichever way it went. After a success the row goes. After a
  // failure the table may be what is wrong: a 404 means somebody else already
  // removed this person, and without a reload the row would stay and invite
  // the same refused click again.
  void loadRoster()
  // The dialog stays open to show the refusal, but the button that had focus
  // was disabled while the request ran, and the browser moved focus to the
  // page body. From there Esc never reaches the dialog (ConfirmDialog listens
  // on its own element) and Tab walks the page behind it. Radix trapped focus
  // in the React dialog, so this puts it back inside: on the reason, which is
  // what there is to read, with Cancel next in Tab order.
  if (refused) {
    await nextTick()
    revokeErrorEl.value?.focus()
  }
}

/** The confirmation's Cancel button. ConfirmDialog teleports to body and
 *  exposes no ref, so it is found by the title this page gave it, the way
 *  TicketDetailPanel.vue finds its "Keep it". */
function cancelButton(): HTMLButtonElement | null {
  for (const dialog of Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]'))) {
    if (dialog.querySelector('h2')?.textContent?.trim() !== revokeTitle.value) continue
    const buttons = Array.from(dialog.querySelectorAll<HTMLButtonElement>('button'))
    return buttons.find((button) => button.textContent?.trim() === 'Cancel') ?? null
  }
  return null
}

// The confirmation opens on Cancel, as the React AlertDialog did (Radix
// focuses its Cancel). ConfirmDialog focuses its confirm button instead, one
// tick after it opens (ConfirmDialog.vue focusConfirm), and here that is
// "Revoke access": a second Enter, or a key held down, would revoke straight
// away. So focus is moved once that has happened: the first tick here
// resumes before ConfirmDialog's (both wait on the same render), the second
// after it. The same fix as the delete confirmation in TicketDetailPanel.vue.
//
// ConfirmDialog moves focus in but never back. Return it to the Revoke button
// that opened the dialog; when that row is going (the revoke went through),
// land on the page heading rather than on the document body.
watch(revokeOpen, async (isOpen) => {
  if (isOpen) {
    await nextTick()
    await nextTick()
    if (revokeOpen.value) cancelButton()?.focus()
    return
  }
  pending.value = null
  revokeError.value = null
  const from = opener
  const revoked = revokedOnClose
  opener = null
  revokedOnClose = false
  await nextTick()
  if (!revoked && from && from.isConnected) from.focus()
  else heading.value?.focus()
})
</script>

<style scoped>
/* The colours this page and its two components print, in one place so the
   spec can measure them (supportAgentsContrast.spec.ts). --text-muted and
   --danger are 4.45:1 and 4.30:1 on .content-area's --bg-light, both under
   AA, so light takes literal values: #616970 and #a71d2a as
   TicketDetailPage.vue measured them, and #92400e for the amber mark (React
   used amber-700, #b45309, which is 4.39:1 on the row hover). Dark takes the
   theme's own --text-muted and --danger values, written out as literals so
   the spec can measure them, and a light amber.

   The first redesign round (October 2026) brings the muted grey to #5a6268,
   heads the roster in #24524a on pale green, and gives the search the
   ticket screens' placeholder, #6c757d. The rest are not text. The search
   box's edge is #84938f: 3.04:1 on the page and 3.21:1 on its white field;
   dark #70827d is 4.49:1 and 4.15:1. Revoke sits on a table row that turns
   peach under the pointer, where #84938f falls to 2.80:1, so it takes
   #7a8884, the bulk bar's edge on the same peach (3.23:1). In dark it keeps
   #70827d, 3.59:1 on a hovered row. Then come the results card's frame,
   rules and shadow, and the green edge on Grant and on the search box when
   it has focus. The designer drew this page in light only; dark keeps its
   colours. */
.support-agents {
  --roster-muted: #5a6268;
  --roster-danger: #a71d2a;
  --roster-warn: #92400e;
  --roster-head: #24524a;
  --roster-placeholder: #6c757d;
  --roster-edge: #84938f;
  --roster-row-edge: #7a8884;
  --roster-frame: #e3e7e5;
  --roster-rule: #e6eae8;
  --roster-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);
  --roster-accent: var(--dark-green);
  --roster-focus: var(--dark-green);

  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

:root[data-theme='dark'] .support-agents {
  --roster-muted: #8a9a96;
  --roster-danger: #f87171;
  --roster-warn: #fbbf24;
  --roster-head: #e6efed;
  --roster-placeholder: #8a9a96;
  --roster-edge: #70827d;
  --roster-row-edge: #70827d;
  --roster-frame: var(--border-light);
  --roster-rule: var(--border-light);
  --roster-shadow: 0 1px 2px var(--shadow);
  --roster-accent: var(--mint-green);
  --roster-focus: var(--mint-green);
}

.support-agents__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

/* Spaced as the Tickets section's title: a 1px gap, not 4px, puts the
   subtitle where the design has it. */
.support-agents__title {
  margin: 0 0 1px;
  font-size: 2rem;
  line-height: 1.1;
  letter-spacing: -0.01em;
}

.support-agents__title:focus {
  outline: none;
}

.support-agents__title:focus-visible {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

.support-agents__muted {
  margin: 0;
  color: var(--roster-muted);
}

.support-agents__prose {
  max-width: 47.5rem;
  font-size: 0.875rem;
}

/* Words close together, a little more air before the controls. */
.support-agents > .support-grant {
  margin-top: 0.5rem;
}

.support-agents :deep(.support-roster) {
  margin-top: 0.375rem;
}

/* The redesign's secondary button: white, a brand green edge, bold. Written
   over the global .btn-outline here rather than changed there. */
.support-agents__create {
  min-height: 2.5rem;
  padding: 0 1.25rem;
  border: 1px solid var(--roster-accent);
  border-radius: 8px;
  background-color: var(--white);
  font-size: 0.875rem;
  font-weight: 700;
}

/* The global focus ring is --dark-green, which the dark theme does not
   redefine: 2.79:1 on the --white under the Grant and Revoke buttons, under
   the 3:1 a focus indicator needs. --mint-green is 6.13:1 there, the colour
   the audit, analytics and detail rings already use in dark. :deep so it
   reaches the two components and the table they sit in. It cannot reach the
   revoke confirmation, which ConfirmDialog teleports to body. Checked by
   supportAgentsContrast.spec.ts. */
:root[data-theme='dark'] .support-agents :deep(:focus-visible) {
  outline-color: var(--mint-green);
}

/* --dark-green is not redefined in the dark theme and is 3.02:1 on its
   --bg-light there; --mint-green is 6.63:1. Scoped to this page's buttons so
   the global .btn-outline stays Team 1's. */
:root[data-theme='dark'] .support-agents :deep(.btn-outline) {
  color: var(--mint-green);
}

/* Teleported with the dialog, so it cannot inherit --roster-danger from the
   page: the dialog is a child of body. Measured on the dialog's --white. */
.support-agents__dialog-error {
  margin: 0.75rem 0 0;
  color: #a71d2a;
}

:root[data-theme='dark'] .support-agents__dialog-error {
  color: #f87171;
}
</style>
