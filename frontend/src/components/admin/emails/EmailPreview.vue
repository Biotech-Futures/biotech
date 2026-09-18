<template>
  <section class="email-preview" aria-label="Email preview">
    <header class="email-preview__header">
      <div class="email-preview__heading">
        <i class="fas fa-eye" aria-hidden="true"></i>
        <h3>Preview</h3>
        <span v-if="loading" class="email-preview__updating">
          <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          Updating…
        </span>
      </div>
    </header>

    <div v-if="!preview && loading" class="email-preview__state" role="status">
      <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
      <span>Rendering preview…</span>
    </div>

    <div v-else-if="!preview" class="email-preview__state">
      <i class="fas fa-envelope-open-text" aria-hidden="true"></i>
      <span>Select an email to preview it.</span>
    </div>

    <template v-else>
      <dl class="email-preview__subject">
        <dt>Subject</dt>
        <dd>{{ preview.subject }}</dd>
      </dl>
      <div class="email-preview__frame-wrap">
        <iframe
          class="email-preview__frame"
          title="Email preview"
          sandbox=""
          :srcdoc="preview.html"
        ></iframe>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import type { SystemEmailPreview } from '@/utils/systemEmail'

defineProps<{
  preview: SystemEmailPreview | null
  loading: boolean
}>()
</script>

<style scoped>
.email-preview {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.email-preview__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.email-preview__heading {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: #111827;
}

.email-preview__heading h3 {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
}

.email-preview__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 16rem;
  border: 1px dashed #d1d5db;
  border-radius: 0.5rem;
  color: #6b7280;
  font-size: 0.8125rem;
}

.email-preview__updating {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
}

.email-preview__subject {
  display: flex;
  gap: 0.5rem;
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  background: #f9fafb;
  font-size: 0.8125rem;
}

.email-preview__subject dt {
  font-weight: 600;
  color: #6b7280;
}

.email-preview__subject dd {
  margin: 0;
  color: #111827;
  word-break: break-word;
}

.email-preview__frame-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  overflow: hidden;
  background: #ffffff;
}

.email-preview__frame {
  display: block;
  width: 100%;
  min-height: 28rem;
  border: none;
}
</style>
