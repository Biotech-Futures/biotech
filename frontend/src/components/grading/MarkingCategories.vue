<template>
  <div class="marking-categories">
    <div class="marking-categories__group" role="group" aria-label="Product Category">
      <p class="marking-categories__legend">
        Product Category <span class="marking-categories__hint">(Select one or more)</span>
      </p>
      <div class="marking-categories__options">
        <label
          v-for="option in PRODUCT_OPTIONS"
          :key="option"
          class="marking-categories__option"
        >
          <input
            type="checkbox"
            :checked="form.product_categories.includes(option)"
            @change="toggleProduct(option)"
          />
          <span>{{ option }}</span>
        </label>
        <label class="marking-categories__option">
          <input
            type="checkbox"
            :checked="form.product_categories.includes(OTHER)"
            @change="toggleProduct(OTHER)"
          />
          <span>Other:</span>
          <input
            v-model="form.product_category_other"
            type="text"
            class="marking-categories__other"
            :disabled="!form.product_categories.includes(OTHER)"
            aria-label="Other product category"
          />
        </label>
      </div>
    </div>

    <div class="marking-categories__group" role="radiogroup" aria-label="Category of Solution">
      <p class="marking-categories__legend">
        Category of Solution <span class="marking-categories__hint">(Select one)</span>
      </p>
      <div class="marking-categories__options">
        <label
          v-for="option in SOLUTION_OPTIONS"
          :key="option"
          class="marking-categories__option"
        >
          <input
            type="radio"
            :name="`solution-category-${groupId}`"
            :checked="form.solution_category === option"
            @change="pickSolution(option)"
          />
          <span>{{ option }}</span>
        </label>
        <label class="marking-categories__option">
          <input
            type="radio"
            :name="`solution-category-${groupId}`"
            :checked="form.solution_category === OTHER"
            @change="pickSolution(OTHER)"
          />
          <span>Other:</span>
          <input
            v-model="form.solution_category_other"
            type="text"
            class="marking-categories__other"
            :disabled="form.solution_category !== OTHER"
            aria-label="Other solution category"
          />
        </label>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  fetchGroupCategories,
  saveGroupCategories,
  type GroupCategories
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const props = defineProps<{ groupId: number }>()

// Only a failed load reports here (the page shows it in its error banner).
// Saving is the page's Save button, which calls save() below.
const emit = defineEmits<{
  (e: 'status', value: { text: string; error: boolean } | null): void
}>()

const PRODUCT_OPTIONS = [
  'Health and Medicine',
  'Sustainable Environment',
  'Emerging Technologies',
  'Regulation Ethics'
]
const SOLUTION_OPTIONS = ['Product/Device', 'Technique/Method', 'Treatment']
const OTHER = 'Other'

const blank = (): GroupCategories => ({
  product_categories: [],
  product_category_other: '',
  solution_category: '',
  solution_category_other: ''
})
const copy = (c: GroupCategories): GroupCategories => ({
  ...c,
  product_categories: [...c.product_categories]
})
const sameCategories = (a: GroupCategories, b: GroupCategories) =>
  a.product_category_other === b.product_category_other &&
  a.solution_category === b.solution_category &&
  a.solution_category_other === b.solution_category_other &&
  [...a.product_categories].sort().join('\n') === [...b.product_categories].sort().join('\n')

const form = reactive<GroupCategories>(blank())
// The selections as last loaded or saved, to tell unsaved edits apart.
const stored = ref<GroupCategories>(blank())
const loaded = ref(false)

// Edits the Save button has not stored yet. The page folds this into the
// SAQ form's dirty state, so Save enables and the leave guards ask first.
const isDirty = computed(() => loaded.value && !sameCategories(form, stored.value))

watch(
  () => props.groupId,
  async (id) => {
    loaded.value = false
    emit('status', null)
    try {
      const data = await fetchGroupCategories(id)
      stored.value = copy(data)
      Object.assign(form, copy(data))
      loaded.value = true
    } catch (err) {
      emit('status', {
        text: `Category load failed: ${apiErrorFromUnknown(err).message}`,
        error: true
      })
    }
  },
  { immediate: true }
)

// Called by the page's Save button. A failure throws for the page to
// report, and the edits stay unsaved so pressing Save again retries.
const save = async () => {
  if (!isDirty.value) return
  const sent = copy(form)
  const saved = await saveGroupCategories(props.groupId, sent)
  stored.value = copy(saved)
  // Keep anything typed while the request was in flight.
  if (sameCategories(form, sent)) Object.assign(form, copy(saved))
}

defineExpose({ isDirty, save })

const toggleProduct = (option: string) => {
  const idx = form.product_categories.indexOf(option)
  if (idx >= 0) form.product_categories.splice(idx, 1)
  else form.product_categories.push(option)
}

const pickSolution = (option: string) => {
  form.solution_category = option
}
</script>

<style scoped>
.marking-categories {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 1rem;
  /* Same width as the rubric form below it (RubricForm's max-width). */
  max-width: 22rem;
}

/* Both boxes read as one seamless panel, like the rubric criteria below:
   no gap, no divider between them. */
.marking-categories__group + .marking-categories__group {
  border-top: none;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
  /* Tighter than a fresh box's top padding: the section above already
     leaves room below its options. */
  padding-top: 0.2rem;
}

.marking-categories__group:has(+ .marking-categories__group) {
  border-bottom: none;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}

.marking-categories__group {
  min-width: 0;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
  padding: 0.6rem 0.85rem 0.75rem;
  margin: 0;
}

/* A plain heading inside the box — a real <legend> straddles the border.
   Sized like the rubric column's section titles ("Short Answer Questions"). */
.marking-categories__legend {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--charcoal);
  margin: 0 0 0.5rem;
}

.marking-categories__hint {
  color: var(--text-muted);
  font-weight: 400;
  font-style: italic;
}

.marking-categories__options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 1rem;
}

.marking-categories__option {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--charcoal);
  cursor: pointer;
}

.marking-categories__option input[type='checkbox'],
.marking-categories__option input[type='radio'] {
  accent-color: var(--dark-green);
}

.marking-categories__other {
  border: 1px solid var(--border-light);
  border-radius: 5px;
  background: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.82rem;
  font-family: inherit;
  padding: 0.2rem 0.4rem;
  width: 9rem;
}

.marking-categories__other:disabled {
  opacity: 0.55;
}

.marking-categories__other:focus {
  outline: none;
  border-color: var(--dark-green);
}

</style>
