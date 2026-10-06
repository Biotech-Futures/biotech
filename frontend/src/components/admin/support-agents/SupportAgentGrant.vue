<template>
  <section class="support-grant" aria-label="Grant support access">
    <input
      ref="searchInput"
      v-model="term"
      type="search"
      class="support-grant__search"
      placeholder="Search by name or email to add someone"
      aria-label="Search for a person to grant support access"
      autocomplete="off"
    />

    <ul v-if="trimmed !== ''" class="support-grant__results">
      <!-- role="status" on an inner span, not on the li: a role on the li
           replaces listitem and leaves the ul with a child that is not one. -->
      <li v-if="shownCandidates.length === 0" class="support-grant__status">
        <span role="status">{{ searchStatus }}</span>
      </li>
      <li v-for="person in shownCandidates" :key="person.id" class="support-grant__candidate">
        <span class="support-grant__who">
          <!-- Which of two similar names is the live account. The server
               refuses a grant to an account that cannot sign in
               (views_admin._grant_refusal) and answers with a sentence, which
               is the message below.

               The mark is not that refusal repeated: this reads isActive,
               which is false for an invited or a pending account as well, and
               both of those the server grants. So a row can carry this mark
               and still go through. The roster table marks rows off the
               account's own status, which is the field that decides it.

               One line on purpose: the spaces between the spans keep name,
               email and mark apart in the text a screen reader gets. -->
          <span>{{ displayName(person) }}</span> <span class="support-grant__email">{{ person.email }}</span> <span v-if="!person.isActive" class="support-grant__mark">Not an active account</span>
        </span>
        <!-- Disabled only while a grant is in flight or for someone already on
             the roster. Never on isActive: that is false for an invited
             account the server is happy to grant, so refusing here would block
             an ordinary case on a signal that does not decide it. The server
             owns the rule, and the refusal below shows what it said. -->
        <button
          type="button"
          class="btn btn-outline btn-sm support-grant__button"
          :class="{ 'support-grant__button--on': isOnRoster(person) }"
          :disabled="isOnRoster(person) || granting"
          @click="grant(person, $event.currentTarget as HTMLButtonElement)"
        >
          {{ isOnRoster(person) ? 'Already on' : 'Grant' }}
          <span class="sr-only">{{ displayName(person) }}</span>
        </button>
      </li>
    </ul>

    <!-- The other half of the grant guard. The server refuses a student
         account and an account that cannot sign in, and each refusal is a
         sentence written for the admin reading it ("Reactivate it first, then
         grant support access."). Nothing read them in the first React
         version, so pressing Grant on one of those rows did nothing at all:
         the row stayed put, the button stayed enabled, and the admin pressed
         it again.

         serverMessage and not ticketRefusalReason: this endpoint answers the
         msg/data envelope directly rather than raising, so the reason is in
         msg and not in the error/code shape the ticket write path uses. -->
    <p v-if="grantError" class="support-grant__error" role="alert">{{ grantError }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import '@/components/support/ticketControls.css'

import { fetchAdminUsers, type AdminUser } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { grantSupport, serverMessage } from '@/utils/ticketAgentAPI'

const props = defineProps<{
  /** Ids of everybody already on the roster, for the "Already on" button. */
  rosterIds: number[]
}>()

const emit = defineEmits<{
  (e: 'granted', userId: number): void
}>()

// Same pause as the People page's own search box (useAdminUsersView.ts uses
// 350 ms, AdminGroupsPage 300 ms): a request per keystroke would put five
// requests in flight for a five-letter name.
const SEARCH_DEBOUNCE_MS = 300
const CANDIDATE_LIMIT = 10

const searchInput = ref<HTMLInputElement | null>(null)
const term = ref('')
const trimmed = computed(() => term.value.trim())

// What came back, and for which term. items null means the search failed.
// Keyed by term so a result is only ever shown under the words it answers.
const outcome = ref<{ term: string; items: AdminUser[] | null } | null>(null)

const granting = ref(false)
const grantError = ref<string | null>(null)

let timer: ReturnType<typeof setTimeout> | null = null
// Every search, and every clearing of the box, takes a new number; an answer
// carrying an older one is dropped. Without it a slow reply for "ol" could
// land after the reply for "ola" and list the wrong people under "ola".
let searchSeq = 0

async function runSearch(forTerm: string) {
  const seq = ++searchSeq
  try {
    const data = await fetchAdminUsers({ search: forTerm, limit: CANDIDATE_LIMIT })
    if (seq !== searchSeq) return
    outcome.value = { term: forTerm, items: data.items }
  } catch (error) {
    if (seq !== searchSeq) return
    logApiError('admin.supportAgents.search', error)
    outcome.value = { term: forTerm, items: null }
  }
}

// Only searches once there is something to search for: an empty term would
// pull the whole user list to fill a dropdown nobody opened. (The React
// version said this in a comment while its query still ran on an empty term;
// here the request is simply never made.)
watch(trimmed, (value) => {
  if (timer) clearTimeout(timer)
  timer = null
  if (value === '') {
    searchSeq += 1
    outcome.value = null
    return
  }
  timer = setTimeout(() => {
    timer = null
    void runSearch(value)
  }, SEARCH_DEBOUNCE_MS)
})

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
  searchSeq += 1
})

const shownCandidates = computed<AdminUser[]>(() => {
  const current = outcome.value
  if (!current || current.term !== trimmed.value || !current.items) return []
  return current.items
})

const searchStatus = computed(() => {
  const current = outcome.value
  if (!current || current.term !== trimmed.value) return 'Searching…'
  // Not in the React version, which answered a failed search with "Nobody
  // matched." and so told the admin the person does not exist.
  if (current.items === null) return 'The search could not be run. Try again.'
  return 'Nobody matched.'
})

// AdminUser.id is typed as a number and the endpoint sends one, but
// adminAPI.ts does not validate what it receives, so the type is a claim and
// not a check. adminweb's copy of this endpoint really did hand out string ids
// while the ticket module works in numbers, so every crossing point converts
// explicitly rather than relying on == somewhere downstream.
const rosterSet = computed(() => new Set(props.rosterIds.map(Number)))
const isOnRoster = (person: AdminUser) => rosterSet.value.has(Number(person.id))

function displayName(person: AdminUser) {
  const name = [person.firstName, person.lastName].filter(Boolean).join(' ').trim()
  return name || person.email || ''
}

async function grant(person: AdminUser, pressed?: HTMLButtonElement) {
  // Reads the live flag, not what the button last rendered: a second click
  // can arrive before the disabled state is painted.
  if (granting.value || isOnRoster(person)) return
  const userId = Number(person.id)
  granting.value = true
  grantError.value = null
  let refused = false
  try {
    await grantSupport(userId)
    // Done with this person: the box empties, the list closes, and focus goes
    // back to the box for the next name rather than to the page body (the
    // button that had it is gone with the list).
    term.value = ''
    emit('granted', userId)
    await nextTick()
    searchInput.value?.focus()
  } catch (error) {
    logApiError('admin.supportAgents.grant', error)
    // A network fault has no msg, and printing only serverMessage would put
    // an empty alert on screen for it.
    grantError.value = serverMessage(error) ?? 'That person was not added to the queue.'
    refused = true
  } finally {
    granting.value = false
  }
  // Every Grant button is disabled while the request runs, and a browser
  // drops focus from a disabled button to the page body. After a refusal the
  // list is still there, so focus goes back to the button that was pressed:
  // the reason is announced by its role="alert", and the next Tab is the next
  // candidate rather than the top of the page. Only when focus really was
  // lost: somebody who went back to the search box while the request ran
  // keeps their place.
  if (refused) {
    await nextTick()
    const active = document.activeElement
    const lost = !active || active === document.body || active === pressed
    if (lost && pressed?.isConnected) pressed.focus()
  }
}
</script>

<style scoped>
/* Colours come from the page (SupportAgentsPage.vue sets --roster-* for both
   themes and its spec measures them); this box sits on --white. The first
   redesign round (October 2026) gives the search a visible edge, the
   results a floating card with a rule between people, Grant a green edge and
   Already on plain grey words. */
.support-grant {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

/* Focus shows on the edge itself, green with a soft wash round it, the way
   the student form's fields do. The browser's cross is swapped for the thin
   one from ticketControls.css. */
.support-grant__search {
  width: 100%;
  max-width: 27.5rem;
  height: 2.75rem;
  padding: 0 0.75rem;
  border: 1px solid var(--roster-edge);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.95rem;
}

.support-grant__search::placeholder {
  color: var(--roster-placeholder);
  opacity: 1;
}

.support-grant__search:focus-visible {
  outline: none;
  border-color: var(--roster-focus);
  box-shadow: 0 0 0 3px var(--light-green);
}

.support-grant__search::-webkit-search-cancel-button {
  -webkit-appearance: none;
  appearance: none;
  width: 0.875rem;
  height: 0.875rem;
  margin-right: 0.35rem;
  background: var(--ticket-clear-x) no-repeat center;
  cursor: pointer;
}

.support-grant__results {
  max-width: 27.5rem;
  margin: 0;
  padding: 0.375rem;
  list-style: none;
  border: 1px solid var(--roster-frame);
  border-radius: 12px;
  background-color: var(--white);
  box-shadow: var(--roster-shadow);
}

.support-grant__status {
  padding: 0.25rem;
  color: var(--roster-muted);
  font-size: 0.875rem;
}

.support-grant__candidate {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-height: 2.75rem;
  padding: 0 0.45rem 0 0.7rem;
  font-size: 0.9rem;
  color: var(--charcoal);
}

.support-grant__candidate + .support-grant__candidate {
  border-top: 1px solid var(--roster-rule);
}

.support-grant__who {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 0.625rem;
  min-width: 0;
  overflow-wrap: anywhere;
}

.support-grant__email {
  color: var(--roster-muted);
  font-size: 0.8rem;
}

.support-grant__mark {
  color: var(--roster-warn);
  font-size: 0.75rem;
  font-weight: 600;
}

.support-grant__button {
  flex-shrink: 0;
  min-height: 2rem;
  padding: 0 0.75rem;
  border-color: var(--roster-accent);
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 700;
}

/* Someone already listed: the same disabled button, read as words. Solid,
   not faded the way a disabled button is, since it is a fact rather than a
   control that cannot be used right now. */
.support-grant__button--on,
.support-grant__button--on:disabled,
.support-grant__button--on:disabled:hover {
  border-color: transparent;
  background-color: transparent;
  color: var(--roster-muted);
  opacity: 1;
}

.support-grant__error {
  margin: 0;
  color: var(--roster-danger);
  font-size: 0.875rem;
}
</style>
