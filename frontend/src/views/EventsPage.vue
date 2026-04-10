<template>
  <div class="content-area">
    <div class="page-head">
      <h1>Events & Workshops</h1>
      <div class="head-actions">
        <button class="btn btn-outline">
          <i class="fas fa-filter"></i> Filter
        </button>
        <button v-if="isAdmin" class="btn btn-primary" @click="createEvent">
          <i class="fas fa-plus"></i> Create Event
        </button>
      </div>
    </div>

    <!-- 两列网格 -->
    <div class="events-grid" v-if="events.length">
      <div v-for="ev in events" :key="ev.id" class="event-card">
        <!-- 封面：支持自定义图片/占位背景 -->
        <div class="event-banner" :style="bannerStyle(ev)">
          <i v-if="!ev.cover" class="fas fa-calendar-alt"></i>

          <!-- 管理员可编辑封面 -->
          <button
            v-if="isAdmin"
            type="button"
            class="edit-cover-btn"
            @click="triggerCoverPicker(ev.id)"
            title="Change cover image"
          >
            <i class="fas fa-image"></i>
          </button>
          <!-- （可选）重置封面 -->
          <button
            v-if="isAdmin && ev.cover"
            type="button"
            class="edit-cover-btn"
            style="right: 46px;"
            @click="resetCover(ev)"
            title="Remove cover image"
          >
            <i class="fas fa-trash"></i>
          </button>
          <!-- 隐藏文件选择器 -->
          <input
            type="file"
            accept="image/*"
            class="hidden-file"
            :ref="el => setCoverInputRef(el, ev.id)"
            @change="onCoverPicked($event, ev)"
          />
        </div>

        <div class="event-content">
          <span class="event-date">{{ formatDate(ev.date) }}</span>
          <h3 class="event-title">{{ ev.title }}</h3>
          <p class="event-description">
            {{ ev.description || 'Join us for this important session as part of the BIOTech Futures program.' }}
          </p>

          <div class="event-meta">
            <div class="event-meta-item">
              <i class="fas fa-clock"></i> {{ ev.time }}
            </div>
            <div class="event-meta-item">
              <i class="fas fa-map-marker-alt"></i> {{ ev.location }}
            </div>
            <div class="event-meta-item">
              <i class="fas fa-users"></i> {{ ev.type }}
            </div>
          </div>

          <!-- CTA 区：View Details + Register Now -->
          <div class="cta-row">
            <button class="btn btn-outline" @click="openDetails(ev)">View Details</button>

            <a
              v-if="ev.registerLink"
              class="btn btn-primary"
              :href="ev.registerLink"
              target="_blank"
              rel="noopener"
            >
              Register Now
            </a>
            <button v-else class="btn btn-primary" @click="register(ev)">Register Now</button>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="card">
      <h3>No upcoming events</h3>
    </div>

    <!-- 详情弹窗 -->
    <div class="modal" :class="{ show: showModal }" @click.self="closeDetails">
      <div class="modal-content">
        <div class="modal-header">
          <div class="modal-title">{{ selected?.title }}</div>
          <button class="modal-close" @click="closeDetails">&times;</button>
        </div>
        <div class="modal-body">
          <div class="detail-banner" :style="bannerStyle(selected)">
            <i v-if="selected && !selected.cover" class="fas fa-calendar-alt"></i>
          </div>
          <p style="color:#6c757d; margin: 0.75rem 0;">
            {{ formatDate(selected?.date) }} • {{ selected?.time }} • {{ selected?.location }} • {{ selected?.type }}
          </p>
          <p>{{ selected?.longDescription || selected?.description || defaultLong }}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeDetails">Close</button>
          <a
            v-if="selected?.registerLink"
            class="btn btn-primary"
            :href="selected.registerLink"
            target="_blank"
            rel="noopener"
          >Register Now</a>
          <button v-else class="btn btn-primary" @click="register(selected)">Register Now</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { mockEvents } from '../data/mock.js'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

const events = ref(mockEvents.map(e => ({ ...e })))

const defaultLong =
  'This session is part of the BIOTech Futures program. Learn, collaborate, and build your project with mentors and peers.'

// --- 显示与格式化 ---
const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-AU', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

const bannerStyle = (ev) => {
  const base = 'height: 150px; display:flex; align-items:center; justify-content:center; color: #fff;'
  if (!ev) return base
  if (ev.cover) {
    return `${base} background-image: url('${ev.cover}'); background-size: cover; background-position: center;`
  }
  // 无封面则用品牌渐变/纯色占位
  return `${base} background: linear-gradient(135deg, var(--dark-green), var(--mint-green));`
}

// --- 详情弹窗 ---
const showModal = ref(false)
const selected = ref(null)
const openDetails = (ev) => {
  selected.value = ev
  showModal.value = true
}
const closeDetails = () => {
  showModal.value = false
  selected.value = null
}

// --- 注册（占位逻辑，可换成你的实际流程） ---
const register = (ev) => {
  alert(`Registering for: ${ev?.title || 'Event'}`)
}

// --- 封面可编辑（管理员）：文件选择 & 本地预览 & localStorage 持久化 ---
const coverInputs = new Map()
const setCoverInputRef = (el, id) => {
  if (el) coverInputs.set(id, el)
}
const triggerCoverPicker = (id) => {
  const input = coverInputs.get(id)
  if (input) input.click()
}
const onCoverPicked = (e, ev) => {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    ev.cover = String(reader.result) // data URL，本地预览
    try {
      localStorage.setItem(`eventCover:${ev.id}`, ev.cover)
    } catch {}
  }
  reader.readAsDataURL(file)
  // 清空 input 值，防止同图不触发 change
  e.target.value = ''
}
const resetCover = (ev) => {
  try { localStorage.removeItem(`eventCover:${ev.id}`) } catch {}
  ev.cover = null
}

// 初始载入：还原持久化封面
onMounted(() => {
  events.value.forEach(ev => {
    try {
      const saved = localStorage.getItem(`eventCover:${ev.id}`)
      if (saved) ev.cover = saved
    } catch {}
  })
})

// 可扩展：创建活动（仅管理员）
const createEvent = () => {
  alert('Create Event (demo)')
}
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}
.head-actions {
  display: flex;
  gap: 1rem;
}

/* 两列布局（小屏 1 列） */
.events-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.5rem;
}
@media (max-width: 900px) {
  .events-grid {
    grid-template-columns: 1fr;
  }
}

/* 复用现有卡片样式，细节增强 */
.event-card {
  background-color: var(--white);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px var(--shadow);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.event-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow);
}
.event-banner {
  position: relative;
}
.event-banner i {
  font-size: 2.25rem;
  opacity: 0.9;
}

/* 编辑封面按钮（仅管理员可见） */
.edit-cover-btn {
  position: absolute;
  right: 10px;
  bottom: 10px;
  background: rgba(0,0,0,0.55);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  cursor: pointer;
  font-size: 0.875rem;
}
.edit-cover-btn:hover {
  background: rgba(0,0,0,0.7);
}
.hidden-file {
  display: none;
}

.event-content {
  padding: 1.5rem;
}
.event-date {
  display: inline-block;
  background-color: var(--light-green);
  color: var(--dark-green);
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}
.event-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--charcoal);
  margin: 0.25rem 0 0.5rem;
}
.event-description {
  color: #6c757d;
  margin-bottom: 1rem;
  line-height: 1.5;
}
.event-meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.875rem;
  color: #6c757d;
  margin-bottom: 1rem;
}
.event-meta-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

/* CTA 行 */
.cta-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

/* 详情弹窗里的横幅（沿用卡片风格） */
.detail-banner {
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  border-radius: 6px;
  margin-bottom: 1rem;
}
.detail-banner i {
  font-size: 2.5rem;
}
</style>
