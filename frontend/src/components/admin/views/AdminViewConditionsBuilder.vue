<template>
  <div class="conditions-builder">
    <div v-if="!modelValue.length" class="conditions-builder__empty">
      <p class="conditions-builder__empty-text">No custom conditions defined yet.</p>
    </div>

    <div v-else class="conditions-builder__list">
      <div
        v-for="(row, index) in modelValue"
        :key="index"
        class="conditions-builder__row-container"
      >
        <!-- Logic connector between rows -->
        <div v-if="index > 0" class="conditions-builder__connector">
          <button
            type="button"
            class="conditions-builder__logic-pill"
            :class="{ 'conditions-builder__logic-pill--or': row.logic === 'OR' }"
            @click="toggleLogic(index)"
            :title="`Click to switch to ${row.logic === 'OR' ? 'AND' : 'OR'}`"
          >
            {{ row.logic || 'AND' }}
          </button>
        </div>

        <!-- Condition Rule Row -->
        <div class="conditions-builder__row">
          <!-- Field picker -->
          <div class="conditions-builder__field">
            <label :for="`cond-field-${index}`" class="sr-only">Field</label>
            <select
              :id="`cond-field-${index}`"
              v-model="row.field"
              class="form-input form-select"
              @change="onFieldChange(row)"
            >
              <option v-for="f in FIELD_OPTIONS" :key="f.value" :value="f.value">
                {{ f.label }}
              </option>
            </select>
          </div>

          <!-- Operator picker -->
          <div class="conditions-builder__operator">
            <label :for="`cond-op-${index}`" class="sr-only">Operator</label>
            <select
              :id="`cond-op-${index}`"
              v-model="row.operator"
              class="form-input form-select"
            >
              <option v-for="op in OPERATOR_OPTIONS" :key="op.value" :value="op.value">
                {{ op.label }}
              </option>
            </select>
          </div>

          <!-- Value input / picker -->
          <div class="conditions-builder__value">
            <label :for="`cond-val-${index}`" class="sr-only">Value</label>
            
            <template v-if="row.operator === 'is_empty' || row.operator === 'is_set'">
              <input
                :id="`cond-val-${index}`"
                type="text"
                disabled
                placeholder="(No value needed)"
                class="form-input form-input--disabled"
              />
            </template>

            <template v-else-if="row.field === 'country'">
              <select
                :id="`cond-val-${index}`"
                v-model="row.value"
                class="form-input form-select"
              >
                <option value="">Select country...</option>
                <option
                  v-for="c in countries"
                  :key="c.id"
                  :value="c.countryName"
                >
                  {{ c.countryName }}
                </option>
              </select>
            </template>

            <template v-else-if="row.field === 'state'">
              <select
                :id="`cond-val-${index}`"
                v-model="row.value"
                class="form-input form-select"
              >
                <option value="">Select state...</option>
                <option
                  v-for="s in states"
                  :key="s.id"
                  :value="s.stateName"
                >
                  {{ s.stateName }}
                </option>
              </select>
            </template>

            <template v-else-if="row.field === 'role'">
              <select
                :id="`cond-val-${index}`"
                v-model="row.value"
                class="form-input form-select"
              >
                <option value="student">Student</option>
                <option value="mentor">Mentor</option>
                <option value="supervisor">Supervisor</option>
                <option value="admin">Admin</option>
              </select>
            </template>

            <template v-else>
              <input
                :id="`cond-val-${index}`"
                v-model="row.value"
                type="text"
                placeholder="Enter value..."
                class="form-input"
              />
            </template>
          </div>

          <!-- Delete Row Button -->
          <button
            type="button"
            class="conditions-builder__remove-btn"
            aria-label="Remove condition"
            @click="removeRow(index)"
          >
            <i class="fas fa-trash-can" aria-hidden="true"></i>
          </button>
        </div>
      </div>
    </div>

    <div class="conditions-builder__actions">
      <button
        type="button"
        class="btn btn-sm btn-outline conditions-builder__add-btn"
        @click="addRow"
      >
        <i class="fas fa-plus" aria-hidden="true"></i>
        <span>Add condition rule</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  fetchAdminCountries,
  fetchAdminStates,
  type AdminUserCountry,
  type AdminUserState,
  type ViewCondition,
} from '@/utils/adminAPI'

const props = defineProps<{
  modelValue: ViewCondition[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: ViewCondition[]): void
}>()

const FIELD_OPTIONS = [
  { value: 'program', label: 'Program / Group' },
  { value: 'country', label: 'Country' },
  { value: 'state', label: 'State' },
  { value: 'school', label: 'School / Institution' },
  { value: 'yearLevel', label: 'Year Level' },
  { value: 'interests', label: 'Interests' },
  { value: 'role', label: 'Role' },
]

const OPERATOR_OPTIONS = [
  { value: 'equals', label: 'equals' },
  { value: 'not_equals', label: 'not equals' },
  { value: 'contains', label: 'contains' },
  { value: 'is_empty', label: 'is empty' },
  { value: 'is_set', label: 'is set' },
]

const countries = ref<AdminUserCountry[]>([])
const states = ref<AdminUserState[]>([])

onMounted(async () => {
  try {
    const [cList, sList] = await Promise.all([
      fetchAdminCountries({ inUse: true }).catch(() => []),
      fetchAdminStates().catch(() => []),
    ])
    countries.value = cList
    states.value = sList
  } catch {
    // Non-blocking metadata failure
  }
})

const addRow = () => {
  const current = [...props.modelValue]
  current.push({
    field: 'program',
    operator: 'equals',
    value: '',
    logic: current.length > 0 ? 'AND' : undefined,
  })
  emit('update:modelValue', current)
}

const removeRow = (index: number) => {
  const current = props.modelValue.filter((_, i) => i !== index)
  if (current.length > 0 && current[0].logic) {
    current[0].logic = undefined
  }
  emit('update:modelValue', current)
}

const toggleLogic = (index: number) => {
  const current = [...props.modelValue]
  const row = current[index]
  if (row) {
    row.logic = row.logic === 'OR' ? 'AND' : 'OR'
    emit('update:modelValue', current)
  }
}

const onFieldChange = (row: ViewCondition) => {
  row.value = ''
}
</script>

<style scoped>
.conditions-builder {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.conditions-builder__empty {
  padding: 1rem;
  background-color: var(--bg-light);
  border: 1px dashed var(--border-light);
  border-radius: 6px;
  text-align: center;
}

.conditions-builder__empty-text {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.conditions-builder__list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.conditions-builder__row-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.conditions-builder__connector {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.conditions-builder__connector::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background-color: var(--border-light);
  z-index: 1;
}

.conditions-builder__logic-pill {
  position: relative;
  z-index: 2;
  padding: 0.15rem 0.65rem;
  font-size: 0.75rem;
  font-weight: 700;
  border-radius: 9999px;
  border: 1px solid var(--border-light);
  background-color: var(--surface-elevated, #ffffff);
  color: var(--dark-green);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
}

.conditions-builder__logic-pill:hover {
  background-color: var(--light-green);
}

.conditions-builder__logic-pill--or {
  color: #c05621;
  background-color: #fefcbf;
  border-color: #fbd38d;
}

.conditions-builder__row {
  display: grid;
  grid-template-columns: 1.4fr 1.1fr 2fr auto;
  gap: 0.5rem;
  align-items: center;
}

.form-input {
  width: 100%;
  padding: 0.45rem 0.65rem;
  font-size: 0.9rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--surface-elevated, #ffffff);
  color: var(--charcoal);
}

.form-input--disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

.conditions-builder__remove-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  background: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.15s ease-in-out;
}

.conditions-builder__remove-btn:hover {
  color: var(--danger);
  background-color: rgba(220, 53, 69, 0.1);
}

.conditions-builder__actions {
  margin-top: 0.25rem;
}

.conditions-builder__add-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 500;
  color: var(--dark-green);
  border-color: var(--border-light);
}

.conditions-builder__add-btn:hover {
  border-color: var(--dark-green);
  background-color: var(--light-green);
}

@media (max-width: 600px) {
  .conditions-builder__row {
    grid-template-columns: 1fr;
  }
}
</style>
