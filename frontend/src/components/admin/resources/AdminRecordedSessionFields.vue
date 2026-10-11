<template>
  <div class="admin-recorded-session-fields">
    <!-- Video File Section (Required) -->
    <div class="admin-resource-form__field-wrap">
      <label class="form-label" for="admin-resource-video-file">Session Video Recording *</label>
      <div class="admin-resource-file-upload">
        <div class="admin-resource-file-upload__controls">
          <input
            id="admin-resource-video-file"
            ref="videoInputRef"
            type="file"
            accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
            class="admin-resource-file-input"
            @change="onVideoChange"
          />
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="triggerVideoInput"
          >
            <i class="fas fa-video" aria-hidden="true"></i>
            <span>{{ videoFile || currentVideoName ? 'Change Video' : 'Browse Video' }}</span>
          </button>
          <button
            v-if="videoFile"
            type="button"
            class="btn btn-outline btn-sm"
            @click="clearVideo"
          >
            <i class="fas fa-times" aria-hidden="true"></i>
            <span>Clear</span>
          </button>
        </div>

        <div v-if="videoFile" class="admin-resource-file-badge">
          <i class="fas fa-file-video" aria-hidden="true"></i>
          <span class="admin-resource-file-name">{{ videoFile.name }}</span>
          <span class="admin-resource-file-size">({{ formatFileSize(videoFile.size) }})</span>
        </div>
        <div v-else-if="currentVideoName" class="admin-resource-file-badge admin-resource-file-badge--existing">
          <i class="fas fa-file-check" aria-hidden="true"></i>
          <span class="admin-resource-file-name">Current: {{ currentVideoName }}</span>
          <span v-if="currentVideoSize" class="admin-resource-file-size">({{ formatFileSize(currentVideoSize) }})</span>
        </div>

        <!-- Large video file confirmation -->
        <div v-if="isVideoOversized && videoFile" class="admin-resource-form__oversize" role="alert">
          <p class="admin-resource-form__oversize-text">
            <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
            This video is {{ formatFileSize(videoFile.size) }}, over the 25 MB guideline. Large videos
            take longer to upload and process.
          </p>
          <label class="admin-resource-form__checkbox-label">
            <input
              id="res-video-oversize-ack"
              type="checkbox"
              :checked="acknowledgedOversized"
              :disabled="saving"
              @change="onAckChange"
            />
            <span>I understand this video is large</span>
          </label>
        </div>

        <p class="admin-resource-form__hint">
          Accepted: MP4, WebM, MOV &bull; Files over 25 MB need confirmation
        </p>
      </div>
    </div>

    <!-- Slides File Section (Optional) -->
    <div class="admin-resource-form__field-wrap">
      <label class="form-label" for="admin-resource-slides-file">Presentation Slides (Optional)</label>
      <div class="admin-resource-file-upload">
        <div class="admin-resource-file-upload__controls">
          <input
            id="admin-resource-slides-file"
            ref="slidesInputRef"
            type="file"
            accept="application/pdf,.pdf"
            class="admin-resource-file-input"
            @change="onSlidesChange"
          />
          <button
            type="button"
            class="btn btn-outline btn-sm"
            @click="triggerSlidesInput"
          >
            <i class="fas fa-file-pdf" aria-hidden="true"></i>
            <span>{{ slidesFile || currentSlidesName ? 'Change Slides' : 'Browse Slides' }}</span>
          </button>
          <button
            v-if="slidesFile"
            type="button"
            class="btn btn-outline btn-sm"
            @click="clearSlides"
          >
            <i class="fas fa-times" aria-hidden="true"></i>
            <span>Clear</span>
          </button>
        </div>

        <div v-if="slidesFile" class="admin-resource-file-badge">
          <i class="fas fa-file-pdf" aria-hidden="true"></i>
          <span class="admin-resource-file-name">{{ slidesFile.name }}</span>
          <span class="admin-resource-file-size">({{ formatFileSize(slidesFile.size) }})</span>
        </div>
        <div v-else-if="currentSlidesName" class="admin-resource-file-badge admin-resource-file-badge--existing">
          <i class="fas fa-file-check" aria-hidden="true"></i>
          <span class="admin-resource-file-name">Current: {{ currentSlidesName }}</span>
          <span v-if="currentSlidesSize" class="admin-resource-file-size">({{ formatFileSize(currentSlidesSize) }})</span>
        </div>

        <p v-if="slidesError" class="admin-resource-form__error" role="alert">
          <i class="fas fa-circle-exclamation" aria-hidden="true"></i>
          {{ slidesError }}
        </p>

        <p class="admin-resource-form__hint">
          Accepted: PDF only &bull; Leave empty if no slides are attached to this session
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const OVERSIZE_THRESHOLD_BYTES = 25 * 1024 * 1024

const props = defineProps<{
  videoFile: File | null
  slidesFile: File | null
  currentVideoName?: string | null
  currentVideoSize?: number | null
  currentSlidesName?: string | null
  currentSlidesSize?: number | null
  acknowledgedOversized: boolean
  saving?: boolean
  isEditing?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:videoFile', file: File | null): void
  (e: 'update:video-file', file: File | null): void
  (e: 'update:slidesFile', file: File | null): void
  (e: 'update:slides-file', file: File | null): void
  (e: 'update:acknowledgedOversized', val: boolean): void
  (e: 'update:acknowledged-oversized', val: boolean): void
}>()

const videoInputRef = ref<HTMLInputElement | null>(null)
const slidesInputRef = ref<HTMLInputElement | null>(null)

watch(
  () => props.videoFile,
  (nextFile) => {
    if (!nextFile && videoInputRef.value) {
      videoInputRef.value.value = ''
    }
  }
)

watch(
  () => props.slidesFile,
  (nextFile) => {
    if (!nextFile && slidesInputRef.value) {
      slidesInputRef.value.value = ''
    }
  }
)

const isVideoOversized = computed(() => {
  return Boolean(props.videoFile && props.videoFile.size > OVERSIZE_THRESHOLD_BYTES)
})

const formatFileSize = (bytes?: number | null): string => {
  if (!bytes || bytes <= 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx++
  }
  return `${size.toFixed(size >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`
}

const triggerVideoInput = () => {
  videoInputRef.value?.click()
}

const triggerSlidesInput = () => {
  slidesInputRef.value?.click()
}

const setVideoFile = (file: File | null) => {
  emit('update:videoFile', file)
  emit('update:video-file', file)
}

const setSlidesFile = (file: File | null) => {
  emit('update:slidesFile', file)
  emit('update:slides-file', file)
}

const setAcknowledgedOversized = (val: boolean) => {
  emit('update:acknowledgedOversized', val)
  emit('update:acknowledged-oversized', val)
}

const onVideoChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0] || null
  setVideoFile(file)
  setAcknowledgedOversized(false)
}

const slidesError = ref('')

const isPdf = (file: File) => {
  return file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf'
}

const onSlidesChange = (e: Event) => {
  slidesError.value = ''
  const input = e.target as HTMLInputElement
  const file = input.files?.[0] || null
  if (file && !isPdf(file)) {
    slidesError.value = 'Presentation slides must be a PDF file.'
    if (slidesInputRef.value) slidesInputRef.value.value = ''
    setSlidesFile(null)
    return
  }
  setSlidesFile(file)
}

const clearVideo = () => {
  if (videoInputRef.value) videoInputRef.value.value = ''
  setVideoFile(null)
  setAcknowledgedOversized(false)
}

const clearSlides = () => {
  slidesError.value = ''
  if (slidesInputRef.value) slidesInputRef.value.value = ''
  setSlidesFile(null)
}

const onAckChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  setAcknowledgedOversized(input.checked)
}
</script>

<style scoped>
.admin-recorded-session-fields {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.admin-resource-form__field-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-label {
  display: block;
  font-size: 0.825rem;
  font-weight: 600;
  color: var(--charcoal);
  margin-bottom: 0.15rem;
}

.admin-resource-file-upload {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.admin-resource-file-upload__controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-resource-file-input {
  display: none;
}

.admin-resource-file-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.75rem;
  background-color: var(--bg-light);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--charcoal);
  width: fit-content;
  max-width: 100%;
}

.admin-resource-file-badge--existing {
  background-color: rgba(1, 113, 81, 0.06);
  border-color: rgba(1, 113, 81, 0.2);
  color: var(--dark-green);
}

.admin-resource-file-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-resource-file-size {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.admin-resource-form__hint {
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.admin-resource-form__oversize {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  background-color: #fffbeb;
  border: 1px solid #fcd34d;
}

.admin-resource-form__oversize-text {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin: 0;
  font-size: 0.85rem;
  color: #92400e;
}

.admin-resource-form__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--charcoal);
  cursor: pointer;
}

.admin-resource-form__checkbox-label input {
  accent-color: var(--dark-green);
  width: 16px;
  height: 16px;
}

.admin-resource-form__error {
  align-items: center;
  color: var(--danger, #dc3545);
  display: flex;
  font-size: 0.85rem;
  gap: 6px;
  margin: 6px 0 0;
}
</style>
