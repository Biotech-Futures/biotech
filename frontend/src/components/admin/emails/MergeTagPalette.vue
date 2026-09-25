<template>
  <div class="merge-tags">
    <ul class="merge-tags__list">
      <li v-for="tag in tags" :key="tag.name">
        <button
          type="button"
          class="merge-tags__tag"
          :title="tagTitle(tag)"
          @click="emit('insert', tag)"
        >
          <code>{{ tokenFor(tag.name) }}</code>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { mergeTagToken, type SystemEmailMergeTag } from '@/utils/systemEmail'

defineProps<{
  tags: SystemEmailMergeTag[]
}>()

const emit = defineEmits<{
  (e: 'insert', tag: SystemEmailMergeTag): void
}>()

const tokenFor = (name: string) => mergeTagToken(name)

const tagTitle = (tag: SystemEmailMergeTag) =>
  tag.sample ? `${tag.description} — e.g. ${tag.sample}` : tag.description
</script>

<style scoped>
.merge-tags__list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.merge-tags__tag {
  padding: 0.25rem 0.5rem;
  border: 1px solid rgba(1, 113, 81, 0.35);
  border-radius: 0.375rem;
  background: var(--accent-green-soft);
  color: var(--dark-green);
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.merge-tags__tag:hover {
  background: rgba(1, 113, 81, 0.18);
  border-color: var(--dark-green);
}

.merge-tags__tag code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.75rem;
}
</style>