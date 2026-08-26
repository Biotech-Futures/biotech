<!--
  TEMP (skeleton Part 2): throwaway smoke-test page proving Vuetify renders
  with the BTF brand theme, follows the app dark-mode toggle, and picks up
  Font Awesome icons. Replaced by the real /admin route tree in Part 3.
-->
<script setup lang="ts">
import { useAdminVuetify } from '@/admin/vuetify'

useAdminVuetify()

const headers = [
  { title: 'Name', key: 'name' },
  { title: 'Role', key: 'role' },
  { title: 'Status', key: 'status' },
]

const rows = [
  { name: 'Ada Lovelace', role: 'Mentor', status: 'Active' },
  { name: 'Grace Hopper', role: 'Student', status: 'Invited' },
  { name: 'Alan Turing', role: 'Supervisor', status: 'Active' },
]
</script>

<template>
  <v-app>
    <v-main>
      <v-container>
        <h1 class="mb-4">Vuetify smoke test</h1>
        <div class="d-flex ga-2 mb-6">
          <v-btn color="primary" prepend-icon="fas fa-check">Primary</v-btn>
          <v-btn color="secondary" variant="tonal">Secondary</v-btn>
          <v-btn color="error" variant="outlined" prepend-icon="fas fa-trash">Danger</v-btn>
        </div>
        <v-alert type="info" class="mb-6" text="Theme follows the app-wide dark mode toggle." />
        <v-data-table :headers="headers" :items="rows" />
      </v-container>
    </v-main>
  </v-app>
</template>
