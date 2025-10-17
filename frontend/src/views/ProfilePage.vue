<template>
  <div class="content-area">
    <div class="card" style="overflow:hidden;padding:0;">
      <div class="profile-header">
        <div class="profile-avatar-large">{{ getInitials(user.name) }}</div>
        <h2 class="profile-name">{{ user.name }}</h2>
        <p class="profile-role">{{ capitalise(user.role) }} • {{ user.track }}</p>
      </div>

      <div class="profile-content">
        <!-- Personal Information -->
        <div class="profile-section">
          <h3 class="profile-section-title">Personal Information</h3>
          <div class="profile-field">
            <span class="profile-field-label">Email:</span>
            <span class="profile-field-value">{{ user.email }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Track/Region:</span>
            <span class="profile-field-value">{{ user.track }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field-label">Member Since:</span>
            <span class="profile-field-value">August 2025</span>
          </div>
        </div>

        <!-- Interests -->
        <div class="profile-section">
          <h3 class="profile-section-title">Interests & Expertise</h3>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            <span
              v-for="interest in interests"
              :key="interest"
              class="status-badge"
              style="background-color:var(--light-green);color:var(--dark-green);"
            >{{ interest }}</span>

            <div style="display:flex;gap:0.5rem;align-items:center;">
              <input v-model="newInterest" class="form-control" placeholder="Add interest…" style="width:220px;" />
              <button class="btn btn-outline btn-sm" @click="addInterest">+ Add</button>
            </div>
          </div>
        </div>

        <!-- Contact Preferences -->
        <div class="profile-section">
          <h3 class="profile-section-title">Contact Preferences</h3>
          <div class="form-group">
            <label class="form-label">Preferred Contact Method</label>
            <select v-model="contactMethod" class="form-control">
              <option>Email</option>
              <option>Platform Messages</option>
              <option>Both</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Availability</label>
            <textarea v-model="availability" class="form-control" rows="3" placeholder="Enter your general availability..."></textarea>
          </div>
        </div>

        <div style="display:flex;justify-content:flex-end;gap:1rem;">
          <button class="btn btn-outline" @click="reset">Cancel</button>
          <button class="btn btn-primary" @click="save">Save Changes</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { mockUsers } from '../data/mock.js'

const user = ref(mockUsers[0])

const original = {
  contactMethod: 'Both',
  availability: '',
  interests: ['Biotechnology', 'Research', 'Mentoring', 'Innovation']
}

const contactMethod = ref(original.contactMethod)
const availability = ref(original.availability)
const interests = ref([...original.interests])
const newInterest = ref('')

const getInitials = (name) => name.split(' ').map(n => n[0]).join('').toUpperCase()
const capitalise = (s) => s.charAt(0).toUpperCase() + s.slice(1)

const addInterest = () => {
  const v = newInterest.value.trim()
  if (!v) return
  if (!interests.value.includes(v)) interests.value.push(v)
  newInterest.value = ''
}

const reset = () => {
  contactMethod.value = original.contactMethod
  availability.value = original.availability
  interests.value = [...original.interests]
  newInterest.value = ''
  alert('Changes discarded.')
}

const save = () => {
  // 这里作为演示，只弹框；后续可替换为 API 调用
  alert('Profile saved (demo).')
}
</script>
