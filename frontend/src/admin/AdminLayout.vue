<!--
  Root layout for the /admin route tree. Minimal for the skeleton — the
  sidebar sections, hub tabs and breadcrumbs arrive in Part 4. Installing
  Vuetify here covers every admin child route.
-->
<script setup lang="ts">
import { useAdminVuetify } from '@/admin/vuetify'

useAdminVuetify()
</script>

<template>
  <v-app>
    <v-main>
      <v-container>
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>
