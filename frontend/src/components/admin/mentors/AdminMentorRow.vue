<template>
  <tr
    class="admin-mentors__row"
    :class="{
      'admin-mentors__row--inactive': effectivelyInactive,
      'admin-mentors__row--selected': selected
    }"
    @click="emit('toggle-expand', mentor.mentorId)"
  >
    <td class="admin-mentors__check" @click.stop>
      <input
        type="checkbox"
        :checked="selected"
        :aria-label="`Select ${mentor.name}`"
        :disabled="loading"
        @change="emit('toggle-select', mentor.mentorId)"
      />
    </td>
    <td class="admin-mentors__expand">
      <button
        type="button"
        class="admin-mentors__chevron"
        :aria-expanded="expanded"
        :aria-label="expanded ? `Collapse ${mentor.name}` : `Expand ${mentor.name}`"
        @click.stop="emit('toggle-expand', mentor.mentorId)"
      >
        <i class="fas" :class="expanded ? 'fa-chevron-down' : 'fa-chevron-right'" aria-hidden="true"></i>
      </button>
    </td>
    <td>
      <p class="admin-mentors__name">{{ mentor.name }}</p>
      <p class="admin-mentors__sub">{{ mentor.email }}</p>
    </td>
    <td>
      <span class="admin-mentors__pill">{{ mentor.countryName ?? 'Unknown' }}</span>
    </td>
    <td class="admin-mentors__muted">{{ mentor.institution ?? '—' }}</td>
    <td>
      {{ mentor.currentAssignedCount }}/{{ mentor.maxGroupCount }}
      <span class="admin-mentors__sub">({{ mentor.remainingCapacity }} left)</span>
    </td>
    <td class="admin-mentors__muted">
      <span
        v-if="mentor.lastMessageAt"
        :class="{ 'admin-mentors__danger': lastMessageDays(mentor.lastMessageAt) >= inactiveDays }"
      >
        {{ relativeDays(mentor.lastMessageAt) }}
      </span>
      <span v-else class="admin-mentors__never">
        <i class="fas fa-comment-slash" aria-hidden="true"></i>
        Never
      </span>
    </td>
    <td @click.stop>
      <div class="admin-mentors__status-cell">
        <span v-if="mentor.isActive" class="admin-mentors__active-badge">
          <i class="fas fa-check-circle" aria-hidden="true"></i>
          Active
        </span>
        <span v-else class="admin-mentors__danger">
          <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
          Inactive
        </span>
        <button
          type="button"
          class="btn btn-sm btn-outline"
          :disabled="statusBusy"
          @click="emit('toggle-active', mentor)"
        >
          {{ mentor.isActive ? 'Deactivate' : 'Activate' }}
        </button>
      </div>
    </td>
    <td class="admin-mentors__muted">
      <span v-if="mentor.hasLoggedIn" class="admin-mentors__logged-in">
        <span class="admin-mentors__pill admin-mentors__pill--green">Yes</span>
        <span v-if="mentor.lastLogin" class="admin-mentors__sub" :title="formatLogin(mentor.lastLogin)">
          {{ loginDate(mentor.lastLogin) }}
        </span>
      </span>
      <span v-else class="admin-mentors__pill">No</span>
    </td>
  </tr>

  <tr v-if="expanded" class="admin-mentors__detail-row">
    <td :colspan="9" class="admin-mentors__detail">
      <div class="admin-mentors__detail-grid">
        <section>
          <p class="admin-mentors__section-title">Account Info</p>
          <dl class="admin-mentors__detail-list">
            <div><dt>User ID:</dt><dd class="admin-mentors__mono">{{ mentor.mentorId }}</dd></div>
            <div><dt>Email:</dt><dd>{{ mentor.email }}</dd></div>
            <div><dt>Institution:</dt><dd>{{ mentor.institution ?? '—' }}</dd></div>
            <div><dt>Max Groups:</dt><dd>{{ mentor.maxGroupCount }}</dd></div>
            <div>
              <dt>Logged In:</dt>
              <dd>{{ mentor.hasLoggedIn ? `Yes${mentor.lastLogin ? ` (${formatLogin(mentor.lastLogin)})` : ''}` : 'No (Never logged in)' }}</dd>
            </div>
          </dl>
        </section>

        <section>
          <p class="admin-mentors__section-title">Interests</p>
          <div v-if="mentor.interests.length" class="admin-mentors__chips">
            <span v-for="interest in mentor.interests" :key="interest" class="admin-mentors__chip">
              {{ interest }}
            </span>
          </div>
          <p v-else class="admin-mentors__muted">No interests listed.</p>
        </section>

        <section>
          <p class="admin-mentors__section-title">
            <i class="fas fa-clock" aria-hidden="true"></i>
            Availability
          </p>
          <div v-if="mentor.availability.length" class="admin-mentors__chips">
            <span
              v-for="(slot, index) in sortedAvailability(mentor.availability)"
              :key="index"
              class="admin-mentors__availability-slot"
            >
              <span class="admin-mentors__slot-day">{{ WEEKDAYS[slot.weekday] }}</span>
              <span class="admin-mentors__muted">{{ slot.startTime.slice(0, 5) }}–{{ slot.endTime.slice(0, 5) }}</span>
            </span>
          </div>
          <p v-else class="admin-mentors__muted">No availability set.</p>
        </section>

        <section>
          <p class="admin-mentors__section-title">
            <i class="fas fa-shield-alt" aria-hidden="true"></i>
            Certificates
          </p>
          <div v-if="mentor.certificates.length" class="admin-mentors__certificates">
            <div v-for="(cert, index) in mentor.certificates" :key="index" class="admin-mentors__cert">
              <div>
                <span class="admin-mentors__cert-name">{{ cert.certificateTypeName }}</span>
                <span v-if="cert.verifiedAt" class="admin-mentors__verified">
                  <i class="fas fa-shield-alt" aria-hidden="true"></i>
                  Verified
                </span>
                <span v-else class="admin-mentors__muted">Unverified</span>
              </div>
              <div class="admin-mentors__sub">
                <template v-if="cert.certificateNumber">No. {{ cert.certificateNumber }}</template>
                <template v-if="cert.issuedBy">Issued by: {{ cert.issuedBy }}</template>
                <span>Issued: {{ cert.issuedAt }}</span>
                <span v-if="cert.expiresAt">Expires: {{ cert.expiresAt }}</span>
              </div>
              <a
                v-if="cert.fileUrl"
                :href="cert.fileUrl"
                target="_blank"
                rel="noopener noreferrer"
                class="admin-mentors__link"
              >
                View file
              </a>
            </div>
          </div>
          <p v-else class="admin-mentors__muted">No certificates on file.</p>
        </section>
      </div>
    </td>
  </tr>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AdminMentorDetail } from '@/utils/adminAPI'
import {
  WEEKDAYS,
  formatLogin,
  isEffectivelyInactive,
  lastMessageDays,
  loginDate,
  relativeDays,
  sortedAvailability
} from '@/utils/mentorFormat'

const props = withDefaults(
  defineProps<{
    mentor: AdminMentorDetail
    selected: boolean
    expanded: boolean
    statusBusy?: boolean
    loading?: boolean
    inactiveDays: number
  }>(),
  {
    statusBusy: false,
    loading: false
  }
)

const effectivelyInactive = computed(() => isEffectivelyInactive(props.mentor, props.inactiveDays))

const emit = defineEmits<{
  (e: 'toggle-select', mentorId: number): void
  (e: 'toggle-expand', mentorId: number): void
  (e: 'toggle-active', mentor: AdminMentorDetail): void
}>()
</script>

<style scoped>
.admin-mentors__row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.admin-mentors__row:hover {
  background-color: var(--light-green);
}

.admin-mentors__row--selected {
  background-color: rgba(1, 113, 81, 0.08);
}

.admin-mentors__row--inactive {
  background-color: rgba(220, 53, 69, 0.04);
}

.admin-mentors__row td {
  padding: 0.75rem 1rem;
  color: var(--charcoal);
  border-bottom: 1px solid var(--border-light);
}

.admin-mentors__check {
  width: 42px;
  padding: 0.75rem 0.5rem;
  text-align: center;
}

.admin-mentors__check input[type='checkbox'] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--dark-green);
}

.admin-mentors__expand {
  width: 34px;
  padding: 0.75rem 0.25rem;
}

.admin-mentors__chevron {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background-color: transparent;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: pointer;
}

.admin-mentors__chevron:hover {
  background-color: var(--light-green);
  color: var(--dark-green);
}

.admin-mentors__name {
  margin: 0;
  font-weight: 600;
}

.admin-mentors__sub {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.admin-mentors__muted {
  font-size: 0.9rem;
  color: var(--text-muted);
}

.admin-mentors__danger {
  color: var(--danger);
  font-size: 0.85rem;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.admin-mentors__never {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.admin-mentors__pill {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--bg-light);
  font-size: 0.8rem;
  color: var(--charcoal);
  white-space: nowrap;
}

.admin-mentors__pill--green {
  border-color: rgba(25, 135, 84, 0.3);
  background-color: rgba(25, 135, 84, 0.1);
  color: var(--dark-green);
}

.admin-mentors__status-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-mentors__active-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--dark-green);
}

.admin-mentors__logged-in {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
}

.admin-mentors__mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.admin-mentors__detail-row td {
  padding: 0;
  background-color: rgba(1, 113, 81, 0.04);
}

.admin-mentors__detail {
  border-bottom: 1px solid var(--border-light);
}

.admin-mentors__detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
  padding: 1.1rem 1.5rem;
}

.admin-mentors__detail-grid section {
  min-width: 0;
}

.admin-mentors__section-title {
  margin: 0 0 0.5rem;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.admin-mentors__section-title i {
  font-size: 0.8rem;
}

.admin-mentors__detail-list {
  margin: 0;
}

.admin-mentors__detail-list div {
  display: flex;
  gap: 0.5rem;
  margin: 0.15rem 0;
  font-size: 0.8rem;
}

.admin-mentors__detail-list dt {
  color: var(--text-muted);
}

.admin-mentors__detail-list dd {
  margin: 0;
}

.admin-mentors__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.admin-mentors__chip {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background-color: var(--light-green);
  border: 1px solid var(--border-light);
  font-size: 0.8rem;
}

.admin-mentors__availability-slot {
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  font-size: 0.8rem;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.admin-mentors__slot-day {
  font-weight: 600;
}

.admin-mentors__certificates {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.admin-mentors__cert {
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  font-size: 0.8rem;
}

.admin-mentors__cert-name {
  font-weight: 600;
}

.admin-mentors__verified {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  margin-left: 0.5rem;
  color: var(--dark-green);
  font-size: 0.75rem;
}

.admin-mentors__cert > div:nth-child(2) {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  margin: 0.2rem 0;
}

.admin-mentors__link {
  color: var(--dark-green);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.admin-mentors__link:hover {
  text-decoration: none;
}
</style>