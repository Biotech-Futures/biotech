<template>
  <div v-if="images.length" class="gallery" :class="galleryClass">
    <button
      v-for="(image, index) in visible"
      :key="image.url"
      type="button"
      class="gallery__item"
      :aria-label="`Open image ${index + 1} of ${images.length}`"
      @click="emit('open', index)"
    >
      <img
        :src="image.url"
        :alt="image.alt || `Announcement image ${index + 1}`"
        loading="lazy"
        @error="onError(image.url)"
      />
      <span
        v-if="images.length > MAX_VISIBLE && index === MAX_VISIBLE - 1"
        class="gallery__more"
        aria-hidden="true"
      >
        +{{ images.length - MAX_VISIBLE }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AnnouncementImage } from '@/composables/useAnnouncements'

const props = defineProps<{
  images: AnnouncementImage[]
}>()

const emit = defineEmits<{
  (e: 'open', index: number): void
  (e: 'image-error', url: string): void
}>()

const MAX_VISIBLE = 4

const visible = computed(() => props.images.slice(0, MAX_VISIBLE))

const galleryClass = computed(() => {
  const count = props.images.length
  if (count <= 1) return 'gallery--single'
  if (count === 2) return 'gallery--two'
  if (count === 3) return 'gallery--three'
  return 'gallery--many'
})

const onError = (url: string) => emit('image-error', url)
</script>

<style scoped>
.gallery {
  display: grid;
  gap: 4px;
  background: rgba(1, 113, 81, 0.12);
  width: 100%;
  height: 100%;
  min-height: 240px;
  border-radius: inherit;
  overflow: hidden;
}

.gallery--single {
  grid-template-columns: 1fr;
}

.gallery--two {
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.gallery--three,
.gallery--many {
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.75fr);
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.gallery--three .gallery__item:first-child,
.gallery--many .gallery__item:first-child {
  grid-row: 1 / span 2;
}

.gallery__item {
  position: relative;
  display: block;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  margin: 0;
  padding: 0;
  border: 0;
  background: var(--white);
  cursor: zoom-in;
  overflow: hidden;
}

.gallery__item img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.gallery__item:hover img,
.gallery__item:focus-visible img {
  transform: scale(1.04);
}

.gallery__item:focus-visible {
  outline: 3px solid var(--dark-green);
  outline-offset: -3px;
}

.gallery__more {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgba(19, 28, 34, 0.55);
  color: var(--white);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}
</style>
