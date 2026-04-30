<template>
  <!--
  --------------------------------------------------------------------------------------------------------------
   * @file LoginPage.vue
   *
   * @description LoginPage.vue is the unified entry page for the BIOTech Futures mentoring platform.
   It combines role-guided access selection, passwordless email-to-OTP authentication, multilingual support,
   and branded platform presentation in one structured login experience.
   *
   * @author Shiqi Fang
   * @author Jiachen Ding
   * @author Qin Chen
   * @version 1.4.0
   *
   * Project: Group Based 5703 Capstone Project
   * Group: CS17-1
   * Team: CS17-1 Frontend Team
   *
   * Component Type: Frontend Page Component
   * File Role: Unified role-guided login entry page
   *
   * Purpose: Provide a structured and user-friendly entry point for students, mentors, supervisors,
   and administrators to sign in with email OTP while understanding the platform context before entering the system.
   *
   * Scope: Covers the left hero showcase, role selection and preview, language switching, email submission,
   OTP verification, resend flow, and post-login navigation.
   *
   * Responsibilities:
   * - Display platform branding, role-guided access selection, and overview information
   * - Support multilingual login experience with LTR and RTL layout handling
   * - Handle the full passwordless email-to-OTP authentication flow
   * - Provide reusable role-aware login copy for different access identities
   * - Keep authentication feedback, loading state, and OTP interaction consistent
   *
   * Dependencies:
   * - Vue 3 Composition API
   * - Vue Router
   * - Pinia auth store
   * - Login language data
   * - Login background data
   * - CSRF header helper
   * - String and storage utilities
   *
   * Revision Summary:
   * - Major revisions: 5
   * - Minor revisions: 5
   *
   * Last Modified: 2026-04-10
   * Modified By: CS17-1 Frontend Team
   *
   -----------------------------------------------------------------------------------------------------------------------------
   -->



  <!-- Page shell and two-column layout. -->
  <div
    ref="loginShellRef"
    class="login-shell"
    :dir="currentDir"
    :class="{
        'pointer-inside': isShellPointerInside
      }"
    @pointermove="handleShellPointerMove"
    @pointerleave="handleShellPointerLeave"
  >
    <div class="shell-aurora" aria-hidden="true">
      <span class="shell-aurora-orb shell-aurora-orb--one"></span>
      <span class="shell-aurora-orb shell-aurora-orb--two"></span>
      <span class="shell-aurora-orb shell-aurora-orb--three"></span>
      <span class="shell-mesh"></span>
    </div>
    <!-- Left hero pane: background stage, role selection, and platform overview. -->
    <section class="hero-pane">
      <!-- Background stage with slideshow and emerald mode. -->
      <div class="hero-stage" aria-hidden="true">
        <!-- Slideshow scene. -->
        <div class="hero-scene hero-scene--slideshow" :class="{ active: activeLeftBackground === 'original' }">
          <img
            v-for="(image, index) in backgroundImages"
            :key="`${image}-${index}`"
            class="hero-slide-image"
            :src="image"
            alt=""
            :style="{
              animationDelay: `${index * slideDuration}s`
            }"
          />
        </div>

        <!-- Emerald visual mode scene. -->
        <div class="hero-scene hero-scene--emerald" :class="{ active: activeLeftBackground === 'green' }">
          <div class="hero-green-image" :style="{ backgroundImage: `url(${backgroundImages2})` }"></div>
        </div>

        <!-- Readability overlay and subtle texture. -->
        <div class="hero-overlay"></div>
        <div class="hero-noise"></div>
      </div>

      <!-- Foreground hero content. -->
      <div class="hero-content">
        <!-- Brand block. -->
        <div class="hero-brand-row">
          <div class="brand-mark">
            <img :src="logo" alt="BIOTech Futures" />
          </div>

          <div class="brand-copy">
            <span class="eyebrow">{{ t('brandTitle') }}</span>
            <h1 class="hero-title">{{ t('aboutTitle') }}</h1>
          </div>
        </div>

        <!-- Main hero card grid. -->
        <div class="hero-grid">
          <!-- Role-guided access card. -->
          <article
            class="hero-card hero-card--primary interactive-surface"
            @pointermove="handleCardPointerMove"
            @pointerleave="handleCardPointerLeave"
          >
            <div class="section-head">
              <div>
                <h2 class="section-kicker">{{ t('previewRolesTitle') }}</h2>
              </div>
            </div>

            <!-- Role selector. -->
            <!-- Click selects the login identity. Hover or focus previews the role content. -->
            <div
              class="role-selector"
              aria-label="Portal roles"
            >
              <button
                v-for="(item, index) in rolePreviewItems"
                :key="item.key"
                type="button"
                class="role-pill"
                :class="[
                  roleThemeClass(item.key),
                  {
                    selected: pinnedRoleKey === item.key,
                    active: activeDisplayRoleKey === item.key
                  }
                ]"
                :aria-pressed="pinnedRoleKey === item.key"
                :ref="(el) => setRoleButtonRef(el, index)"
                @click="selectLoginRole(item.key)"
                @keydown="handleRoleKeydown($event, index)"
                @mouseenter="previewLoginRole(item.key)"
                @mouseleave="clearPreviewRole"
                @focus="previewLoginRole(item.key)"
                @blur="clearPreviewRole"
              >
                <span class="role-pill-dot"></span>
                <span>{{ t(item.labelKey) }}</span>
              </button>
            </div>

            <!-- Role detail card. -->
            <!-- The displayed data follows preview first, then selected state as fallback. -->
            <transition name="content-fade" mode="out-in">
              <div
                v-if="activeDisplayRoleKey"
                :key="activeDisplayRoleKey"
                class="role-detail-card"
              >
                <div class="role-detail-glow" aria-hidden="true"></div>
                <div class="role-detail-header">
                  <div class="role-detail-badge" :class="roleThemeClass(activeDisplayRoleKey)"></div>

                  <div>
                    <p class="role-detail-kicker">{{ t('rolePreviewLabel') }}</p>
                    <h3 class="role-detail-title">{{ activeRoleTitle }}</h3>
                  </div>
                </div>

                <p class="role-detail-summary">
                  {{ activeRoleSummary }}
                </p>

                <ul class="role-detail-list">
                  <li v-for="point in activeRolePoints" :key="point">
                    {{ point }}
                  </li>
                </ul>
              </div>
            </transition>
          </article>

          <!-- Platform overview card. -->
          <article
            class="hero-card hero-card--secondary interactive-surface"
            @pointermove="handleCardPointerMove"
            @pointerleave="handleCardPointerLeave"
          >
            <div class="section-head section-head--compact">
              <div>
                <span class="section-kicker">{{ t('platformOverview') }}</span>
              </div>
            </div>

            <!-- Showcase metrics. -->
            <div class="hero-stats">
              <div v-for="stat in showcaseStats" :key="stat.label" class="stat-card">
                <span class="stat-value">{{ stat.value }}</span>
                <span class="stat-label">{{ stat.label }}</span>
              </div>
            </div>

            <div class="overview-capabilities">
              <div
                v-for="item in platformCapabilities"
                :key="item.title"
                class="capability-card"
              >
                <span class="capability-title">{{ item.title }}</span>
                <span class="capability-subtitle">{{ item.subtitle }}</span>
              </div>
            </div>

            <!-- Background mode switch and official website link. -->
            <div class="hero-footer">
              <div class="mode-switch" role="group" :aria-label="t('visualMode')">
                <button
                  type="button"
                  class="mode-button"
                  :class="{ active: activeLeftBackground === 'original' }"
                  @click="setBackgroundMode('original')"
                >
                  {{ t('imageMode') }}
                </button>
                <button
                  type="button"
                  class="mode-button"
                  :class="{ active: activeLeftBackground === 'green' }"
                  @click="setBackgroundMode('green')"
                >
                  {{ t('emeraldMode') }}
                </button>
              </div>

              <a
                class="hero-link"
                href="https://biotechfutures.org"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ t('visitWebsite') }}
              </a>
            </div>
          </article>
        </div>
      </div>
    </section>

    <!-- Right auth pane: badges, language, email step, OTP step. -->
    <section class="auth-pane" @mousemove="handleInkMouseMove" @mouseleave="handleInkMouseLeave">
      <!-- Chinese ink ripple canvas — sits behind all auth content. -->
      <canvas ref="inkCanvasRef" class="ink-canvas" aria-hidden="true"></canvas>
      <div class="auth-shell">
        <!-- Top bar with trust badges and language switcher. -->
        <div class="auth-topbar">
          <div class="top-badges">
            <span class="top-badge">{{ t('secureAccess') }}</span>
            <span class="top-badge">{{ t('enterpriseReady') }}</span>
          </div>

          <div class="language-switcher" role="tablist" aria-label="Language switcher">
            <button
              v-for="item in languageOptions"
              :key="item.value"
              type="button"
              class="language-option"
              :class="{ active: locale === item.value }"
              @click="switchLanguage(item.value)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <!-- Auth card container. -->
        <div
          class="auth-card interactive-surface"
          @pointermove="handleCardPointerMove"
          @pointerleave="handleCardPointerLeave"
        >
          <div class="auth-card-glow"></div>
          <div class="auth-card-noise"></div>

          <!-- Two-step progress indicator. -->
          <div class="auth-progress" aria-label="Authentication progress">
            <div class="progress-item active current">
              <span class="progress-dot">1</span>
              <span class="progress-label">{{ t('emailStep') }}</span>
            </div>
            <div class="progress-line active"></div>
            <div class="progress-item active">
              <span class="progress-dot">2</span>
              <span class="progress-label">{{ credentialStepLabel }}</span>
            </div>
          </div>

          <!-- Step transition wrapper. -->
          <transition name="content-fade" mode="out-in">
            <!-- Email step panel. -->
            <div v-if="currentStep === 'email'" key="email" class="step-panel">
              <header class="auth-header">
                <div class="auth-logo-wrap">
                  <div class="auth-logo">
                    <img :src="logo" alt="BIOTech Futures" />
                  </div>

                  <div class="auth-logo-copy">
                    <h2 class="auth-title">{{ authHeading }}</h2>
                  </div>
                </div>

                <p class="auth-subtitle">{{ authSubtitle }}</p>

                <!-- Meta chips for selected identity and auth method. -->
                <div class="meta-row">
                  <span class="meta-chip meta-chip--neutral">{{ activeLoginModeLabel }}</span>
                </div>
              </header>

              <!-- Email submission form. -->
              <form class="auth-form" @submit.prevent="handleLogin" novalidate>
                <div class="login-mode-switch" role="tablist" :aria-label="t('loginMethod')">
                  <button
                    type="button"
                    class="login-mode-button"
                    :class="{ active: loginMode === 'password' }"
                    role="tab"
                    :aria-selected="loginMode === 'password'"
                    @click="setLoginMode('password')"
                  >
                    {{ t('passwordSignIn') }}
                  </button>
                  <button
                    type="button"
                    class="login-mode-button"
                    :class="{ active: loginMode === 'code' }"
                    role="tab"
                    :aria-selected="loginMode === 'code'"
                    @click="setLoginMode('code')"
                  >
                    {{ t('emailCodeSignIn') }}
                  </button>
                </div>

                <div class="field-block">
                  <label class="field-label" for="login-email">{{ t('emailLabel') }}</label>

                  <!-- Field shell highlights focus and error state at container level. -->
                  <div class="field-shell" :class="{ 'is-error': Boolean(error) }">

                    <input
                      id="login-email"
                      ref="emailInputRef"
                      v-model.trim="email"
                      type="email"
                      class="field-input"
                      :placeholder="t('emailPlaceholder')"
                      :aria-invalid="Boolean(error)"
                      autocomplete="email"
                      required
                    />
                  </div>

                  <small class="field-help">{{ emailStepHelper }}</small>
                </div>

                <div v-if="loginMode === 'password'" class="field-block">
                  <label class="field-label" for="login-password">{{ t('passwordLabel') }}</label>

                  <div class="field-shell" :class="{ 'is-error': Boolean(error) }">
                    <input
                      id="login-password"
                      ref="passwordInputRef"
                      v-model="password"
                      type="password"
                      class="field-input"
                      :placeholder="t('passwordPlaceholder')"
                      :aria-invalid="Boolean(error)"
                      autocomplete="current-password"
                      required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  class="primary-button"
                  :disabled="sendingCode"
                >
                  <span v-if="sendingCode" class="button-spinner" aria-hidden="true"></span>
                  <span v-else>{{ loginActionLabel }}</span>
                </button>
              </form>

              <!-- Step feedback messages. -->
              <transition name="message-slide">
                <p v-if="statusMessage" class="status-message" aria-live="polite">
                  {{ statusMessage }}
                </p>
              </transition>

              <transition name="message-slide">
                <p v-if="error" class="error-message" role="alert" aria-live="assertive">
                  {{ error }}
                </p>
              </transition>
            </div>

            <!-- OTP step panel. -->
            <div v-else key="otp" class="step-panel step-panel--otp">
              <header class="auth-header auth-header--compact">
                <div class="auth-logo-wrap">
                  <div class="auth-logo auth-logo--small">
                    <img :src="logo" alt="BIOTech Futures" />
                  </div>

                  <div class="auth-logo-copy">
                    <span class="auth-kicker">{{ t('secureAccess') }}</span>
                    <h2 class="auth-title">{{ t('verifyHeading') }}</h2>
                  </div>
                </div>

                <p class="auth-subtitle">{{ t('codeSentTo') }} {{ maskedEmail }}</p>

                <!-- Meta row keeps role context visible during OTP verification. -->
                <div class="meta-row meta-row--stack">
                  <button type="button" class="text-link" @click="goBackToEmailStep">
                    {{ t('changeEmail') }}
                  </button>
                </div>
              </header>

              <!-- OTP box. -->
              <!-- Each box binds to one digit, while input, keyboard, focus, and paste are centrally handled in script helpers. -->
              <div class="otp-box" :class="{ 'has-error': otpErrorActive, 'is-complete': isOtpComplete && !otpErrorActive, shaking: otpShake }">
                <input
                  v-for="(digit, index) in otpDigits"
                  :key="index"
                  :ref="(el) => setOtpRef(el, index)"
                  v-model="otpDigits[index]"
                  type="text"
                  maxlength="1"
                  class="otp-input"
                  :class="{ 'otp-input-error': otpErrorActive, 'otp-input-filled': Boolean(digit) }"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  :aria-label="`${t('digit')} ${index + 1}`"
                  @input="handleOTPInput($event, index)"
                  @keydown="handleOTPKeydown($event, index)"
                  @keydown.enter.prevent="handleOTPEnter"
                  @focus="handleOTPFocus($event)"
                  @paste="handleOTPPaste($event, index)"
                />
              </div>
              <div class="otp-footer-copy">
                <p>{{ t('codeExpiryHint') }}</p>
              </div>

              <!-- OTP primary and secondary actions. -->
              <div class="otp-action-stack">
                <button
                  type="button"
                  class="primary-button"
                  :disabled="verifyingCode || !isOtpComplete"
                  @click="verifyOTP"
                >
                  <span v-if="verifyingCode" class="button-spinner" aria-hidden="true"></span>
                  <span v-else>{{ t('verifyCode') }}</span>
                </button>

                <div class="otp-secondary-actions">
                  <button
                    type="button"
                    class="secondary-button"
                    :disabled="resendingCode || resendCountdown > 0"
                    @click="resendCode"
                  >
                    {{ resendCountdown > 0 ? `${t('resendIn')} ${resendCountdown}s` : t('resendCode') }}
                  </button>
                </div>
              </div>

              <transition name="message-slide">
                <p v-if="statusMessage" class="status-message" aria-live="polite">
                  {{ statusMessage }}
                </p>
              </transition>

              <transition name="message-slide">
                <p v-if="error" class="error-message" role="alert" aria-live="assertive">
                  {{ error }}
                </p>
              </transition>

              <!-- Support link row. -->
              <div class="support-row">
                <span>{{ t('needHelp') }}</span>
                <a href="mailto:support@biotechfutures.org">{{ t('contactSupport') }}</a>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
/*
  Imports and external modules.
*/
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import * as THREE from 'three'

import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'
import { isValidEmail, maskEmail } from '@/utils/string'
import {
  LOGIN_LANGUAGE_KEY,
  safeLocalStorageGet,
  safeLocalStorageSet
} from '@/utils/storage'

import logo from '@/assets/btf-logo.png'
import {
  LOGIN_LANGUAGE_OPTIONS,
  LOGIN_MESSAGES,
  LOGIN_ROLE_PREVIEW_CONTENT,
  LOGIN_ROLE_PREVIEW_ITEMS
} from '@/data/login_language'
import {
  LOGIN_BACKGROUND_IMAGES,
  LOGIN_BACKGROUND_IMAGES2,
  LOGIN_SLIDE_DURATION
} from '@/data/login_background'

/*
  Page-level instances.
*/
const router = useRouter()
const auth = useAuthStore()

/*
  Static configuration.
*/
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const RESEND_SECONDS = 30
const REQUEST_TIMEOUT_MS = 15000

/*
  Shared page data.
*/
const backgroundImages = LOGIN_BACKGROUND_IMAGES
const backgroundImages2 = LOGIN_BACKGROUND_IMAGES2
const slideDuration = LOGIN_SLIDE_DURATION
const languageOptions = LOGIN_LANGUAGE_OPTIONS
const messages = LOGIN_MESSAGES
const rolePreviewItems = LOGIN_ROLE_PREVIEW_ITEMS
const rolePreviewContent = LOGIN_ROLE_PREVIEW_CONTENT

/*
  Auth flow state.
*/
const email = ref('')
const password = ref('')
const loginMode = ref('password')
const currentStep = ref('email')
const error = ref('')
const statusMessage = ref('')
const sendingCode = ref(false)
const verifyingCode = ref(false)
const resendingCode = ref(false)
const resendCountdown = ref(0)

/*
  OTP interaction state.
*/
const otpDigits = ref(['', '', '', '', '', ''])
const otpRefs = ref([])
const roleButtonRefs = ref([])
const otpShake = ref(false)
const otpErrorActive = ref(false)

/*
  UI presentation state.
*/
const locale = ref('en')
const activeLeftBackground = ref('original')
const previewLoginRoleKey = ref('')
const pinnedRoleKey = ref(rolePreviewItems[0]?.key || '')
const isShellPointerInside = ref(false)
const prefersReducedMotion = ref(false)

/*
  DOM refs.
*/
const emailInputRef = ref(null)
const passwordInputRef = ref(null)
const loginShellRef = ref(null)
const inkCanvasRef = ref(null)

/*
  Runtime timer handles.
  运行时定时器句柄。
*/
let resendTimer = null
let otpErrorTimer = null
let otpAutoSubmitTimer = null
let reduceMotionQuery = null

/*
  Three.js ink effect state (non-reactive — managed entirely outside Vue reactivity).
  水墨效果 Three.js 状态（不参与 Vue 响应式系统）。
*/
const INK_MAX_DROPS = 12
const INK_DROP_INTERVAL_MS = 80   // ~12 Hz — sparse trail, not a dense smear
const INK_LIFESPAN = 1.8          // seconds each drop lives

const INK_VERT = /* glsl */`
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`

/*
  INK_FRAG — Chinese ink-wash (水墨) fragment shader.

  Techniques used:
  1. Quintic-interpolated Perlin gradient noise  — eliminates banding present in value noise.
  2. 5-octave FBM with per-octave rotation       — prevents axis-alignment grid artifacts.
  3. Two-level domain warping (Inigo Quilez)      — computed ONCE per pixel, shared by all
     drops; simulates how paper fibres guide ink in complex, non-circular paths.
  4. Very slow time drift on the warp base        — ink "breathes" gently even after the mouse
     stops moving.
  5. Gaussian (exp(-d²/2σ²)) ink blob             — far softer than smoothstep; mirrors how
     pigment concentration follows a Fick-diffusion bell curve.
  6. Backrun / edge-darkening ring                — real ink and watercolour deposit pigment
     at the drying front (the most distinctive feature of traditional brush work).
  7. Fast outer wave + trailing secondary ring    — represent the initial kinetic impact and
     capillary recoil of the drop hitting wet paper.
  8. Paper-grain texture (value-noise FBM)        — uneven fibre absorption breaks uniformity.
  9. Micro brush-stroke texture overlay           — adds fine directional variation inside
     dense ink regions.
  10. Two-tone ink colour blend                   — dense regions near-black (墨); diluted
      wash lighter blue-grey, as traditional 水墨 painting uses.
*/
const INK_FRAG = /* glsl */`
precision highp float;
varying vec2 vUv;

uniform float uTime;
uniform float uAspect;
uniform int   uDropCount;
uniform vec3  uDrops[${INK_MAX_DROPS}]; // .xy = UV position (unscaled), .z = birth time

// ── Gradient noise helpers ────────────────────────────────────────────────────
vec2 hash22(vec2 p) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return fract(sin(p) * 43758.5453) * 2.0 - 1.0;
}

// Quintic-interpolated Perlin noise (smooth, no banding)
float gnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0); // quintic fade
  float a = dot(hash22(i),            f            );
  float b = dot(hash22(i+vec2(1,0)),  f-vec2(1,0)  );
  float c = dot(hash22(i+vec2(0,1)),  f-vec2(0,1)  );
  float d = dot(hash22(i+vec2(1,1)),  f-vec2(1,1)  );
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y);
}

// 5-octave FBM — rotated each octave to break axis symmetry
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  mat2 m = mat2(0.80, 0.60, -0.60, 0.80); // 36.87° rotation
  for (int i = 0; i < 5; i++) {
    v += a * gnoise(p);
    p  = m * p * 2.1;
    a *= 0.48;
  }
  return v;
}

// ── Value noise — fast, used only for paper grain ─────────────────────────────
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = fract(sin(dot(i,            vec2(127.1,311.7))) * 43758.5);
  float b = fract(sin(dot(i+vec2(1,0),  vec2(127.1,311.7))) * 43758.5);
  float c = fract(sin(dot(i+vec2(0,1),  vec2(127.1,311.7))) * 43758.5);
  float d = fract(sin(dot(i+vec2(1,1),  vec2(127.1,311.7))) * 43758.5);
  return mix(mix(a,b,f.x), mix(c,d,f.x), f.y);
}

float paperFbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { v += a * vnoise(p); p *= 2.1; a *= 0.5; }
  return v;
}

void main() {
  vec2 uv  = vUv;
  vec2 asp = vec2(uv.x * uAspect, uv.y);

  // ── Global domain warp (computed once — shared by all drops) ─────────────────
  // Represents the paper fibre structure that bends ink paths.
  // uTime * 0.013 gives an imperceptibly slow "breathing" drift.
  vec2 wc = uv * 4.3 + uTime * 0.013;
  vec2 q  = vec2(fbm(wc),               fbm(wc + vec2(5.2, 1.3)));
  vec2 gw = vec2(fbm(wc + 3.2*q + vec2(1.7, 9.2)),
                 fbm(wc + 3.2*q + vec2(8.3, 2.8)));  // two-level warp

  float totalInk = 0.0;

  for (int i = 0; i < ${INK_MAX_DROPS}; i++) {
    if (i >= uDropCount) break;

    float age = uTime - uDrops[i].z;
    if (age < 0.0 || age > ${INK_LIFESPAN.toFixed(1)}) continue;

    vec2  dpos = vec2(uDrops[i].x * uAspect, uDrops[i].y);
    float t    = clamp(age / ${INK_LIFESPAN.toFixed(1)}, 0.0, 1.0);

    // Per-drop rotation offset — makes each drop's boundary slightly different
    float seed = fract(uDrops[i].z * 7.53);
    vec2  perDrop = vec2(cos(seed * 6.2832), sin(seed * 6.2832)) * 0.010;

    // Warp grows gently — subtle organic boundary, never jagged
    float ws = 0.032 * (0.2 + pow(age, 0.50) * 0.60);
    float d  = distance(asp + gw * ws + perDrop, dpos);

    // ── Spread radius (Fick diffusion: r ∝ √age) ─────────────────────────────
    float r = 0.003 + pow(age, 0.50) * 0.026;

    // ── Layer 1 — moisture halo: paper absorbs water before visible ink ───────
    // Extremely soft, barely-there pale wash at the outermost edge
    float haloSig = r * 3.0;
    float halo    = exp(-(d*d) / (2.0*haloSig*haloSig)) * 0.09;

    // ── Layer 2 — diffusion fringe: diluted ink wash spreading outward ────────
    float fringeSig = r * 1.4;
    float fringe    = exp(-(d*d) / (2.0*fringeSig*fringeSig)) * 0.18;

    // ── Layer 3 — dense core: concentrated pigment at impact point ───────────
    float coreSig = r * 0.45;
    float core    = exp(-(d*d) / (2.0*coreSig*coreSig)) * 0.28;

    // ── Backrun ring: dark halo at drying front — characteristic of real brush ink
    float backrun = exp(-pow((d - r) / max(r * 0.20, 0.0005), 2.0));
    backrun *= (1.0 - smoothstep(0.0, 0.35, t)) * 0.22; // disappears as ink dries

    // ── Whisper wave: barely perceptible kinetic ring, like ink touching water ─
    float wR   = age * 0.082;
    float wW   = 0.008 * max(0.10, 1.0 - t * 0.88);
    float wave = exp(-pow((d - wR) / max(wW, 0.0005), 2.0));
    wave *= max(0.0, 1.0 - t * 1.6) * 0.14;

    // ── Natural drying: exponential decay — fast onset, long graceful tail ────
    float fade = exp(-3.8 * t);

    totalInk += (halo + fringe + core + backrun + wave) * fade;
  }

  // ── Dual-scale paper grain: coarse fibre bundles + fine individual fibres ────
  float coarseGrain = paperFbm(uv * 7.0  + vec2(2.7, 6.1));
  float fineGrain   = paperFbm(uv * 28.0 + vec2(9.1, 3.4));
  float grain       = coarseGrain * 0.60 + fineGrain * 0.40;
  totalInk *= mix(0.68, 1.0, grain); // fibres cause ±16% uneven absorption

  // ── Ultra-fine gnoise — adds imperceptible depth to ink without noise
  float micro = gnoise(uv * 65.0 + vec2(1.2, 4.7)) * 0.5 + 0.5;
  totalInk   += micro * totalInk * 0.055;

  totalInk = clamp(totalInk, 0.0, 0.52);

  // ── 墨 Ink colour with warm/cool tonal variation ──────────────────────────────
  // Real sumi-e ink shifts between indigo-black (cool, well-ground ink stick)
  // and warm brown-black (older or more diluted ink). The variation is subtle
  // but prevents the effect from looking like a flat opacity mask.
  float warmth  = fbm(asp * 5.2 + vec2(7.3, 2.1)) * 0.5 + 0.5; // slow spatial variation
  vec3 inkCool  = vec3(0.050, 0.060, 0.090); // indigo-black
  vec3 inkWarm  = vec3(0.072, 0.063, 0.078); // warm brown-black
  vec3 inkDense = mix(inkCool, inkWarm, warmth * 0.38);
  vec3 inkWash  = vec3(0.15,  0.17,  0.23 ); // very pale blue-grey diluted wash
  vec3 inkColor = mix(inkWash, inkDense, smoothstep(0.07, 0.55, totalInk));

  gl_FragColor  = vec4(inkColor, totalInk);
}
`

let inkRenderer  = null
let inkScene     = null
let inkCamera    = null
let inkMaterial  = null
let inkClock     = null
let inkAnimId    = null
let inkDrops     = []           // { x, y, birthTime }[]
let inkLastDropT = 0            // timestamp of last drop (Date.now)

/*
  Translation accessor.
  统一翻译读取函数。
*/
const t = (key) => messages[locale.value]?.[key] || messages.en?.[key] || key

/*
  Basic derived values.
  基础衍生值。
*/
const currentDir = computed(() => (locale.value === 'ar' ? 'rtl' : 'ltr'))
const currentStepIndex = computed(() => (currentStep.value === 'email' ? 1 : 2))
const maskedEmail = computed(() => maskEmail(email.value))
const isOtpComplete = computed(() => otpDigits.value.every((digit) => /^\d$/.test(digit)))
const otpProgressPercent = computed(() => {
  const filledCount = otpDigits.value.filter((digit) => /^\d$/.test(digit)).length
  return `${(filledCount / otpDigits.value.length) * 100}%`
})

/*
  Role display state.
  角色显示状态。
*/
const activeDisplayRoleKey = computed(() => {
  return previewLoginRoleKey.value || pinnedRoleKey.value || rolePreviewItems[0]?.key || ''
})

const activeRoleData = computed(() => {
  if (!activeDisplayRoleKey.value) {
    return null
  }

  return rolePreviewContent[locale.value]?.[activeDisplayRoleKey.value]
    || rolePreviewContent.en?.[activeDisplayRoleKey.value]
    || null
})

const activeRoleLabel = computed(() => {
  if (!activeDisplayRoleKey.value) {
    return ''
  }

  const currentRoleItem = rolePreviewItems.find((item) => item.key === activeDisplayRoleKey.value)
  return currentRoleItem ? t(currentRoleItem.labelKey) : ''
})

const authHeading = computed(() => t('signIn'))

const authSubtitle = computed(() => t('welcomeSubtitle'))

const isPasswordLoginMode = computed(() => loginMode.value === 'password')
const activeLoginModeLabel = computed(() => isPasswordLoginMode.value ? t('passwordSignIn') : t('emailCodeSignIn'))
const credentialStepLabel = computed(() => isPasswordLoginMode.value ? t('passwordStep') : t('otpStep'))
const loginActionLabel = computed(() => isPasswordLoginMode.value ? t('signIn') : t('sendVerificationCode'))
const emailStepHelper = computed(() => isPasswordLoginMode.value ? t('passwordHelper') : t('emailHelper'))

const activeRoleTitle = computed(() => activeRoleData.value?.title || activeRoleLabel.value)
const activeRoleSummary = computed(() => activeRoleData.value?.summary || '')
const activeRolePoints = computed(() => activeRoleData.value?.points?.slice(0, 3) || [])

/*
  Hero showcase metrics.
*/
const showcaseStats = computed(() => [
  {
    // 转成字符串，如果长度不够2在前面补零："3".padStart(2, '0')   // "03"
    value: String(rolePreviewItems.length).padStart(2, '0'),
    label: t('statsRoles')
  },
  {
    value: '10',
    label: t('statsWeeks')
  },
  {
    value: 'JWT',
    label: t('statsSecureAccess')
  }
])

const platformCapabilities = computed(() => [
  {
    title: t('capabilityGroupSpacesTitle'),
    subtitle: t('capabilityGroupSpacesSubtitle')
  },
  {
    title: t('capabilityResourcesTitle'),
    subtitle: t('capabilityResourcesSubtitle')
  },
  {
    title: t('capabilityProgressTitle'),
    subtitle: t('capabilityProgressSubtitle')
  },
  {
    title: t('capabilityEventsTitle'),
    subtitle: t('capabilityEventsSubtitle')
  },
  {
    title: t('capabilityMatchingTitle'),
    subtitle: t('capabilityMatchingSubtitle')
  },
  {
    title: t('capabilityAdminTitle'),
    subtitle: t('capabilityAdminSubtitle')
  }
])

/*
  Theme class builder.
*/
const roleThemeClass = (roleKey) => `role-theme--${roleKey || 'default'}`

// 保存每一个role按钮的DOM元素
const setRoleButtonRef = (element, index) => {
  if (element) {
    roleButtonRefs.value[index] = element
  }
}

const focusRoleButton = async (index) => {
  await nextTick()
  roleButtonRefs.value[index]?.focus()
}

// 处理键盘按键对role的选取
const handleRoleKeydown = async (event, index) => {
  const total = rolePreviewItems.length

  if (!total) {
    return
  }

  const isRtl = currentDir.value === 'rtl'
  // 相当于循环数组
  const previousIndex = (index - 1 + total) % total
  const nextIndex = (index + 1) % total

  if (event.key === 'ArrowRight') {
    event.preventDefault()
    await focusRoleButton(isRtl ? previousIndex : nextIndex)
    return
  }

  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    await focusRoleButton(isRtl ? nextIndex : previousIndex)
    return
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    await focusRoleButton(nextIndex)
    return
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    await focusRoleButton(previousIndex)
    return
  }

  if (event.key === 'Home') {
    event.preventDefault()
    await focusRoleButton(0)
    return
  }

  if (event.key === 'End') {
    event.preventDefault()
    await focusRoleButton(total - 1)
  }
}

const selectLoginRole = (roleKey) => {
  pinnedRoleKey.value = roleKey
}

const previewLoginRole = (roleKey) => {
  previewLoginRoleKey.value = roleKey
}

const clearPreviewRole = () => {
  previewLoginRoleKey.value = ''
}

const resetPointerVariables = (element) => {
  if (!element) {
    return
  }

  element.style.setProperty('--pointer-x', '50%')
  element.style.setProperty('--pointer-y', '50%')
  element.style.setProperty('--rotate-x', '0deg')
  element.style.setProperty('--rotate-y', '0deg')
  element.style.setProperty('--glow-opacity', '0')
}

//
const updatePointerVariables = (element, clientX, clientY) => {
  if (!element) {
    return
  }

  // 获取矩形信息对象，包含：rect.left这个元素离浏览器左边多远，
  // rect.top离顶部多远,rect.width宽多少,rect.height高多少
  const rect = element.getBoundingClientRect()
  const x = clientX - rect.left
  const y = clientY - rect.top

  element.style.setProperty('--pointer-x', `${x}px`)
  element.style.setProperty('--pointer-y', `${y}px`)

  if (prefersReducedMotion.value) {
    element.style.setProperty('--rotate-x', '0deg')
    element.style.setProperty('--rotate-y', '0deg')
    element.style.setProperty('--glow-opacity', '0')
    return
  }

  const rotateX = ((0.5 - y / rect.height) * 9).toFixed(2)
  const rotateY = (((x / rect.width) - 0.5) * 9).toFixed(2)
  const glowOpacity = (0.14 + Math.abs(Number(rotateX)) * 0.018 + Math.abs(Number(rotateY)) * 0.018).toFixed(2)

  element.style.setProperty('--rotate-x', `${rotateX}deg`)
  element.style.setProperty('--rotate-y', `${rotateY}deg`)
  element.style.setProperty('--glow-opacity', glowOpacity)
}

const handleCardPointerMove = (event) => {
  updatePointerVariables(event.currentTarget, event.clientX, event.clientY)
}

const handleCardPointerLeave = (event) => {
  resetPointerVariables(event.currentTarget)
}

const handleShellPointerMove = (event) => {
  updatePointerVariables(loginShellRef.value, event.clientX, event.clientY)
  isShellPointerInside.value = true
}

const handleShellPointerLeave = () => {
  isShellPointerInside.value = false
  resetPointerVariables(loginShellRef.value)
}

/*
  Message helpers.
  消息状态辅助函数。
*/
const clearMessages = () => {
  error.value = ''
  statusMessage.value = ''
}

/*
  Timer cleanup helpers.
  定时器清理辅助函数。
*/
const clearOtpAnimationTimers = () => {
  if (otpErrorTimer) {
    clearTimeout(otpErrorTimer)
    otpErrorTimer = null
  }
}

const clearOtpAutoSubmitTimer = () => {
  if (otpAutoSubmitTimer) {
    clearTimeout(otpAutoSubmitTimer)
    otpAutoSubmitTimer = null
  }
}

/*
  Hero pane interaction helpers.
  左侧展示区交互辅助函数。
*/
const setBackgroundMode = (mode) => {
  activeLeftBackground.value = mode
}

const setLoginMode = async (mode) => {
  if (!['password', 'code'].includes(mode) || loginMode.value === mode) {
    return
  }

  loginMode.value = mode
  currentStep.value = 'email'
  clearMessages()
  clearOtpAutoSubmitTimer()
  otpErrorActive.value = false
  otpShake.value = false

  await nextTick()

  if (mode === 'password') {
    passwordInputRef.value?.focus()
    return
  }

  emailInputRef.value?.focus()
}

/*
  Language switching and persistence.
  语言切换与本地持久化。
*/
const switchLanguage = (lang) => {
  locale.value = lang
  clearMessages()
  safeLocalStorageSet(LOGIN_LANGUAGE_KEY, lang)
}

const handleReduceMotionChange = (event) => {
  prefersReducedMotion.value = event.matches
}

/*
  OTP ref collection.
  OTP 输入框 ref 收集。
*/
const setOtpRef = (element, index) => {
  if (element) {
    otpRefs.value[index] = element
  }
}

/*
  OTP state reset.
  OTP 输入状态重置。
*/
const resetOtpState = async () => {
  clearOtpAutoSubmitTimer()
  otpDigits.value = ['', '', '', '', '', '']
  otpShake.value = false
  otpErrorActive.value = false
  await nextTick()
  otpRefs.value[0]?.focus()
}

/*
  Fill OTP digits from pasted or merged input text.
  将粘贴文本或多字符输入拆分填入 OTP。
*/
const fillOtpFromText = async (value, startIndex = 0) => {
  const digits = value.replace(/\D/g, '').slice(0, 6 - startIndex).split('')

  if (!digits.length) {
    return
  }

  digits.forEach((digit, offset) => {
    otpDigits.value[startIndex + offset] = digit
  })

  await nextTick()

  const nextIndex = Math.min(startIndex + digits.length, 5)
  otpRefs.value[nextIndex]?.focus()
}

/*
  OTP input handlers.
*/
const handleOTPInput = async (event, index) => {
  otpErrorActive.value = false
  otpShake.value = false
  clearOtpAnimationTimers()

  const normalizedValue = event.target.value.replace(/\D/g, '')

  if (!normalizedValue) {
    otpDigits.value[index] = ''
    return
  }

  if (normalizedValue.length > 1) {
    otpDigits.value[index] = ''
    await fillOtpFromText(normalizedValue, index)
    return
  }

  otpDigits.value[index] = normalizedValue

  if (index < otpDigits.value.length - 1) {
    otpRefs.value[index + 1]?.focus()
  }
}

const handleOTPKeydown = (event, index) => {
  const key = event.key

  /*
    Allow common system shortcuts such as Ctrl/Cmd + C/V/A/X.
  */
  if (event.ctrlKey || event.metaKey) {
    return
  }

  if (key === 'Backspace') {
    event.preventDefault()

    if (otpDigits.value[index]) {
      otpDigits.value[index] = ''
      return
    }

    if (index > 0) {
      otpDigits.value[index - 1] = ''
      otpRefs.value[index - 1]?.focus()
    }

    return
  }

  if (key === 'ArrowLeft' && index > 0) {
    event.preventDefault()
    otpRefs.value[index - 1]?.focus()
    return
  }

  if (key === 'ArrowRight' && index < otpDigits.value.length - 1) {
    event.preventDefault()
    otpRefs.value[index + 1]?.focus()
    return
  }

  if (key === ' ' || key === 'Spacebar') {
    event.preventDefault()
    return
  }

  if (['Tab', 'Shift', 'Control', 'Meta', 'Alt', 'Enter', 'Delete', 'Home', 'End'].includes(key)) {
    return
  }

  if (!/^\d$/.test(key)) {
    event.preventDefault()
  }
}

const handleOTPFocus = (event) => {
  event.target.select()
}

const handleOTPPaste = async (event, index = 0) => {
  event.preventDefault()
  otpErrorActive.value = false
  otpShake.value = false
  clearOtpAnimationTimers()

  const pastedText = event.clipboardData?.getData('text') || ''
  await fillOtpFromText(pastedText, index)
}

const handleOTPEnter = async () => {
  if (!isOtpComplete.value || verifyingCode.value) {
    return
  }

  await verifyOTP()
}

/*
  Request helpers.
  请求辅助函数。
*/
const buildCallbackUrl = () => `${window.location.origin}/#/auth/callback`

const parseErrorMessage = async (response, fallbackText) => {
  try {
    const data = await response.json()
    return data.error || data.message || fallbackText
  } catch {
    return fallbackText
  }
}

/*
  Shared JSON POST request helper.
*/
const postJson = async (path, payload) => {
  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) {
    throw new Error(t('errorCsrfFailed'))
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: buildSessionHeaders({
        includeCSRF: true
      }),
      credentials: 'include',
      body: JSON.stringify(payload),
      signal: controller.signal
    })
  } finally {
    clearTimeout(timeoutId)
  }
}

/*
  Resend countdown logic.
*/
const startResendCountdown = () => {
  resendCountdown.value = RESEND_SECONDS

  if (resendTimer) {
    clearInterval(resendTimer)
  }

  resendTimer = setInterval(() => {
    if (resendCountdown.value <= 1) {
      resendCountdown.value = 0
      clearInterval(resendTimer)
      resendTimer = null
      return
    }

    resendCountdown.value -= 1
  }, 1000)
}

/*
  OTP error feedback.
*/
const triggerOtpErrorFeedback = async () => {
  clearOtpAnimationTimers()
  clearOtpAutoSubmitTimer()
  otpErrorActive.value = true
  otpShake.value = false
  otpDigits.value = ['', '', '', '', '', '']

  await nextTick()

  otpShake.value = true
  otpRefs.value[0]?.focus()

  otpErrorTimer = setTimeout(() => {
    otpShake.value = false
  }, 420)
}

/*
  Step navigation helper.
*/
const goBackToEmailStep = async () => {
  currentStep.value = 'email'
  previewLoginRoleKey.value = ''
  clearMessages()
  otpErrorActive.value = false
  otpShake.value = false
  clearOtpAutoSubmitTimer()
  await nextTick()
  emailInputRef.value?.focus()
}

/*
  Authentication flow: send code.
*/
const handleLogin = async () => {
  const normalizedEmail = email.value.trim().toLowerCase()
  const enteredPassword = password.value

  clearMessages()

  if (!normalizedEmail) {
    error.value = t('errorEnterEmail')
    return
  }

  if (!isValidEmail(normalizedEmail)) {
    error.value = t('errorInvalidEmail')
    return
  }

  if (isPasswordLoginMode.value && !enteredPassword) {
    error.value = t('errorEnterPassword')
    await nextTick()
    passwordInputRef.value?.focus()
    return
  }

  if (sendingCode.value) {
    return
  }

  email.value = normalizedEmail
  sendingCode.value = true
  statusMessage.value = isPasswordLoginMode.value ? t('signingIn') : t('sendingCode')

  try {
    if (isPasswordLoginMode.value) {
      await auth.loginWithPassword(normalizedEmail, enteredPassword)

      if (!auth.user) {
        error.value = t('errorUserLoadFailed')
        statusMessage.value = ''
        return
      }

      previewLoginRoleKey.value = ''

      try {
        await router.replace('/dashboard')
      } catch {
        window.location.href = '/#/dashboard'
      }
      return
    }

    const response = await postJson('/services/send-login-code/', {
      email: normalizedEmail,
      redirect_url: buildCallbackUrl()
    })

    if (!response.ok) {
      statusMessage.value = ''
      error.value = await parseErrorMessage(response, t('errorSendLink'))
      return
    }

    previewLoginRoleKey.value = ''
    statusMessage.value = t('sendingSuccess')
    currentStep.value = 'otp'
    await resetOtpState()
    startResendCountdown()
  } catch (requestError) {
    console.error('Login error:', requestError)
    statusMessage.value = ''
    error.value = requestError instanceof Error ? requestError.message : t('errorNetworkLogin')
  } finally {
    sendingCode.value = false
  }
}

/*
  Authentication flow: verify OTP.
*/
const verifyOTP = async () => {
  const code = otpDigits.value.join('')

  if (code.length !== 6) {
    error.value = t('errorCompleteCode')
    statusMessage.value = ''
    return
  }

  const csrfReady = await ensureCsrfCookie(API_BASE_URL)
  if (!csrfReady) {
    error.value = t('errorCsrfFailed')
    statusMessage.value = ''
    return
  }

  clearMessages()
  verifyingCode.value = true
  statusMessage.value = t('signingIn')

  try {
    const response = await postJson('/services/verify-login-code/', {
      email: email.value,
      code
    })

    if (!response.ok) {
      statusMessage.value = ''
      error.value = await parseErrorMessage(response, t('errorInvalidCode'))
      await triggerOtpErrorFeedback()
      return
    }

    await auth.fetchUserData()

    if (!auth.user) {
      error.value = t('errorUserLoadFailed')
      statusMessage.value = ''
      return
    }

    previewLoginRoleKey.value = ''

    try {
      await router.replace('/dashboard')
    } catch {
      window.location.href = '/#/dashboard'
    }
  } catch (requestError) {
    console.error('OTP verification error:', requestError)
    statusMessage.value = ''
    error.value = t('errorNetworkOtp')
  } finally {
    verifyingCode.value = false
  }
}

/*
  Authentication flow: resend code.
*/
const resendCode = async () => {
  if (!email.value) {
    error.value = t('errorEnterEmailFirst')
    statusMessage.value = ''
    return
  }

  if (resendCountdown.value > 0 || resendingCode.value) {
    return
  }

  clearMessages()
  resendingCode.value = true

  try {
    const response = await postJson('/services/send-login-code/', {
    email: email.value,
    redirect_url: buildCallbackUrl()
  })

  if (!response.ok) {
    error.value = await parseErrorMessage(response, t('errorResendFail'))
    return
  }

  previewLoginRoleKey.value = ''

  statusMessage.value = t('resendSuccess')
  await resetOtpState()
  startResendCountdown()
  } catch (requestError) {
    console.error('Resend code error:', requestError)
    error.value = t('errorNetworkOtp')
  } finally {
    resendingCode.value = false
  }
}

/*
  Document language and direction sync.
*/
watch(
  locale,
  (nextLocale) => {
    const direction = nextLocale === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = nextLocale
    document.documentElement.dir = direction
  },
  { immediate: true }
)

/*
  Step focus sync.
*/
watch(currentStep, async (step) => {
  await nextTick()

  if (step === 'email') {
    emailInputRef.value?.focus()
  } else {
    otpRefs.value[0]?.focus()
  }
})

watch(
  [isOtpComplete, currentStep],
  ([complete, step]) => {
    clearOtpAutoSubmitTimer()

    if (step !== 'otp' || !complete || verifyingCode.value || otpErrorActive.value) {
      return
    }

    otpAutoSubmitTimer = setTimeout(() => {
      if (isOtpComplete.value && currentStep.value === 'otp' && !verifyingCode.value) {
        verifyOTP()
      }
    }, 160)
  }
)

/*
  Restore saved language.
*/
const savedLanguage = safeLocalStorageGet(LOGIN_LANGUAGE_KEY, 'en')
if (savedLanguage && languageOptions.some((item) => item.value === savedLanguage)) {
  locale.value = savedLanguage
}

/*
  Ink effect: init, resize, drop creation, mouse handlers, dispose.
*/
function initInkEffect() {
  if (!inkCanvasRef.value || prefersReducedMotion.value) return

  const pane = inkCanvasRef.value.parentElement
  const { width, height } = pane.getBoundingClientRect()

  inkRenderer = new THREE.WebGLRenderer({
    canvas: inkCanvasRef.value,
    alpha: true,
    antialias: false,
    powerPreference: 'low-power'
  })
  inkRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
  inkRenderer.setClearColor(0x000000, 0)
  inkRenderer.setSize(width, height)

  inkScene  = new THREE.Scene()
  inkCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10)
  inkCamera.position.z = 1

  // Build initial drops uniform array (all inactive)
  const dropVecs = Array.from({ length: INK_MAX_DROPS }, () => new THREE.Vector3(0, 0, -9999))

  inkMaterial = new THREE.ShaderMaterial({
    vertexShader: INK_VERT,
    fragmentShader: INK_FRAG,
    uniforms: {
      uTime:      { value: 0 },
      uAspect:    { value: width / height },
      uDropCount: { value: 0 },
      uDrops:     { value: dropVecs }
    },
    transparent: true,
    depthWrite:  false,
    depthTest:   false
  })

  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), inkMaterial)
  inkScene.add(quad)

  inkClock = new THREE.Clock()
  inkDrops = []

  animateInk()
}

function resizeInkCanvas() {
  if (!inkRenderer || !inkCanvasRef.value) return
  const { width, height } = inkCanvasRef.value.parentElement.getBoundingClientRect()
  inkRenderer.setSize(width, height)
  if (inkMaterial) inkMaterial.uniforms.uAspect.value = width / height
}

function syncInkDropUniforms() {
  if (!inkMaterial) return
  for (let i = 0; i < INK_MAX_DROPS; i++) {
    if (i < inkDrops.length) {
      inkMaterial.uniforms.uDrops.value[i].set(inkDrops[i].x, inkDrops[i].y, inkDrops[i].birthTime)
    } else {
      inkMaterial.uniforms.uDrops.value[i].set(0, 0, -9999)
    }
  }
  inkMaterial.uniforms.uDropCount.value = inkDrops.length
}

function addInkDrop(uvX, uvY) {
  if (!inkMaterial || !inkClock) return
  const birthTime = inkClock.getElapsedTime()
  if (inkDrops.length >= INK_MAX_DROPS) inkDrops.shift()
  inkDrops.push({ x: uvX, y: uvY, birthTime })
  syncInkDropUniforms()
}

function handleInkMouseMove(event) {
  if (!inkCanvasRef.value || prefersReducedMotion.value) return
  const now = Date.now()
  if (now - inkLastDropT < INK_DROP_INTERVAL_MS) return
  inkLastDropT = now

  const rect = inkCanvasRef.value.parentElement.getBoundingClientRect()
  const uvX  = (event.clientX - rect.left)  / rect.width
  const uvY  = 1.0 - (event.clientY - rect.top) / rect.height  // flip Y for GL coords
  addInkDrop(uvX, uvY)
}

function handleInkMouseLeave() {
  // Drops fade out naturally; no explicit action needed.
}

function animateInk() {
  if (!inkRenderer) return
  inkAnimId = requestAnimationFrame(animateInk)

  const elapsed = inkClock.getElapsedTime()
  inkMaterial.uniforms.uTime.value = elapsed

  // Prune expired drops so the uniform array stays clean
  const before = inkDrops.length
  inkDrops = inkDrops.filter((d) => elapsed - d.birthTime < INK_LIFESPAN + 0.2)
  if (inkDrops.length !== before) syncInkDropUniforms()

  inkRenderer.render(inkScene, inkCamera)
}

function disposeInkEffect() {
  if (inkAnimId) { cancelAnimationFrame(inkAnimId); inkAnimId = null }
  if (inkRenderer) { inkRenderer.dispose(); inkRenderer = null }
  inkScene    = null
  inkCamera   = null
  inkMaterial = null
  inkClock    = null
  inkDrops    = []
}

/*
  Lifecycle: initial focus.
*/
onMounted(async () => {
  ensureCsrfCookie(API_BASE_URL).catch((error) => {
    console.error('Initial CSRF warm-up failed:', error)
  })

  reduceMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = reduceMotionQuery.matches

  if (reduceMotionQuery.addEventListener) {
    reduceMotionQuery.addEventListener('change', handleReduceMotionChange)
  } else if (reduceMotionQuery.addListener) {
    reduceMotionQuery.addListener(handleReduceMotionChange)
  }

  await nextTick()
  emailInputRef.value?.focus()
  initInkEffect()
  window.addEventListener('resize', resizeInkCanvas)
})

/*
  Lifecycle: cleanup timers.
*/
onBeforeUnmount(() => {
  clearOtpAnimationTimers()
  clearOtpAutoSubmitTimer()
  disposeInkEffect()
  window.removeEventListener('resize', resizeInkCanvas)

  if (resendTimer) {
    clearInterval(resendTimer)
    resendTimer = null
  }

  if (reduceMotionQuery) {
    if (reduceMotionQuery.removeEventListener) {
      reduceMotionQuery.removeEventListener('change', handleReduceMotionChange)
    } else if (reduceMotionQuery.removeListener) {
      reduceMotionQuery.removeListener(handleReduceMotionChange)
    }

    reduceMotionQuery = null
  }
})
</script>

<style scoped>
/*
  Module 1: page tokens and global two-column shell.
*/

.login-shell {
  --emerald-950: #081714;
  --emerald-900: #0d241f;
  --emerald-850: #123129;
  --emerald-800: #173d33;
  --emerald-700: #1f5d4f;
  --emerald-600: #27846d;
  --emerald-500: #2fa486;
  --emerald-400: #69c3aa;
  --mint-50: #f5fbf8;
  --mint-100: #edf7f2;
  --mint-200: #deefe6;
  --mint-300: #cce6d8;
  --stone-900: #10211d;
  --stone-700: #36514a;
  --stone-500: #648178;
  --stone-300: #b6c9c2;
  --white-soft: rgba(255, 255, 255, 0.74);
  --border-soft: rgba(16, 33, 29, 0.1);
  --border-strong: rgba(255, 255, 255, 0.18);
  --shadow-hero: 0 32px 90px rgba(3, 12, 10, 0.45);
  --shadow-card: 0 26px 70px rgba(12, 41, 34, 0.14);
  --shadow-focus: 0 0 0 4px rgba(47, 164, 134, 0.14);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 540px);
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(48, 173, 138, 0.16), transparent 24%),
    radial-gradient(circle at bottom right, rgba(23, 93, 79, 0.08), transparent 28%),
    linear-gradient(180deg, #eef7f2 0%, #e7f3ec 40%, #dcece2 100%);
}

/*
  Module 2: hero pane, background stage, and visual effects.
*/
.hero-pane {
  position: relative;
  overflow: hidden;
  min-height: 100vh;
}

.hero-stage {
  position: absolute;
  inset: 0;
}

.hero-scene {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.45s ease;
}

.hero-scene.active {
  opacity: 1;
}

.hero-slide-image,
.hero-green-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.hero-slide-image {
  object-fit: cover;
  opacity: 0;
  animation: heroSlideshow 18s infinite;
  filter: saturate(1.02) contrast(1.01);
}

.hero-green-image {
  background-position: center center;
  background-repeat: no-repeat;
  background-size: cover;
  filter: saturate(0.95) contrast(1.02) brightness(0.94);
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 14% 18%, rgba(115, 232, 193, 0.10), transparent 18%),
    radial-gradient(circle at 86% 16%, rgba(72, 179, 148, 0.12), transparent 24%),
    radial-gradient(circle at 50% 88%, rgba(72, 179, 148, 0.06), transparent 28%),
    linear-gradient(135deg, rgba(3, 15, 13, 0.16) 0%, rgba(4, 18, 15, 0.30) 48%, rgba(4, 12, 11, 0.46) 100%);
}

.hero-noise {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.22) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.18) 1px, transparent 1px);
  background-size: 24px 24px;
  mask-image: radial-gradient(circle at center, black 34%, transparent 100%);
}

/*
  Module 3: hero foreground layout, brand block, and cards.
*/
.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 28px;
  min-height: 100vh;
  padding: clamp(28px, 4vw, 52px);
  color: rgba(255, 255, 255, 0.96);
}

.hero-brand-row {
  width: min(100%, 860px);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  margin-bottom: 0;
  text-align: center;
}

.brand-mark,
.auth-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 22px;
  overflow: hidden;
}

.brand-mark {
  width: 68px;
  height: 68px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.08));
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow: 0 20px 35px rgba(3, 11, 10, 0.28);
  backdrop-filter: blur(14px);
}

.brand-mark img,
.auth-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.eyebrow,
.section-kicker,
.auth-kicker,
.role-detail-kicker {
  font-size: 1.2rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.eyebrow {
  color: rgba(208, 255, 235, 0.82);
}

.hero-title {
  margin: 0;
  font-size: clamp(2rem, 3.2vw, 2.8rem);
  line-height: 1.05;
  letter-spacing: -0.03em;
  color: #d8fff0;
}


.hero-grid {
  width: min(100%, 960px);
  display: grid;
  grid-template-columns: 1.08fr 0.92fr;
  gap: 20px;
  align-items: stretch;
}

.hero-card {
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: 30px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.07));
  box-shadow: var(--shadow-hero);
  backdrop-filter: blur(18px);
}

.hero-card::before,
.auth-card::before {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  pointer-events: none;
}

.hero-card--primary {
  min-height: 468px;
}

.hero-card--secondary {
  min-height: 468px;
  background: linear-gradient(180deg, rgba(6, 22, 19, 0.42), rgba(7, 18, 16, 0.28));
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-head--compact {
  margin-bottom: 20px;
}

.section-kicker {
  display: inline-block;
  margin-bottom: 8px;
  color: rgba(205, 255, 232, 0.7);
}

.section-title,
.role-detail-title,
.auth-title {
  margin: 0;
  letter-spacing: -0.02em;
}

.section-title {
  font-size: 1.2rem;
  color: #ffffff;
}

.selection-pill,
.meta-chip,
.top-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 700;
  white-space: nowrap;
}

.selection-pill {
  color: #fff;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.16);
}

/*
  Module 4: role selector and role detail presentation.
*/
.role-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 18px;
}

.role-pill {
  --role-color: rgba(255, 255, 255, 0.92);
  --role-surface: rgba(255, 255, 255, 0.08);
  --role-border: rgba(255, 255, 255, 0.12);
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid var(--role-border);
  border-radius: 999px;
  background: var(--role-surface);
  color: var(--role-color);
  font-size: 0.8rem;
  font-weight: 700;
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease, background 0.22s ease;
}

.role-pill:hover,
.role-pill:focus-visible,
.mode-button:hover,
.mode-button:focus-visible,
.hero-link:hover,
.hero-link:focus-visible,
.language-option:hover,
.language-option:focus-visible,
.primary-button:hover,
.primary-button:focus-visible,
.secondary-button:hover,
.secondary-button:focus-visible,
.text-link:hover,
.text-link:focus-visible {
  transform: translateY(-1px);
}

.role-pill:focus-visible,
.mode-button:focus-visible,
.hero-link:focus-visible,
.language-option:focus-visible,
.field-input:focus-visible,
.primary-button:focus-visible,
.secondary-button:focus-visible,
.text-link:focus-visible,
.otp-input:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

.role-pill-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 6px rgba(255, 255, 255, 0.08);
}

.role-pill {
  position: relative;
  overflow: hidden;
}

.role-pill.selected {
  transform: translateY(-2px) scale(1.03);
  border-color: currentColor;
  background: rgba(255, 255, 255, 0.16);
  box-shadow:
    0 0 0 1px currentColor inset,
    0 16px 32px rgba(5, 14, 12, 0.28),
    0 0 18px rgba(255, 255, 255, 0.12);
}

.role-pill.active:not(.selected) {
  border-color: rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.12);
}

.role-pill.selected::before {
  opacity: 1;
}

.role-pill.selected .role-pill-dot {
  transform: scale(1.2);
  box-shadow:
    0 0 0 7px rgba(255, 255, 255, 0.10),
    0 0 12px currentColor;
}

.role-pill-dot {
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.role-detail-card {
  position: relative;
  overflow: hidden;
  flex: 1;
  min-height: 250px;
  padding: 20px;
  border-radius: 26px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.04));
}

.role-detail-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 10px;
}

.role-detail-badge {
  width: 16px;
  height: 42px;
  border-radius: 999px;
  background: currentColor;
  opacity: 0.86;
}

.role-detail-kicker {
  margin: 0 0 4px;
  color: rgba(215, 255, 237, 0.66);
}

.role-detail-title {
  font-size: 1.1rem;
  color: #fff;
}

.role-detail-summary,
.role-detail-list {
  margin: 0;
  color: rgba(238, 247, 242, 0.86);
  line-height: 1.72;
}

.role-detail-list {
  padding-left: 1.2rem;
}

.role-detail-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

/*
  Module 5: hero overview stats and footer actions.
*/
.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.stat-value {
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #fff;
}

.stat-label {
  font-size: 0.7rem;
  color: rgba(222, 245, 235, 0.74);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.hero-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 20px;
}

.mode-switch {
  display: inline-flex;
  gap: 8px;
  padding: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.mode-button,
.hero-link,
.language-option,
.primary-button,
.secondary-button,
.text-link {
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease, background 0.22s ease, border-color 0.22s ease, color 0.22s ease;
}

.mode-button {
  min-height: 38px;
  padding: 0 14px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: rgba(233, 247, 240, 0.76);
  font-weight: 700;
}

.mode-button.active {
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
}

.hero-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 16px;
  border-radius: 999px;
  color: #fff;
  text-decoration: none;
  font-weight: 700;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
}


.overview-capabilities {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  flex: 1;
}

.capability-card {
  display: grid;
  gap: 6px;
  padding: 14px 15px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  min-height: 82px;
}

.capability-title {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ffffff;
  line-height: 1.25;
}

.capability-subtitle {
  font-size: 0.8rem;
  line-height: 1.5;
  color: rgba(230, 244, 237, 0.76);
}

.stat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
  transition: all 0.35s ease;
}

.stat-card:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.25);
}

.stat-card:hover::after {
  opacity: 1;
}


.capability-card {
  position: relative;
  display: grid;
  gap: 6px;
  padding: 14px 15px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  min-height: 82px;
  overflow: hidden;
  transition: all 0.35s ease;
}

.capability-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg,
    transparent,
    rgba(115, 232, 193, 0.12),
    transparent
  );
  opacity: 0;
  transition: opacity 0.35s ease;
}

.capability-card::after {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  background: linear-gradient(120deg,
    rgba(115, 232, 193, 0.4),
    rgba(72, 179, 148, 0.2),
    transparent
  );
  opacity: 0;
  z-index: -1;
  transition: opacity 0.35s ease;
}

.capability-card:hover {
  transform: translateY(-6px) scale(1.02);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 24px 50px rgba(5, 18, 15, 0.35);
}

.capability-card:hover::before {
  opacity: 1;
}

.capability-card:hover::after {
  opacity: 1;
}


.mode-switch {
  position: relative;
  display: inline-flex;
  gap: 6px;
  padding: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(10px);
}

.mode-button {
  position: relative;
  min-height: 36px;
  padding: 0 14px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: rgba(233, 247, 240, 0.7);
  font-weight: 700;
  transition: all 0.3s ease;
}

.mode-button.active {
  color: #fff;
  background: linear-gradient(135deg, rgba(47,164,134,0.6), rgba(115,232,193,0.4));
  box-shadow: 0 10px 20px rgba(47,164,134,0.3);
}

.mode-button:hover {
  color: #fff;
  background: rgba(255,255,255,0.12);
}


.hero-link {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 18px;
  border-radius: 999px;
  color: #fff;
  text-decoration: none;
  font-weight: 700;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
  transition: all 0.35s ease;
}

.hero-link::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg,
    transparent,
    rgba(115,232,193,0.2),
    transparent
  );
  opacity: 0;
  transition: opacity 0.35s ease;
}

.hero-link:hover {
  transform: translateY(-2px);
  border-color: rgba(115,232,193,0.6);
  box-shadow: 0 18px 40px rgba(0,0,0,0.35);
}

.hero-link:hover::before {
  opacity: 1;
}

/*
  Module 6: auth pane shell, top bar, and card container.
*/
.auth-pane {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: clamp(22px, 4vw, 40px);
}

/* Ink canvas: fills the auth-pane, lives behind all content. */
.ink-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}

.auth-shell {
  position: relative;
  z-index: 1;
  width: min(100%, 560px);
  display: grid;
  justify-items: center;
  gap: 18px;
}

.auth-topbar {
  width: min(100%, 520px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
}

.top-badges {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.top-badge {
  color: var(--emerald-700);
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(31, 93, 79, 0.08);
  box-shadow: 0 8px 24px rgba(12, 41, 34, 0.06);
}

.language-switcher {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.language-option {
  min-height: 34px;
  padding: 0 11px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.56);
  color: var(--stone-700);
  font-size: 0.82rem;
  font-weight: 700;
}

.language-option.active {
  color: #fff;
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  box-shadow: 0 14px 24px rgba(31, 93, 79, 0.16);
}

.auth-card {
  position: relative;
  overflow: hidden;
  width: min(100%, 520px);
  border-radius: 32px;
  padding: 28px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 248, 0.94));
  border: 1px solid rgba(255, 255, 255, 0.78);
  box-shadow: var(--shadow-card);
}

.auth-card::before {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0));
}

.auth-card-glow {
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 200px;
  background: radial-gradient(circle at top left, rgba(47, 164, 134, 0.16), transparent 58%);
  pointer-events: none;
}

/*
  Module 7: auth progress and shared header presentation.
*/
.auth-progress {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 26px;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--stone-500);
}

.progress-item.active {
  color: var(--stone-900);
}

.progress-item.current .progress-dot {
  box-shadow: 0 12px 26px rgba(31, 93, 79, 0.18);
}

.progress-dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  font-size: 0.9rem;
  font-weight: 800;
  background: rgba(31, 93, 79, 0.08);
  color: inherit;
}

.progress-item.active .progress-dot {
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  color: #fff;
}

.progress-label {
  font-size: 0.88rem;
  font-weight: 700;
}

.progress-line {
  flex: 1;
  height: 2px;
  margin: 0 14px;
  border-radius: 999px;
  background: rgba(16, 33, 29, 0.08);
}

.progress-line.active {
  background: linear-gradient(90deg, var(--emerald-700), var(--emerald-400));
}

.step-panel {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  margin: 0 auto;
  display: grid;
  gap: 22px;
}

.auth-header {
  display: grid;
  justify-items: center;
  gap: 14px;
  text-align: center;
}

.auth-header--compact {
  gap: 12px;
}

.auth-logo-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
}

.auth-logo {
  width: 62px;
  height: 62px;
  background: linear-gradient(180deg, rgba(39, 132, 109, 0.12), rgba(39, 132, 109, 0.04));
  border: 1px solid rgba(39, 132, 109, 0.1);
}

.auth-logo--small {
  width: 54px;
  height: 54px;
}

.auth-logo-copy {
  display: grid;
  gap: 6px;
}

.auth-kicker,
.role-detail-kicker {
  color: var(--emerald-700);
}

.auth-title {
  font-size: clamp(1.55rem, 2.6vw, 2rem);
  color: var(--stone-900);
}

.auth-subtitle {
  margin: 0;
  color: var(--stone-700);
  line-height: 1.7;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.meta-row--stack {
  justify-content: center;
  align-items: center;
}

.meta-chip {
  color: var(--stone-900);
  border: 1px solid rgba(16, 33, 29, 0.08);
  background: rgba(39, 132, 109, 0.08);
}

.meta-chip--neutral {
  background: rgba(16, 33, 29, 0.05);
  color: var(--stone-700);
}

/*
  Module 8: form fields and action buttons.
*/
.auth-form {
  width: 100%;
  display: grid;
  gap: 18px;
}

.login-mode-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  padding: 6px;
  border: 1px solid rgba(16, 33, 29, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.62);
}

.login-mode-button {
  min-height: 42px;
  border: 0;
  border-radius: 14px;
  background: transparent;
  color: var(--stone-700);
  font-size: 0.9rem;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
}

.login-mode-button.active {
  color: #fff;
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  box-shadow: 0 12px 22px rgba(31, 93, 79, 0.18);
}

.login-mode-button:focus-visible {
  outline: 3px solid rgba(72, 165, 140, 0.22);
  outline-offset: 2px;
}

.field-block {
  display: grid;
  gap: 10px;
}

.field-label {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--stone-900);
}

.field-shell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 58px;
  padding: 0 16px;
  border-radius: 18px;
  border: 1px solid var(--border-soft);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.42);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.field-shell:focus-within {
  border-color: rgba(39, 132, 109, 0.38);
  box-shadow: var(--shadow-focus);
  background: #fff;
}

.field-shell.is-error {
  border-color: rgba(210, 75, 75, 0.34);
}


.field-input {
  width: 100%;
  border: 0;
  background: transparent;
  font-size: 1rem;
  color: var(--stone-900);
}

.field-input::placeholder {
  color: rgba(54, 81, 74, 0.54);
}

.field-help {
  color: var(--stone-500);
  line-height: 1.6;
}

.primary-button,
.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 54px;
  padding: 0 18px;
  border-radius: 18px;
  font-size: 0.98rem;
  font-weight: 800;
}

.primary-button {
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, var(--emerald-700), var(--emerald-500));
  box-shadow: 0 18px 28px rgba(31, 93, 79, 0.2);
}

.primary-button:disabled,
.secondary-button:disabled,
.text-link:disabled {
  cursor: not-allowed;
  transform: none;
  opacity: 0.6;
  box-shadow: none;
}

.secondary-button {
  border: 1px solid rgba(16, 33, 29, 0.1);
  color: var(--stone-700);
  background: rgba(255, 255, 255, 0.74);
}

.text-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--emerald-700);
  font-size: 0.9rem;
  font-weight: 800;
}

.button-spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
}

/*
  Module 9: OTP inputs, feedback blocks, and support row.
*/
.otp-footer-copy p,
.support-row {
  margin: 0;
  color: var(--stone-700);
  line-height: 1.68;
}

.otp-box {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.otp-input {
  min-width: 0;
  height: 62px;
  border-radius: 18px;
  border: 1px solid rgba(16, 33, 29, 0.1);
  background: rgba(255, 255, 255, 0.92);
  text-align: center;
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--stone-900);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.44);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.otp-input:focus {
  border-color: rgba(39, 132, 109, 0.38);
  transform: translateY(-1px);
}

.otp-input-error,
.otp-box.has-error .otp-input {
  border-color: rgba(210, 75, 75, 0.34);
  background: rgba(255, 245, 245, 0.94);
}

.otp-box.is-complete .otp-input {
  border-color: rgba(39, 132, 109, 0.22);
  box-shadow:
    0 10px 22px rgba(31, 93, 79, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.44);
}

.otp-box.shaking {
  animation: shake 0.42s ease;
}

.otp-action-stack {
  display: grid;
  gap: 12px;
}

.otp-secondary-actions {
  display: flex;
  justify-content: center;
}

.status-message,
.error-message {
  margin: 0;
  padding: 13px 15px;
  border-radius: 16px;
  font-size: 0.92rem;
  line-height: 1.55;
}

.status-message {
  color: var(--emerald-700);
  border: 1px solid rgba(39, 132, 109, 0.12);
  background: rgba(39, 132, 109, 0.08);
}

.error-message {
  color: #b33d3d;
  border: 1px solid rgba(210, 75, 75, 0.18);
  background: rgba(255, 235, 235, 0.76);
}

.support-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.support-row a {
  color: var(--emerald-700);
  font-weight: 800;
  text-decoration: none;
}

.support-row a:hover,
.support-row a:focus-visible {
  text-decoration: underline;
}

/*
  Module 10: role theme utilities and transition effects.
*/
.role-theme--student {
  color: #6fc6ff;
}

.role-theme--mentor {
  color: #75d9b7;
}

.role-theme--supervisor {
  color: #ffd37b;
}

.role-theme--teacher {
  color: #ffd37b;
}

.role-theme--admin {
  color: #c5b0ff;
}

.role-theme--default {
  color: #9fddd0;
}

.content-fade-enter-active,
.content-fade-leave-active,
.message-slide-enter-active,
.message-slide-leave-active {
  transition: opacity 0.24s ease, transform 0.24s ease;
}

.content-fade-enter-from,
.content-fade-leave-to,
.message-slide-enter-from,
.message-slide-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@keyframes heroSlideshow {
  0% {
    opacity: 0;
  }
  6% {
    opacity: 1;
  }
  24% {
    opacity: 1;
  }
  30% {
    opacity: 0;
  }
  100% {
    opacity: 0;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes shake {
  0%,
  100% {
    transform: translateX(0);
  }
  25% {
    transform: translateX(-6px);
  }
  50% {
    transform: translateX(6px);
  }
  75% {
    transform: translateX(-4px);
  }
}

/*
  Module 11: responsive behavior.
*/
@media (max-width: 1200px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .hero-pane {
    min-height: auto;
  }

  .hero-content {
    min-height: auto;
  }

  .hero-grid {
    grid-template-columns: 1fr;
  }

  .auth-pane {
    min-height: auto;
    padding-top: 0;
  }
}

@media (max-width: 760px) {
  .hero-content,
  .auth-pane {
    padding: 20px;
  }

  .overview-capabilities {
  grid-template-columns: 1fr;
  }

  .overview-flow-track {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-brand-row,
  .auth-topbar,
  .meta-row--stack,
  .hero-footer {
    flex-direction: column;
    align-items: center;
  }

  .hero-stats {
    grid-template-columns: 1fr;
  }

  .auth-card {
    padding: 22px 18px;
    border-radius: 24px;
  }

  .otp-box {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

/*
  Module 12: reduced-motion accessibility support.
*/
@media (prefers-reduced-motion: reduce) {
  .hero-slide-image,
  .button-spinner,
  .otp-box.shaking,
  .content-fade-enter-active,
  .content-fade-leave-active,
  .message-slide-enter-active,
  .message-slide-leave-active,
  .role-pill,
  .mode-button,
  .hero-link,
  .language-option,
  .primary-button,
  .secondary-button,
  .text-link,
  .otp-input {
    animation: none !important;
    transition: none !important;
  }
}


/*
  Module 13: immersive motion polish and premium interaction upgrades.
*/

.login-shell {
  --pointer-x: 50%;
  --pointer-y: 32%;
  isolation: isolate;
}

.login-shell::before,
.login-shell::after {
  content: '';
  position: fixed;
  inset: auto;
  pointer-events: none;
  z-index: 0;
  border-radius: 50%;
  filter: blur(48px);
  transition: transform 0.22s ease, opacity 0.22s ease;
}

.login-shell::before {
  top: calc(var(--pointer-y) * 0.18);
  left: calc(var(--pointer-x) * 0.16);
  width: 280px;
  height: 280px;
  background: radial-gradient(circle, rgba(103, 228, 193, 0.24), transparent 72%);
  transform: translate(-50%, -50%);
  opacity: 0;
}

.login-shell.pointer-inside::before {
  opacity: 0.5;
}

.login-shell::after {
  right: 5%;
  bottom: 4%;
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, rgba(20, 94, 79, 0.16), transparent 72%);
  opacity: 0.5;
}

.hero-stage::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(115deg, rgba(255, 255, 255, 0.06), transparent 30%),
    linear-gradient(0deg, rgba(255, 255, 255, 0.03), transparent 42%);
  pointer-events: none;
}


.interactive-surface {
  --pointer-x: 50%;
  --pointer-y: 50%;
  transform-style: preserve-3d;
  transition: transform 0.26s ease, box-shadow 0.26s ease, border-color 0.26s ease, background 0.26s ease;
}

.interactive-surface::after {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  pointer-events: none;
  background:
    radial-gradient(
      240px circle at var(--pointer-x) var(--pointer-y),
      rgba(255, 255, 255, 0.20),
      rgba(255, 255, 255, 0.10) 18%,
      transparent 56%
    );
  opacity: 0;
  transition: opacity 0.22s ease;
}

.interactive-surface:hover {
  transform: translateY(-4px);
}

.interactive-surface:hover::after {
  opacity: 1;
}

.hero-card--primary,
.hero-card--secondary,
.auth-card {
  backdrop-filter: blur(24px);
}

.hero-card--primary:hover,
.hero-card--secondary:hover {
  border-color: rgba(214, 255, 239, 0.24);
  box-shadow:
    0 34px 84px rgba(3, 12, 10, 0.46),
    0 0 0 1px rgba(255, 255, 255, 0.08) inset;
}

.auth-card:hover {
  border-color: rgba(47, 164, 134, 0.18);
  box-shadow:
    0 30px 70px rgba(12, 41, 34, 0.18),
    0 0 0 1px rgba(255, 255, 255, 0.38) inset;
}

.hero-brand-row,
.hero-grid,
.auth-shell {
  position: relative;
  z-index: 1;
}

.selection-pill,
.meta-chip,
.top-badge,
.language-option,
.mode-button,
.hero-link,
.primary-button,
.secondary-button,
.text-link,
.otp-input,
.field-shell,
.stat-card,
.capability-card {
  will-change: transform;
}

.role-pill {
  backdrop-filter: blur(10px);
}

.role-pill:hover,
.role-pill:focus-visible {
  border-color: rgba(255, 255, 255, 0.24);
  background: rgba(255, 255, 255, 0.14);
  box-shadow: 0 18px 38px rgba(4, 14, 12, 0.22);
}

.role-detail-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.10), rgba(255, 255, 255, 0.04)),
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.14), transparent 36%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.stat-card,
.capability-card {
  backdrop-filter: blur(12px);
}

.capability-card:hover {
  border-color: rgba(115, 232, 193, 0.22);
}

.auth-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 251, 248, 0.92)),
    radial-gradient(circle at top left, rgba(115, 232, 193, 0.12), transparent 34%);
}

.auth-card-glow {
  height: 240px;
  background:
    radial-gradient(circle at top left, rgba(47, 164, 134, 0.18), transparent 54%),
    radial-gradient(circle at top right, rgba(103, 228, 193, 0.12), transparent 36%);
}

.top-badge {
  backdrop-filter: blur(10px);
}

.language-option {
  position: relative;
  overflow: hidden;
}

.language-option::before,
.primary-button::before,
.secondary-button::before,
.hero-link::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 18%, rgba(255, 255, 255, 0.28), transparent 72%);
  opacity: 0;
  transition: opacity 0.22s ease;
}

.language-option:hover::before,
.primary-button:hover::before,
.secondary-button:hover::before,
.hero-link:hover::after {
  opacity: 1;
}

.progress-dot {
  position: relative;
  overflow: hidden;
}

.progress-dot::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.36), transparent 52%);
  opacity: 0.78;
}

.field-shell {
  position: relative;
  overflow: hidden;
}

.field-shell::after {
  content: '';
  position: absolute;
  inset: auto 12px 0 12px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(47, 164, 134, 0.4), transparent);
  opacity: 0;
  transform: translateY(4px);
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.field-shell:focus-within::after {
  opacity: 1;
  transform: translateY(0);
}

.primary-button,
.secondary-button {
  position: relative;
  overflow: hidden;
}

.primary-button {
  background:
    linear-gradient(135deg, rgba(18, 96, 80, 1), rgba(47, 164, 134, 0.96)),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.14), transparent 28%);
  box-shadow:
    0 18px 36px rgba(31, 93, 79, 0.20),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.primary-button:hover,
.primary-button:focus-visible {
  box-shadow:
    0 24px 42px rgba(31, 93, 79, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.secondary-button {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 251, 249, 0.92)),
    radial-gradient(circle at top left, rgba(47, 164, 134, 0.08), transparent 32%);
}

.otp-box {
  position: relative;
}

.otp-input {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 247, 0.96)),
    radial-gradient(circle at top left, rgba(47, 164, 134, 0.08), transparent 34%);
}

.otp-input:hover,
.otp-input:focus-visible {
  transform: translateY(-2px);
  box-shadow:
    0 12px 26px rgba(31, 93, 79, 0.14),
    var(--shadow-focus);
}


.status-message,
.error-message {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  padding: 12px 14px;
}

.status-message::before,
.error-message::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.18), transparent);
  opacity: 0.4;
}

.support-row {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(16, 33, 29, 0.03);
  border: 1px solid rgba(16, 33, 29, 0.05);
}

@keyframes ambientFloatA {
  0%, 100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(18px, -14px, 0);
  }
}

@keyframes ambientFloatB {
  0%, 100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(-18px, 16px, 0);
  }
}

@media (max-width: 1120px) {
  .interactive-surface:hover {
    transform: none;
  }
}



.shell-aurora {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.shell-aurora-orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(18px);
  opacity: 0.78;
  mix-blend-mode: screen;
  will-change: transform;
}

.shell-aurora-orb--one {
  top: 6%;
  left: -3%;
  width: 320px;
  height: 320px;
  background: radial-gradient(circle, rgba(126, 255, 223, 0.32), rgba(74, 209, 176, 0.08) 58%, transparent 76%);
  animation: ambientFloatA 16s ease-in-out infinite;
}

.shell-aurora-orb--two {
  right: 10%;
  top: 12%;
  width: 260px;
  height: 260px;
  background: radial-gradient(circle, rgba(193, 224, 255, 0.22), rgba(116, 184, 255, 0.06) 54%, transparent 76%);
  animation: ambientFloatB 19s ease-in-out infinite;
}

.shell-aurora-orb--three {
  right: -4%;
  bottom: 2%;
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, rgba(124, 255, 217, 0.18), rgba(32, 124, 103, 0.06) 52%, transparent 78%);
  animation: ambientFloatA 22s ease-in-out infinite reverse;
}

.shell-mesh {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at center, rgba(0, 0, 0, 0.64), transparent 82%);
  opacity: 0.18;
}

.hero-pane,
.auth-pane {
  position: relative;
  z-index: 1;
}

.hero-card,
.auth-card,
.role-detail-card,
.field-shell,
.language-switcher,
.mode-switch {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.hero-card::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.16), transparent 34%);
  opacity: 0.58;
}

.interactive-surface {
  --pointer-x: 50%;
  --pointer-y: 50%;
  --rotate-x: 0deg;
  --rotate-y: 0deg;
  --glow-opacity: 0;
  transform-style: preserve-3d;
  transform: perspective(1400px) rotateX(var(--rotate-x)) rotateY(var(--rotate-y)) translate3d(0, 0, 0);
  transition:
    transform 320ms cubic-bezier(0.2, 0.8, 0.2, 1),
    box-shadow 320ms cubic-bezier(0.2, 0.8, 0.2, 1),
    border-color 280ms ease,
    background 280ms ease;
}

.interactive-surface::after {
  opacity: var(--glow-opacity, 0);
  background:
    radial-gradient(
      240px circle at var(--pointer-x) var(--pointer-y),
      rgba(255, 255, 255, 0.24),
      rgba(255, 255, 255, 0.10) 18%,
      transparent 58%
    );
}

.interactive-surface:hover {
  transform: perspective(1400px) rotateX(var(--rotate-x)) rotateY(var(--rotate-y)) translate3d(0, -8px, 0);
}

.interactive-surface:hover::after {
  opacity: calc(var(--glow-opacity, 0) + 0.12);
}

.role-selector {
  align-items: center;
}

.role-pill {
  min-height: 42px;
  padding: 0 14px;
  letter-spacing: 0.01em;
}

.role-pill::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 18%, rgba(255, 255, 255, 0.18), transparent 74%);
  opacity: 0;
  transition: opacity 0.24s ease;
}

.role-pill:hover::after,
.role-pill:focus-visible::after,
.role-pill.active::after,
.role-pill.selected::after {
  opacity: 1;
}

.role-pill:active {
  transform: translateY(0) scale(0.99);
}

.role-detail-card {
  position: relative;
  isolation: isolate;
}

.role-detail-glow {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background:
    radial-gradient(circle at 88% 16%, rgba(255, 255, 255, 0.18), transparent 24%),
    radial-gradient(circle at 18% 100%, rgba(117, 217, 183, 0.12), transparent 32%);
  opacity: 0.9;
}

.role-detail-header,
.role-detail-summary,
.role-detail-list {
  position: relative;
  z-index: 1;
}

.hero-stats,
.overview-capabilities {
  position: relative;
  z-index: 1;
}

.stat-card,
.capability-card {
  border-color: rgba(255, 255, 255, 0.10);
}

.auth-topbar {
  position: relative;
  z-index: 1;
}

.language-switcher {
  padding: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.48);
  box-shadow:
    0 14px 30px rgba(12, 41, 34, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.54);
}

.language-option {
  min-width: 64px;
}

.language-option.active {
  transform: translateY(-1px);
}

.mode-switch {
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.10),
    0 10px 24px rgba(4, 15, 13, 0.12);
}

.mode-button {
  min-width: 86px;
}

.auth-card {
  isolation: isolate;
}

.auth-card::after {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.44);
  pointer-events: none;
}

.auth-card-glow {
  animation: ambientFloatA 13s ease-in-out infinite;
}

.auth-card-noise {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    radial-gradient(rgba(16, 33, 29, 0.035) 0.8px, transparent 0.8px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.10), transparent 24%);
  background-size: 18px 18px, auto;
  opacity: 0.46;
}

.auth-progress,
.step-panel {
  position: relative;
  z-index: 1;
}

.progress-item {
  transition: transform 0.24s ease, color 0.24s ease;
}

.progress-item.current {
  transform: translateY(-1px);
}

.field-shell {
  gap: 12px;
  min-height: 62px;
  padding: 0 18px 0 16px;
}

.field-leading-icon {
  position: relative;
  width: 12px;
  height: 12px;
  flex: 0 0 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(31, 93, 79, 0.88), rgba(103, 228, 193, 0.92));
  box-shadow:
    0 0 0 6px rgba(47, 164, 134, 0.10),
    0 10px 18px rgba(31, 93, 79, 0.16);
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.field-leading-icon::after {
  content: '';
  position: absolute;
  inset: -7px;
  border-radius: inherit;
  border: 1px solid rgba(47, 164, 134, 0.16);
  opacity: 0.9;
}

.field-shell:focus-within .field-leading-icon {
  transform: scale(1.08);
  box-shadow:
    0 0 0 8px rgba(47, 164, 134, 0.12),
    0 12px 24px rgba(31, 93, 79, 0.20);
}

.field-input {
  letter-spacing: 0.01em;
}

.primary-button,
.secondary-button {
  min-height: 56px;
  border-radius: 20px;
}

.primary-button:active,
.secondary-button:active,
.hero-link:active,
.language-option:active,
.mode-button:active {
  transform: translateY(0) scale(0.99);
}

.otp-progress-rail {
  position: relative;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(16, 33, 29, 0.06);
  box-shadow: inset 0 1px 2px rgba(16, 33, 29, 0.06);
}

.otp-progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background:
    linear-gradient(90deg, rgba(31, 93, 79, 0.94), rgba(103, 228, 193, 0.92)),
    linear-gradient(120deg, rgba(255, 255, 255, 0.16), transparent 72%);
  box-shadow: 0 10px 18px rgba(31, 93, 79, 0.18);
  transition: width 0.3s cubic-bezier(0.2, 0.8, 0.2, 1), box-shadow 0.24s ease;
}

.otp-input {
  backdrop-filter: blur(10px);
}

.otp-input-filled {
  border-color: rgba(39, 132, 109, 0.20);
  box-shadow:
    0 10px 22px rgba(31, 93, 79, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.50);
}

.otp-box.is-complete .otp-progress-fill {
  box-shadow:
    0 14px 24px rgba(31, 93, 79, 0.18),
    0 0 0 1px rgba(255, 255, 255, 0.20) inset;
}

.status-message,
.error-message,
.support-row {
  backdrop-filter: blur(10px);
}

.support-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 760px) {
  .shell-aurora-orb--one {
    width: 240px;
    height: 240px;
  }

  .shell-aurora-orb--two {
    width: 200px;
    height: 200px;
  }

  .shell-aurora-orb--three {
    width: 260px;
    height: 260px;
  }

  .language-switcher {
    width: 100%;
  }

  .language-option {
    flex: 1 1 auto;
  }

  .support-row {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-shell::before,
  .login-shell::after,
  .interactive-surface,
  .interactive-surface::after,
  .language-option::before,
  .primary-button::before,
  .secondary-button::before,
  .hero-link::after,
  .shell-aurora-orb,
  .auth-card-glow,
  .field-leading-icon,
  .role-detail-glow {
    animation: none !important;
    transition: none !important;
    transform: none !important;
  }

  /* Hide WebGL ink canvas for users who prefer reduced motion. */
  .ink-canvas {
    display: none !important;
  }
}

</style>
