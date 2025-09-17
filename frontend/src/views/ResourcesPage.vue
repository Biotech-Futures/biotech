<template>
  <div class="content-area">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;">
      <h1>Resource Library</h1>
      <div style="display:flex;gap:1rem;">
        <input
          type="text"
          v-model="searchQuery"
          class="form-control"
          placeholder="Search resources..."
          style="width:300px"
        />
        <button v-if="isAdmin" class="btn btn-primary">
          <i class="fas fa-upload"></i> Upload Resource
        </button>
      </div>
    </div>

    <div style="display:flex;gap:1rem;margin-bottom:2rem;">
      <button
        v-for="f in filters"
        :key="f"
        @click="activeFilter = f"
        :class="['btn', activeFilter === f ? 'btn-primary' : 'btn-outline']"
      >
        {{ f }}
      </button>
    </div>

    <div class="resource-grid">
      <div
        v-for="resource in filteredResources"
        :key="resource.id"
        class="resource-card"
        @click="openResource(resource)"
      >
        <!-- 顶部封面（可编辑，admin 可见按钮） -->
        <div class="resource-banner" :style="bannerStyle(resource)">
          <i v-if="!resource.cover" :class="getResourceIcon(resource.type)" class="banner-icon"></i>

          <!-- 管理员：变更封面 -->
          <button
            v-if="isAdmin"
            type="button"
            class="edit-cover-btn"
            title="Change cover image"
            @click.stop="triggerCoverPicker(resource.id)"
          >
            <i class="fas fa-image"></i>
          </button>

          <!-- 管理员：移除封面 -->
          <button
            v-if="isAdmin && resource.cover"
            type="button"
            class="edit-cover-btn"
            style="right: 46px;"
            title="Remove cover image"
            @click.stop="resetCover(resource)"
          >
            <i class="fas fa-trash"></i>
          </button>

          <!-- 隐藏的文件选择器 -->
          <input
            type="file"
            accept="image/*"
            class="hidden-file"
            :ref="el => setCoverInputRef(el, resource.id)"
            @change="onCoverPicked($event, resource)"
          />
        </div>

        <div class="resource-content">
          <div class="resource-title">{{ resource.title }}</div>
          <!-- 移除 Updated ...，仅保留类型 -->
          <div class="resource-meta">
            <span class="res-type">{{ prettyType(resource.type) }}</span>
          </div>
          <div style="margin-top:0.5rem;">
            <span class="status-badge" :class="getAudienceClass(resource.role)">{{ getAudienceLabel(resource.role) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="filteredResources.length === 0" class="card" style="margin-top:1.5rem;">
      <h3>No results</h3>
      <p style="color:#6c757d;">Try changing your search keywords or filter.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { mockResources } from '../data/mock.js'
import { useAuthStore } from '../stores/auth' // 如未接入 Pinia，可改回你之前的 isAdmin 逻辑

// 资源数据（复制一份，避免直接改 mock）
const resources = ref(mockResources.map(r => ({ ...r })))

/** Admin 权限（Pinia） */
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

// 搜索/筛选
const searchQuery = ref('')
const filters = ['All Resources', 'Documents', 'Videos', 'Templates', 'Guides']
const activeFilter = ref('All Resources')

const typeMap = {
  'All Resources': null,
  Documents: 'document',
  Videos: 'video',
  Templates: 'template',
  Guides: 'guide'
}

const filteredResources = computed(() => {
  let list = resources.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(r => r.title.toLowerCase().includes(q))
  }
  const t = typeMap[activeFilter.value]
  if (t) list = list.filter(r => r.type === t)
  return list
})

// 图标与类型显示
const getResourceIcon = (type) => {
  const icons = {
    document: 'fas fa-file-alt',
    video: 'fas fa-video',
    template: 'fas fa-file-code',
    guide: 'fas fa-book'
  }
  return icons[type] || 'fas fa-file'
}
const prettyType = (type) => {
  const map = { document: 'Document', video: 'Video', template: 'Template', guide: 'Guide' }
  return map[type] || 'Resource'
}

// 打开资源（占位逻辑）
const openResource = (resource) => {
  alert(`Opening resource: ${resource.title}`)
}

// —— 封面图可编辑（仅 admin） —— //
const coverInputs = new Map()
const setCoverInputRef = (el, id) => { if (el) coverInputs.set(id, el) }
const triggerCoverPicker = (id) => { coverInputs.get(id)?.click() }

const onCoverPicked = (e, res) => {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    res.cover = String(reader.result) // dataURL 即时预览
    try { localStorage.setItem(`resourceCover:${res.id}`, res.cover) } catch {}
  }
  reader.readAsDataURL(file)
  e.target.value = '' // 清空，避免同图不触发 change
}

const resetCover = (res) => {
  try { localStorage.removeItem(`resourceCover:${res.id}`) } catch {}
  res.cover = null
}

// 载入时恢复本地封面持久化
onMounted(() => {
  resources.value.forEach(r => {
    try {
      const saved = localStorage.getItem(`resourceCover:${r.id}`)
      if (saved) r.cover = saved
    } catch {}
  })
})

// 横幅样式：有封面则显示图片，否则用品牌渐变
const bannerStyle = (res) => {
  const base = 'height:120px; display:flex; align-items:center; justify-content:center; color:#fff;'
  if (res?.cover) {
    return `${base} background-image:url('${res.cover}'); background-size:cover; background-position:center;`
  }
  return `${base} background: linear-gradient(135deg, var(--dark-green), var(--eucalypt));`
}

const getAudienceLabel = (role) => {
  const labels = {
    'all': 'All Users',
    'student': 'Student',
    'mentor': 'Mentor',
    'supervisor': 'Supervisor',
    'admin': 'Admin'
  }
  return labels[role] || 'Unknown'
}

const getAudienceClass = (role) => {
  const classes = {
    'all': 'status-active',
    'student': 'status-info',
    'mentor': 'status-warning',
    'supervisor': 'status-pending',
    'admin': 'status-danger'
  }
  return classes[role] || 'status-active'
}
</script>

<style scoped>
.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

.resource-card {
  background-color: var(--white);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px var(--shadow);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}
.resource-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--shadow);
}

.resource-banner {
  position: relative;
}
.banner-icon {
  font-size: 2rem;
  opacity: 0.95;
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
  padding: 0.35rem 0.55rem;
  cursor: pointer;
  font-size: 0.85rem;
}
.edit-cover-btn:hover {
  background: rgba(0,0,0,0.7);
}
.hidden-file { display: none; }

.resource-content { padding: 1.25rem; }
.resource-title {
  font-weight: 600;
  color: var(--charcoal);
  margin-bottom: 0.35rem;
}
.resource-meta {
  font-size: 0.9rem;
  color: #6c757d;
}
.res-type { text-transform: capitalize; }
</style>
