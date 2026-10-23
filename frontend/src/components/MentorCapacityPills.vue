<template>
  <!-- How many groups a mentor can take on, as the pages' tabs (tab-bar and
       tab-pill): the one chosen is the open tab. Each is a radio underneath,
       hidden, so the keyboard and screen readers still have it. On
       registering and on the mentor's own profile. -->
  <div class="tab-bar capacity-pills">
    <label
      v-for="(option, index) in options"
      :key="option.value"
      class="tab-pill"
      :class="{ active: modelValue === option.value }"
    >
      <input
        :id="index === 0 ? id : undefined"
        type="radio"
        :name="name"
        :value="option.value"
        :checked="modelValue === option.value"
        :aria-invalid="invalid"
        :required="required"
        @change="emit('update:modelValue', option.value)"
      />
      <span>{{ option.label }}</span>
    </label>
  </div>
</template>

<script setup lang="ts" generic="T extends string | number">
defineProps<{
  /** The first choice's id, for a label or an error to point at. */
  id: string
  name: string
  modelValue: T | '' | null
  options: { value: T; label: string }[]
  invalid?: boolean
  required?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<style scoped>
/* On one line, as wide as its choices; where it sits is the page's. */
.capacity-pills {
  display: flex;
  width: fit-content;
  margin-bottom: 0;
}

.capacity-pills .tab-pill {
  position: relative;
  justify-content: center;
  cursor: pointer;
}

.capacity-pills input {
  position: absolute;
  inset: 0;
  margin: 0;
  opacity: 0;
  cursor: pointer;
}

.capacity-pills .tab-pill:has(input:focus-visible) {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
}

.capacity-pills:has(input[aria-invalid='true']) {
  border-color: #a93732;
}
</style>
