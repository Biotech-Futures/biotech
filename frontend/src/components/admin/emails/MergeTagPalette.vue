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
  border: 1px solid #c7d2fe;
  border-radius: 0.375rem;
  background: #eef2ff;
  color: #3730a3;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.merge-tags__tag:hover {
  background: #e0e7ff;
  border-color: #818cf8;
}

.merge-tags__tag code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.75rem;
}
</style>