<template>
  <div class="content-area">

    <div v-if="isLoading" class="card">
      <p>Finding your team…</p>
    </div>

    <div v-else-if="loadError" class="card">
      <h2 class="card-title">Could not load your teams</h2>
      <p class="submission-landing__muted">{{ loadError }}</p>
      <button class="btn btn-outline btn-sm" type="button" @click="resolve">Try again</button>
    </div>

    <!-- Admins aren't on teams: entries are opened from the Grading tables. -->
    <div v-else-if="!groups.length && auth.isAdmin" class="card">
      <p class="submission-landing__muted">
        Please contact the administrator via {{ SUPPORT_EMAIL }}
      </p>
    </div>

    <!-- No team. Deliberately an explanation rather than an error: entries are
         currently made by teams, so a student not in one has nothing to open. -->
    <div v-else-if="!groups.length" class="card">
      <h2 class="card-title">You are not part of a team yet</h2>
      <p class="submission-landing__muted">
        Competition entries are submitted by teams. Once you have been placed in one, your
        team's submission will appear here.
      </p>
      <p class="submission-landing__muted">
        If you think this is wrong, contact {{ SUPPORT_EMAIL }}.
      </p>
    </div>

    <!-- More than one team: let the student choose rather than guessing. -->
    <div v-else class="card">
      <div class="card-header"><h2 class="card-title">Choose a team</h2></div>
      <p class="submission-landing__muted">You are part of more than one team.</p>
      <ul class="submission-landing__list">
        <li v-for="group in groups" :key="group.id">
          <RouterLink
            class="btn btn-outline"
            :to="{ name: 'group-submission', params: { id: group.id } }"
          >
            {{ group.name }}
          </RouterLink>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useGroupsStore } from '@/stores/groups'
import { useAuthStore } from '@/stores/auth'
import { SUPPORT_EMAIL } from '@/constants/brand'

const router = useRouter()
const store = useGroupsStore()
const auth = useAuthStore()

const isLoading = ref(true)
const loadError = ref('')

const groups = computed(() => store.sorted)


async function resolve() {
  isLoading.value = true
  loadError.value = ''

  await store.ensureLoaded()

  if (store.error) {
    loadError.value = store.error
    isLoading.value = false
    return
  }

  // The common case by far — one team, so skip the picker entirely and send
  // the student straight to their entry. `replace` keeps this hop out of the
  // back-button history.
  if (store.groups.length === 1) {
    await router.replace({
      name: 'group-submission',
      params: { id: store.groups[0].id }
    })
    return
  }

  isLoading.value = false
}

onMounted(resolve)
</script>

<style scoped>
.submission-landing__heading {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0.5rem 0 1rem;
}

.submission-landing__muted {
  color: #6b7280;
  font-size: 0.9rem;
}


.submission-landing__list {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
</style>
