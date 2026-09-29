<template>
  <!-- Placeholder that holds the route while the audit log is ported; the
       AUDIT owner replaces this file (port-design.md section 6). -->
  <AdminStubSection
    class="tickets-tab-stub"
    title="Ticket audit"
    icon="fa-scroll"
    description="The ticket audit log is being moved here from the admin app."
  />
</template>

<script setup lang="ts">
import AdminStubSection from '@/components/admin/AdminStubSection.vue'
</script>

<style scoped>
/* AdminStubSection is a whole page (.content-area); inside the section shell,
   which already is one, drop the second page padding and height. */
.tickets-tab-stub {
  padding: 0;
  min-height: 0;
  background: transparent;
}
</style>
