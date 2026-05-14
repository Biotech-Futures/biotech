<template>
  <div class="content-area">
    <nav class="detail-breadcrumb" aria-label="Breadcrumb">
      <RouterLink :to="{ name: 'announcements' }" class="detail-breadcrumb__back">
        <span aria-hidden="true">&larr;</span>
        <span>All announcements</span>
      </RouterLink>
    </nav>

    <AnnouncementSkeleton v-if="isLoading" with-media />

    <div v-else-if="notFound" class="detail-empty card">
      <h2>Announcement not found</h2>
      <p>It may have been archived or you no longer have access to it.</p>
      <RouterLink :to="{ name: 'announcements' }" class="btn btn-outline btn-sm">
        Back to announcements
      </RouterLink>
    </div>

    <div v-else-if="error" class="detail-empty card detail-empty--error">
      <h2>{{ errorTitle }}</h2>
      <p>{{ error.message }}</p>
      <button class="btn btn-outline btn-sm" type="button" @click="reload">Try again</button>
    </div>

    <article v-else-if="announcement" class="detail">
      <header class="detail__header">
        <span
          class="status-badge detail__badge"
          :class="getAudienceClass(announcement.audience)"
        >
          {{ getAudienceLabel(announcement.audience) }}
        </span>
        <h1 class="detail__title">{{ announcement.title }}</h1>
        <div class="detail__meta">
          <div class="detail__author">
            <div class="detail__avatar" aria-hidden="true">
              {{ authorInitial(announcement.author) }}
            </div>
            <div>
              <div class="detail__author-name">{{ announcement.author }}</div>
              <time
                class="detail__date"
                :datetime="announcement.date || undefined"
                :title="fullDate"
              >
                {{ relativeDate }}
                <span v-if="fullDate" class="detail__date-full"> &middot; {{ fullDate }}</span>
              </time>
            </div>
          </div>
          <button
            v-if="canShare"
            type="button"
            class="btn btn-outline btn-sm"
            @click="share"
          >
            {{ shareLabel }}
          </button>
        </div>
      </header>

      <div v-if="announcement.images.length" class="detail__media">
        <AnnouncementGallery
          :images="announcement.images"
          @open="openLightbox"
          @image-error="onImageError"
        />
      </div>

      <div class="detail__body announcement-rich" v-html="announcement.bodyHtml"></div>

      <footer class="detail__footer">
        <RouterLink
          v-if="announcement.route"
          :to="announcement.route"
          class="btn btn-primary"
        >
          Open referenced page
        </RouterLink>
        <a
          v-else-if="announcement.link"
          :href="announcement.link"
          target="_blank"
          rel="noopener noreferrer"
          class="btn btn-primary"
        >
          Open external link
        </a>
      </footer>
    </article>

    <AnnouncementLightbox
      v-if="announcement"
      v-model:open="lightboxOpen"
      :images="announcement.images"
      :initial-index="lightboxIndex"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AnnouncementGallery from '@/components/announcements/AnnouncementGallery.vue'
import AnnouncementLightbox from '@/components/announcements/AnnouncementLightbox.vue'
import AnnouncementSkeleton from '@/components/announcements/AnnouncementSkeleton.vue'
import {
  authorInitial,
  formatFullDate,
  formatRelativeDate,
  getAudienceClass,
  getAudienceLabel,
  useAnnouncementDetail
} from '@/composables/useAnnouncements'

const route = useRoute()
const { announcement, isLoading, error, notFound, load } = useAnnouncementDetail()

const lightboxOpen = ref(false)
const lightboxIndex = ref(0)
const shareLabel = ref('Copy link')

const relativeDate = computed(() =>
  announcement.value ? formatRelativeDate(announcement.value.date) : ''
)
const fullDate = computed(() =>
  announcement.value ? formatFullDate(announcement.value.date) : ''
)

const errorTitle = computed(() => {
  if (!error.value) return 'Something went wrong'
  if (error.value.kind === 'auth') return 'Session expired'
  if (error.value.kind === 'network') return 'No connection'
  if (error.value.kind === 'server') return 'Service unavailable'
  return 'Something went wrong'
})

const canShare = computed(
  () => typeof navigator !== 'undefined' && 'clipboard' in navigator
)

async function reload() {
  const id = route.params.id
  if (typeof id === 'string' || typeof id === 'number') {
    await load(id)
  }
}

const openLightbox = (index: number) => {
  lightboxIndex.value = index
  lightboxOpen.value = true
}

const onImageError = (url: string) => {
  if (!announcement.value) return
  announcement.value.images = announcement.value.images.filter(image => image.url !== url)
}

async function share() {
  if (typeof window === 'undefined' || !announcement.value) return
  const url = window.location.href
  try {
    await navigator.clipboard.writeText(url)
    shareLabel.value = 'Copied!'
    setTimeout(() => {
      shareLabel.value = 'Copy link'
    }, 1500)
  } catch {
    shareLabel.value = 'Copy failed'
    setTimeout(() => {
      shareLabel.value = 'Copy link'
    }, 1500)
  }
}

onMounted(reload)
watch(() => route.params.id, reload)
</script>

<style scoped>
.content-area {
  width: min(100%, 860px);
  margin: 0 auto;
}

.detail-breadcrumb {
  margin-bottom: 1rem;
}

.detail-breadcrumb__back {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--dark-green);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9rem;
  padding: 0.35rem 0.6rem;
  border-radius: 8px;
  transition: background-color 0.18s ease;
}

.detail-breadcrumb__back:hover,
.detail-breadcrumb__back:focus-visible {
  background-color: rgba(1, 113, 81, 0.08);
  outline: none;
}

.detail-empty {
  text-align: center;
  padding: 2.5rem 1.5rem;
}

.detail-empty h2 {
  margin: 0 0 0.5rem;
  color: var(--charcoal);
}

.detail-empty p {
  margin: 0 0 1.25rem;
  color: #6c757d;
}

.detail-empty--error {
  border-left: 4px solid var(--danger);
}

.detail {
  background: var(--white);
  border: 1px solid rgba(14, 31, 25, 0.08);
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(7, 17, 15, 0.03);
  overflow: hidden;
}

.detail__header {
  padding: 2rem 2.25rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  border-bottom: 1px solid rgba(14, 31, 25, 0.06);
}

.detail__badge {
  align-self: flex-start;
}

.detail__title {
  margin: 0;
  font-size: 1.85rem;
  font-weight: 700;
  line-height: 1.25;
  color: var(--charcoal);
}

.detail__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.detail__author {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.detail__avatar {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--dark-green), var(--mint-green));
  color: var(--white);
  font-weight: 600;
}

.detail__author-name {
  font-weight: 600;
  color: var(--charcoal);
  font-size: 0.95rem;
}

.detail__date {
  color: #6c757d;
  font-size: 0.85rem;
}

.detail__date-full {
  color: #95a4a0;
}

.detail__media {
  background: var(--light-green);
  min-height: 280px;
  max-height: 480px;
  overflow: hidden;
}

.detail__body {
  padding: 1.75rem 2.25rem;
  line-height: 1.75;
  color: var(--charcoal);
  font-size: 1rem;
}

.detail__footer {
  padding: 0 2.25rem 2rem;
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.announcement-rich :deep(*) {
  max-width: 100%;
}

.announcement-rich :deep(p),
.announcement-rich :deep(ul),
.announcement-rich :deep(ol),
.announcement-rich :deep(blockquote),
.announcement-rich :deep(pre),
.announcement-rich :deep(table),
.announcement-rich :deep(figure) {
  margin: 0 0 1rem;
}

.announcement-rich :deep(h1),
.announcement-rich :deep(h2),
.announcement-rich :deep(h3),
.announcement-rich :deep(h4),
.announcement-rich :deep(h5),
.announcement-rich :deep(h6) {
  margin: 1.25rem 0 0.55rem;
  color: var(--dark-green);
  line-height: 1.25;
}

.announcement-rich :deep(h1:first-child),
.announcement-rich :deep(h2:first-child),
.announcement-rich :deep(h3:first-child),
.announcement-rich :deep(h4:first-child),
.announcement-rich :deep(h5:first-child),
.announcement-rich :deep(h6:first-child) {
  margin-top: 0;
}

.announcement-rich :deep(ul),
.announcement-rich :deep(ol) {
  padding-left: 1.4rem;
}

.announcement-rich :deep(a) {
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.announcement-rich :deep(blockquote) {
  padding: 0.85rem 1.1rem;
  border-left: 3px solid var(--dark-green);
  background: rgba(1, 113, 81, 0.06);
  border-radius: 0 10px 10px 0;
}

.announcement-rich :deep(pre) {
  padding: 0.95rem 1.1rem;
  overflow-x: auto;
  background: #f5f7f8;
  border-radius: 10px;
}

.announcement-rich :deep(code) {
  padding: 0.1rem 0.3rem;
  background: #f5f7f8;
  border-radius: 4px;
  font-size: 0.92em;
}

.announcement-rich :deep(pre code) {
  padding: 0;
  background: transparent;
}

.announcement-rich :deep(img) {
  display: block;
  width: 100%;
  height: auto;
  max-height: 480px;
  object-fit: contain;
  border-radius: 10px;
  background: var(--light-green);
}

.announcement-rich :deep(table) {
  width: 100%;
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}

.announcement-rich :deep(th),
.announcement-rich :deep(td) {
  padding: 0.6rem 0.7rem;
  border: 1px solid rgba(1, 113, 81, 0.14);
  text-align: left;
}

@media (max-width: 720px) {
  .detail__header {
    padding: 1.5rem 1.25rem 1rem;
  }
  .detail__title {
    font-size: 1.5rem;
  }
  .detail__body,
  .detail__footer {
    padding-left: 1.25rem;
    padding-right: 1.25rem;
  }
}
</style>
