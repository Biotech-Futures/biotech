<template>
  <div class="content-area">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;">
      <h1>Recent Announcements</h1>
      <div style="display:flex;gap:0.75rem;align-items:center;">
        <input
          v-model="q"
          type="text"
          class="form-control"
          placeholder="Search announcements..."
          style="width: 320px;"
        />
      </div>
    </div>

    <div class="card" v-for="a in filtered" :key="a.id" style="margin-bottom:1rem;">
      <div class="card-header" style="margin-bottom:0;padding-bottom:0;border-bottom:none;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
          <h3 class="card-title" style="margin:0;">{{ a.title }}</h3>
          <span class="status-badge" :class="getAudienceClass(a.audience)">
            {{ getAudienceLabel(a.audience) }}
          </span>
        </div>
      </div>
      <div style="color:#6c757d;margin:0.25rem 0 1rem;">
        {{ formatDate(a.date) }} · {{ a.author || 'Program Team' }}
      </div>
      <p style="margin-bottom:1rem;line-height:1.7;">{{ a.summary }}</p>

      <div>
        <!-- 内部详情页（若未来有） -->
        <RouterLink v-if="a.route" :to="a.route" class="btn btn-outline btn-sm">Read more</RouterLink>

        <!-- 外部链接 -->
        <a
          v-else-if="a.link"
          :href="a.link"
          target="_blank"
          rel="noopener"
          class="btn btn-outline btn-sm"
        >
          Open link
        </a>
      </div>
    </div>

    <div v-if="filtered.length === 0" class="card">
      <p style="margin:0;color:#6c757d;">No announcements found.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { mockAnnouncements } from '../data/mock.js'

const q = ref('')
const announcements = ref(mockAnnouncements)

const filtered = computed(() => {
  const text = q.value.trim().toLowerCase()
  if (!text) return announcements.value
  return announcements.value.filter(a =>
    [a.title, a.summary, a.author].some(f => String(f || '').toLowerCase().includes(text))
  )
})

const formatDate = (iso) => {
  const d = new Date(iso)
  return d.toLocaleDateString('en-AU', { year: 'numeric', month: 'short', day: 'numeric' })
}

const getAudienceLabel = (audience) => {
  const labels = {
    'all': 'All Users',
    'student': 'Student',
    'mentor': 'Mentor',
    'supervisor': 'Supervisor',
    'admin': 'Admin'
  }
  return labels[audience] || 'Unknown'
}

const getAudienceClass = (audience) => {
  const classes = {
    'all': 'status-active',
    'student': 'status-info',
    'mentor': 'status-warning',
    'supervisor': 'status-pending',
    'admin': 'status-danger'
  }
  return classes[audience] || 'status-active'
}
</script>
