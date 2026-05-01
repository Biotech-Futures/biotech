<script setup>
import { ref, computed } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth' // Pinia Auth
import { mockGroups, mockResources, mockAnnouncements } from '../data/mock.js'

const router = useRouter()

// 从 Pinia 取当前登录用户与是否管理员
const auth = useAuthStore()
const { user, isAdmin } = storeToRefs(auth)
// 若 store 没有 isAdmin getter，则兜底判断 role
const effectiveIsAdmin = computed(() => (isAdmin?.value ?? (user.value?.role === 'admin')))

const groups = ref(mockGroups)
const resources = ref(mockResources)
const announcements = ref(mockAnnouncements)
const announcementsCount = computed(() => announcements.value.length)

const getCurrentDate = () =>
  new Date().toLocaleDateString('en-AU', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })

const getResourceIcon = (type) => {
  const icons = { document: 'fas fa-file-alt', video: 'fas fa-video', link: 'fas fa-link' }
  return icons[type] || 'fas fa-file'
}
</script>

<template>
  <div class="content-area">
    <div style="margin-bottom: 2rem;">
      <h1>Welcome back, {{ user?.name || 'User' }}!</h1>
      <p style="color:#6c757d;">
        {{ getCurrentDate() }} - Track: {{ user?.track || '—' }}
      </p>
    </div>

    <div class="grid grid-3" style="margin-bottom: 2rem;">
      <!-- Active Groups：仅管理员可见 -->
      <div class="widget" v-if="effectiveIsAdmin">
        <div class="widget-header">
          <span class="widget-title">Active Groups</span>
          <i class="fas fa-users" style="color: var(--eucalypt);"></i>
        </div>
        <div class="widget-value">{{ groups.length }}</div>
        <div class="widget-footer">
          <RouterLink to="/groups" style="color: var(--dark-green);">View all groups →</RouterLink>
        </div>
      </div>

      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Upcoming Events</span>
          <i class="fas fa-calendar" style="color: var(--mint-green);"></i>
        </div>
        <div class="widget-value">3</div>
        <div class="widget-footer">
          <RouterLink to="/events" style="color: var(--dark-green);">View calendar →</RouterLink>
        </div>
      </div>

      <!-- Resources -> Recent Announcements -->
      <div class="widget">
        <div class="widget-header">
          <span class="widget-title">Recent Announcements</span>
          <i class="fas fa-bullhorn" style="color: var(--air-force-blue);"></i>
        </div>
        <div class="widget-value">{{ announcementsCount }}</div>
        <div class="widget-footer">
          <RouterLink to="/announcements" style="color: var(--dark-green);">
            View announcements →
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- My Active Groups：所有用户可见 -->
    <div class="card" v-if="groups.length">
      <div class="card-header">
        <h3 class="card-title">My Active Groups ({{ groups.length }})</h3>
        <RouterLink to="/groups" style="color: var(--dark-green);">View all</RouterLink>
      </div>

      <div class="grid grid-2">
        <div
          v-for="group in groups"
          :key="group.id"
          class="group-card"
          @click="router.push('/groups/' + group.id)"
        >
          <div class="group-header">
            <div class="group-avatars">
              <div class="group-avatar">AP</div>
              <div class="group-avatar" style="background-color: var(--mint-green);">YG</div>
              <div class="group-avatar" style="background-color: var(--air-force-blue);">
                +{{ group.members - 2 }}
              </div>
            </div>
            <div class="group-info">
              <div class="group-name">{{ group.name }}</div>
              <!-- 胶囊样式的操作标签；.stop 防止触发整卡跳转 -->
              <!-- <button type="button" class="chip-action" @click.stop>
                {{ group.status }}
              </button> -->
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 资源区（所有用户可见） -->
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">Learn more with resources</h3>
        <RouterLink to="/resources" style="color: var(--dark-green);">View all</RouterLink>
      </div>

      <div class="resource-grid">
        <div
          v-for="resource in resources.slice(0, 6)"
          :key="resource.id"
          class="resource-card"
          @click="router.push('/resources/' + resource.id)"
        >
          <div class="resource-icon">
            <i :class="getResourceIcon(resource.type)"></i>
          </div>
          <div class="resource-content">
            <div class="resource-title">{{ resource.title }}</div>
            <div class="resource-meta">Updated {{ resource.updated }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 更精致的“Schedule Workshop”胶囊按钮 */
.chip-action {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.65rem;
  font-size: 0.8125rem;
  font-weight: 600;
  line-height: 1;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  border: 1px solid var(--dark-green);
  cursor: pointer;
  transition: all 0.2s ease;
}
.chip-action:hover {
  background-color: var(--dark-green);
  color: var(--white);
  transform: translateY(-1px);
  box-shadow: 0 2px 4px var(--shadow);
}
<<<<<<< Updated upstream
=======

.showcase-nav-btn:first-child:hover { transform: translateX(-2px) translateY(-1px) scale(1.04); }
.showcase-nav-btn:last-child:hover  { transform: translateX(2px) translateY(-1px) scale(1.04); }

.showcase-body {
  display: flex;
  flex-direction: column;
  gap: 0.88rem;
  flex: 1;
}

.showcase-image {
  position: relative;
  aspect-ratio: 16 / 8;
  width: 100%;
  border-radius: 22px;
  overflow: hidden;
  background-size: cover;
  background-position: center;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 22px 50px rgba(0, 3, 18, 0.26);
  transition: transform var(--t-slow) var(--ease-out), filter var(--t-slow), box-shadow var(--t-slow);
}

.showcase-image::before {
  content: '';
  position: absolute;
  inset: -35% auto auto -18%;
  width: 42%;
  height: 170%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.22), transparent);
  transform: skewX(-16deg);
  animation: showcaseImageSheen 10s ease-in-out infinite;
}

.showcase-card:hover .showcase-image {
  transform: translateY(-2px) scale(1.022);
  filter: saturate(1.12) contrast(1.02);
  box-shadow: 0 28px 62px rgba(0, 3, 18, 0.34);
}

.showcase-image-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(0, 3, 18, 0.04), rgba(0, 3, 18, 0.38)),
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.10), transparent 28%);
}

.showcase-copy {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.showcase-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.12rem;
  font-weight: 850;
  line-height: 1.35;
  letter-spacing: -0.02em;
}

.showcase-summary {
  margin: 0.4rem 0 0;
  color: color-mix(in srgb, var(--text-secondary) 90%, white 10%);
  font-size: 0.9rem;
  line-height: 1.72;
}

.showcase-footer {
  margin-top: auto;
  padding-top: 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.showcase-dots {
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.showcase-dot {
  width: 8px;
  height: 8px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.20);
  cursor: pointer;
  transition: background var(--t-fast), width var(--t-base), box-shadow var(--t-fast), transform var(--t-fast);
}

.showcase-dot:hover {
  transform: translateY(-1px) scale(1.08);
}

.showcase-dot.active {
  width: 22px;
  background: linear-gradient(90deg, #60a5fa, #7c3aed);
  box-shadow: 0 0 14px rgba(96, 165, 250, 0.45);
}

.showcase-link-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.52rem;
  min-height: 40px;
  padding: 0.5rem 0.96rem;
  border-radius: 999px;
  border: 1px solid rgba(60, 200, 110, 0.26);
  background: linear-gradient(145deg, rgba(40, 160, 80, 0.16), rgba(30, 130, 60, 0.08));
  color: #d6ffec;
  cursor: pointer;
  font-weight: 800;
  font-size: 0.84rem;
  overflow: hidden;
  transition: transform var(--t-fast), background var(--t-fast), border-color var(--t-fast), box-shadow var(--t-fast);
}

.showcase-link-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(100deg, transparent 18%, rgba(255, 255, 255, 0.16) 50%, transparent 82%);
  transform: translateX(-110%);
  transition: transform 0.8s ease;
}

.showcase-link-btn:hover::before {
  transform: translateX(110%);
}

.showcase-link-btn:hover {
  transform: translateY(-2px);
  background: linear-gradient(145deg, rgba(40, 160, 80, 0.24), rgba(30, 130, 60, 0.12));
  border-color: rgba(80, 220, 140, 0.42);
  box-shadow: 0 14px 30px rgba(30, 130, 60, 0.18);
}

.showcase-fade-enter-active,
.showcase-fade-leave-active {
  transition: opacity 0.34s ease, transform 0.34s ease;
}

.showcase-fade-enter-from,
.showcase-fade-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
}

@keyframes showcaseBorderSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes showcaseImageSheen {
  0%, 72%, 100% { transform: translateX(0) skewX(-16deg); opacity: 0; }
  10%, 42% { opacity: 1; }
  50% { transform: translateX(240%) skewX(-16deg); opacity: 0; }
}

@keyframes heroSheen {
  0%, 100% { transform: translateX(0) skewX(-18deg); opacity: 0; }
  14%, 34% { opacity: 1; }
  46% { transform: translateX(260%) skewX(-18deg); opacity: 0; }
}

/* ──────────────────────────────────────────────────────────────
   § 10  SUMMARY CARDS  (vivid neon top-border differentiates each)
   ────────────────────────────────────────────────────────────── */
.summary-card {
  position: relative;
  overflow: hidden;
  min-height: 170px;
  padding: 1.25rem 1.2rem 1.1rem;
  border-radius: var(--radius-card);
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: linear-gradient(160deg, rgba(6, 18, 12, 0.90), rgba(7, 16, 10, 0.76));
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-base), border-color var(--t-fast);
}

.summary-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2.5px;
  border-radius: var(--radius-card) var(--radius-card) 0 0;
}

.summary-card::after {
  content: '';
  position: absolute;
  right: -24px; top: -28px;
  width: 130px; height: 130px;
  border-radius: 999px;
  opacity: 0.32;
  pointer-events: none;
}

.summary-card:hover { transform: translateY(-7px) scale(1.014); box-shadow: var(--shadow-lg); }
.summary-card:hover .summary-icon-wrap { transform: translateY(-4px) rotate(-8deg); }

.accent-blue::before  { background: linear-gradient(90deg, transparent, #60a5fa, #38bdf8, transparent); }
.accent-blue::after   { background: radial-gradient(circle, rgba(96, 165, 250, 0.9), transparent 70%); }
.accent-blue:hover    { border-color: rgba(96, 165, 250, 0.26); }
.accent-blue .summary-icon-wrap { color: #93c5fd; }

.accent-violet::before { background: linear-gradient(90deg, transparent, #a78bfa, #c084fc, transparent); }
.accent-violet::after  { background: radial-gradient(circle, rgba(167, 139, 250, 0.88), transparent 70%); }
.accent-violet:hover   { border-color: rgba(167, 139, 250, 0.26); }
.accent-violet .summary-icon-wrap { color: #c4b5fd; }

.accent-teal::before { background: linear-gradient(90deg, transparent, #2dd4bf, #5eead4, transparent); }
.accent-teal::after  { background: radial-gradient(circle, rgba(45, 212, 191, 0.9), transparent 70%); }
.accent-teal:hover   { border-color: rgba(45, 212, 191, 0.26); }
.accent-teal .summary-icon-wrap { color: #5eead4; }

.accent-amber::before { background: linear-gradient(90deg, transparent, #fbbf24, #fcd34d, transparent); }
.accent-amber::after  { background: radial-gradient(circle, rgba(251, 191, 36, 0.88), transparent 70%); }
.accent-amber:hover   { border-color: rgba(251, 191, 36, 0.26); }
.accent-amber .summary-icon-wrap { color: #fcd34d; }

.accent-rose::before { background: linear-gradient(90deg, transparent, #f87171, #fb7185, transparent); }
.accent-rose::after  { background: radial-gradient(circle, rgba(248, 113, 113, 0.86), transparent 70%); }
.accent-rose:hover   { border-color: rgba(248, 113, 113, 0.26); }
.accent-rose .summary-icon-wrap { color: #fca5a5; }

.summary-card-top { display: flex; align-items: center; gap: 0.8rem; }

.summary-icon-wrap {
  width: 46px; height: 46px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.10);
  font-size: 0.96rem;
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-fast);
}

.summary-label   { color: var(--text-secondary); font-size: 0.91rem; font-weight: 700; }
.summary-card-value { margin-top: 1rem; font-size: clamp(2rem, 3vw, 2.5rem); line-height: 1; font-weight: 800; color: var(--text-primary); letter-spacing: -0.05em; }
.summary-card-subtext { margin-top: 0.65rem; max-width: 26ch; color: var(--text-muted); font-size: 0.87rem; line-height: 1.55; }

/* ──────────────────────────────────────────────────────────────
   § 11  SURFACE CARDS  (generic feature card base)
   ────────────────────────────────────────────────────────────── */
.surface-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-card);
  padding: 1.25rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: linear-gradient(160deg, rgba(6, 18, 12, 0.86), rgba(7, 16, 10, 0.72));
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.feature-card { min-height: 100%; }

.surface-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1.1rem; }

/* HUD-style kicker: animated dot + label */
.surface-kicker {
  margin: 0 0 0.22rem;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: #3cc87a;
  display: flex;
  align-items: center;
  gap: 0.42rem;
}

.surface-kicker::before {
  content: '';
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #3cc87a;
  box-shadow: 0 0 8px rgba(60, 200, 110, 0.85);
  flex-shrink: 0;
  animation: hud-pulse 2.2s ease-in-out infinite;
}

@keyframes hud-pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(60, 200, 110, 0.85); }
  50%       { opacity: 0.52; box-shadow: 0 0 4px rgba(60, 200, 110, 0.38); }
}

.surface-card-title { margin: 0; color: var(--text-primary); font-size: 1.12rem; font-weight: 800; letter-spacing: -0.02em; }

.surface-link {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0.36rem 0.78rem;
  border-radius: var(--radius-chip);
  background: rgba(255, 255, 255, 0.04);
  color: #7adfc8;
  border: 1px solid rgba(60, 200, 120, 0.16);
  text-decoration: none;
  font-size: 0.82rem;
  font-weight: 700;
  transition: transform var(--t-fast), border-color var(--t-fast), background var(--t-fast);
}

.surface-link:hover { transform: translateY(-1px); border-color: rgba(60, 200, 120, 0.32); background: rgba(60, 200, 120, 0.09); }

/* ──────────────────────────────────────────────────────────────
   § 12  ACTION CENTER  (cyberpunk terminal aesthetic)
   ────────────────────────────────────────────────────────────── */
/* ──────────────────────────────────────────────────────────────
   § 13  PROGRESS CARD  (orbital ring display)
   ────────────────────────────────────────────────────────────── */
.progress-card { border-color: rgba(167, 139, 250, 0.16); }

.progress-card::after {
  content: '';
  position: absolute;
  bottom: -20%; right: -10%;
  width: 38%; aspect-ratio: 1;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(103, 232, 249, 0.10), transparent 70%);
  pointer-events: none;
  filter: blur(16px);
}

.progress-layout { display: flex; gap: 1.1rem; align-items: center; flex-wrap: wrap; }

.progress-ring-shell { flex: 0 0 148px; display: flex; justify-content: center; position: relative; isolation: isolate; }

.progress-ring {
  position: relative;
  width: 130px; height: 130px;
  border-radius: 999px;
  padding: 10px;
  box-shadow: 0 24px 52px rgba(0, 3, 18, 0.40), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
  transition: transform var(--t-slow) var(--ease-out), box-shadow var(--t-base);
}

/* Radial halo — breathing */
.progress-ring::before {
  content: '';
  position: absolute;
  inset: -16px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(60, 200, 110, 0.16), rgba(167, 139, 250, 0.12) 52%, transparent 74%);
  z-index: -1;
  animation: halo-breath 6s ease-in-out infinite;
}

/* Orbiting arc */
.progress-ring::after {
  content: '';
  position: absolute;
  inset: -8px;
  border-radius: 999px;
  background: conic-gradient(
    from 0deg,
    transparent 0deg, transparent 30deg,
    rgba(60, 200, 110, 0.85) 46deg,
    rgba(45, 212, 170, 0.70) 80deg,
    transparent 118deg, transparent 360deg
  );
  -webkit-mask: radial-gradient(circle, transparent 58%, black 64%, black 73%, transparent 78%);
  mask: radial-gradient(circle, transparent 58%, black 64%, black 73%, transparent 78%);
  animation: orbit-spin 6s linear infinite;
  opacity: 0.82;
}

.progress-ring-inner {
  width: 100%; height: 100%;
  border-radius: 999px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(5, 16, 10, 0.97), rgba(5, 14, 9, 0.97));
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.progress-card:hover .progress-ring { transform: scale(1.06); box-shadow: 0 32px 64px rgba(0, 3, 18, 0.46), 0 0 38px rgba(96, 165, 250, 0.12); }

.progress-value { font-size: 1.85rem; font-weight: 800; color: var(--text-primary); letter-spacing: -0.04em; }
.progress-label { margin-top: 0.14rem; color: var(--text-muted); font-size: 0.78rem; font-weight: 700; }

.progress-details { flex: 1; min-width: 220px; }

.progress-detail-row {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.70rem 0.82rem;
  border-radius: 12px;
  color: var(--text-secondary);
  transition: transform var(--t-fast), background var(--t-fast);
}

.progress-detail-row:hover { transform: translateX(4px); background: rgba(255, 255, 255, 0.04); }
.progress-detail-row strong { color: var(--text-primary); font-weight: 800; }

.progress-bar-shell { margin-top: 0.9rem; height: 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.06); overflow: visible; }

.progress-bar-fill {
  position: relative;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #38bdf8 0%, #2dd4bf 36%, #818cf8 74%, #f472b6 100%);
  box-shadow: 0 0 16px rgba(96, 165, 250, 0.32);
}

/* Glowing end-dot */
.progress-bar-fill::after {
  content: '';
  position: absolute;
  right: -7px; top: 50%;
  width: 16px; height: 16px;
  border-radius: 50%;
  transform: translateY(-50%);
  background: radial-gradient(circle, white, rgba(255, 255, 255, 0.12));
  box-shadow: 0 0 12px rgba(103, 232, 249, 0.65), 0 0 4px rgba(255, 255, 255, 0.85);
}

@keyframes orbit-spin  { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes halo-breath { 0%, 100% { transform: scale(0.95); opacity: 0.70; } 50% { transform: scale(1.07); opacity: 1; } }

/* ──────────────────────────────────────────────────────────────
   § 14  EVENTS CARD  (calendar badge style)
   ────────────────────────────────────────────────────────────── */
.event-detail-card {
  display: flex;
  gap: 1rem;
  align-items: stretch;
  padding: 0.88rem;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.07);
}

.event-date-badge {
  flex: 0 0 82px;
  min-height: 96px;
  border-radius: 16px;
  padding: 0.82rem 0.72rem;
  background: linear-gradient(145deg, rgba(56, 189, 248, 0.24), rgba(45, 212, 191, 0.12));
  border: 1px solid rgba(56, 189, 248, 0.26);
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  box-shadow: 0 0 24px rgba(56, 189, 248, 0.14);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-fast);
}

.event-detail-card:hover .event-date-badge { transform: rotate(-4deg) translateY(-4px); box-shadow: 0 0 34px rgba(56, 189, 248, 0.24); }

.event-date-day  { color: #f0f8ff; font-size: 1.5rem; font-weight: 800; line-height: 1; }
.event-date-rest { margin-top: 0.34rem; color: rgba(186, 230, 255, 0.88); font-size: 0.80rem; line-height: 1.3; }

.event-content { flex: 1; min-width: 0; transition: transform var(--t-base); }
.event-detail-card:hover .event-content { transform: translateX(3px); }

.event-title { font-size: 1.08rem; font-weight: 800; color: var(--text-primary); }

.event-meta-row { display: flex; flex-wrap: wrap; gap: 0.88rem; margin-top: 0.62rem; color: var(--text-secondary); font-size: 0.90rem; }
.event-meta-row span { display: inline-flex; align-items: center; gap: 0.42rem; }
.location-row { margin-top: 0.42rem; }
.event-actions { margin-top: 0.82rem; }

.primary-chip {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 0.48rem 0.9rem;
  border-radius: var(--radius-chip);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.24), rgba(45, 212, 191, 0.16));
  color: #bfdbfe;
  text-decoration: none;
  font-size: 0.84rem;
  font-weight: 700;
  border: 1px solid rgba(96, 165, 250, 0.24);
  transition: transform var(--t-fast), background var(--t-fast), box-shadow var(--t-fast);
}

.primary-chip:hover {
  transform: translateY(-2px);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.34), rgba(45, 212, 191, 0.26));
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.22);
}

/* ──────────────────────────────────────────────────────────────
   § 15  LISTS  (announcements)
   ────────────────────────────────────────────────────────────── */
.list-stack { display: flex; flex-direction: column; gap: 0.70rem; }

.list-row { display: flex; align-items: flex-start; gap: 0.82rem; text-decoration: none; color: inherit; }

.premium-row {
  padding: 0.85rem 0.95rem;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  background: rgba(255, 255, 255, 0.03);
  transition: transform var(--t-base) var(--ease-out), border-color var(--t-fast), background var(--t-fast);
}

.premium-row:hover { transform: translateX(5px); border-color: rgba(251, 191, 36, 0.22); background: rgba(251, 191, 36, 0.05); }

.list-row-icon {
  width: 40px; height: 40px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 0.90rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: transform var(--t-fast), box-shadow var(--t-fast);
}

.announcement-icon { background: rgba(251, 191, 36, 0.12); color: #fcd34d; }

.premium-row:hover .announcement-icon { transform: scale(1.08) rotate(-8deg); box-shadow: 0 10px 22px rgba(251, 191, 36, 0.22); }

.list-row-content { min-width: 0; flex: 1; }
.list-row-title       { color: var(--text-primary); font-weight: 800; line-height: 1.45; }
.list-row-meta        { margin-top: 0.14rem; color: var(--text-muted); font-size: 0.84rem; }
.list-row-description { margin-top: 0.24rem; color: var(--text-secondary); font-size: 0.87rem; line-height: 1.55; }
.list-row-tail        { color: var(--text-muted); padding-top: 0.18rem; transition: transform var(--t-fast), color var(--t-fast); }
.premium-row:hover .list-row-tail { transform: translateX(3px); color: var(--text-secondary); }

/* ──────────────────────────────────────────────────────────────
   § 16  GROUPS GRID  (identity cards — distinct per card)
   ────────────────────────────────────────────────────────────── */
.groups-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.1rem; }

.group-card-link,
.resource-card-link { display: block; text-decoration: none; color: inherit; }

.group-card-surface {
  position: relative;
  overflow: hidden;
  height: 100%;
  padding: 1rem;
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  transition: transform var(--t-slow) var(--ease-out), box-shadow var(--t-base), border-color var(--t-fast);
}

.group-card-link:nth-child(1) .group-card-surface { background: linear-gradient(150deg, rgba(20, 100, 50, 0.28), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(60, 200, 120, 0.18); }
.group-card-link:nth-child(2) .group-card-surface { background: linear-gradient(150deg, rgba(91, 33, 182, 0.28), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(167, 139, 250, 0.18); }
.group-card-link:nth-child(3) .group-card-surface { background: linear-gradient(150deg, rgba(13, 148, 100, 0.28), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(45, 212, 170, 0.18); }
.group-card-link:nth-child(4) .group-card-surface { background: linear-gradient(150deg, rgba(234, 88, 12, 0.26), rgba(5, 15, 9, 0.84) 50%); border-color: rgba(251, 146, 60, 0.18); }

/* Bottom shine sweep */
.group-card-surface::after {
  content: '';
  position: absolute;
  inset: auto 16px 14px;
  height: 2px; border-radius: 999px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.72), transparent);
  transform: scaleX(0.26); transform-origin: center;
  opacity: 0;
  transition: opacity var(--t-fast), transform var(--t-base) var(--ease-out);
}

.group-card-link:hover .group-card-surface { transform: translateY(-10px) rotateX(2deg) rotateY(-2deg); box-shadow: 0 28px 60px rgba(0, 3, 18, 0.38); }
.group-card-link:hover .group-card-surface::after { opacity: 1; transform: scaleX(1); }

.group-card-top { display: flex; align-items: center; justify-content: space-between; gap: 0.72rem; }
.group-avatars  { display: flex; align-items: center; flex-shrink: 0; }

.group-avatar {
  width: 2.35rem; height: 2.35rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(7, 13, 28, 0.82);
  margin-left: -0.30rem;
  font-size: 0.74rem; font-weight: 800;
  box-shadow: 0 8px 20px rgba(0, 3, 18, 0.26);
  transition: transform var(--t-base) var(--ease-out);
}

.group-avatar:first-child { margin-left: 0; }

.group-card-link:nth-child(1) .primary-avatar { background: linear-gradient(135deg, #60a5fa, #22d3ee); color: #0c4a6e; }
.group-card-link:nth-child(2) .primary-avatar { background: linear-gradient(135deg, #a78bfa, #f472b6); color: #2e1065; }
.group-card-link:nth-child(3) .primary-avatar { background: linear-gradient(135deg, #34d399, #38bdf8); color: #064e3b; }
.group-card-link:nth-child(4) .primary-avatar { background: linear-gradient(135deg, #fb923c, #facc15); color: #431407; }

.secondary-avatar { background: linear-gradient(135deg, #0f766e, #14b8a6); color: #ccfbf1; }
.tertiary-avatar  { background: linear-gradient(135deg, #7c3aed, #a78bfa); color: #ede9fe; }

.group-card-link:hover .primary-avatar   { transform: translateX(-8px) translateY(-2px) scale(1.08); }
.group-card-link:hover .secondary-avatar { transform: translateX(2px) translateY(3px); }
.group-card-link:hover .tertiary-avatar  { transform: translateX(10px) translateY(-2px); }

.group-open-indicator {
  width: 32px; height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  color: #7ec8ff;
  border: 1px solid rgba(255, 255, 255, 0.10);
  transition: transform var(--t-fast);
}

.group-card-link:hover .group-open-indicator { transform: translateY(-2px) scale(1.08); }

.group-name { margin-top: 0.9rem; color: var(--text-primary); font-size: 0.98rem; font-weight: 800; }
.group-meta { margin-top: 0.26rem; color: var(--text-secondary); font-size: 0.86rem; line-height: 1.5; }

/* ──────────────────────────────────────────────────────────────
   § 17  RESOURCES GRID  (color-coded left accent bar)
   ────────────────────────────────────────────────────────────── */
.resource-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.88rem; }

.resource-card-surface {
  position: relative;
  overflow: hidden;
  height: 100%;
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  padding: 1rem;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-base), border-color var(--t-fast);
}

/* Left accent bar */
.resource-card-surface::before {
  content: '';
  position: absolute;
  left: 0; top: 12px; bottom: 12px;
  width: 4px; border-radius: 0 3px 3px 0;
  opacity: 0.72;
  transition: width var(--t-fast), opacity var(--t-fast);
}

.resource-card-link:nth-child(1) .resource-card-surface { background: linear-gradient(155deg, rgba(40, 140, 70, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(60, 200, 110, 0.16); }
.resource-card-link:nth-child(1) .resource-card-surface::before { background: #3cc87a; }
.resource-card-link:nth-child(2) .resource-card-surface { background: linear-gradient(155deg, rgba(168, 85, 247, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(167, 139, 250, 0.16); }
.resource-card-link:nth-child(2) .resource-card-surface::before { background: #a78bfa; }
.resource-card-link:nth-child(3) .resource-card-surface { background: linear-gradient(155deg, rgba(45, 212, 170, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(45, 212, 170, 0.16); }
.resource-card-link:nth-child(3) .resource-card-surface::before { background: #2dd4aa; }
.resource-card-link:nth-child(4) .resource-card-surface { background: linear-gradient(155deg, rgba(244, 114, 182, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(244, 114, 182, 0.16); }
.resource-card-link:nth-child(4) .resource-card-surface::before { background: #f472b6; }
.resource-card-link:nth-child(5) .resource-card-surface { background: linear-gradient(155deg, rgba(251, 191, 36, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(251, 191, 36, 0.16); }
.resource-card-link:nth-child(5) .resource-card-surface::before { background: #fbbf24; }
.resource-card-link:nth-child(6) .resource-card-surface { background: linear-gradient(155deg, rgba(16, 185, 100, 0.16), rgba(5, 15, 9, 0.80) 50%); border-color: rgba(52, 200, 140, 0.16); }
.resource-card-link:nth-child(6) .resource-card-surface::before { background: #34d399; }

.resource-card-link:hover .resource-card-surface { transform: translateY(-6px) rotateZ(-0.4deg); box-shadow: 0 24px 52px rgba(0, 3, 18, 0.34); }
.resource-card-link:hover .resource-card-surface::before { width: 7px; opacity: 1; }

.resource-icon {
  width: 44px; height: 44px;
  flex-shrink: 0; border-radius: 13px;
  display: inline-flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.07);
  color: #93c5fd;
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: transform var(--t-base) var(--ease-out), box-shadow var(--t-fast);
}

.resource-card-link:hover .resource-icon { transform: translateY(-3px) rotate(8deg); box-shadow: 0 14px 28px rgba(96, 165, 250, 0.22); }

.resource-content { min-width: 0; }
.resource-title { color: var(--text-primary); font-weight: 800; line-height: 1.45; }
.resource-meta  { margin-top: 0.22rem; color: var(--text-secondary); font-size: 0.84rem; line-height: 1.5; }

/* ──────────────────────────────────────────────────────────────
   § 18  TIMELINE  (sci-fi roadmap with connecting line)
   ────────────────────────────────────────────────────────────── */
/* ──────────────────────────────────────────────────────────────
   § 19  ALERT, LOADING, EMPTY STATE
   ────────────────────────────────────────────────────────────── */
.dashboard-alert {
  display: flex; align-items: center; gap: 0.65rem;
  padding: 0.9rem 1rem; margin-bottom: 1.25rem;
  border-radius: 16px;
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.20);
  color: #fcd34d;
  box-shadow: var(--shadow-sm);
  backdrop-filter: blur(16px);
}

.dashboard-loading {
  position: fixed; right: 1.35rem; bottom: 1.35rem; z-index: 20;
  display: inline-flex; align-items: center; gap: 0.65rem;
  padding: 0.72rem 1rem;
  border-radius: var(--radius-chip);
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(160deg, rgba(6, 18, 12, 0.92), rgba(7, 16, 10, 0.86));
  color: var(--text-primary);
  box-shadow: var(--shadow-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.loading-ring {
  width: 16px; height: 16px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #38bdf8;
  border-right-color: #a78bfa;
  border-bottom-color: #2dd4bf;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  min-height: 140px;
  border-radius: 18px;
  border: 1px dashed rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.02);
  display: flex; align-items: center; justify-content: center;
  gap: 0.62rem; flex-direction: column;
  color: var(--text-secondary);
  text-align: center; padding: 1.5rem;
}

.empty-state i { font-size: 1.4rem; color: var(--text-muted); }

/* ──────────────────────────────────────────────────────────────
   § 20  INTERACTIVE SURFACE  (legacy compat stub)
   ────────────────────────────────────────────────────────────── */
.interactive-surface { position: relative; isolation: isolate; }

/* ──────────────────────────────────────────────────────────────
   § 21  RESPONSIVE
   ────────────────────────────────────────────────────────────── */
@media (max-width: 1400px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .groups-grid  { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

.dashboard-page-shell.is-day-mode .dashboard-hero-message {
  color: rgba(74, 84, 100, 0.94);
}

.dashboard-page-shell.is-day-mode .dashboard-fx-canvas {
  opacity: 0.12;
}

.dashboard-page-shell.is-day-mode .orb-one {
  background: radial-gradient(circle, rgba(190, 154, 88, 0.24), rgba(190, 154, 88, 0.08) 52%, transparent 74%);
}

.dashboard-page-shell.is-day-mode .orb-two {
  background: radial-gradient(circle, rgba(92, 138, 128, 0.16), rgba(92, 138, 128, 0.06) 52%, transparent 74%);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip::before,
.dashboard-page-shell.is-day-mode .showcase-card::before {
  opacity: 0.42;
}

.dashboard-page-shell.is-day-mode .showcase-card::after {
  background: linear-gradient(160deg, rgba(255, 248, 238, 0.94), rgba(246, 236, 216, 0.88));
}

.dashboard-page-shell.is-day-mode .showcase-controls,
.dashboard-page-shell.is-day-mode .showcase-nav-btn,
.dashboard-page-shell.is-day-mode .theme-rail-trigger,
.dashboard-page-shell.is-day-mode .group-open-indicator,
.dashboard-page-shell.is-day-mode .premium-row,
.dashboard-page-shell.is-day-mode .progress-ring-inner {
  box-shadow: 0 10px 26px rgba(137, 109, 53, 0.10);
}

.dashboard-page-shell.is-day-mode .group-avatar {
  border-color: rgba(250, 245, 236, 0.92);
  box-shadow: 0 10px 24px rgba(137, 109, 53, 0.16);
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(1) { color: #8a5f1f; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(2) { color: #1f7f70; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(3) { color: #7a4fc1; }

.dashboard-page-shell.is-day-mode .showcase-kicker {
  color: #8a5f1f;
}

.dashboard-page-shell.is-day-mode .announcement-icon { color: #a56418; }

.dashboard-page-shell.is-day-mode .primary-chip {
  color: #755019;
  border-color: rgba(130, 100, 40, 0.18);
  background: linear-gradient(135deg, rgba(175, 122, 22, 0.12), rgba(63, 108, 198, 0.08));
}

.dashboard-page-shell.is-day-mode .primary-chip:hover {
  background: linear-gradient(135deg, rgba(175, 122, 22, 0.16), rgba(63, 108, 198, 0.12));
  box-shadow: 0 12px 28px rgba(137, 109, 53, 0.14);
}

/* ──────────────────────────────────────────────────────────────
   § 22  DAY MODE — COMPREHENSIVE INTERACTIVE & EFFECT OVERRIDES
   Replaces neon / near-invisible dark-mode values with
   yellow-green equivalents readable on the lime-cream background.
   ────────────────────────────────────────────────────────────── */

/* --- 22.1  Design tokens ------------------------------------ */
.dashboard-page-shell.is-day-mode {
  --text-primary:   #1a3818;
  --text-secondary: #3a5e2c;
  --text-muted:     #5e8040;
  --text-link:      #265c3c;

  --surface-base:     rgba(180, 212, 140, 0.88);
  --surface-elevated: rgba(194, 224, 156, 0.94);

  --border-default: rgba(80, 130, 40, 0.18);
  --border-strong:  rgba(60, 110, 28, 0.28);

  --accent-blue:   #2a6048;
  --accent-teal:   #1f8a6a;
  --accent-violet: #7c5cb0;
  --accent-amber:  #6a9820;
  --accent-rose:   #b05060;

  --shadow-lg: 0 24px 64px rgba(30, 70, 14, 0.24);
  --shadow-md: 0 14px 38px rgba(30, 70, 14, 0.18);
  --shadow-sm: 0 8px  22px rgba(30, 70, 14, 0.12);
}

/* Backdrop grid — soften on yellow-green */
.dashboard-page-shell.is-day-mode .dashboard-backdrop-grid {
  opacity: 0.05;
  background-image:
    linear-gradient(rgba(60, 120, 30, 0.30) 1px, transparent 1px),
    linear-gradient(90deg, rgba(60, 120, 30, 0.30) 1px, transparent 1px);
}

/* --- 22.2  Hero card --------------------------------------- */
.dashboard-page-shell.is-day-mode .dashboard-hero-card {
  background: linear-gradient(145deg, rgba(210, 234, 174, 0.94), rgba(198, 222, 158, 0.82));
  border-color: rgba(90, 148, 50, 0.22);
  box-shadow: 0 24px 64px rgba(30, 70, 14, 0.18), inset 0 1px 0 rgba(240, 255, 220, 0.70);
}

.dashboard-page-shell.is-day-mode .hero-eyebrow {
  color: #1e4010;
  border-color: rgba(60, 110, 20, 0.24);
  background: linear-gradient(135deg, rgba(100, 160, 40, 0.16), rgba(188, 216, 158, 0.60));
  box-shadow: inset 0 0 0 1px rgba(120, 180, 60, 0.12), 0 8px 20px rgba(50, 100, 20, 0.12);
}

.dashboard-page-shell.is-day-mode .hero-title {
  color: #0e2c08;
  text-shadow: 0 6px 24px rgba(30, 70, 14, 0.12), 0 0 40px rgba(80, 180, 40, 0.10);
}

/* Hero meta chips — yellow-green variants */
.dashboard-page-shell.is-day-mode .hero-meta-chip {
  border-color: rgba(90, 140, 40, 0.18);
  color: var(--text-primary);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip:hover {
  box-shadow: 0 18px 42px rgba(30, 70, 14, 0.18);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--neutral {
  background: linear-gradient(145deg, rgba(200, 228, 162, 0.86), rgba(186, 214, 146, 0.76));
  border-color: rgba(90, 140, 40, 0.20);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--neutral::after {
  background: radial-gradient(circle at top left, rgba(120, 180, 60, 0.12), transparent 42%),
              linear-gradient(145deg, rgba(100, 160, 50, 0.10), rgba(190, 220, 150, 0.06));
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--cyan {
  background: linear-gradient(135deg, rgba(30, 110, 70, 0.18), rgba(186, 214, 158, 0.72));
  border-color: rgba(40, 150, 100, 0.28);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--cyan::after {
  background: radial-gradient(circle at top left, rgba(40, 150, 100, 0.18), transparent 38%),
              linear-gradient(135deg, rgba(40, 150, 100, 0.08), transparent);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--violet {
  background: linear-gradient(135deg, rgba(90, 60, 160, 0.16), rgba(186, 214, 158, 0.72));
  border-color: rgba(130, 100, 200, 0.28);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip--violet::after {
  background: radial-gradient(circle at top left, rgba(140, 108, 210, 0.16), transparent 38%),
              linear-gradient(135deg, rgba(130, 100, 200, 0.08), transparent);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip-label {
  color: var(--text-secondary);
}

.dashboard-page-shell.is-day-mode .hero-meta-chip-value {
  color: var(--text-primary);
}

/* Status pills on yellow-green */
.dashboard-page-shell.is-day-mode .status-pill {
  background: linear-gradient(145deg, rgba(140, 196, 90, 0.14), rgba(120, 180, 70, 0.08));
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(1) {
  border-color: rgba(40, 110, 60, 0.26);
  color: #1a5c2a;
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(2) {
  border-color: rgba(30, 140, 100, 0.26);
  color: #10603e;
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(3) {
  border-color: rgba(130, 80, 190, 0.22);
  color: #5e3498;
}

/* --- 22.3  Showcase card ----------------------------------- */
.dashboard-page-shell.is-day-mode .showcase-card {
  background:
    linear-gradient(160deg, rgba(206, 232, 168, 0.92), rgba(194, 220, 154, 0.82)),
    radial-gradient(circle at top right,  rgba(40, 120, 60, 0.10), transparent 32%),
    radial-gradient(circle at bottom left, rgba(124, 92, 176, 0.08), transparent 28%);
  border-color: rgba(90, 148, 40, 0.20);
  box-shadow: 0 14px 38px rgba(30, 70, 14, 0.14), inset 0 1px 0 rgba(230, 255, 200, 0.50);
}

.dashboard-page-shell.is-day-mode .showcase-card:hover {
  border-color: rgba(60, 160, 80, 0.28);
  box-shadow: 0 28px 70px rgba(30, 70, 14, 0.22), 0 0 0 1px rgba(60, 160, 80, 0.06) inset;
}

/* Spinning border — forest green/sage/teal */
.dashboard-page-shell.is-day-mode .showcase-card::before {
  background: conic-gradient(
    from 0deg,
    transparent 0deg 40deg,
    rgba(50, 140, 50, 0.50) 78deg,
    transparent 126deg, transparent 185deg,
    rgba(100, 60, 180, 0.38) 230deg,
    transparent 286deg,
    rgba(30, 140, 100, 0.38) 326deg,
    transparent 360deg
  );
  opacity: 0.60;
}

.dashboard-page-shell.is-day-mode .showcase-controls {
  background: linear-gradient(145deg, rgba(186, 216, 148, 0.70), rgba(172, 204, 132, 0.56));
  border-color: rgba(90, 148, 40, 0.18);
  box-shadow: inset 0 1px 0 rgba(220, 255, 190, 0.40);
}

.dashboard-page-shell.is-day-mode .showcase-nav-btn {
  background: rgba(100, 160, 50, 0.12);
  color: var(--text-primary);
}

.dashboard-page-shell.is-day-mode .showcase-nav-btn:hover {
  background: rgba(100, 160, 50, 0.20);
  box-shadow: 0 8px 20px rgba(30, 70, 14, 0.14);
}

.dashboard-page-shell.is-day-mode .showcase-dot {
  background: rgba(80, 140, 40, 0.28);
}

.dashboard-page-shell.is-day-mode .showcase-dot.active {
  background: linear-gradient(90deg, #2a6840, #7c5cb0);
  box-shadow: 0 0 10px rgba(42, 104, 64, 0.40);
}

.dashboard-page-shell.is-day-mode .showcase-link-btn {
  border-color: rgba(40, 120, 60, 0.30);
  background: linear-gradient(145deg, rgba(40, 120, 60, 0.14), rgba(30, 100, 48, 0.08));
  color: #1a5028;
}

.dashboard-page-shell.is-day-mode .showcase-link-btn:hover {
  background: linear-gradient(145deg, rgba(40, 120, 60, 0.22), rgba(30, 100, 48, 0.14));
  border-color: rgba(60, 160, 80, 0.46);
  box-shadow: 0 12px 26px rgba(30, 100, 48, 0.18);
}

.dashboard-page-shell.is-day-mode .showcase-image {
  border-color: rgba(80, 148, 40, 0.14);
  box-shadow: 0 16px 38px rgba(30, 70, 14, 0.18);
}

.dashboard-page-shell.is-day-mode .showcase-image-overlay {
  background:
    linear-gradient(180deg, rgba(120, 180, 70, 0.06), rgba(100, 160, 50, 0.24)),
    radial-gradient(circle at top right, rgba(220, 255, 190, 0.18), transparent 28%);
}

/* --- 22.4  Summary cards ----------------------------------- */
.dashboard-page-shell.is-day-mode .summary-card {
  background: linear-gradient(160deg, rgba(202, 232, 162, 0.92), rgba(190, 220, 148, 0.80));
  border-color: rgba(90, 148, 40, 0.16);
  box-shadow: 0 14px 38px rgba(30, 70, 14, 0.14);
}

.dashboard-page-shell.is-day-mode .summary-icon-wrap {
  background: rgba(100, 160, 50, 0.14);
  border-color: rgba(80, 148, 40, 0.20);
}

/* Muted accents readable on yellow-green */
.dashboard-page-shell.is-day-mode .accent-blue::before  { background: linear-gradient(90deg, transparent, #2a6848, #3a8860, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-blue::after   { background: radial-gradient(circle, rgba(42, 104, 72, 0.64), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-blue:hover    { border-color: rgba(42, 104, 72, 0.28); }
.dashboard-page-shell.is-day-mode .accent-blue .summary-icon-wrap { color: #1e5438; }

.dashboard-page-shell.is-day-mode .accent-violet::before { background: linear-gradient(90deg, transparent, #7c5cb0, #9058c0, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-violet::after  { background: radial-gradient(circle, rgba(124, 92, 176, 0.62), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-violet:hover   { border-color: rgba(124, 92, 176, 0.28); }
.dashboard-page-shell.is-day-mode .accent-violet .summary-icon-wrap { color: #6a48a0; }

.dashboard-page-shell.is-day-mode .accent-teal::before { background: linear-gradient(90deg, transparent, #1f8a6a, #2aaa82, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-teal::after  { background: radial-gradient(circle, rgba(31, 138, 106, 0.66), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-teal:hover   { border-color: rgba(31, 138, 106, 0.28); }
.dashboard-page-shell.is-day-mode .accent-teal .summary-icon-wrap { color: #145c46; }

.dashboard-page-shell.is-day-mode .accent-amber::before { background: linear-gradient(90deg, transparent, #6a9820, #88ba28, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-amber::after  { background: radial-gradient(circle, rgba(106, 152, 32, 0.64), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-amber:hover   { border-color: rgba(106, 152, 32, 0.28); }
.dashboard-page-shell.is-day-mode .accent-amber .summary-icon-wrap { color: #4e7010; }

.dashboard-page-shell.is-day-mode .accent-rose::before { background: linear-gradient(90deg, transparent, #b05060, #c06070, transparent); opacity: 0.72; }
.dashboard-page-shell.is-day-mode .accent-rose::after  { background: radial-gradient(circle, rgba(176, 80, 96, 0.62), transparent 70%); }
.dashboard-page-shell.is-day-mode .accent-rose:hover   { border-color: rgba(176, 80, 96, 0.28); }
.dashboard-page-shell.is-day-mode .accent-rose .summary-icon-wrap { color: #923848; }

/* --- 22.5  Surface cards ----------------------------------- */
.dashboard-page-shell.is-day-mode .surface-card {
  background: linear-gradient(160deg, rgba(196, 228, 156, 0.90), rgba(184, 216, 142, 0.76));
  border-color: rgba(90, 148, 40, 0.16);
  box-shadow: 0 14px 38px rgba(30, 70, 14, 0.14);
}

/* HUD kicker dot — forest green */
.dashboard-page-shell.is-day-mode .surface-kicker {
  color: #1e5c28;
}

.dashboard-page-shell.is-day-mode .surface-kicker::before {
  background: #2a8040;
  box-shadow: 0 0 6px rgba(42, 128, 64, 0.60);
}

@keyframes hud-pulse-day {
  0%, 100% { opacity: 1;    box-shadow: 0 0 6px rgba(42, 128, 64, 0.60); }
  50%       { opacity: 0.54; box-shadow: 0 0 3px rgba(42, 128, 64, 0.28); }
}

.dashboard-page-shell.is-day-mode .surface-kicker::before {
  animation: hud-pulse-day 2.2s ease-in-out infinite;
}

.dashboard-page-shell.is-day-mode .surface-link {
  background: rgba(100, 160, 50, 0.10);
  color: #1e5c28;
  border-color: rgba(60, 140, 40, 0.20);
}

.dashboard-page-shell.is-day-mode .surface-link:hover {
  border-color: rgba(60, 140, 40, 0.36);
  background: rgba(60, 140, 40, 0.12);
}

/* --- 22.7  Progress card ----------------------------------- */
.dashboard-page-shell.is-day-mode .progress-card {
  border-color: rgba(124, 92, 176, 0.18);
}

.dashboard-page-shell.is-day-mode .progress-ring-inner {
  background: linear-gradient(180deg, rgba(202, 232, 162, 0.98), rgba(188, 218, 146, 0.98));
  border-color: rgba(90, 148, 40, 0.16);
}

.dashboard-page-shell.is-day-mode .progress-ring {
  box-shadow: 0 20px 46px rgba(30, 70, 14, 0.22), inset 0 0 0 1px rgba(120, 200, 60, 0.12);
}

.dashboard-page-shell.is-day-mode .progress-ring::before {
  background: radial-gradient(circle,
    rgba(80, 180, 50, 0.18),
    rgba(124, 92, 176, 0.12) 52%,
    transparent 74%
  );
}

/* Orbiting arc — forest green/sage */
.dashboard-page-shell.is-day-mode .progress-ring::after {
  background: conic-gradient(
    from 0deg,
    transparent 0deg, transparent 30deg,
    rgba(50, 160, 60, 0.80) 46deg,
    rgba(30, 140, 100, 0.62) 80deg,
    transparent 118deg, transparent 360deg
  );
}

.dashboard-page-shell.is-day-mode .progress-detail-row:hover {
  background: rgba(100, 160, 50, 0.10);
  border-radius: 10px;
}

/* --- 22.8  Events / date badge ----------------------------- */
.dashboard-page-shell.is-day-mode .event-date-badge {
  background: linear-gradient(145deg, rgba(30, 140, 90, 0.22), rgba(30, 150, 100, 0.12));
  border-color: rgba(30, 150, 100, 0.28);
  box-shadow: 0 0 20px rgba(30, 140, 90, 0.14);
}

.dashboard-page-shell.is-day-mode .event-date-day  { color: #0a4020; }
.dashboard-page-shell.is-day-mode .event-date-rest { color: rgba(16, 70, 40, 0.82); }

/* --- 22.9  Lists (announcements) --------------------------- */
.dashboard-page-shell.is-day-mode .premium-row {
  border-color: rgba(90, 148, 40, 0.14);
  background: rgba(140, 196, 90, 0.08);
}

.dashboard-page-shell.is-day-mode .premium-row:hover {
  border-color: rgba(100, 160, 40, 0.28);
  background: rgba(100, 160, 40, 0.10);
}

.dashboard-page-shell.is-day-mode .announcement-icon {
  background: rgba(100, 160, 40, 0.14);
  color: #4a7010;
  border-color: rgba(80, 140, 30, 0.18);
}

.dashboard-page-shell.is-day-mode .premium-row:hover .announcement-icon {
  box-shadow: 0 8px 18px rgba(100, 160, 40, 0.22);
}

/* --- 22.10  Groups grid ------------------------------------ */
.dashboard-page-shell.is-day-mode .group-card-link:nth-child(1) .group-card-surface {
  background: linear-gradient(150deg, rgba(40, 130, 60, 0.22), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(40, 130, 60, 0.22);
}

.dashboard-page-shell.is-day-mode .group-card-link:nth-child(2) .group-card-surface {
  background: linear-gradient(150deg, rgba(124, 92, 176, 0.22), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(124, 92, 176, 0.20);
}

.dashboard-page-shell.is-day-mode .group-card-link:nth-child(3) .group-card-surface {
  background: linear-gradient(150deg, rgba(30, 140, 100, 0.22), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(30, 140, 100, 0.20);
}

.dashboard-page-shell.is-day-mode .group-card-link:nth-child(4) .group-card-surface {
  background: linear-gradient(150deg, rgba(184, 90, 20, 0.18), rgba(194, 224, 158, 0.88) 50%);
  border-color: rgba(184, 90, 20, 0.18);
}

.dashboard-page-shell.is-day-mode .group-card-link:hover .group-card-surface {
  box-shadow: 0 24px 52px rgba(30, 70, 14, 0.22);
}

.dashboard-page-shell.is-day-mode .group-card-surface::after {
  background: linear-gradient(90deg, transparent, rgba(220, 255, 200, 0.82), transparent);
}

.dashboard-page-shell.is-day-mode .group-avatar {
  border-color: rgba(210, 240, 180, 0.92);
}

.dashboard-page-shell.is-day-mode .group-open-indicator {
  background: rgba(100, 160, 50, 0.14);
  color: #1e5828;
  border-color: rgba(80, 148, 40, 0.18);
}

/* --- 22.11  Resources grid --------------------------------- */
.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(1) .resource-card-surface {
  background: linear-gradient(155deg, rgba(40, 130, 60, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(40, 130, 60, 0.18);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(2) .resource-card-surface {
  background: linear-gradient(155deg, rgba(124, 92, 176, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(124, 92, 176, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(3) .resource-card-surface {
  background: linear-gradient(155deg, rgba(30, 140, 100, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(30, 140, 100, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(4) .resource-card-surface {
  background: linear-gradient(155deg, rgba(176, 80, 96, 0.14), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(176, 80, 96, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(5) .resource-card-surface {
  background: linear-gradient(155deg, rgba(106, 152, 32, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(106, 152, 32, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(6) .resource-card-surface {
  background: linear-gradient(155deg, rgba(30, 150, 80, 0.16), rgba(188, 220, 152, 0.84) 50%);
  border-color: rgba(30, 150, 80, 0.16);
}

.dashboard-page-shell.is-day-mode .resource-card-link:hover .resource-card-surface {
  box-shadow: 0 20px 46px rgba(30, 70, 14, 0.22);
}

.dashboard-page-shell.is-day-mode .resource-icon {
  background: rgba(100, 160, 50, 0.14);
  color: #1e5828;
  border-color: rgba(80, 148, 40, 0.18);
}

.dashboard-page-shell.is-day-mode .resource-card-link:hover .resource-icon {
  box-shadow: 0 12px 24px rgba(40, 130, 60, 0.18);
}

/* --- 22.13  Alert / loading / empty state ------------------ */
.dashboard-page-shell.is-day-mode .dashboard-alert {
  background: rgba(100, 160, 40, 0.10);
  border-color: rgba(100, 160, 40, 0.28);
  color: #3a6010;
}

.dashboard-page-shell.is-day-mode .dashboard-loading {
  background: linear-gradient(160deg, rgba(200, 232, 160, 0.94), rgba(184, 218, 144, 0.90));
  border-color: rgba(80, 148, 40, 0.22);
  color: var(--text-primary);
  box-shadow: 0 20px 50px rgba(30, 70, 14, 0.18);
}

.dashboard-page-shell.is-day-mode .loading-ring {
  border-top-color:    #1f8a6a;
  border-right-color:  #7c5cb0;
  border-bottom-color: #6a9820;
}

.dashboard-page-shell.is-day-mode .empty-state {
  border-color: rgba(80, 148, 40, 0.22);
  background: rgba(120, 180, 70, 0.06);
  color: var(--text-secondary);
}

.dashboard-page-shell.is-day-mode .empty-state i {
  color: var(--text-muted);
}

/* Hero copy section overlay — yellow-green */
.dashboard-page-shell.is-day-mode .dashboard-hero-copy {
  background: linear-gradient(155deg, rgba(210, 238, 172, 0.90), rgba(196, 226, 156, 0.78));
  border-color: rgba(90, 148, 40, 0.18);
  box-shadow: inset 0 1px 0 rgba(220, 255, 190, 0.60);
}

.dashboard-page-shell.is-day-mode .dashboard-subtext {
  color: #2a5018;
}

.dashboard-page-shell.is-night-mode .showcase-card::after {
  background: linear-gradient(160deg, rgba(6, 18, 11, 0.96), rgba(7, 16, 10, 0.90));
}

.dashboard-page-shell.is-night-mode .theme-rail-trigger:hover,
.dashboard-page-shell.is-night-mode .showcase-nav-btn:hover,
.dashboard-page-shell.is-night-mode .showcase-link-btn:hover,
.dashboard-page-shell.is-night-mode .primary-chip:hover {
  box-shadow: 0 12px 28px rgba(60, 200, 120, 0.16);
}

.dashboard-page-shell.is-night-mode .status-pill:nth-child(1) { color: #8fffcc; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(2) { color: #41d9c6; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(3) { color: #ff8cab; }

@media (max-width: 1180px) {
  .dashboard-hero-main { grid-template-columns: 1fr; padding-top: 3rem; }
  .dashboard-hero-copy { padding: 1.2rem 1.15rem 1.22rem; }
  .showcase-card { min-height: 0; }
  .two-col-layout { grid-template-columns: 1fr; }
}

@media (max-width: 880px) {
  .dashboard-page-shell { padding: 1rem 0.8rem 2rem; }
  .summary-grid, .groups-grid, .resource-grid { grid-template-columns: 1fr; }
  .event-detail-card { flex-direction: column; }
  .event-date-badge { width: 100%; min-height: 72px; flex-direction: row; justify-content: flex-start; align-items: center; gap: 0.72rem; }
  .dashboard-theme-rail { position: static; flex-direction: column; align-items: stretch; margin-bottom: 1rem; }
  .theme-rail-trigger { width: 100%; justify-content: center; }
  .dashboard-hero-main { padding-top: 0; }
  .dashboard-hero-copy,
  .dashboard-hero-aside { display: block; }
  .showcase-footer { flex-direction: column; align-items: stretch; }
  .showcase-image { aspect-ratio: 16 / 9; }
}

@media (max-width: 560px) {
  .dashboard-hero-card, .surface-card, .summary-card { border-radius: 20px; }
  .hero-title { font-size: 1.75rem; }
  .dashboard-subtext, .dashboard-hero-message { font-size: 0.90rem; }
  .summary-card-value { font-size: 1.9rem; }
  .showcase-title { font-size: 1rem; }
}

/* ──────────────────────────────────────────────────────────────
   § 22  TOUCH & REDUCED-MOTION
   ────────────────────────────────────────────────────────────── */
@media (max-width: 1120px) {
  .group-card-link:hover .group-card-surface,
  .resource-card-link:hover .resource-card-surface,
  .summary-card:hover,
  .hero-meta-chip:hover,
  .event-detail-card:hover .event-date-badge,
  .event-detail-card:hover .event-content,
  .progress-card:hover .progress-ring { transform: none; }
}

@media (prefers-reduced-motion: reduce) {
  .orb-one, .orb-two,
  .progress-ring::before, .progress-ring::after,
  .surface-kicker::before { animation: none !important; }

  .group-card-link:hover .group-card-surface,
  .resource-card-link:hover .resource-card-surface,
  .summary-card:hover,
  .hero-meta-chip:hover,
  .event-detail-card:hover .event-date-badge,
  .event-detail-card:hover .event-content,
  .progress-card:hover .progress-ring,
  .showcase-card:hover { transform: none !important; }
}


/* ──────────────────────────────────────────────────────────────
   § 23  HERO ENRICHMENT & ADAPTIVE OVERRIDES
   ────────────────────────────────────────────────────────────── */
.dashboard-page-shell {
  color: var(--text-primary);
}

.dashboard-page-shell::before {
  background: var(--dashboard-shell-backdrop, linear-gradient(135deg, #060c1a, #0a1224));
}

.dashboard-hero-card {
  background: linear-gradient(145deg, var(--hero-overlay-a), var(--hero-overlay-b));
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg), inset 0 1px 0 rgba(255, 255, 255, 0.07);
}

.surface-card,
.summary-card,
.showcase-card,
.dashboard-loading,
.dashboard-alert {
  box-shadow: var(--shadow-md);
}

.hero-title,
.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.summary-card-value,
.event-title,
.progress-value,
.hero-meta-chip-value {
  color: var(--text-primary);
}

.dashboard-subtext,
.dashboard-hero-message,
.showcase-summary,
.summary-card-subtext,
.progress-detail-row span,
.progress-label,
.progress-caption,
.resource-meta,
.group-meta,
.list-row-meta,
.list-row-description,
.surface-link,
.theme-rail-trigger,
.showcase-mini-label,
.event-meta-row,
.empty-state,
.dashboard-alert,
.dashboard-loading,
.hero-meta-chip-label,
.summary-label,
.status-pill,
.hero-eyebrow {
  color: var(--text-secondary);
}

.hero-eyebrow,
.hero-meta-chip,
.status-pill,
.summary-card,
.surface-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.theme-rail-trigger,
.dashboard-loading {
  border-color: var(--border-default);
}

.surface-card,
.summary-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.hero-meta-chip,
.status-pill,
.theme-rail-trigger,
.hero-eyebrow {
  background: linear-gradient(165deg, color-mix(in srgb, var(--surface-elevated) 88%, transparent), color-mix(in srgb, var(--surface-base) 94%, transparent));
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

.hero-meta-chip:hover,
.status-pill:hover,
.summary-card:hover,
.surface-card:hover,
.group-card-link:hover .group-card-surface,
.resource-card-link:hover .resource-card-surface,
.list-row:hover,
.showcase-card:hover {
  transform: translateY(-4px);
  border-color: var(--border-strong);
}

.progress-ring-shell {
  flex: 0 0 220px;
  min-height: 220px;
  display: grid;
  place-items: center;
  position: relative;
  isolation: isolate;
}

.progress-ring-aura,
.progress-ring-track,
.progress-ring-orbit,
.progress-ring-marker,
.progress-ring-spark {
  position: absolute;
  border-radius: 999px;
  pointer-events: none;
}

.progress-ring-aura {
  width: 198px;
  height: 198px;
  background: radial-gradient(circle, color-mix(in srgb, var(--accent-blue) 22%, transparent), transparent 66%);
  filter: blur(22px);
  opacity: 0.95;
}

.progress-ring-track {
  width: 192px;
  height: 192px;
  border: 1px dashed color-mix(in srgb, var(--text-link) 28%, transparent);
  opacity: 0.42;
}

.progress-ring-orbit {
  animation: orbitFloat 10s linear infinite;
}

.progress-ring-orbit--outer {
  width: 210px;
  height: 210px;
  border: 1px solid color-mix(in srgb, var(--accent-teal) 18%, transparent);
}

.progress-ring-orbit--inner {
  width: 160px;
  height: 160px;
  border: 1px solid color-mix(in srgb, var(--accent-violet) 16%, transparent);
  animation-direction: reverse;
  animation-duration: 12s;
}

.progress-ring-marker {
  left: calc(50% - 7px);
  top: calc(50% - 7px);
  width: 14px;
  height: 14px;
  background: linear-gradient(135deg, var(--accent-amber), var(--accent-violet));
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--surface-elevated) 74%, transparent), 0 0 18px color-mix(in srgb, var(--accent-blue) 40%, transparent);
}

.progress-ring-spark {
  width: 8px;
  height: 8px;
  background: var(--text-link);
  opacity: 0.64;
  filter: blur(1px);
  animation: sparkleOrbit 7s ease-in-out infinite;
}

.progress-ring-spark--one { top: 32px; left: 42px; }
.progress-ring-spark--two { right: 34px; bottom: 42px; animation-delay: -2.6s; }

.progress-ring {
  width: 172px;
  height: 172px;
  border-radius: 50%;
  padding: 13px;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-blue) 18%, transparent), 0 18px 42px rgba(0, 4, 20, 0.24);
}

.progress-ring-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: linear-gradient(160deg, color-mix(in srgb, var(--surface-elevated) 98%, transparent), color-mix(in srgb, var(--surface-base) 98%, transparent));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.progress-value {
  font-size: 2rem;
  font-weight: 800;
}

.progress-label {
  margin-top: 0.14rem;
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}

.progress-caption {
  margin-top: 0.35rem;
  font-size: 0.82rem;
  color: var(--text-link);
  font-weight: 700;
}

@keyframes orbitFloat {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes sparkleOrbit {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.44; }
  50% { transform: translate3d(6px, -8px, 0) scale(1.5); opacity: 0.92; }
}

.summary-card:nth-child(1) { border-radius: 28px 18px 24px 18px; }
.summary-card:nth-child(2) { border-radius: 18px 30px 18px 24px; }
.summary-card:nth-child(3) { border-radius: 24px 18px 30px 18px; }
.summary-card:nth-child(4) { border-radius: 18px 24px 18px 30px; }
.progress-card { border-radius: 22px 34px 22px 34px; }
.event-detail-card { border-radius: 26px 22px 30px 22px; }
.list-row { border-radius: 18px 14px 18px 14px; }
.group-card-surface { border-radius: 26px 20px 32px 18px; }
.resource-card-surface { border-radius: 20px 28px 18px 28px; }

.hero-meta-chip--neutral { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text-primary) 8%, transparent); }
.hero-meta-chip--cyan { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-teal) 18%, transparent); }
.hero-meta-chip--violet { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-violet) 18%, transparent); }

@media (max-width: 1180px) {
  .progress-ring-shell {
    flex: 0 0 auto;
    margin-inline: auto;
  }
}

@media (max-width: 680px) {
  .hero-meta-row,
  .hero-highlight-wrap {
    gap: 0.55rem;
  }

  .progress-ring-shell {
    min-height: 192px;
  }
}



/* ================================================================
   Typography and text-color refinement override
   ================================================================ */
.dashboard-page-shell {
  --font-display: "Aptos Display", "Segoe UI Variable Display", "Inter", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
  --font-body: "Aptos", "Segoe UI Variable Text", "Inter", "SF Pro Text", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  --font-label: "JetBrains Mono", "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
  --font-number: "Bahnschrift", "Inter", "Segoe UI", sans-serif;
  font-family: var(--font-body);
}

.dashboard-page-shell.is-night-mode {
  --text-primary: #f2fff7;
  --text-secondary: #b8d8c8;
  --text-muted: #84a997;
  --text-link: #8ee7c0;
  --text-hero-accent: #b6fff1;
  --text-card-accent: #f1ce82;
}

.dashboard-page-shell.is-day-mode {
  --text-primary: #18311e;
  --text-secondary: #496652;
  --text-muted: #708b78;
  --text-link: #305f48;
  --text-hero-accent: #214533;
  --text-card-accent: #7e6233;
}

.dashboard-page-shell,
.dashboard-page-shell * {
  font-variant-ligatures: common-ligatures;
}

.hero-title,
.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.summary-card-value,
.event-title,
.progress-value,
.hero-meta-chip-value,
.list-row-title {
  font-family: var(--font-display);
  letter-spacing: -0.03em;
}

.hero-title {
  color: var(--text-primary);
  font-size: clamp(2rem, 3.4vw, 2.95rem);
  font-weight: 820;
}

.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.event-title,
.list-row-title {
  color: var(--text-primary);
  font-weight: 780;
}

.summary-card-value,
.progress-value,
.event-date-day {
  font-family: var(--font-number);
  color: var(--text-primary);
  letter-spacing: -0.05em;
}

.surface-kicker,
.hero-eyebrow,
.showcase-kicker,
.summary-label,
.hero-meta-chip-label,
.progress-label,
.progress-caption,
.status-pill,
.showcase-mini-label,
.list-row-meta,
.event-date-rest,
.theme-rail-trigger {
  font-family: var(--font-label);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.dashboard-subtext {
  color: var(--text-card-accent);
  font-size: 0.97rem;
  font-weight: 620;
  line-height: 1.65;
}

.dashboard-hero-message,
.showcase-summary,
.summary-card-subtext,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row,
.empty-state,
.dashboard-alert,
.dashboard-loading {
  color: var(--text-secondary);
  font-family: var(--font-body);
  line-height: 1.7;
}

.hero-eyebrow {
  color: var(--text-hero-accent);
}

.surface-kicker,
.showcase-kicker {
  color: var(--accent-blue);
}

.hero-meta-chip,
.status-pill,
.summary-card,
.surface-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.theme-rail-trigger,
.event-detail-card,
.dashboard-alert,
.dashboard-loading {
  border-color: var(--border-default);
  background: linear-gradient(165deg, color-mix(in srgb, var(--surface-elevated) 92%, transparent), color-mix(in srgb, var(--surface-base) 96%, transparent));
}

.dashboard-hero-card {
  background: linear-gradient(145deg, var(--hero-overlay-a), var(--hero-overlay-b));
  border-color: var(--border-strong);
}

.dashboard-page-shell.is-day-mode .dashboard-hero-copy {
  background: linear-gradient(155deg, rgba(243, 250, 236, 0.94), rgba(232, 243, 223, 0.90));
}

.dashboard-page-shell.is-night-mode .dashboard-hero-copy {
  background: linear-gradient(155deg, rgba(13, 30, 20, 0.94), rgba(9, 23, 16, 0.88));
}

.theme-rail-trigger,
.showcase-nav-btn,
.showcase-link-btn,
.primary-chip,
.surface-link {
  color: var(--text-link);
  font-family: var(--font-display);
  font-weight: 720;
}

.showcase-link-btn,
.primary-chip,
.theme-rail-trigger {
  border-color: color-mix(in srgb, var(--accent-blue) 18%, var(--border-default));
}

.list-row-meta,
.progress-label,
.progress-caption,
.event-date-rest,
.summary-label,
.showcase-mini-label {
  color: var(--text-muted);
}

.progress-detail-row strong,
.hero-meta-chip-value {
  color: var(--text-primary);
}

.progress-detail-row span,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row {
  color: var(--text-secondary);
}

.showcase-dot.active {
  background: var(--accent-teal);
}

.dashboard-page-shell.is-night-mode .status-pill:nth-child(1) { color: #9df6cf; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(2) { color: #7db8ff; }
.dashboard-page-shell.is-night-mode .status-pill:nth-child(3) { color: #f3c977; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(1) { color: #3c6e54; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(2) { color: #587fbc; }
.dashboard-page-shell.is-day-mode .status-pill:nth-child(3) { color: #9f7240; }

.dashboard-page-shell.is-day-mode .event-date-badge {
  background: rgba(93, 131, 188, 0.08);
}

.dashboard-page-shell.is-night-mode .event-date-badge {
  background: rgba(125, 184, 255, 0.10);
}

.dashboard-page-shell.is-day-mode .summary-card,
.dashboard-page-shell.is-day-mode .surface-card,
.dashboard-page-shell.is-day-mode .showcase-card,
.dashboard-page-shell.is-day-mode .group-card-surface,
.dashboard-page-shell.is-day-mode .resource-card-surface,
.dashboard-page-shell.is-day-mode .list-row {
  box-shadow: 0 16px 36px rgba(18, 31, 21, 0.08);
}

.dashboard-page-shell.is-night-mode .summary-card,
.dashboard-page-shell.is-night-mode .surface-card,
.dashboard-page-shell.is-night-mode .showcase-card,
.dashboard-page-shell.is-night-mode .group-card-surface,
.dashboard-page-shell.is-night-mode .resource-card-surface,
.dashboard-page-shell.is-night-mode .list-row {
  box-shadow: 0 18px 42px rgba(0, 8, 3, 0.26);
}

/* Clean white/grey dashboard theme, aligned with Events and Resources pages. */
.dashboard-page-shell,
.dashboard-page-shell.is-day-mode,
.dashboard-page-shell.is-night-mode {
  --text-primary: var(--charcoal);
  --text-secondary: #6c757d;
  --text-muted: #8a949e;
  --text-link: var(--dark-green);
  --text-hero-accent: var(--dark-green);
  --text-card-accent: #6c757d;
  --surface-base: var(--white);
  --surface-elevated: var(--white);
  --surface-soft: #f8f9fa;
  --border-default: var(--border-light);
  --border-strong: #cfd6dc;
  --accent-blue: #39687b;
  --accent-teal: #5ea99e;
  --accent-violet: #6f63a8;
  --accent-amber: #b88a2d;
  --accent-rose: #b95670;
  --shadow-lg: 0 4px 12px var(--shadow);
  --shadow-md: 0 2px 4px var(--shadow);
  --shadow-sm: 0 1px 2px var(--shadow);
  --hero-overlay-a: var(--white);
  --hero-overlay-b: var(--white);
  --dashboard-shell-backdrop: var(--bg-light);
  --page-glow-one: transparent;
  --page-glow-two: transparent;
  --page-glow-three: transparent;
  color: var(--charcoal);
  background: var(--bg-light);
}

.dashboard-page-shell::before {
  background: var(--bg-light) !important;
}

.dashboard-fx-canvas,
.dashboard-backdrop-orb,
.dashboard-backdrop-grid {
  display: none !important;
}

.dashboard-page-inner {
  position: relative;
  z-index: 1;
}

.dashboard-hero-card,
.surface-card,
.summary-card,
.showcase-card,
.group-card-surface,
.resource-card-surface,
.list-row,
.hero-meta-chip,
.status-pill,
.event-detail-card,
.theme-rail-trigger,
.dashboard-alert,
.dashboard-loading {
  background: var(--white) !important;
  border: 1px solid var(--border-light) !important;
  border-radius: 8px !important;
  box-shadow: 0 2px 4px var(--shadow) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.dashboard-hero-card,
.surface-card,
.summary-card {
  overflow: hidden;
}

.dashboard-hero-copy,
.dashboard-page-shell.is-day-mode .dashboard-hero-copy,
.dashboard-page-shell.is-night-mode .dashboard-hero-copy {
  background: var(--white) !important;
  border: 1px solid var(--border-light) !important;
  border-radius: 8px !important;
  box-shadow: none !important;
}

.dashboard-hero-card:hover,
.surface-card:hover,
.summary-card:hover,
.showcase-card:hover,
.group-card-link:hover .group-card-surface,
.resource-card-link:hover .resource-card-surface,
.list-row:hover,
.hero-meta-chip:hover,
.status-pill:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 4px 12px var(--shadow) !important;
  border-color: var(--border-light) !important;
}

.dashboard-hero-card {
  padding: 1.5rem;
}

.dashboard-hero-shell,
.dashboard-hero-main {
  background: transparent !important;
  box-shadow: none !important;
}

.dashboard-hero-main {
  padding-top: 3rem;
}

.dashboard-hero-aside {
  align-items: stretch !important;
  border-radius: 8px !important;
  overflow: hidden !important;
}

.dashboard-hero-aside > .showcase-card {
  flex: 1 1 auto !important;
  width: 100% !important;
  height: 100% !important;
  min-height: 100% !important;
  margin: 0 !important;
}

.dashboard-hero-card::before,
.dashboard-hero-card::after,
.dashboard-hero-copy::before,
.showcase-card::before,
.showcase-card::after,
.hero-meta-chip::before,
.hero-meta-chip::after,
.status-pill::before,
.status-pill::after {
  display: none !important;
  content: none !important;
  background: none !important;
}

.hero-title,
.surface-card-title,
.group-name,
.resource-title,
.showcase-title,
.summary-card-value,
.event-title,
.progress-value,
.hero-meta-chip-value,
.list-row-title {
  color: var(--charcoal) !important;
  letter-spacing: 0 !important;
}

.dashboard-subtext,
.dashboard-hero-message,
.showcase-summary,
.summary-card-subtext,
.list-row-description,
.resource-meta,
.group-meta,
.event-meta-row,
.empty-state,
.hero-meta-chip-label,
.summary-label,
.status-pill,
.showcase-mini-label,
.list-row-meta,
.progress-detail-row span,
.progress-label,
.progress-caption {
  color: #6c757d !important;
}

.surface-kicker,
.hero-eyebrow,
.showcase-kicker,
.surface-link,
.theme-rail-trigger,
.showcase-link-btn,
.primary-chip {
  color: var(--dark-green) !important;
}

.summary-icon-wrap,
.list-row-icon,
.resource-icon,
.event-date-badge {
  background: #f8f9fa !important;
  border: 1px solid var(--border-light) !important;
  color: var(--dark-green) !important;
  box-shadow: none !important;
}

.primary-avatar,
.secondary-avatar,
.tertiary-avatar {
  background: var(--eucalypt) !important;
  color: var(--white) !important;
  border-color: var(--white) !important;
}

.progress-ring-aura,
.progress-ring-orbit,
.progress-ring-marker,
.progress-ring-spark {
  display: none !important;
}

.progress-ring-track {
  border-color: var(--border-light) !important;
}

.progress-ring {
  box-shadow: inset 0 0 0 1px var(--border-light), 0 2px 4px var(--shadow) !important;
}

.progress-ring-inner {
  background: var(--white) !important;
}

.progress-bar-shell {
  background: #eef1f3 !important;
}

.progress-bar-fill {
  background: var(--dark-green) !important;
}

.showcase-image-overlay {
  background: transparent !important;
}

.showcase-dot.active {
  background: var(--dark-green) !important;
}

.dashboard-page-shell.is-day-mode .resource-card-link:nth-child(n) .resource-card-surface,
.dashboard-page-shell.is-day-mode .group-card-link:nth-child(n) .group-card-surface,
.dashboard-page-shell.is-night-mode .resource-card-link:nth-child(n) .resource-card-surface,
.dashboard-page-shell.is-night-mode .group-card-link:nth-child(n) .group-card-surface {
  background: var(--white) !important;
  border-color: var(--border-light) !important;
}

.dashboard-page-shell.is-day-mode .status-pill:nth-child(n),
.dashboard-page-shell.is-night-mode .status-pill:nth-child(n) {
  color: #6c757d !important;
}

@media (max-width: 880px) {
  .dashboard-hero-main {
    padding-top: 0;
  }
}

>>>>>>> Stashed changes
</style>
