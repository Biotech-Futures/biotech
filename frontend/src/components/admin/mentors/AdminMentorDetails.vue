<template>
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
</template>

<script setup lang="ts">
import type { AdminMentorDetail } from '@/utils/adminAPI'
import { WEEKDAYS, formatLogin, sortedAvailability } from '@/utils/mentorFormat'

// A mentor's account, interests, availability and certificates, shown under
// their row on the Mentors tab.
defineProps<{
  mentor: AdminMentorDetail
}>()
</script>

<style scoped>
/* The table's details row gives the padding. */
.admin-mentors__detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
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

.admin-mentors__mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
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
