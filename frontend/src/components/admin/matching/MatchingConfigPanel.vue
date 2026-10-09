<template>
  <section class="matching-config" aria-labelledby="matching-config-title">
    <div class="matching-config__head">
      <h3 id="matching-config-title" class="matching-config__title">Scoring weights</h3>
      <p class="matching-config__scope">Changes apply to the next student matching run.</p>
    </div>

    <p v-if="status === 'loading'" class="matching-config__state" role="status">
      Loading matching weights...
    </p>

    <p v-else-if="status === 'forbidden'" class="matching-config__error" role="alert">
      <i class="fas fa-lock" aria-hidden="true"></i>
      <span>{{ FORBIDDEN_MESSAGE }}</span>
    </p>

    <p v-else-if="status === 'error'" class="matching-config__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ loadError }}</span>
      <button type="button" class="btn btn-sm btn-outline" @click="load">Retry</button>
    </p>

    <form v-else class="matching-config__form" novalidate @submit.prevent="onSave">
      <div class="matching-config__grid">
        <div v-for="(field, index) in fields" :key="field.key" class="form-field">
          <div class="matching-config__label-row">
            <label class="form-label" :for="`matching-config-${field.key}`">
              {{ field.label }}
            </label>
            <!-- Help lives in a tooltip to keep the row compact. It stays in the
                 input's aria-describedby, so screen readers still hear it with
                 the field, and the button opens it on keyboard focus. -->
            <span class="matching-config__tip-wrap">
              <button
                type="button"
                class="matching-config__info"
                :aria-label="`About the ${field.label} weight`"
                :aria-describedby="`matching-config-${field.key}-help`"
              >
                <i class="fas fa-circle-info" aria-hidden="true"></i>
              </button>
              <span
                :id="`matching-config-${field.key}-help`"
                class="matching-config__tip"
                :class="{ 'matching-config__tip--end': index === fields.length - 1 }"
                role="tooltip"
              >
                {{ field.help }}
              </span>
            </span>
          </div>
          <div class="matching-config__input-wrap">
            <input
              :id="`matching-config-${field.key}`"
              v-model.number="weights[field.key]"
              type="number"
              inputmode="decimal"
              min="0"
              max="100"
              step="1"
              class="form-input"
              :aria-invalid="Boolean(weightError(field.key))"
              :aria-describedby="describedBy(field.key)"
            />
            <span class="matching-config__suffix" aria-hidden="true">%</span>
          </div>
          <p
            v-if="weightError(field.key)"
            :id="`matching-config-${field.key}-error`"
            class="matching-config__field-error"
          >
            {{ weightError(field.key) }}
          </p>
        </div>
      </div>

      <p v-if="saveError" class="matching-config__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ saveError }}</span>
      </p>

      <p v-if="notice" class="matching-config__notice" role="status">
        <i class="fas fa-check" aria-hidden="true"></i>
        <span>{{ notice }}</span>
      </p>

      <!-- Total on the left, Save on the right. -->
      <div class="matching-config__footer">
        <div
          id="matching-config-total"
          class="matching-config__total"
          :class="{ 'matching-config__total--invalid': !totalMatches }"
        >
          <p class="matching-config__total-value" aria-live="polite">
            <i
              v-if="!totalMatches"
              class="fas fa-triangle-exclamation"
              aria-hidden="true"
            ></i>
            Total: <strong>{{ totalLabel }}</strong>
          </p>
          <p class="matching-config__total-hint">
            Weights must total exactly {{ requiredTotal }}%. They are not adjusted
            automatically.
          </p>
          <p v-if="fieldErrors?.weightTotal" class="matching-config__field-error" role="alert">
            {{ fieldErrors.weightTotal }}
          </p>
        </div>

        <!-- Described by the total, so a disabled Save says why. -->
        <button
          type="submit"
          class="btn btn-sm btn-primary"
          :disabled="!canSave"
          aria-describedby="matching-config-total"
        >
          <i class="fas fa-floppy-disk" aria-hidden="true"></i>
          <span>{{ saving ? 'Saving...' : 'Save weights' }}</span>
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import {
  FORBIDDEN_MESSAGE,
  MATCHING_WEIGHT_FIELDS,
  useMatchingConfig
} from '@/composables/admin/useMatchingConfig'
import type { MatchingWeightKey } from '@/utils/matchingConfig'

const fields = MATCHING_WEIGHT_FIELDS

const {
  status,
  loadError,
  weights,
  saving,
  saveError,
  fieldErrors,
  notice,
  requiredTotal,
  totalLabel,
  totalMatches,
  canSave,
  weightError,
  load,
  save
} = useMatchingConfig()

const describedBy = (key: MatchingWeightKey) =>
  [`matching-config-${key}-help`, weightError(key) ? `matching-config-${key}-error` : '']
    .filter(Boolean)
    .join(' ')

const onSave = () => {
  void save()
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.matching-config {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background-color: var(--white);
}

.matching-config__title {
  margin: 0 0 0.25rem;
  font-size: 1rem;
}

.matching-config__scope,
.matching-config__muted {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.matching-config__form {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

/* The shared .btn class doesn't space an icon from its label. */
.matching-config .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.matching-config__warning {
  margin: 0;
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--warning);
  border-radius: 6px;
  color: #8a6100;
  font-size: 0.85rem;
}

/* Fields — same look as the admin form sheets. */
/* Four across at desktop widths; auto-fit wraps them on narrower screens. */
.matching-config__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: 0.75rem;
}

.matching-config__label-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  margin-bottom: 0.3rem;
}

.form-label {
  display: block;
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
}

/* Field help tooltip — same pattern as the matching mode pills. */
.matching-config__tip-wrap {
  position: relative;
  display: inline-flex;
}

.matching-config__info {
  display: inline-flex;
  padding: 0.1rem;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.8rem;
  line-height: 1;
  cursor: help;
}

.matching-config__info:hover,
.matching-config__info:focus-visible {
  color: var(--charcoal);
}

.matching-config__tip {
  position: absolute;
  top: calc(100% + 0.4rem);
  left: 0;
  z-index: 30;
  display: none;
  width: 15rem;
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--surface-elevated);
  box-shadow: 0 8px 24px var(--shadow);
  color: var(--charcoal);
  font-size: 0.75rem;
  font-weight: 400;
  line-height: 1.4;
  white-space: normal;
}

/* The last field opens inwards so the tip stays inside the panel. */
.matching-config__tip--end {
  right: 0;
  left: auto;
}

.matching-config__tip-wrap:hover .matching-config__tip,
.matching-config__tip-wrap:focus-within .matching-config__tip {
  display: block;
}

.form-input {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
}

.form-input[aria-invalid='true'] {
  border-color: var(--danger);
}

.matching-config__input-wrap {
  position: relative;
}

.matching-config__input-wrap .form-input {
  padding-right: 1.8rem;
}

.matching-config__suffix {
  position: absolute;
  top: 50%;
  right: 0.7rem;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.85rem;
  pointer-events: none;
}

.matching-config__field-error {
  margin: 0.3rem 0 0;
  color: var(--danger);
  font-size: 0.8rem;
}

/* Live total, in the footer row beside Save. */
.matching-config__total {
  min-width: 0;
}

.matching-config__total-value {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  font-size: 0.95rem;
}

.matching-config__total-hint {
  margin: 0.15rem 0 0;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.matching-config__total--invalid .matching-config__total-value,
.matching-config__total--invalid .matching-config__total-hint {
  color: var(--danger);
}

.matching-config__state {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.matching-config__error,
.matching-config__notice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.6rem 0.85rem;
  border-radius: 8px;
  font-size: 0.9rem;
}

.matching-config__error {
  border: 1px solid var(--danger);
  color: var(--danger);
}

.matching-config__notice {
  border: 1px solid var(--border-light);
  color: var(--charcoal);
}

.matching-config__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-light);
}
</style>
