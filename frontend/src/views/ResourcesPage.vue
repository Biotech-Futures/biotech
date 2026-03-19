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

    <div v-if="loading" class="card" style="margin-top:1.5rem;">
      <p style="text-align:center;color:#6c757d;">Loading resources...</p>
    </div>

    <div v-else-if="error" class="card" style="margin-top:1.5rem;border-left:4px solid #dc3545;">
      <h3 style="color:#dc3545;">Error</h3>
      <p style="color:#6c757d;">{{ error }}</p>
      <button @click="loadResources" class="btn btn-primary" style="margin-top:1rem;">Retry</button>
    </div>

    <div v-else-if="filteredResources.length === 0" class="card" style="margin-top:1.5rem;">
      <h3>No resources found</h3>
      <p style="color:#6c757d;">
        <span v-if="searchQuery || activeFilter !== 'All Resources'">
          Try changing your search keywords or filter.
        </span>
        <span v-else>
          There are no resources available yet. Check back later or contact your administrator.
        </span>
      </p>
    </div>

    <div v-else class="resource-grid">
      <div
        v-for="resource in filteredResources"
        :key="resource.id"
        class="resource-card"
        @click="openResource(resource)"
      >
        <!-- Top cover (editable; admin-only controls) -->
        <div class="resource-banner" :style="bannerStyle(resource)">
          <i v-if="!resource.cover" :class="getResourceIcon(resource.type)" class="banner-icon"></i>

          <!-- Admin: change cover -->
          <button
            v-if="isAdmin"
            type="button"
            class="edit-cover-btn"
            title="Change cover image"
            @click.stop="triggerCoverPicker(resource.id)"
          >
            <i class="fas fa-image"></i>
          </button>

          <!-- Admin: remove cover -->
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

          <!-- Hidden file input -->
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
          <!-- Remove "Updated..." text; show only the type -->
          <div class="resource-meta">
            <span class="res-type">{{ prettyType(resource.type) }}</span>
          </div>
          <div style="margin-top:0.5rem;">
            <span class="status-badge" :class="getAudienceClass(resource.role)">{{ getAudienceLabel(resource.role) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type ComponentPublicInstance } from 'vue'
import { fetchResources, type Resource } from '../utils/resourcesAPI'
import { useAuthStore } from '../stores/auth'

type ResourceTypeKey = 'document' | 'video' | 'template' | 'guide' | string
type Audience = 'all' | 'student' | 'mentor' | 'supervisor' | 'admin' | string

// Transform backend Resource to frontend format
interface FrontendResource {
  id: number
  title: string
  type: ResourceTypeKey
  updated: string
  role: Audience
  cover?: string | null
}

// Resource data (from API)
const backendResources = ref<Resource[]>([])
const loading = ref(false)
const error = ref('')

// Transform backend resources to frontend format
const resources = computed<FrontendResource[]>(() => {
  return backendResources.value.map(r => ({
    id: r.id,
    title: r.resource_name,
    type: (r.resource_type_detail?.type_name as ResourceTypeKey) || 'document',
    updated: new Date(r.upload_datetime).toLocaleString(),
    role: (r.visible_roles?.[0]?.role_name as Audience) || 'all',
    cover: null
  }))
})

/** Admin permissions (Pinia) */
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)

// Search/filter
const filters = ['All Resources', 'Documents', 'Videos', 'Templates', 'Guides'] as const
type FilterOption = typeof filters[number]
const activeFilter = ref<FilterOption>('All Resources')

const typeMap: Record<FilterOption, ResourceTypeKey | null> = {
  'All Resources': null,
  Documents: 'document',
  Videos: 'video',
  Templates: 'template',
  Guides: 'guide'
}

const filteredResources = computed<FrontendResource[]>(() => {
  let list = resources.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(r => r.title.toLowerCase().includes(q))
  }
  const t = typeMap[activeFilter.value]
  if (t) list = list.filter(r => r.type === t)
  return list
})

// Load resources from API
const loadResources = async (): Promise<void> => {
  // Check if user is authenticated
  if (!auth.isAuthenticated) {
    error.value = 'You must be logged in to view resources'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const response = await fetchResources()
    backendResources.value = response.results
  } catch (err: any) {
    error.value = err.message || 'Failed to load resources'
    console.error('Error loading resources:', err)
  } finally {
    loading.value = false
  }
}

// Icons and type labels
  const iconMap: Record<'document' | 'video' | 'template' | 'guide', string> = {
    document: 'fas fa-file-alt',
    video: 'fas fa-video',
    template: 'fas fa-file-code',
    guide: 'fas fa-book'
  }
  if (type in iconMap) {
    return iconMap[type as keyof typeof iconMap]
  }
  return 'fas fa-file'
}
const prettyType = (type: ResourceTypeKey): string => {
  const labelMap: Record<'document' | 'video' | 'template' | 'guide', string> = {
    document: 'Document',
    video: 'Video',
    template: 'Template',
    guide: 'Guide'
  }
  if (type in labelMap) {
    return labelMap[type as keyof typeof labelMap]
  }
  return 'Resource'
}

// Open resource (placeholder logic)
  alert(`Opening resource: ${resource.title}`)
}

// --- Editable cover (admin only) ---
const coverInputs = new Map<number, HTMLInputElement>()
const setCoverInputRef = (el: Element | ComponentPublicInstance | null, id: number) => {
  if (el instanceof HTMLInputElement) {
    coverInputs.set(id, el)
  }
}
const triggerCoverPicker = (id: number) => { coverInputs.get(id)?.click() }

const onCoverPicked = (event: Event, res: FrontendResource) => {
  const input = event.target as HTMLInputElement | null
  if (!input) return
  const file = input.files && input.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    res.cover = String(reader.result) // data URL preview
    try { localStorage.setItem(`resourceCover:${res.id}`, res.cover) } catch {}
  }
  reader.readAsDataURL(file)
  input.value = '' // Clear to allow the same file to trigger change
}

const resetCover = (resource: FrontendResource) => {
  try { localStorage.removeItem(`resourceCover:${resource.id}`) } catch {}
  resource.cover = null
}

// On load: restore persisted covers and fetch resources
  await loadResources()

  resources.value.forEach(r => {
    try {
      const saved = localStorage.getItem(`resourceCover:${r.id}`)
      if (saved) r.cover = saved
    } catch {}
  })
})

// Banner style: show cover image or brand gradient
  const base = 'height:120px; display:flex; align-items:center; justify-content:center; color:#fff;'
  if (res?.cover) {
    return `${base} background-image:url('${res.cover}'); background-size:cover; background-position:center;`
  }
  return `${base} background: linear-gradient(135deg, var(--dark-green), var(--eucalypt));`
}

const getAudienceLabel = (role: Audience): string => {
  const labels: Record<'all' | 'student' | 'mentor' | 'supervisor' | 'admin', string> = {
    all: 'All Users',
    student: 'Student',
    mentor: 'Mentor',
    supervisor: 'Supervisor',
    admin: 'Admin'
  }
  if (role in labels) {
    return labels[role as keyof typeof labels]
  }
  return 'Unknown'
}

const getAudienceClass = (role: Audience): string => {
  const classes: Record<'all' | 'student' | 'mentor' | 'supervisor' | 'admin', string> = {
    all: 'status-active',
    student: 'status-info',
    mentor: 'status-warning',
    supervisor: 'status-pending',
    admin: 'status-danger'
  }
  if (role in classes) {
    return classes[role as keyof typeof classes]
  }
  return 'status-active'
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

/* Edit cover button (admins only) */
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
