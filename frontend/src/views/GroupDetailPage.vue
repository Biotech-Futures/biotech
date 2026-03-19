<template>
  <div class="content-area group-detail" :data-active="activeTab">
    <!-- Header -->
    <div class="gd-head">
      <div class="gd-head-left">
        <div class="group-avatars">
          <div class="group-avatar" style="width:48px;height:48px;font-size:1.1rem;">YG</div>
        </div>
        <div>
          <h2 class="gd-title">{{ group.name }}</h2>
          <p class="gd-subtitle">{{ group.members }} members · Group since August 04, 2025</p>
        </div>
      </div>
    </div>

    <!-- Mobile tabs (hidden on desktop) -->
    <nav class="mobile-tabs">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'plan' }"
        @click="activeTab = 'plan'"
      >
        Plan
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'discussion' }"
        @click="activeTab = 'discussion'"
      >
        Discussion
      </button>
    </nav>

    <!-- Desktop: two columns; mobile: single column via tabs -->
    <div class="split" :data-active="activeTab">
      <!-- Left column: Plan -->
      <section class="pane pane--plan card">
        <div class="card-header">
          <h3 class="card-title">Plan</h3>
          <button type="button" class="btn btn-primary btn-sm">
            <i class="fas fa-plus"></i> Add Milestone
          </button>
        </div>
        <div class="card-content plan-content">
          <div v-for="m in tasks" :key="m.id" class="milestone">
            <div class="milestone-header">
              <div class="milestone-title">
                <i class="fas fa-flag"></i>
                {{ m.milestone }}
              </div>
              <div class="milestone-status">
                {{ countCompleted(m) }}/{{ m.tasks.length }} Completed
              </div>
            </div>

            <div class="task-list">
              <div
                v-for="t in m.tasks"
                :key="t.id"
                class="task-item"
                @click="t.completed = !t.completed"
              >
                <div :class="['task-checkbox', { checked: t.completed }]" />
                <div :class="['task-label', { completed: t.completed }]">{{ t.name }}</div>
                <i class="fas fa-calendar" style="color:#6c757d;"></i>
                <i class="fas fa-user" style="color:#6c757d;"></i>
              </div>

              <div class="add-task-row">
                <button
                  type="button"
                  class="btn btn-outline btn-sm add-task-btn"
                  @click.stop="addTask(m)"
                  title="Add a new task under this milestone"
                >
                  <i class="fas fa-plus"></i>
                  Add Task
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Right column: Discussion -->
      <section class="pane pane--discussion">
        <div class="chat-container">
          <!-- Discussion header in white -->
          <div class="chat-header">
            <h3 style="margin:0;">Discussion Board</h3>

          </div>

          <div class="chat-messages" ref="msgList">
            <div
              v-for="message in messages"
              :key="message.id"
              :class="['message', { own: message.isOwn }]"
            >
              <div class="message-avatar">{{ getInitials(message.author) }}</div>
              <div class="message-content">
                <div class="message-header">
                  <span class="message-author">{{ message.author }}</span>
                  <span class="message-meta">
                    <span class="message-date">{{ formatDate(message.date) }}</span>
                    <span class="message-time">{{ message.time }}</span>
                  </span>
                </div>
                <div class="message-text">{{ message.text }}</div>
              </div>
            </div>
          </div>

          <div class="chat-input">
            <div class="chat-input-group">
              <textarea
                ref="composer"
                v-model="newMessage"
                class="chat-input-field"
                placeholder="Type your message..."
                rows="2"
                @keydown.enter.exact.prevent="sendMessage"
              ></textarea>
              <div class="chat-actions">
                <button class="chat-btn" title="Attach file">
                  <i class="fas fa-paperclip"></i>
                </button>
                <button class="chat-btn" @click="sendMessage" title="Send">
                  <i class="fas fa-paper-plane"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { mockGroups } from '../data/mock.js'

const route = useRoute()
const groupId = route.params.id
const group = ref(mockGroups.find(g => g.id === groupId) || mockGroups[0])

// Only keep plan / discussion
const activeTab = ref('plan')

// Sample task data
const tasks = ref([
  {
    id: 1,
    milestone: 'Getting Started',
    tasks: [
      { id: 11, name: 'Determine Group Topic', completed: false },
      { id: 12, name: 'Determine Meeting Time', completed: false }
    ]
  },
  {
    id: 2,
    milestone: 'Working Towards a Solution',
    tasks: [
      { id: 21, name: 'Meeting 1: Initialisation', completed: false },
      { id: 22, name: 'Meeting 2: Project Planning & Poster Outline', completed: false },
      { id: 23, name: 'Meeting 3: Draft Review & Optional Deliverables', completed: false }
    ]
  }
])

const countCompleted = (m) => m.tasks.filter(t => t.completed).length

const addTask = (m) => {
  const nextId = (m.tasks.reduce((max, t) => Math.max(max, t.id), 0) || 0) + 1
  m.tasks.push({ id: nextId, name: 'New Task', completed: false })
}

// Discussion data (each message includes a date field)
const messages = ref([
  {
    id: 1,
    author: 'Anita Pickard',
    text: 'Hi team! How is your idea going?',
    time: '03:04 PM',
    date: '2025-09-03',
    isOwn: false
  },
  {
    id: 2,
    author: 'You',
    text: 'Sounds great!',
    time: '03:20 PM',
    date: '2025-09-03',
    isOwn: true
  }
])

const newMessage = ref('')
const composer = ref(null)
const msgList = ref(null)

const getInitials = (name) => name.split(' ').map(n => n[0]).join('').toUpperCase()

const formatDate = (d) => {
  const date = new Date(d)
  if (Number.isNaN(date.getTime())) return d
  return date.toLocaleDateString('en-AU', { year: 'numeric', month: 'short', day: 'numeric' })
}

const sendMessage = async () => {
  if (!newMessage.value.trim()) return
  const now = new Date()
  messages.value.push({
    id: Date.now(),
    author: 'You',
    text: newMessage.value.trim(),
    time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    date: now.toISOString().slice(0, 10), // YYYY-MM-DD
    isOwn: true
  })
  newMessage.value = ''
  await nextTick()
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
  composer.value?.focus()
}

const focusComposer = () => composer.value?.focus()

onMounted(() => {
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
})
</script>

<style scoped>
/* Header */
.gd-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
}
.gd-head-left {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}
.gd-title { margin: 0; color: var(--charcoal); }
.gd-subtitle { color: #6c757d; margin-top: 0.15rem; }

/* Mobile tabs (hidden on desktop) */
.mobile-tabs {
  display: none;
  gap: 0.75rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border-light);
  padding-bottom: 0.5rem;
}
.tab-btn {
  background: transparent;
  border: none;
  padding: 0.5rem 0.25rem;
  color: var(--charcoal);
  font-weight: 500;
  border-bottom: 3px solid transparent;
  cursor: pointer;
}
.tab-btn.active {
  color: var(--dark-green);
  border-bottom-color: var(--dark-green);
}

/* Two-column layout container */
.split {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 1.5rem;
  align-items: stretch;
  max-height: 70vh;
  height: 70vh;
}

/* Left column: Plan */
.pane--plan {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
}

/* Right column: Discussion */
.pane--discussion {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 320px;
}

/* Card styles */
.card {
  height: 100%;
  min-height: 320px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.card-content {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}
.plan-content {
  padding-right: 2px; /* for visible scrollbar */
}

/* Discussion board: chat-container fills card, chat-messages scrolls */
.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
}

.pane--discussion .chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}

/* Tweak Add Task row to match global button styles */
.add-task-row {
  padding-left: 0.25rem;
  margin-top: 0.4rem;
}
.add-task-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-color: var(--border-light);
}

/* Discussion header in white (override global .chat-header green background) */
.pane--discussion .chat-header {
  background-color: var(--white) !important;
  color: var(--charcoal) !important;
  border-bottom: 1px solid var(--border-light);
}

/* Ensure chat-container fills available space */
.pane--discussion .chat-container {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  height: 100%;
  min-height: 0;
}

/* Let chat-messages take available space */
.chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}

/* Layout to show date and time on the right of each message header */
.message-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.message-date {
  color: #6c757d;
  font-weight: 500;
}

/* Only own messages: make date text white to match the bubble */
.pane--discussion .message.own .message-date {
  color: #fff !important;
  opacity: 0.95;
}

/* Message text color for own messages */
.pane--discussion .message.own .message-text {
  color: #fff !important;
}

/* Mobile: single column with tabs controlling visibility */
@media (max-width: 900px) {
  .split {
    grid-template-columns: 1fr;
    max-height: 80vh;
    height: 80vh;
  }
  .mobile-tabs { display: flex; }
  .split .pane { display: none; }
  .split[data-active="plan"] .pane--plan { display: block; }
  .split[data-active="discussion"] .pane--discussion { display: block; }
  .card {
    min-height: 220px;
  }
}
</style>
