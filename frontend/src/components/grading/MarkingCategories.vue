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
            @input="queueSave"
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
            @input="queueSave"
          />
        </label>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, reactive, watch } from 'vue'
import {
  fetchGroupCategories,
  saveGroupCategories,
  type GroupCategories
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const props = defineProps<{ groupId: number }>()

// Save state renders on the page's "Submitted" line, not inside the boxes.
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

const form = reactive<GroupCategories>({
  product_categories: [],
  product_category_other: '',
  solution_category: '',
  solution_category_other: ''
})

let loaded = false
let saveTimer: ReturnType<typeof setTimeout> | null = null
let statusTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.groupId,
  async (id) => {
    loaded = false
    emit('status', null)
    try {
      Object.assign(form, await fetchGroupCategories(id))
      loaded = true
    } catch (err) {
      emit('status', { text: apiErrorFromUnknown(err).message, error: true })
    }
  },
  { immediate: true }
)

const save = async () => {
  if (!loaded) return
  try {
    Object.assign(form, await saveGroupCategories(props.groupId, { ...form }))
    emit('status', { text: 'Saved.', error: false })
    if (statusTimer) clearTimeout(statusTimer)
    statusTimer = setTimeout(() => emit('status', null), 1500)
  } catch (err) {
    emit('status', {
      text: `Save failed: ${apiErrorFromUnknown(err).message}`,
      error: true
    })
  }
}

// Selections save themselves shortly after the last change — no button, the
// same way the checkbox on the certificates release page behaves.
const queueSave = () => {
  if (!loaded) return
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => void save(), 600)
}

onBeforeUnmount(() => {
  if (saveTimer) clearTimeout(saveTimer)
  if (statusTimer) clearTimeout(statusTimer)
})

const toggleProduct = (option: string) => {
  const idx = form.product_categories.indexOf(option)
  if (idx >= 0) form.product_categories.splice(idx, 1)
  else form.product_categories.push(option)
  queueSave()
}

const pickSolution = (option: string) => {
  form.solution_category = option
  queueSave()
}
</script>

<style scoped>
.marking-categories {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
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
