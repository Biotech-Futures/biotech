<template>
  <section class="matching-config" aria-labelledby="matching-config-title">
    <div class="matching-config__head">
      <h3 id="matching-config-title" class="matching-config__title">Student matching weights</h3>
      <p class="matching-config__scope">
        These weights apply to <strong>student matching only</strong>. Mentor matching is not
        affected. Changes take effect from the next student matching run.
      </p>
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
      <!-- First save: what is in force now, and what saving will change. -->
      <div v-if="isFirstConfig" class="matching-config__builtin" role="note">
        <p class="matching-config__builtin-title">
          <i class="fas fa-circle-info" aria-hidden="true"></i>
          No saved weights yet — student matching is using its built-in weighting.
        </p>
        <p class="matching-config__muted">
          Currently applied built-in values (score points, not percentages, so they do not total
          100):
        </p>
        <dl class="matching-config__builtin-values">
          <div v-for="field in fields" :key="field.key" class="matching-config__builtin-value">
            <dt>{{ field.label }}</dt>
            <dd>{{ active?.appliedWeights[field.key] }}</dd>
          </div>
        </dl>
        <p class="matching-config__warning">
          Saving a configuration replaces the built-in weighting and may change student matching
          results. The form below starts from the suggested defaults.
        </p>
      </div>

      <p v-else class="matching-config__muted">
        Editing the active configuration. Saving updates it in place.
      </p>

      <div class="form-field">
        <label class="form-label" for="matching-config-name">Configuration name</label>
        <input
          id="matching-config-name"
          v-model="name"
          type="text"
          class="form-input"
          maxlength="100"
          placeholder="e.g. Student weights 2026"
          :aria-invalid="Boolean(fieldErrors?.name)"
          :aria-describedby="fieldErrors?.name ? 'matching-config-name-error' : undefined"
        />
        <p
          v-if="fieldErrors?.name"
          id="matching-config-name-error"
          class="matching-config__field-error"
        >
          {{ fieldErrors.name }}
        </p>
      </div>

      <div class="matching-config__grid">
        <div v-for="field in fields" :key="field.key" class="form-field">
          <label class="form-label" :for="`matching-config-${field.key}`">{{ field.label }}</label>
          <div class="matching-config__input-wrap">
            <input
              :id="`matching-config-${field.key}`"
              v-model.number="weights[field.key]"
              type="number"
              inputmode="decimal"
              min="0"
              max="100"
              step="0.01"
              class="form-input"
              :aria-invalid="Boolean(weightError(field.key))"
              :aria-describedby="describedBy(field.key)"
            />
            <span class="matching-config__suffix" aria-hidden="true">%</span>
          </div>
          <p :id="`matching-config-${field.key}-help`" class="matching-config__help">
            {{ field.help }}
          </p>
          <p
            v-if="weightError(field.key)"
            :id="`matching-config-${field.key}-error`"
            class="matching-config__field-error"
          >
            {{ weightError(field.key) }}
          </p>
        </div>
      </div>

      <div class="matching-config__total" :class="{ 'matching-config__total--ok': totalMatches }">
        <p class="matching-config__total-value" aria-live="polite">
          Total: <strong>{{ totalLabel }}</strong>
        </p>
        <p class="matching-config__help">
          The weights must total exactly {{ requiredTotal }}%. They are not adjusted
          automatically, so change them until the total matches.
        </p>
        <p v-if="fieldErrors?.weightTotal" class="matching-config__field-error" role="alert">
          {{ fieldErrors.weightTotal }}
        </p>
      </div>

      <p v-if="saveError" class="matching-config__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ saveError }}</span>
      </p>

      <p v-if="notice" class="matching-config__notice" role="status">
        <i class="fas fa-check" aria-hidden="true"></i>
        <span>{{ notice }}</span>
      </p>

      <div class="matching-config__footer">
        <button type="submit" class="btn btn-sm btn-primary" :disabled="!canSave">
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
  active,
  name,
  weights,
  saving,
  saveError,
  fieldErrors,
  notice,
  requiredTotal,
  isFirstConfig,
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
.matching-config__muted,
.matching-config__help {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.matching-config__help {
  margin-top: 0.3rem;
  font-size: 0.78rem;
  line-height: 1.4;
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

/* Built-in weighting notice (no saved config yet) */
.matching-config__builtin {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--bg-light);
}

.matching-config__builtin-title {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin: 0;
  font-weight: 600;
}

.matching-config__builtin-values {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.25rem;
  margin: 0;
}

.matching-config__builtin-value {
  display: flex;
  gap: 0.35rem;
  font-size: 0.85rem;
}

.matching-config__builtin-value dt {
  color: var(--text-muted);
}

.matching-config__builtin-value dd {
  margin: 0;
  font-weight: 600;
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
.matching-config__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: 0.85rem;
}

.form-label {
  display: block;
  margin-bottom: 0.3rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
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

/* Live total */
.matching-config__total {
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--danger);
  border-radius: 8px;
}

.matching-config__total--ok {
  border-color: var(--border-light);
}

.matching-config__total-value {
  margin: 0;
  font-size: 0.95rem;
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
  justify-content: flex-end;
}
</style>
