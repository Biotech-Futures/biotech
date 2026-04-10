<template>
  <!--
   * @file LoginPage.vue
   * @description LoginPage.vue is the unified entry page for the BIOTech Futures mentoring platform. It combines role-guided access selection, passwordless email-to-OTP authentication, multilingual support, and branded platform presentation in one structured login experience.
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
   * Purpose: Provide a structured and user-friendly entry point for students, mentors, supervisors, and administrators to sign in with email OTP while understanding the platform context before entering the system.
   * Scope: Covers the left hero showcase, role selection and preview, language switching, email submission, OTP verification, resend flow, and post-login navigation.
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
   * - Major revisions: 4
   * - Minor revisions: 3
   *
   * Last Modified: 2026-04-07
   * Modified By: CS17-1 Frontend Team
   *
   * @文件 LoginPage.vue
   * @描述 LoginPage.vue 是 BIOTech Futures 导师平台的统一入口页面。该页面将角色引导式访问选择、无密码邮箱验证码登录、多语言支持以及平台品牌展示整合到同一个结构化登录体验中。
   * @作者 Shiqi Fang
   * @作者 Jiachen Ding
   * @作者 Qin Chen
   * @版本 1.4.0
   *
   * 项目名称: Group Based 5703 Capstone Project
   * 小组编号: CS17-1
   * 负责方向: CS17-1 Frontend Team
   *
   * 组件类型: 前端页面组件
   * 文件角色: 统一的角色引导式登录入口页
   * 主要用途: 为学生、导师、监督老师和管理员提供一个结构清晰、易于理解的登录入口，在进入系统前先完成角色感知、平台理解和邮箱 OTP 验证。
   * 作用范围: 覆盖左侧展示区、角色选择与预览、多语言切换、邮箱提交、OTP 校验、验证码重发以及登录后跳转。
   *
   * 核心职责:
   * - 展示平台品牌、角色化访问入口与平台概览信息
   * - 支持 LTR 与 RTL 的多语言登录体验
   * - 处理完整的邮箱到 OTP 的无密码登录流程
   * - 为不同身份提供角色化登录文案与提示
   * - 统一登录反馈、加载状态与 OTP 输入交互体验
   *
   * 主要依赖:
   * - Vue 3 Composition API
   * - Vue Router
   * - Pinia auth store
   * - 登录语言配置数据
   * - 登录背景配置数据
   * - CSRF 请求头辅助工具
   * - 字符串与本地存储工具
   *
   * 修改统计:
   * - 大改次数: 4
   * - 小改次数: 3
   *
   * 最后修改时间: 2026-04-07
   * 修改人: CS17-1 Frontend Team
   -->

  <!-- Page shell and two-column layout. -->
  <!-- 页面总容器与左右双栏布局。 
        1.dir和class动态绑定HTML的dir属性，即文字方向属性，为了适配阿拉伯语言
        2.pointermove锁定鼠标指针，持续触发，通过计算坐标激活跟随性的光斑
        3.pointerleave复位不然光斑会卡住
        4.loginShellRef是为了获取鼠标坐标而给DOM命名作为搭载节点-->
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
    <!-- Left hero pane: background stage, role selection, and platform overview. -->
    <!-- 左侧展示区：背景舞台、角色选择与平台概览。 -->
    <section class="hero-pane">
      <!-- Background stage with slideshow and emerald mode. -->
      <!-- 背景舞台，承载图片轮播和绿色模式。 -->
      <div class="hero-stage" aria-hidden="true">
        <!-- Slideshow scene. -->
        <!-- 图片轮播场景。 
              1.active，Vue的动态绑定，是original背景css就是加上active的字符串，否则就没有active
              2.:src即source,访问的是存在image变量里的值，也就是地址，才能获取到真实图片
                类比一下静态写法：<img src="/images/fixed-banner.jpg" />
              3.alt是给用户无障碍阅读用的，这里没有意义所以就不写
              4.style动态行内样式，每个图片错开时间展示-->
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
        <!-- 绿色视觉模式场景。 -->
        <div class="hero-scene hero-scene--emerald" :class="{ active: activeLeftBackground === 'green' }">
          <div class="hero-green-image" :style="{ backgroundImage: `url(${backgroundImages2})` }"></div>
        </div>

        <!-- Readability overlay and subtle texture. -->
        <!-- 提升可读性的遮罩层与轻纹理。 -->
        <div class="hero-overlay"></div>
        <div class="hero-noise"></div>
      </div>

      <!-- Foreground hero content. -->
      <!-- 前景展示内容。 -->
      <div class="hero-content">
        <!-- Brand block. -->
        <!-- 品牌展示区。 -->
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
        <!-- 左侧主体卡片网格。 -->
        <div class="hero-grid">
          <!-- Role-guided access card. -->
          <!-- 角色引导式访问卡片。 -->
          <article
            class="hero-card hero-card--primary"
            @pointermove="handleCardPointerMove"
          >
            <div class="section-head">
              <div>
                <span class="section-kicker">{{ t('accessMode') }}</span>
                <h2 class="section-title">{{ t('chooseRoleTitle') }}</h2>
              </div>

              <!-- Persistent role hint for the selected access identity. -->
              <!-- 当前选中访问身份的固定提示。 -->
              <span class="selection-pill" :class="roleThemeClass(selectedLoginRole)">
                {{ selectedRoleLoginHint }}
              </span>
            </div>

            <!-- Role selector. -->
            <!-- 角色选择器。 -->
            <!-- Click selects the login identity. Hover or focus previews the role content. -->
            <!-- 点击用于确定登录身份，悬停或聚焦用于预览角色内容。 -->
            <div
              class="role-selector"
              aria-label="Portal roles"
            >
              <button
                v-for="item in rolePreviewItems"
                :key="item.key"
                type="button"
                class="role-pill"
                :class="[
                  roleThemeClass(item.key),
                  {
                    selected: selectedLoginRole === item.key
                  }
                ]"
                :aria-pressed="selectedLoginRole === item.key"
                @mouseenter="previewLoginRole(item.key)"
                @mouseleave="clearPreviewRole"
                @focus="previewLoginRole(item.key)"
                @blur="clearPreviewRole"
                @click="selectLoginRole(item.key)"
              >
                <span class="role-pill-dot"></span>
                <span>{{ t(item.labelKey) }}</span>
              </button>
            </div>

            <!-- Role detail card. -->
            <!-- 角色详情卡片。 -->
            <!-- The displayed data follows preview first, then selected state as fallback. -->
            <!-- 显示内容优先跟随预览状态，未预览时回退到当前选中角色。 -->
            <transition name="content-fade" mode="out-in">
              <div :key="displayedRoleKey" class="role-detail-card" :class="roleThemeClass(displayedRoleKey)">
                <div class="role-detail-header">
                  <div class="role-detail-badge" :class="roleThemeClass(displayedRoleKey)"></div>

                  <div>
                    <p class="role-detail-kicker">{{ t('selectedAccess') }}</p>
                    <h3 class="role-detail-title">{{ displayedRoleData?.title || selectedRoleLoginLabel }}</h3>
                  </div>
                </div>

                <p class="role-detail-summary">
                  {{ displayedRoleData?.summary || selectedRoleLoginSubtitle }}
                </p>

                <ul class="role-detail-list">
                  <li v-for="point in displayedRoleData?.points?.slice(0, 3) || []" :key="point">
                    {{ point }}
                  </li>
                </ul>
              </div>
            </transition>
          </article>

          <!-- Platform overview card. -->
          <!-- 平台概览卡片。 -->
          <article
            class="hero-card hero-card--secondary interactive-surface"
            @pointermove="handleCardPointerMove"
          >
            <div class="section-head section-head--compact">
              <div>
                <span class="section-kicker">{{ t('platformOverview') }}</span>
                <h2 class="section-title overview-title">{{ t('platformGlanceTitle') }}</h2>
              </div>
            </div>

            <!-- Showcase metrics. -->
            <!-- 展示型指标卡。 -->
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
            <!-- 背景模式切换与官网入口。 -->
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
    <!-- 右侧认证区：顶部标签、语言切换、邮箱步骤、OTP 步骤。 -->
    <section class="auth-pane">
      <div class="auth-shell">
        <!-- Top bar with trust badges and language switcher. -->
        <!-- 顶部工具条，包含信任标签与语言切换器。 -->
        <div class="auth-topbar">
          <div class="top-badges">
            <span class="top-badge">{{ t('passwordless') }}</span>
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
        <!-- 登录卡片容器。 -->
        <div
          class="auth-card interactive-surface"
          @pointermove="handleCardPointerMove"
        >
          <div class="auth-card-glow"></div>

          <!-- Two-step progress indicator. -->
          <!-- 两步式认证进度指示器。 -->
          <div class="auth-progress" aria-label="Authentication progress">
            <div class="progress-item" :class="{ active: currentStepIndex >= 1, current: currentStepIndex === 1 }">
              <span class="progress-dot">1</span>
              <span class="progress-label">{{ t('emailStep') }}</span>
            </div>
            <div class="progress-line" :class="{ active: currentStepIndex === 2 }"></div>
            <div class="progress-item" :class="{ active: currentStepIndex >= 2, current: currentStepIndex === 2 }">
              <span class="progress-dot">2</span>
              <span class="progress-label">{{ t('otpStep') }}</span>
            </div>
          </div>

          <!-- Step transition wrapper. -->
          <!-- 步骤内容切换容器。 -->
          <transition name="content-fade" mode="out-in">
            <!-- Email step panel. -->
            <!-- 邮箱输入步骤。 -->
            <div v-if="currentStep === 'email'" key="email" class="step-panel">
              <header class="auth-header">
                <div class="auth-logo-wrap">
                  <div class="auth-logo">
                    <img :src="logo" alt="BIOTech Futures" />
                  </div>

                  <div class="auth-logo-copy">
                    <span class="auth-kicker">{{ t('secureAccess') }}</span>
                    <h2 class="auth-title">{{ selectedRoleLoginHeading }}</h2>
                  </div>
                </div>

                <p class="auth-subtitle">{{ selectedRoleLoginSubtitle }}</p>

                <!-- Meta chips for selected identity and auth method. -->
                <!-- 当前身份与认证方式标签。 -->
                <div class="meta-row">
                  <span class="meta-chip" :class="roleThemeClass(selectedLoginRole)">
                    {{ selectedRoleLoginHint }}
                  </span>
                  <span class="meta-chip meta-chip--neutral">{{ t('secureOtp') }}</span>
                </div>
              </header>

              <!-- Email submission form. -->
              <!-- 邮箱提交表单。 -->
              <form class="auth-form" @submit.prevent="handleLogin" novalidate>
                <div class="field-block">
                  <label class="field-label" for="login-email">{{ t('emailLabel') }}</label>

                  <!-- Field shell highlights focus and error state at container level. -->
                  <!-- 输入框容器负责表现聚焦态和错误态。 -->
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

                  <small class="field-help">{{ selectedRoleEmailHelper }}</small>
                </div>

                <button
                  type="submit"
                  class="primary-button"
                  :disabled="sendingCode || resendCountdown > 0"
                >
                  <span v-if="sendingCode" class="button-spinner" aria-hidden="true"></span>
                  <span v-else-if="resendCountdown > 0">{{ t('resendIn') }} {{ resendCountdown }}s</span>
                  <span v-else>{{ t('sendVerificationCode') }}</span>
                </button>
              </form>

              <!-- Step feedback messages. -->
              <!-- 当前步骤的反馈消息。 -->
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
            <!-- OTP 验证步骤。 -->
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
                <!-- OTP 步骤继续保留当前角色语境。 -->
                <div class="meta-row meta-row--stack">
                  <span class="meta-chip" :class="roleThemeClass(selectedLoginRole)">
                    {{ selectedRoleLoginHint }}
                  </span>
                  <button type="button" class="text-link" @click="goBackToEmailStep">
                    {{ t('changeEmail') }}
                  </button>
                </div>
              </header>

              <!-- OTP box. -->
              <!-- OTP 输入区。 -->
              <!-- Each box binds to one digit, while input, keyboard, focus, and paste are centrally handled in script helpers. -->
              <!-- 每个输入框只绑定一位数字，输入、键盘、聚焦和粘贴交互统一由 script 中的辅助函数处理。 -->
              <div class="otp-box" :class="{ 'has-error': otpErrorActive, shaking: otpShake }">
                <input
                  v-for="(digit, index) in otpDigits"
                  :key="index"
                  :ref="(el) => setOtpRef(el, index)"
                  v-model="otpDigits[index]"
                  type="text"
                  maxlength="1"
                  class="otp-input"
                  :class="{ 'otp-input-error': otpErrorActive }"
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
              <!-- OTP 主次操作区。 -->
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
              <!-- 帮助与支持入口。 -->
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
  依赖导入与外部模块。
*/
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

import { buildSessionHeaders } from '@/utils/csrf'
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
  LOGIN_ROLE_HINT_PREFIX_MAP,
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
  页面级实例。
*/
const router = useRouter()
const auth = useAuthStore()

/*
  Static configuration.
  静态配置常量。
*/
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const RESEND_SECONDS = 30

/*
  Shared page data.
  页面共享静态数据。
*/
const backgroundImages = LOGIN_BACKGROUND_IMAGES
const backgroundImages2 = LOGIN_BACKGROUND_IMAGES2
const slideDuration = LOGIN_SLIDE_DURATION
const languageOptions = LOGIN_LANGUAGE_OPTIONS
const messages = LOGIN_MESSAGES
const rolePreviewItems = LOGIN_ROLE_PREVIEW_ITEMS
const rolePreviewContent = LOGIN_ROLE_PREVIEW_CONTENT
const loginRoleHintPrefixMap = LOGIN_ROLE_HINT_PREFIX_MAP

/*
  Auth flow state.
  登录流程状态。
*/
const email = ref('')
const currentStep = ref('email')
const error = ref('')
const statusMessage = ref('')
const sendingCode = ref(false)
const verifyingCode = ref(false)
const resendingCode = ref(false)
const resendCountdown = ref(0)

/*
  OTP interaction state.
  OTP 交互状态。
*/
const otpDigits = ref(['', '', '', '', '', ''])
const otpRefs = ref([])
const otpShake = ref(false)
const otpErrorActive = ref(false)

/*
  UI presentation state.
  页面展示状态。
*/
const locale = ref('en')
const activeLeftBackground = ref('original')
const selectedLoginRole = ref(rolePreviewItems[0]?.key || 'student')
const previewLoginRoleKey = ref('')
const isShellPointerInside = ref(false)

/*
  DOM refs.
  DOM 引用。
*/
const emailInputRef = ref(null)
const loginShellRef = ref(null)

/*
  Runtime timer handles.
  运行时定时器句柄。
*/
let resendTimer = null
let otpErrorTimer = null
let otpAutoSubmitTimer = null

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

/*
  Role display state.
  角色显示状态。
*/
/*
  displayedRoleKey prefers hover-preview state and falls back to the currently selected login role.
  displayedRoleKey 优先跟随悬浮预览状态，未预览时回退到当前选中的登录角色。
*/

const selectedRoleData = computed(() => {
  return rolePreviewContent[locale.value]?.[selectedLoginRole.value]
    || rolePreviewContent.en?.[selectedLoginRole.value]
    || null
})

const displayedRoleKey = computed(() => previewLoginRoleKey.value || selectedLoginRole.value)

const displayedRoleData = computed(() => {
  return rolePreviewContent[locale.value]?.[displayedRoleKey.value]
    || rolePreviewContent.en?.[displayedRoleKey.value]
    || null
})

/*
  Role-aware login copy.
  角色化登录文案。
*/
const selectedRoleLoginLabel = computed(() => {
  const currentRoleItem = rolePreviewItems.find((item) => item.key === selectedLoginRole.value)
  return currentRoleItem ? t(currentRoleItem.labelKey) : ''
})

const selectedRoleLoginHeading = computed(() => `${t('signIn')} · ${selectedRoleLoginLabel.value}`)
const selectedRoleLoginSubtitle = computed(() => selectedRoleData.value?.summary || t('welcomeSubtitle'))
const selectedRoleEmailHelper = computed(() => selectedRoleData.value?.points?.[0] || t('emailHelper'))
const selectedRoleLoginHint = computed(() => {
  const prefix = loginRoleHintPrefixMap[locale.value] || loginRoleHintPrefixMap.en || t('selectedAccess')
  return `${prefix}: ${selectedRoleLoginLabel.value}`
})

/*
  Hero showcase metrics.
  左侧展示型统计数据。
*/
const showcaseStats = computed(() => [
  {
    value: String(rolePreviewItems.length).padStart(2, '0'),
    label: t('statsRoles')
  },
  {
    value: '10',
    label: t('statsWeeks')
  },
  {
    value: 'OTP',
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
  角色主题类名构建函数。
*/
const roleThemeClass = (roleKey) => `role-theme--${roleKey || 'default'}`

const previewLoginRole = (roleKey) => {
  previewLoginRoleKey.value = roleKey
}

const clearPreviewRole = () => {
  previewLoginRoleKey.value = ''
}

const updatePointerVariables = (element, clientX, clientY) => {
  if (!element) {
    return
  }

  const rect = element.getBoundingClientRect()
  const x = clientX - rect.left
  const y = clientY - rect.top

  element.style.setProperty('--pointer-x', `${x}px`)
  element.style.setProperty('--pointer-y', `${y}px`)
}

const handleCardPointerMove = (event) => {
  updatePointerVariables(event.currentTarget, event.clientX, event.clientY)
}

const handleShellPointerMove = (event) => {
  updatePointerVariables(loginShellRef.value, event.clientX, event.clientY)
  isShellPointerInside.value = true
}

const handleShellPointerLeave = () => {
  isShellPointerInside.value = false
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

/*
  Role selection persists the login identity and also refreshes the preview state.
  选择角色会记录当前登录身份，并同步刷新预览状态。
*/
const selectLoginRole = (roleKey) => {
  selectedLoginRole.value = roleKey
  previewLoginRoleKey.value = ''
  clearMessages()
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
  OTP 输入交互处理。
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
    允许常见系统快捷键，例如 Ctrl 或 Cmd 加 C、V、A、X。
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
  通用 JSON POST 请求辅助函数。
*/
const postJson = async (path, payload) => {
  return fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: buildSessionHeaders({
      includeCSRF: true
    }),
    credentials: 'include',
    body: JSON.stringify(payload)
  })
}

/*
  Resend countdown logic.
  重发验证码倒计时逻辑。
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
  OTP 错误反馈动画。
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
  步骤回退辅助函数。
*/
const goBackToEmailStep = async () => {
  currentStep.value = 'email'
  clearMessages()
  otpErrorActive.value = false
  otpShake.value = false
  clearOtpAutoSubmitTimer()
  await nextTick()
  emailInputRef.value?.focus()
}

/*
  Post-login route resolver.
  登录后跳转路由解析。
*/
const resolvePostLoginRoute = (user) => {
  const role = user?.role || user?.user_type || user?.role_name || ''

  switch (role) {
    case 'admin':
    case 'global_admin':
    case 'local_admin':
    case 'supervisor':
    case 'mentor':
    case 'student':
    default:
      return '/dashboard'
  }
}

/*
  Authentication flow: send code.
  认证主流程：发送验证码。
*/
const handleLogin = async () => {
  const normalizedEmail = email.value.trim().toLowerCase()

  clearMessages()

  if (!normalizedEmail) {
    error.value = t('errorEnterEmail')
    return
  }

  if (!isValidEmail(normalizedEmail)) {
    error.value = t('errorInvalidEmail')
    return
  }

  if (sendingCode.value) {
    return
  }

  if (resendCountdown.value > 0) {
    statusMessage.value = `${t('resendIn')} ${resendCountdown.value}s`
    return
  }

  email.value = normalizedEmail
  sendingCode.value = true

  try {
    const response = await postJson('/services/send-login-code/', {
      email: normalizedEmail,
      redirect_url: buildCallbackUrl()
    })

    if (!response.ok) {
      error.value = await parseErrorMessage(response, t('errorSendLink'))
      return
    }

    currentStep.value = 'otp'
    statusMessage.value = t('sendingSuccess')
    await resetOtpState()
    startResendCountdown()
  } catch (requestError) {
    console.error('Login error:', requestError)
    error.value = t('errorNetworkLogin')
  } finally {
    sendingCode.value = false
  }
}

/*
  Authentication flow: verify OTP.
  认证主流程：校验 OTP。
*/
const verifyOTP = async () => {
  const code = otpDigits.value.join('')

  if (code.length !== 6) {
    error.value = t('errorCompleteCode')
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

    statusMessage.value = t('signingIn')
    await auth.fetchUserData()
    await nextTick()

    const targetRoute = resolvePostLoginRoute(auth.user || null)

    try {
      await router.replace(targetRoute)
    } catch {
      window.location.href = `/#${targetRoute}`
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
  认证主流程：重发验证码。
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
  文档语言与方向同步。
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
  步骤切换后的焦点同步。
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
  恢复上次保存的语言设置。
*/
const savedLanguage = safeLocalStorageGet(LOGIN_LANGUAGE_KEY, 'en')
if (savedLanguage && languageOptions.some((item) => item.value === savedLanguage)) {
  locale.value = savedLanguage
}

/*
  Lifecycle: initial focus.
  生命周期：初始化聚焦。
*/
onMounted(async () => {
  await nextTick()
  emailInputRef.value?.focus()
})

/*
  Lifecycle: cleanup timers.
  生命周期：清理定时器。
*/
onBeforeUnmount(() => {
  clearOtpAnimationTimers()
  clearOtpAutoSubmitTimer()

  if (resendTimer) {
    clearInterval(resendTimer)
    resendTimer = null
  }
})
</script>

<style scoped>
/*
  Module 1: page tokens and global two-column shell.
  模块一：页面设计变量与双栏外层布局。
*/

/*
  1.display: grid;把这个容器变成 Grid 网格布局容器。
  一旦一个元素设成 grid，它的直接子元素就会按照网格规则来排，不再只是普通块级元素从上到下堆叠。
  login-shell 的直接子元素就是：hero-pane 和 auth-pane

  2.grid-template-columns 这个 grid 容器有几列，每一列多宽。
  第 1 列：minmax(0, 1.1fr)、
  第 2 列：minmax(420px, 540px)

  3.开头定义的一堆颜色，为了后续容器中的样式可以直接复用：color: var(--stone-900);
  emerald 绿色主题，950最深，400最浅，主要用于设置渐变颜色......

  4.white-soft和border是应用于毛玻璃效果

  5.shadow是应用于卡片阴影样式

  6.min-height: 100vh;  viewport height，表示容器最小高度至少等于整个浏览器视口高度

  7.background那部分是分别在左上角和右下角放置圆形渐变光斑，让背景从纯白变成渐变色
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
  模块二：左侧展示区、背景舞台与视觉效果。
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
  object-fit: fill;
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
  模块三：左侧前景布局、品牌区与卡片结构。
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
  font-size: 0.72rem;
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
  font-size: 0.8rem;
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
  模块四：角色选择器与角色详情展示。
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
  font-size: 0.92rem;
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
  模块五：左侧概览统计与底部操作区。
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

.overview-title {
  font-size: 1.65rem;
  line-height: 1.18;
  color: #ffffff;
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


/* 功能卡片升级（核心） */
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


/* 模式按钮升级 */
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


/* 官网按钮升级（高级 outline） */
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
  模块六：右侧认证区外层、顶部工具条与卡片容器。
*/
.auth-pane {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: clamp(22px, 4vw, 40px);
}

.auth-shell {
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
  模块七：认证进度条与步骤头部展示。
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
  模块八：表单字段与操作按钮。
*/
.auth-form {
  width: 100%;
  display: grid;
  gap: 18px;
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

.field-icon {
  font-size: 1rem;
  font-weight: 800;
  color: var(--emerald-700);
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
  模块九：OTP 输入区、反馈消息与支持区域。
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
  模块十：角色主题工具类与过渡动画。
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
  模块十一：响应式适配。
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
  模块十二：降低动画偏好支持。
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
  模块十三：沉浸式动效强化与高级交互升级。
*/

/*
    --pointer分别表示鼠标横向以及纵向的位置，50%也就是容器中间。32%就是容器靠上部分
    isolate相当于给这片区域单独开一个图层
*/
.login-shell {
  --pointer-x: 50%;
  --pointer-y: 32%;
  isolation: isolate;
}

/*
    虚拟子元素，表示浏览器会在login-shell DOM 元素前后额外生成两个装饰用的盒子
    before是在前面插入，after是在后面插入

    <div class="login-shell">
      <pseudo-before></pseudo-before>
      <div class="login-card">...</div>
      <pseudo-after></pseudo-after>
    </div>

    这里是两个为元素的公共样式
    为元素必须有content才可以生成

    ::before 的作用：做一个会根据鼠标位置变化、并且在鼠标进入时才显示的动态发光层。
    ::after 的作用：做一个固定在右下角、一直存在的静态背景发光层。
*/
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

.hero-ambient-orb,
.hero-grid-line {
  position: absolute;
  pointer-events: none;
}

.hero-ambient-orb {
  border-radius: 50%;
  filter: blur(8px);
  mix-blend-mode: screen;
  opacity: 0.9;
  transition: transform 0.22s ease;
}

.hero-ambient-orb--a {
  top: 8%;
  left: 6%;
  width: clamp(160px, 24vw, 280px);
  height: clamp(160px, 24vw, 280px);
  background: radial-gradient(circle, rgba(132, 255, 226, 0.22), rgba(132, 255, 226, 0.02) 64%, transparent 72%);
  animation: ambientFloatA 12s ease-in-out infinite;
}

.hero-ambient-orb--b {
  right: 10%;
  bottom: 12%;
  width: clamp(220px, 28vw, 360px);
  height: clamp(220px, 28vw, 360px);
  background: radial-gradient(circle, rgba(79, 191, 162, 0.18), rgba(79, 191, 162, 0.02) 62%, transparent 72%);
  animation: ambientFloatB 15s ease-in-out infinite;
}

.hero-grid-line {
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: radial-gradient(circle at center, rgba(0, 0, 0, 0.92), transparent 82%);
  opacity: 0.2;
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

.otp-status-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  padding: 0 14px;
  border-radius: 16px;
  border: 1px solid rgba(16, 33, 29, 0.08);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(246, 250, 248, 0.88)),
    radial-gradient(circle at top left, rgba(47, 164, 134, 0.08), transparent 36%);
}

.otp-status-strip.ready {
  border-color: rgba(47, 164, 134, 0.16);
  box-shadow: 0 12px 26px rgba(31, 93, 79, 0.08);
}

.otp-status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(39, 132, 109, 0.08);
  color: var(--emerald-700);
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.otp-status-text {
  font-size: 0.86rem;
  font-weight: 700;
  color: var(--stone-700);
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

  .otp-status-strip {
    flex-wrap: wrap;
    justify-content: center;
    padding: 10px 14px;
  }
}

@media (max-width: 760px) {
  .hero-ambient-orb--a {
    top: -2%;
    left: -10%;
  }

  .hero-ambient-orb--b {
    right: -16%;
    bottom: -4%;
  }

  .otp-status-strip {
    gap: 8px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-shell::before,
  .login-shell::after,
  .hero-ambient-orb,
  .hero-grid-line,
  .interactive-surface,
  .interactive-surface::after,
  .language-option::before,
  .primary-button::before,
  .secondary-button::before,
  .hero-link::after {
    animation: none !important;
    transition: none !important;
    transform: none !important;
  }
}

</style>
