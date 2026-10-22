<template>
  <!-- Every supervisor, and whether they can still register students once
       registration closes by its dates. -->
  <section class="card after-close">
    <h3 class="after-close__title">Supervisors After Close</h3>
    <p class="after-close__hint">
      After the close date, only supervisors switched on here can register students.
    </p>

    <p v-if="error" class="after-close__error" role="alert">{{ error }}</p>

    <AppDataTable
      :columns="columns"
      :rows="rows"
      row-key="user_id"
      :selectable="false"
      :loading="isLoading"
      :default-sort="{ key: 'students', direction: 'desc' }"
      :action-headings="['Late Register']"
      search-placeholder="Name, email or school"
      empty-message="No supervisors yet."
    >
      <template #actions="{ row }">
        <HideShowSwitch
          :on="toSupervisor(row).register_after_close"
          :disabled="savingId === toSupervisor(row).user_id"
          :label="`Let ${toSupervisor(row).name} register students after registration closes`"
          off-text="Off"
          on-text="On"
          @change="switchSupervisor(toSupervisor(row), $event)"
        />
      </template>
    </AppDataTable>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  fetchRegistrationSupervisors,
  saveRegistrationSupervisor,
  type RegistrationSupervisor,
} from '@/utils/managementAPI'
import HideShowSwitch from './HideShowSwitch.vue'

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Supervisor' },
  { key: 'email', label: 'Email' },
  { key: 'school', label: 'School' },
  { key: 'students', label: 'Students', type: 'number' },
]

const supervisors = ref<RegistrationSupervisor[]>([])
const isLoading = ref(true)
const savingId = ref<number | null>(null)
const error = ref('')

const rows = computed(() =>
  supervisors.value.map((supervisor) => ({
    ...supervisor,
    school: supervisor.school || '—',
    supervisor,
  })),
)
const toSupervisor = (row: Record<string, unknown>) => row.supervisor as RegistrationSupervisor

// Saved straight away, as Late Registration's other switches are.
const switchSupervisor = async (supervisor: RegistrationSupervisor, wanted: boolean) => {
  savingId.value = supervisor.user_id
  error.value = ''
  try {
    const saved = await saveRegistrationSupervisor(supervisor.user_id, wanted)
    supervisors.value = supervisors.value.map((item) => (item.user_id === saved.user_id ? saved : item))
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The change could not be saved.').message
  } finally {
    savingId.value = null
  }
}

onMounted(async () => {
  try {
    supervisors.value = await fetchRegistrationSupervisors()
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The supervisors could not be loaded.').message
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
/* Laid out as Late Registration's other cards. */
.after-close {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.after-close__title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
}

.after-close__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.after-close__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}
</style>
