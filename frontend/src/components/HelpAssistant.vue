<template>
  <section class="help-assistant" role="dialog" aria-label="Help assistant" @keydown.esc="emit('close')">
    <header class="help-assistant__header">
      <h2 class="help-assistant__title">{{ BRAND_CONNECT }} help</h2>
      <button type="button" class="help-assistant__close" aria-label="Close help assistant" @click="emit('close')">
        <i class="fas fa-xmark" aria-hidden="true"></i>
      </button>
    </header>

    <div ref="listRef" class="help-assistant__messages" aria-live="polite">
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="help-assistant__message"
        :class="`help-assistant__message--${message.from}`"
      >
        <p>{{ message.text }}</p>
        <div v-if="message.links?.length" class="help-assistant__links">
          <RouterLink v-for="link in message.links" :key="link.to" :to="link.to">{{ link.label }}</RouterLink>
        </div>
      </div>
      <div v-if="isAsking" class="help-assistant__message help-assistant__message--bot">
        <p>Thinking…</p>
      </div>
    </div>

    <div class="help-assistant__suggestions">
      <button
        v-for="question in SUGGESTED_QUESTIONS"
        :key="question"
        type="button"
        :disabled="isAsking"
        @click="ask(question)"
      >
        {{ question }}
      </button>
    </div>

    <form class="help-assistant__form" @submit.prevent="ask(draft)">
      <input
        v-model="draft"
        type="text"
        maxlength="500"
        placeholder="Ask how to use the platform"
        aria-label="Your question"
      />
      <button type="submit" :disabled="isAsking || !draft.trim()">Send</button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { BRAND_CONNECT } from '@/constants/brand'
import { askAssistant, type AssistantLink } from '@/utils/assistantAPI'

const emit = defineEmits<{ close: [] }>()

// The three questions the user story asks the assistant to lead with.
const SUGGESTED_QUESTIONS = [
  'What should I do?',
  'What features does the platform have?',
  'How do I get help?',
]

interface Message {
  from: 'user' | 'bot'
  text: string
  links?: AssistantLink[]
}

const messages = ref<Message[]>([
  { from: 'bot', text: `Hi! I can help you find your way around ${BRAND_CONNECT}. Ask a question or pick one below.` },
])
const draft = ref('')
const isAsking = ref(false)
const listRef = ref<HTMLElement | null>(null)

async function scrollToLatest() {
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

async function ask(text: string) {
  const question = text.trim()
  if (!question || isAsking.value) return
  messages.value.push({ from: 'user', text: question })
  draft.value = ''
  isAsking.value = true
  void scrollToLatest()
  try {
    const reply = await askAssistant(question)
    messages.value.push({ from: 'bot', text: reply.answer, links: reply.links })
  } catch {
    messages.value.push({
      from: 'bot',
      text: 'Sorry, I could not answer just now. Please try again, or raise a ticket on the Support page.',
      links: [{ label: 'Support', to: '/support' }],
    })
  } finally {
    isAsking.value = false
    void scrollToLatest()
  }
}
</script>

<style scoped>
.help-assistant {
  position: fixed;
  top: 4.75rem;
  right: 1rem;
  z-index: 1001;
  width: min(380px, calc(100vw - 2rem));
  max-height: min(560px, calc(100vh - 6rem));
  display: flex;
  flex-direction: column;
  background: var(--white);
  color: var(--teal);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  box-shadow: 0 12px 32px var(--shadow);
  overflow: hidden;
}

.help-assistant__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: var(--dark-green);
  color: #fff;
}

.help-assistant__title {
  margin: 0;
  font-size: 1rem;
  color: inherit;
}

.help-assistant__close {
  border: none;
  background: transparent;
  color: inherit;
  font-size: 1.1rem;
  cursor: pointer;
}

.help-assistant__messages {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.help-assistant__message {
  max-width: 88%;
  padding: 0.5rem 0.75rem;
  border-radius: 10px;
  font-size: 0.9rem;
  line-height: 1.45;
}

.help-assistant__message p {
  margin: 0;
}

.help-assistant__message--bot {
  align-self: flex-start;
  background: var(--bg-light);
  border: 1px solid var(--border-light);
}

.help-assistant__message--user {
  align-self: flex-end;
  background: var(--dark-green);
  color: #fff;
}

.help-assistant__links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.help-assistant__links a {
  color: var(--dark-green);
  font-weight: 600;
}

:root[data-theme='dark'] .help-assistant__links a {
  color: var(--teal);
}

.help-assistant__suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0 1rem 0.5rem;
}

.help-assistant__suggestions button {
  border: 1px solid var(--dark-green);
  border-radius: 999px;
  background: transparent;
  color: inherit;
  padding: 0.2rem 0.6rem;
  font-size: 0.8rem;
  cursor: pointer;
}

.help-assistant__form {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-light);
}

.help-assistant__form input {
  flex: 1;
  min-width: 0;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-light);
  color: inherit;
}

.help-assistant__form button {
  border: none;
  border-radius: 8px;
  padding: 0 0.9rem;
  background: var(--dark-green);
  color: #fff;
  cursor: pointer;
}

.help-assistant button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
