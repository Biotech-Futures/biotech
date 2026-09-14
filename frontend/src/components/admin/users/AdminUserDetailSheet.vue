<template>
  <FormSheet
    :model-value="open"
    :title="detailTitle"
    description="Account details"
    width="min(100vw, 620px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <div class="admin-users-detail">
      <section v-if="user" class="admin-users-detail__section">
        <h3>Account</h3>
        <dl class="admin-users-detail__list">
          <div class="admin-users-detail__item">
            <dt>Email</dt>
            <dd>{{ user.email || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Role</dt>
            <dd><span class="admin-users__role-badge">{{ roleLabel(user.role) }}</span></dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Country</dt>
            <dd>{{ labelizeCountry(user.country) }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>State</dt>
            <dd>{{ labelizeState(user.state) }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Status</dt>
            <dd>
              <span class="admin-users__status-badge" :class="{ 'admin-users__status-badge--inactive': !user.isActive }">
                {{ user.isActive ? 'Active' : 'Inactive' }}
              </span>
            </dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Has logged in</dt>
            <dd>
              <span class="admin-users__logged-in-badge" :class="{ 'admin-users__logged-in-badge--yes': user.hasLoggedIn }">
                {{ user.hasLoggedIn ? 'Yes' : 'No' }}
              </span>
            </dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Last login</dt>
            <dd>{{ user.lastLogin ? formatFullDate(user.lastLogin) : 'Never' }}</dd>
          </div>
        </dl>
      </section>

      <section v-if="user?.role === 'student'" class="admin-users-detail__section">
        <h3>Student Profile</h3>
        <dl class="admin-users-detail__list">
          <div class="admin-users-detail__item">
            <dt>School</dt>
            <dd>{{ user.schoolName || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Year level</dt>
            <dd>{{ user.yearLevel ?? '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Interests</dt>
            <dd>{{ joinInterests(user.interests) }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Group</dt>
            <dd>{{ user.groupName || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Supervisor</dt>
            <dd>{{ supervisorLabel(user) }}</dd>
          </div>
        </dl>
      </section>

      <section v-if="user?.role === 'mentor'" class="admin-users-detail__section">
        <h3>Mentor Profile</h3>
        <dl class="admin-users-detail__list">
          <div class="admin-users-detail__item">
            <dt>Interests / Expertise</dt>
            <dd>{{ joinInterests(user.interests) }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Institution</dt>
            <dd>{{ user.mentorInstitution || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Background</dt>
            <dd>{{ user.mentorBackground || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Mentor reason</dt>
            <dd>{{ user.mentorReason || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Max groups</dt>
            <dd>{{ user.mentorMaxGroupCount ?? '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Group</dt>
            <dd>{{ user.groupName || '—' }}</dd>
          </div>
        </dl>
      </section>

      <section v-if="user?.role === 'supervisor'" class="admin-users-detail__section">
        <h3>Supervisor Profile</h3>
        <dl class="admin-users-detail__list">
          <div class="admin-users-detail__item">
            <dt>School</dt>
            <dd>{{ user.schoolName || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Group</dt>
            <dd>{{ user.groupName || '—' }}</dd>
          </div>
          <div class="admin-users-detail__item">
            <dt>Supervisees</dt>
            <dd class="admin-users-detail__supervisees">
              <span v-if="!user.supervisees?.length">—</span>
              <span v-else>{{ superviseesLabel(user) }}</span>
            </dd>
          </div>
        </dl>
      </section>

      <section v-if="user?.role === 'admin'" class="admin-users-detail__section">
        <h3>Admin Profile</h3>
        <dl class="admin-users-detail__list">
          <div class="admin-users-detail__item">
            <dt>Scope</dt>
            <dd>Admin</dd>
          </div>
        </dl>
      </section>
    </div>

    <div class="admin-users-detail__footer">
      <button type="button" class="btn btn-outline" @click="onDismiss">Close</button>
      <button v-if="user" type="button" class="btn btn-primary" @click="emit('edit', user)">Edit</button>
    </div>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import type { AdminUser } from '@/utils/adminAPI'
import {
  formatFullDate,
  joinInterests,
  labelizeCountry,
  labelizeState,
  roleLabel,
  superviseesLabel,
  supervisorLabel,
  userName
} from '@/utils/userFormat'

const props = defineProps<{
  open: boolean
  user: AdminUser | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'edit', user: AdminUser): void
}>()

const detailTitle = computed(() => userName(props.user) || 'User details')

const onDismiss = () => {
  emit('close')
}
</script>

<style scoped>
.admin-users__role-badge,
.admin-users__status-badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--light-green);
  color: var(--dark-green);
  text-transform: capitalize;
}

.admin-users__status-badge--inactive {
  background-color: var(--bg-light);
  color: var(--text-muted);
}

.admin-users__logged-in-badge {
  display: inline-block;
  width: fit-content;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--bg-light);
  color: var(--text-muted);
  text-transform: capitalize;
}

.admin-users__logged-in-badge--yes {
  background-color: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.admin-users-detail__section h3 {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--dark-green);
}

.admin-users-detail__list {
  margin: 0;
}

.admin-users-detail__item {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border-light);
}

.admin-users-detail__item dt {
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}

.admin-users-detail__item dd {
  margin: 0;
  color: var(--charcoal);
  text-align: right;
  overflow-wrap: anywhere;
}

.admin-users-detail__supervisees {
  text-align: right;
}

.admin-users-detail__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 1.5rem;
}
</style>