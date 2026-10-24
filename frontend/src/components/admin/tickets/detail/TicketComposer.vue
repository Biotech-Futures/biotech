<template>
  <!-- One box with two tabs, as the designer's second round draws it (D2-16,
       after Zendesk and Intercom): a reply the requester reads and is emailed
       about, or a note only support will ever see. The whole box turns amber
       on the note side, so which of the two is open does not depend on
       reading a tab label at the end of a long shift. -->
  <section class="composer" :class="`composer--${mode}`">
    <div class="composer__tabs" role="tablist" aria-label="Write to">
      <button
        v-for="item in MODES"
        :id="tabId(item.key)"
        :key="item.key"
        :ref="(el) => (tabButtons[item.key] = el as HTMLButtonElement | null)"
        type="button"
        role="tab"
        class="composer__tab"
        :aria-selected="mode === item.key"
        :aria-controls="panelId(item.key)"
        :tabindex="mode === item.key ? 0 : -1"
        @click="mode = item.key"
        @keydown="onTabKeydown"
      >
        <TicketIcon v-if="item.key === 'note'" name="lock" :size="14" />
        {{ item.label }}
      </button>
    </div>

    <!-- v-show, so each side keeps its own draft and its own files. Switching
         never carries words across: a note written on the wrong side and
         switched over would otherwise arrive in the reply box, one click away
         from the requester's inbox. -->
    <div
      v-show="mode === 'reply'"
      :id="panelId('reply')"
      role="tabpanel"
      class="composer__panel"
      :aria-labelledby="tabId('reply')"
    >
      <TicketReplyComposer :send="sendReply" />
    </div>
    <div
      v-show="mode === 'note'"
      :id="panelId('note')"
      role="tabpanel"
      class="composer__panel"
      :aria-labelledby="tabId('note')"
    >
      <TicketNoteComposer :send="sendNote" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { nextTick, ref, useId } from 'vue'

import TicketIcon from '@/components/support/TicketIcon.vue'

import type { ReplyStatus } from '@/utils/ticketAgentAPI'

import TicketNoteComposer from './TicketNoteComposer.vue'
import TicketReplyComposer from './TicketReplyComposer.vue'

defineProps<{
  sendReply: (body: string, files: File[], nextStatus: ReplyStatus) => Promise<unknown>
  sendNote: (body: string, files: File[]) => Promise<unknown>
}>()

type Mode = 'reply' | 'note'

const MODES: { key: Mode; label: string }[] = [
  { key: 'reply', label: 'Reply to the requester' },
  { key: 'note', label: 'Internal note' }
]

// The reply side first, as the designer draws every ticket that opens. The
// panel keys this box by ticket, so a new ticket always starts here.
const mode = ref<Mode>('reply')
const tabButtons: Partial<Record<Mode, HTMLButtonElement | null>> = {}

const idBase = useId()
const tabId = (key: Mode) => `${idBase}-tab-${key}`
const panelId = (key: Mode) => `${idBase}-panel-${key}`

// The panel's own tabs work this way too: arrows and Home/End move between
// the two and the focus goes with them.
function onTabKeydown(event: KeyboardEvent) {
  const order = MODES.map((item) => item.key)
  const at = order.indexOf(mode.value)
  let next: Mode | undefined
  if (event.key === 'ArrowRight') next = order[(at + 1) % order.length]
  else if (event.key === 'ArrowLeft') next = order[(at - 1 + order.length) % order.length]
  else if (event.key === 'Home') next = order[0]
  else if (event.key === 'End') next = order[order.length - 1]
  if (!next) return
  event.preventDefault()
  mode.value = next
  void nextTick(() => tabButtons[next]?.focus())
}
</script>

<style scoped>
/* The designer's colours for both sides. Measured (WCAG AA: 4.5:1 for text,
   3:1 for the bar that marks the open tab):
     light  reply  tabs #174243 / #5a6268 on #f8f9fa 10.50 / 5.89
                   open tab #017151 5.72
            note   tabs #174243 / #5a6268 on #fff8e6 10.45 / 5.86
                   open tab #bd851e 3.03
     dark   reply  tabs #e6efed / #a3b3ae on #161f1d 14.37 / 7.71
                   open tab #5ea99e 6.13
            note   tabs #e6efed / #a3b3ae on #2a2516 13.05 / 7.00
                   open tab #d08a1e 5.34
   The light note bar is his #e0a63a taken a shade darker in the same hue:
   his is 2.05:1 on the amber ground, under the 3:1 the mark of the open tab
   needs. */
.composer {
  --composer-ground: #f8f9fa;
  --composer-frame: #e3e7e5;
  --composer-rule: #e6eae8;
  --composer-mark: #017151;
  --composer-muted: #5a6268;

  border: 1px solid var(--composer-frame);
  border-radius: 12px;
  background: var(--composer-ground);
  color: var(--teal);
}

.composer--note {
  --composer-ground: #fff8e6;
  --composer-frame: #f1dfb5;
  --composer-rule: #f1dfb5;
  --composer-mark: #bd851e;
}

:root[data-theme='dark'] .composer {
  --composer-ground: #161f1d;
  --composer-frame: #2b3936;
  --composer-rule: #2b3936;
  --composer-mark: #5ea99e;
  --composer-muted: #a3b3ae;
}

:root[data-theme='dark'] .composer--note {
  --composer-ground: #2a2516;
  --composer-frame: #4a3f22;
  --composer-rule: #4a3f22;
  --composer-mark: #d08a1e;
}

.composer__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0 0.75rem;
  border-bottom: 1px solid var(--composer-rule);
}

.composer__tab {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: -1px;
  padding: 1rem 0.75rem 0.5rem;
  border: none;
  border-bottom: 3px solid transparent;
  background: none;
  color: var(--composer-muted);
  font-family: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}

.composer__tab[aria-selected='true'] {
  border-bottom-color: var(--composer-mark);
  color: var(--teal);
}

.composer__tab:hover:not([aria-selected='true']) {
  color: var(--teal);
}

.composer__panel {
  padding: 0.875rem 1rem;
}

@media (prefers-reduced-motion: no-preference) {
  .composer {
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
}
</style>
