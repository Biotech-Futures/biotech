<template>
  <span class="force-delete-notice">
    Force delete: also permanently delete each {{ subject }}'s chat messages, uploaded resources,
    workshops, match runs, and any support ticket they raised, including the replies and internal
    notes support staff wrote on it. Required to remove accounts that have any activity.
  </span>
</template>

<script setup lang="ts">
/**
 * What "Force delete" destroys, written once (ported from
 * adminweb/src/components/people/ForceDeleteNotice.tsx).
 *
 * There were seven copies of this sentence in adminweb (three checkbox
 * labels, two code comments and two backend docstrings) and they had
 * drifted: every one of them listed chat messages, uploaded resources,
 * workshops and match runs, and none of them mentioned support tickets, which
 * the purge has destroyed since the ticketing work landed (services/user.py,
 * the purge in delete_user). An admin clearing out a student who has left was
 * told four things would go and five did, the fifth being enquiries an agent
 * may still be working. The portal's People page had the same two stale
 * copies (bulk and single delete in AdminUsersView.vue).
 *
 * Adding tickets to every copy would only have moved the drift a release
 * later, so the copies are gone instead: this component is the only place the
 * list exists in the portal.
 *
 * Deliberately just the sentence: no checkbox, no state. Each dialog keeps its
 * own control and its own wiring; what they share is the promise made to the
 * person clicking it.
 *
 * The one change from adminweb's words: "Force delete:" takes a colon where
 * adminweb has an em-dash, because the port's UI copy carries no em-dashes
 * (port-design.md section 7).
 */
defineProps<{
  /** Whose content it is: "user", "student" or "supervisor", the noun of the
   *  People tab the dialog was opened from. Students and Supervisors share
   *  AdminUsersView, so one hard-coded noun would read "each user's" on the
   *  students tab, which is where most tickets come from. */
  subject: string
}>()
</script>
