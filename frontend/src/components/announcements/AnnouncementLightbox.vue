<template>
  <Teleport to="body">
    <Transition name="lightbox">
      <div
        v-if="open"
        class="lightbox"
        role="dialog"
        aria-modal="true"
        :aria-label="`Image ${activeIndex + 1} of ${images.length}`"
        @click.self="close"
        @keydown.esc="close"
        @keydown.left="prev"
        @keydown.right="next"
        tabindex="-1"
        ref="dialogRef"
      >
        <button class="lightbox__close" type="button" aria-label="Close" @click="close">
          <span aria-hidden="true">&times;</span>
        </button>

        <button
          v-if="images.length > 1"
          class="lightbox__nav lightbox__nav--prev"
          type="button"
          aria-label="Previous image"
          @click="prev"
        >
          <span aria-hidden="true">&#8249;</span>
        </button>

        <figure class="lightbox__figure">
          <img
            :src="active.url"
            :alt="active.alt || `Announcement image ${activeIndex + 1}`"
          />
          <figcaption v-if="active.alt" class="lightbox__caption">{{ active.alt }}</figcaption>
        </figure>

        <button
          v-if="images.length > 1"
          class="lightbox__nav lightbox__nav--next"
          type="button"
          aria-label="Next image"
          @click="next"
        >
          <span aria-hidden="true">&#8250;</span>
        </button>

        <div v-if="images.length > 1" class="lightbox__counter" aria-live="polite">
          {{ activeIndex + 1 }} / {{ images.length }}
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { AnnouncementImage } from '@/composables/useAnnouncements'

const props = defineProps<{
  open: boolean
  images: AnnouncementImage[]
  initialIndex?: number
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const activeIndex = ref(props.initialIndex ?? 0)
const dialogRef = ref<HTMLElement | null>(null)
let previouslyFocused: HTMLElement | null = null

const active = computed<AnnouncementImage>(
  () => props.images[activeIndex.value] || { url: '', alt: '' }
)

const close = () => emit('update:open', false)
const next = () => {
  if (!props.images.length) return
  activeIndex.value = (activeIndex.value + 1) % props.images.length
}
const prev = () => {
  if (!props.images.length) return
  activeIndex.value = (activeIndex.value - 1 + props.images.length) % props.images.length
}

watch(
  () => props.open,
  async opened => {
    if (opened) {
      activeIndex.value = Math.min(props.initialIndex ?? 0, Math.max(0, props.images.length - 1))
      previouslyFocused = document.activeElement as HTMLElement | null
      document.body.style.overflow = 'hidden'
      await nextTick()
      dialogRef.value?.focus()
    } else {
      document.body.style.overflow = ''
      previouslyFocused?.focus?.()
    }
  }
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
})
</script>

<style scoped>
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: rgba(7, 17, 15, 0.88);
  outline: none;
}

.lightbox__figure {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  max-width: min(1100px, 100%);
  max-height: 100%;
}

.lightbox__figure img {
  display: block;
  max-width: 100%;
  max-height: 80vh;
  border-radius: 12px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
  object-fit: contain;
  background: #000;
}

.lightbox__caption {
  color: rgba(255, 255, 255, 0.85);
  font-size: 0.9rem;
  text-align: center;
  max-width: 80ch;
}

.lightbox__close,
.lightbox__nav {
  position: absolute;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: var(--white);
  cursor: pointer;
  font-size: 1.5rem;
  line-height: 1;
  transition: background-color 0.15s ease, transform 0.15s ease;
}

.lightbox__close:hover,
.lightbox__nav:hover {
  background: rgba(255, 255, 255, 0.22);
}

.lightbox__close:active,
.lightbox__nav:active {
  transform: scale(0.96);
}

.lightbox__close {
  top: 1.25rem;
  right: 1.25rem;
}

.lightbox__nav {
  top: 50%;
  transform: translateY(-50%);
  font-size: 2rem;
}

.lightbox__nav:active {
  transform: translateY(-50%) scale(0.96);
}

.lightbox__nav--prev {
  left: 1.25rem;
}

.lightbox__nav--next {
  right: 1.25rem;
}

.lightbox__counter {
  position: absolute;
  bottom: 1.25rem;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: var(--white);
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
}

.lightbox-enter-active,
.lightbox-leave-active {
  transition: opacity 0.18s ease;
}

.lightbox-enter-from,
.lightbox-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .lightbox {
    padding: 1rem;
  }
  .lightbox__nav--prev {
    left: 0.5rem;
  }
  .lightbox__nav--next {
    right: 0.5rem;
  }
}
</style>
