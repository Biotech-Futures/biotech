<template>
  <article
    class="announcement"
    :class="{
      'announcement--with-media': hasImages
    }"
    role="link"
    tabindex="0"
    @click="openDetailsFromCard"
    @keydown.enter="openDetailsFromCard"
    @keydown.space="openDetailsFromCard"
  >
    <div v-if="hasImages" class="announcement__media">
      <AnnouncementGallery
        :images="announcement.images"
        @open="openDetails"
        @image-error="onImageError"
      />
    </div>

    <div class="announcement__body">
      <header class="announcement__header">
        <div class="announcement__author">
          <div class="announcement__avatar" :aria-hidden="true">
            {{ authorInitial(announcement.author) }}
          </div>
          <div class="announcement__author-text">
            <span class="announcement__author-name">{{ announcement.author }}</span>
            <time
              class="announcement__date"
              :datetime="announcement.date || undefined"
              :title="fullDate"
            >
              {{ overviewDateTime }}
            </time>
          </div>
        </div>
        <span
          class="status-badge announcement__badge"
          :class="getAudienceClass(announcement.audience)"
        >
          {{ getAudienceLabel(announcement.audience) }}
        </span>
      </header>

      <h2 class="announcement__title">
        <RouterLink
          :to="{ name: 'announcement-detail', params: { id: announcement.id } }"
          class="announcement__title-link"
        >
          {{ announcement.title }}
        </RouterLink>
      </h2>

      <div
        class="announcement__content"
      >
        <div class="announcement__rich" v-html="announcement.bodyHtml"></div>
      </div>

      <div class="announcement__footer">
        <div class="announcement__actions">
          <RouterLink
            v-if="announcement.route"
            :to="announcement.route"
            class="btn btn-outline btn-sm"
          >
            Open
          </RouterLink>
          <a
            v-else-if="announcement.link"
            :href="announcement.link"
            target="_blank"
            rel="noopener noreferrer"
            class="btn btn-outline btn-sm"
          >
            External link
          </a>
          <RouterLink
            :to="{ name: 'announcement-detail', params: { id: announcement.id } }"
            class="btn btn-text btn-sm"
          >
            View details
            <span class="announcement__arrow" aria-hidden="true">&rarr;</span>
          </RouterLink>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AnnouncementGallery from './AnnouncementGallery.vue'
import {
  authorInitial,
  formatFullDate,
  formatOverviewDateTime,
  getAudienceClass,
  getAudienceLabel,
  type Announcement
} from '@/composables/useAnnouncements'

const props = defineProps<{
  announcement: Announcement
}>()

const emit = defineEmits<{
  (e: 'image-error', payload: { id: Announcement['id']; url: string }): void
}>()

const router = useRouter()

const hasImages = computed(() => props.announcement.images.length > 0)
const overviewDateTime = computed(() => formatOverviewDateTime(props.announcement.date))
const fullDate = computed(() => formatFullDate(props.announcement.date))

const detailRoute = computed(() => ({
  name: 'announcement-detail',
  params: { id: props.announcement.id }
}))

const openDetails = () => {
  router.push(detailRoute.value)
}

const shouldIgnoreCardOpen = (event?: Event) => {
  const target = event?.target
  if (!(target instanceof Element)) return false
  return Boolean(target.closest('a, button, input, select, textarea'))
}

const openDetailsFromCard = (event: MouseEvent | KeyboardEvent) => {
  if (shouldIgnoreCardOpen(event)) return
  event.preventDefault()
  openDetails()
}

const onImageError = (url: string) => {
  emit('image-error', { id: props.announcement.id, url })
}
</script>

<style scoped>
.announcement {
  position: relative;
  height: 300px;
  background: var(--white);
  border: 1px solid rgba(14, 31, 25, 0.08);
  border-radius: 18px;
  box-shadow: 0 1px 2px rgba(7, 17, 15, 0.03);
  cursor: pointer;
  overflow: hidden;
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease;
}

.announcement:hover {
  transform: translateY(-2px);
  border-color: rgba(1, 113, 81, 0.22);
  box-shadow: 0 18px 40px rgba(7, 17, 15, 0.08);
}

.announcement:focus-visible {
  outline: 3px solid rgba(1, 113, 81, 0.22);
  outline-offset: 3px;
}

.announcement--with-media {
  display: grid;
  grid-template-columns: minmax(280px, 40%) minmax(0, 1fr);
}

.announcement__media {
  background: var(--light-green);
  min-height: 100%;
}

.announcement__media :deep(.gallery__item) {
  cursor: pointer;
}

.announcement__body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  padding: 1.5rem 1.75rem;
  gap: 1rem;
}

.announcement__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.announcement__author {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
}

.announcement__avatar {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--dark-green), var(--mint-green));
  color: var(--white);
  font-weight: 600;
  font-size: 0.95rem;
  letter-spacing: 0.02em;
}

.announcement__author-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.announcement__author-name {
  color: var(--charcoal);
  font-weight: 600;
  font-size: 0.92rem;
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.announcement__date {
  color: #6c757d;
  font-size: 0.82rem;
  cursor: help;
}

.announcement__badge {
  flex-shrink: 0;
  align-self: center;
  white-space: nowrap;
}

.announcement__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
  line-height: 1.3;
}

.announcement__title-link {
  display: -webkit-box;
  color: var(--charcoal);
  text-decoration: none;
  background-image: linear-gradient(currentColor, currentColor);
  background-size: 0 1px;
  background-repeat: no-repeat;
  background-position: 0 100%;
  line-clamp: 2;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: background-size 0.25s ease, color 0.2s ease;
}

.announcement__title-link:hover,
.announcement__title-link:focus-visible {
  color: var(--dark-green);
  background-size: 100% 1px;
  outline: none;
}

.announcement__content {
  position: relative;
  flex: 1;
  min-height: 0;
  color: var(--charcoal);
  line-height: 1.7;
  max-height: 6.9em;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.announcement__content::after {
  content: '';
  position: absolute;
  inset: auto 0 0 0;
  height: 3em;
  background: linear-gradient(180deg, transparent, var(--white) 80%);
  pointer-events: none;
}

.announcement__content :deep(img),
.announcement__content :deep(figure),
.announcement__content :deep(table),
.announcement__content :deep(pre) {
  display: none;
}

.announcement__rich :deep(*) {
  max-width: 100%;
}

.announcement__rich :deep(p),
.announcement__rich :deep(ul),
.announcement__rich :deep(ol),
.announcement__rich :deep(blockquote),
.announcement__rich :deep(pre),
.announcement__rich :deep(table),
.announcement__rich :deep(figure) {
  margin: 0 0 0.85rem;
}

.announcement__rich :deep(p:last-child),
.announcement__rich :deep(ul:last-child),
.announcement__rich :deep(ol:last-child),
.announcement__rich :deep(blockquote:last-child),
.announcement__rich :deep(pre:last-child),
.announcement__rich :deep(table:last-child),
.announcement__rich :deep(figure:last-child) {
  margin-bottom: 0;
}

.announcement__rich :deep(h1),
.announcement__rich :deep(h2),
.announcement__rich :deep(h3),
.announcement__rich :deep(h4),
.announcement__rich :deep(h5),
.announcement__rich :deep(h6) {
  margin: 1rem 0 0.45rem;
  color: var(--dark-green);
  line-height: 1.25;
}

.announcement__rich :deep(h1:first-child),
.announcement__rich :deep(h2:first-child),
.announcement__rich :deep(h3:first-child),
.announcement__rich :deep(h4:first-child),
.announcement__rich :deep(h5:first-child),
.announcement__rich :deep(h6:first-child) {
  margin-top: 0;
}

.announcement__rich :deep(ul),
.announcement__rich :deep(ol) {
  padding-left: 1.3rem;
}

.announcement__rich :deep(a) {
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.announcement__rich :deep(blockquote) {
  padding: 0.75rem 1rem;
  border-left: 3px solid var(--dark-green);
  background: rgba(1, 113, 81, 0.06);
  border-radius: 0 8px 8px 0;
}

.announcement__rich :deep(pre) {
  max-width: 100%;
  padding: 0.85rem 1rem;
  overflow-x: auto;
  background: #f5f7f8;
  border-radius: 8px;
}

.announcement__rich :deep(code) {
  padding: 0.1rem 0.3rem;
  background: #f5f7f8;
  border-radius: 4px;
  font-size: 0.92em;
}

.announcement__rich :deep(pre code) {
  padding: 0;
  background: transparent;
}

.announcement__rich :deep(img) {
  display: block;
  width: 100%;
  height: auto;
  max-height: 420px;
  object-fit: contain;
  border-radius: 8px;
  background: var(--light-green);
}

.announcement__rich :deep(table) {
  width: 100%;
  border-collapse: collapse;
  display: block;
  overflow-x: auto;
}

.announcement__rich :deep(th),
.announcement__rich :deep(td) {
  padding: 0.55rem 0.65rem;
  border: 1px solid rgba(1, 113, 81, 0.14);
  text-align: left;
}

.announcement__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: auto;
  padding-top: 0.5rem;
  flex-wrap: wrap;
}

.announcement__actions {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
  align-items: center;
}

.announcement__arrow {
  margin-left: 0.25rem;
  transition: transform 0.2s ease;
  display: inline-block;
}

.announcement__actions a:hover .announcement__arrow {
  transform: translateX(3px);
}

.btn-text {
  background: transparent;
  border: 0;
  color: var(--dark-green);
  font-weight: 600;
  padding: 0.35rem 0.6rem;
  border-radius: 8px;
  text-decoration: none;
  font-size: 0.9rem;
  transition: background-color 0.18s ease;
}

.btn-text:hover,
.btn-text:focus-visible {
  background-color: rgba(1, 113, 81, 0.08);
  outline: none;
}

@media (max-width: 780px) {
  .announcement {
    height: auto;
    min-height: 300px;
  }

  .announcement--with-media {
    grid-template-columns: 1fr;
  }

  .announcement__media {
    min-height: 200px;
  }

  .announcement__body {
    padding: 1.25rem;
  }
}

@media (max-width: 480px) {
  .announcement__header {
    flex-direction: column;
    align-items: flex-start;
  }
  .announcement__badge {
    align-self: flex-start;
  }
  .announcement__title {
    font-size: 1.2rem;
  }
}
</style>
