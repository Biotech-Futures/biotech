<template>
  <div class="content-area">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;">
      <h1>Admin Dashboard</h1>
      <div style="display:flex;gap:1rem;">
        <select v-model="activeTrack" class="form-control" style="width:220px;">
          <option value="AUS-NSW">Track: AUS-NSW</option>
          <option value="Brazil">Track: Brazil</option>
          <option value="Global">Track: Global</option>
        </select>
      </div>
    </div>

    <div class="grid grid-4" style="margin-bottom:2rem;">
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Total Users</span>
          <i class="fas fa-users" style="color:var(--eucalypt);"></i>
        </div>
        <div class="widget-value">{{ users.length }}</div>
        <div class="widget-footer">
          <span style="color:var(--success);">demo</span>
        </div>
      </div>
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Active Groups</span>
          <i class="fas fa-layer-group" style="color:var(--mint-green);"></i>
        </div>
        <div class="widget-value">{{ groupsCount }}</div>
        <div class="widget-footer">
          <span>{{ pendingMatches }} pending matches</span>
        </div>
      </div>
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Mentors</span>
          <i class="fas fa-user-tie" style="color:var(--air-force-blue);"></i>
        </div>
        <div class="widget-value">{{ mentorCount }}</div>
        <div class="widget-footer">
          <span>{{ mentorActive }} active, {{ mentorPending }} pending</span>
        </div>
      </div>
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Students</span>
          <i class="fas fa-graduation-cap" style="color:var(--yellow);"></i>
        </div>
        <div class="widget-value">{{ studentCount }}</div>
        <div class="widget-footer">
          <span>Year 9-12 students</span>
        </div>
      </div>
    </div>

    <div class="data-table">
      <div class="table-header">
        <h3 style="margin:0;">User Management</h3>
        <div class="table-actions">
          <input v-model="userSearch" type="text" class="form-control" placeholder="Search users..." style="width:250px;">
          <button class="btn btn-outline"><i class="fas fa-filter"></i> Filter</button>
          <button class="btn btn-outline"><i class="fas fa-download"></i> Export</button>
          <button class="btn btn-primary"><i class="fas fa-user-plus"></i> Add User</button>
        </div>
      </div>

      <div class="table-wrapper">
        <table>
          <thead>
          <tr>
            <th><input type="checkbox" class="table-checkbox" @change="toggleSelectAll($event)"></th>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Track</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
          </thead>
          <tbody>
          <tr v-for="u in filteredUsers" :key="u.id">
            <td><input type="checkbox" class="table-checkbox" v-model="selected" :value="u.id"></td>
            <td>{{ u.name }}</td>
            <td>{{ u.email }}</td>
            <td>{{ u.role }}</td>
            <td>{{ u.track }}</td>
            <td>
                <span :class="['status-badge', u.status === 'active' ? 'status-active' : (u.status === 'pending' ? 'status-pending' : 'status-inactive')]">
                  {{ u.status }}
                </span>
            </td>
            <td>
              <button class="btn btn-outline btn-sm" style="margin-right:0.5rem;">Edit</button>
              <button class="btn btn-outline btn-sm">View</button>
            </td>
          </tr>
          <tr v-if="filteredUsers.length === 0">
            <td colspan="7" style="text-align:center;color:#6c757d;">No users found</td>
          </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { mockUsers, mockGroups } from '../data/mock.js'

const users = ref(mockUsers)
const activeTrack = ref('AUS-NSW')

// Widgets（简单 demo 统计）
const groupsCount = computed(() => mockGroups.length)
const pendingMatches = 8 // demo 占位
const mentorCount = computed(() => users.value.filter(u => u.role === 'mentor').length)
const mentorActive = computed(() => users.value.filter(u => u.role === 'mentor' && u.status === 'active').length)
const mentorPending = computed(() => users.value.filter(u => u.role === 'mentor' && u.status === 'pending').length)
const studentCount = computed(() => users.value.filter(u => u.role === 'student').length)

// Users 过滤与选择
const userSearch = ref('')
const selected = ref([])

const filteredUsers = computed(() => {
  const q = userSearch.value.trim().toLowerCase()
  return users.value.filter(u => {
    const inTrack = activeTrack.value === 'Global' ? true : u.track === activeTrack.value
    const match = !q || [u.name, u.email, u.role, u.track].some(f => String(f).toLowerCase().includes(q))
    return inTrack && match
  })
})

const toggleSelectAll = (e) => {
  if (e.target.checked) {
    selected.value = filteredUsers.value.map(u => u.id)
  } else {
    selected.value = []
  }
}
</script>
