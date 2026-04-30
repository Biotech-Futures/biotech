<template>
  <div class="content-area">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2rem;gap:1rem;flex-wrap:wrap;">
      <div>
        <h1 style="margin-bottom:0.35rem;">Admin Dashboard</h1>
        <p style="margin:0;color:#6c757d;">
          {{ scopeSummary }}
        </p>
      </div>
      <button class="btn btn-outline" @click="loadAdminData" :disabled="loading">
        <i class="fas fa-rotate-right"></i> Refresh
      </button>
    </div>

    <div v-if="error" class="card" style="margin-bottom:1rem;border-left:4px solid var(--danger);">
      <p style="margin:0;color:#6c757d;">{{ error }}</p>
    </div>

    <div class="grid grid-4" style="margin-bottom:2rem;">
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Total Users</span>
          <i class="fas fa-users" style="color:var(--eucalypt);"></i>
        </div>
        <div class="widget-value">{{ totalUsers }}</div>
        <div class="widget-footer">
          <span>{{ summary.active_users }} active users</span>
        </div>
      </div>
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Active Groups</span>
          <i class="fas fa-layer-group" style="color:var(--mint-green);"></i>
        </div>
        <div class="widget-value">{{ summary.active_groups }}</div>
        <div class="widget-footer">
          <span>{{ summary.groups_without_mentor }} groups without mentor</span>
        </div>
      </div>
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Pending Matches</span>
          <i class="fas fa-user-tie" style="color:var(--air-force-blue);"></i>
        </div>
        <div class="widget-value">{{ summary.unassigned_match_recommendations }}</div>
        <div class="widget-footer">
          <span>{{ summary.invited_or_pending_users }} invited or pending users</span>
        </div>
      </div>
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Upcoming Events</span>
          <i class="fas fa-graduation-cap" style="color:var(--yellow);"></i>
        </div>
        <div class="widget-value">{{ summary.upcoming_events }}</div>
        <div class="widget-footer">
          <span>{{ summary.suspended_or_deactivated_users }} suspended or deactivated users</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header" style="margin-bottom:0.75rem;">
        <h3 class="card-title">User Management</h3>
      </div>
      <p style="margin:0 0 1rem;color:#6c757d;line-height:1.6;">
        This page now loads live operational summary data from the backend. The detailed user table has been hidden because the current backend user list endpoint is HTML-only and not consumable as JSON from the SPA.
      </p>
      <div v-if="scopeLabels.length" style="display:flex;gap:0.5rem;flex-wrap:wrap;">
        <span
          v-for="label in scopeLabels"
          :key="label"
          class="status-badge status-info"
        >
          {{ label }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { buildSessionHeaders } from '@/utils/csrf'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const loading = ref(false)
const error = ref('')
const tracksById = ref(new Map())

const summary = ref({
  track_scope: [],
  active_users: 0,
  invited_or_pending_users: 0,
  suspended_or_deactivated_users: 0,
  active_groups: 0,
  groups_without_mentor: 0,
  unassigned_match_recommendations: 0,
  upcoming_events: 0
})

const totalUsers = computed(() => {
  return Number(summary.value.active_users || 0)
    + Number(summary.value.invited_or_pending_users || 0)
    + Number(summary.value.suspended_or_deactivated_users || 0)
})

const scopeLabels = computed(() => {
  const scopeIds = Array.isArray(summary.value.track_scope) ? summary.value.track_scope : []
  if (!scopeIds.length) return ['All assigned tracks']

  return scopeIds.map((trackId) => tracksById.value.get(Number(trackId)) || `Track ${trackId}`)
})

const scopeSummary = computed(() => {
  if (loading.value) return 'Loading admin scope...'
  if (!scopeLabels.value.length) return 'Scope unavailable'
  return `Current scope: ${scopeLabels.value.join(', ')}`
})

async function fetchJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    credentials: 'include',
    headers: buildSessionHeaders({
      headers: {
        Accept: 'application/json'
      }
    })
  })

  const text = await response.text()
  const data = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw new Error(data?.detail || data?.error || `Request failed: ${response.status}`)
  }

  return data
}

async function loadAdminData() {
  loading.value = true
  error.value = ''

  try {
    const [summaryData, tracksData] = await Promise.all([
      fetchJson('/api/v1/admin/summary/'),
      fetchJson('/groups/tracks/?page_size=100')
    ])

    summary.value = {
      track_scope: Array.isArray(summaryData?.track_scope) ? summaryData.track_scope : [],
      active_users: Number(summaryData?.active_users || 0),
      invited_or_pending_users: Number(summaryData?.invited_or_pending_users || 0),
      suspended_or_deactivated_users: Number(summaryData?.suspended_or_deactivated_users || 0),
      active_groups: Number(summaryData?.active_groups || 0),
      groups_without_mentor: Number(summaryData?.groups_without_mentor || 0),
      unassigned_match_recommendations: Number(summaryData?.unassigned_match_recommendations || 0),
      upcoming_events: Number(summaryData?.upcoming_events || 0)
    }

    const trackItems = Array.isArray(tracksData?.results) ? tracksData.results : (Array.isArray(tracksData) ? tracksData : [])
    tracksById.value = new Map(
      trackItems
        .map((track) => [Number(track?.id), track?.track_name])
        .filter((entry) => entry[0] && entry[1])
    )
  } catch (loadError) {
    error.value = loadError instanceof Error
      ? loadError.message
      : 'Admin summary could not be loaded right now.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAdminData()
})
</script>
