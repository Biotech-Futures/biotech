<template>
  <div class="split-login">
    <section ref="leftPaneRef" class="left-pane">
      <div ref="biotechSceneRef" class="biotech-scene"></div>
      <div class="bg-overlay"></div>

      <div
        class="left-inner"
        :dir="currentDir"
        :class="{ rtl: currentDir === 'rtl' }"
      >
        <div class="brand">
          <div class="logo-icon">
            <img :src="logo" alt="BIOTech Futures" />
          </div>
          <h1 class="brand-title">{{ t('brandTitle') }}</h1>
        </div>

        <div class="role-tags" aria-label="Portal roles">
          <span class="role-tag">{{ t('roleStudent') }}</span>
          <span class="role-tag">{{ t('roleMentor') }}</span>
          <span class="role-tag">{{ t('roleSupervisor') }}</span>
          <span class="role-tag">{{ t('roleAdmin') }}</span>
        </div>

        <div class="custom-content" v-html="leftHtml"></div>

        <div class="links">
          <a
            class="btn btn-secondary"
            href="https://biotechfutures.org"
            target="_blank"
            rel="noopener"
          >
            {{ t('visitWebsite') }}
          </a>
        </div>
      </div>
    </section>

    <section class="right-pane">
      <div
        class="login-card fade-in"
        :dir="currentDir"
        :class="{ rtl: currentDir === 'rtl' }"
      >
        <div v-if="currentStep === 'email'" class="step-email">
          <div class="login-logo">
            <div class="login-logo-icon">
              <img :src="logo" alt="BIOTech Futures" />
            </div>
            <h2 class="login-title">{{ t('signIn') }}</h2>
            <p class="login-subtitle">{{ t('welcomeSubtitle') }}</p>
          </div>

          <form @submit.prevent="handleLogin" novalidate>
            <div class="form-group">
              <label class="form-label" for="login-email">
                {{ t('emailLabel') }}
              </label>

              <input
                id="login-email"
                ref="emailInputRef"
                v-model.trim="email"
                type="email"
                class="form-control"
                :placeholder="t('emailPlaceholder')"
                :aria-invalid="Boolean(error)"
                autocomplete="email"
                required
                @input="handleEmailInput"
              />

              <small class="form-text">
                {{ t('emailHelper') }}
              </small>
            </div>

            <button
              type="submit"
              class="btn btn-primary btn-lg full-width"
              :disabled="sendingCode || resendCountdown > 0"
            >
              <span v-if="!sendingCode && resendCountdown === 0">
                {{ t('sendVerificationCode') }}
              </span>
              <span v-else-if="sendingCode" class="loading"></span>
              <span v-else>
                {{ t('resendIn') }} {{ resendCountdown }}s
              </span>
            </button>
          </form>

          <p
            v-if="statusMessage"
            class="status-message"
            aria-live="polite"
          >
            {{ statusMessage }}
          </p>

          <p
            v-if="error"
            class="error-message"
            role="alert"
            aria-live="assertive"
          >
            {{ error }}
          </p>
        </div>

        <div v-else class="step-otp">
          <div class="otp-topbar">
            <button
              type="button"
              class="back-button"
              @click="goBackToEmailStep"
            >
              ← {{ t('back') }}
            </button>
          </div>

          <div class="login-logo otp-logo-compact">
            <div class="login-logo-icon">
              <img :src="logo" alt="BIOTech Futures" />
            </div>
          </div>

          <div class="otp-screen-content">
            <p class="otp-main-title">
              {{ t('otpMessage') }}
            </p>

            <p class="otp-email">
              {{ t('codeSentTo') }} <strong>{{ maskedEmail }}</strong>
            </p>

            <div class="otp-actions-top">
              <button
                type="button"
                class="linklike"
                @click="goBackToEmailStep"
              >
                {{ t('changeEmail') }}
              </button>
            </div>

            <div class="otp-container">
              <input
                v-for="(digit, index) in otpDigits"
                :key="index"
                :ref="(el) => setOtpRef(el, index)"
                v-model="otpDigits[index]"
                type="text"
                maxlength="1"
                class="otp-input"
                inputmode="numeric"
                autocomplete="one-time-code"
                :aria-label="`${t('digit')} ${index + 1}`"
                @input="handleOTPInput($event, index)"
                @keydown="handleOTPKeydown($event, index)"
                @keydown.enter.prevent="handleOTPEnter"
                @focus="handleOTPFocus($event)"
                @paste="handleOTPPaste($event)"
              />
            </div>

            <button
              type="button"
              class="btn btn-primary full-width mt-1"
              :disabled="verifyingCode || !isOtpComplete"
              @click="verifyOTP"
            >
              <span v-if="!verifyingCode">{{ t('verifyCode') }}</span>
              <span v-else class="loading"></span>
            </button>

            <div class="text-center mt-small">
              <button
                type="button"
                class="linklike"
                :disabled="resendingCode || resendCountdown > 0"
                @click="resendCode"
              >
                <span v-if="resendCountdown === 0">
                  {{ t('resendCode') }}
                </span>
                <span v-else>
                  {{ t('resendIn') }} {{ resendCountdown }}s
                </span>
              </button>
            </div>

            <p class="otp-expiry-hint">
              {{ t('codeExpiryHint') }}
            </p>

            <div class="help-links otp-help-links">
              <span>{{ t('needHelp') }}</span>
              <a href="mailto:support@biotechfutures.org">{{ t('contactSupport') }}</a>
            </div>
          </div>

          <p
            v-if="statusMessage"
            class="status-message"
            aria-live="polite"
          >
            {{ statusMessage }}
          </p>

          <p
            v-if="error"
            class="error-message"
            role="alert"
            aria-live="assertive"
          >
            {{ error }}
          </p>
        </div>

        <div class="card-spacer"></div>

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
    </section>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import * as THREE from 'three'
import { useAuthStore } from '../stores/auth'
import logo from '@/assets/btf-logo.png'

const router = useRouter()
const auth = useAuthStore()

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const email = ref('')
const lastVerifiedEmailSnapshot = ref('')
const currentStep = ref('email')

const error = ref('')
const statusMessage = ref('')

const sendingCode = ref(false)
const verifyingCode = ref(false)
const resendingCode = ref(false)

const otpDigits = ref(['', '', '', '', '', ''])
const otpRefs = ref([])
const emailInputRef = ref(null)

const resendCountdown = ref(0)
let resendTimer = null

const hasEmailBeenModifiedAfterBack = ref(false)
const hasResentAfterBack = ref(false)

const locale = ref('en')

const leftPaneRef = ref(null)
const biotechSceneRef = ref(null)

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'ar', label: 'العربية' },
]

const messages = {
  en: {
    brandTitle: 'BIOTech Futures Hub',
    signIn: 'Sign in',
    welcomeSubtitle: 'Access your mentoring portal securely and continue where you left off.',
    emailLabel: 'Email Address',
    emailPlaceholder: 'Enter your email',
    emailHelper: 'We will send a short-lived verification code to your email.',
    sendVerificationCode: 'Send Verification Code',
    otpMessage: 'Enter the 6-digit code from your email to continue.',
    verifyCode: 'Verify Code',
    resendCode: 'Resend Code',
    resendIn: 'Resend in',
    visitWebsite: 'Visit Main Website',
    roleStudent: 'Student',
    roleMentor: 'Mentor',
    roleSupervisor: 'Supervisor',
    roleAdmin: 'Admin',
    codeSentTo: 'Code sent to',
    changeEmail: 'Change email',
    back: 'Back',
    digit: 'Digit',
    codeExpiryHint: 'Codes are single-use and expire after a short time.',
    needHelp: 'Need help?',
    contactSupport: 'Contact support',
    aboutTitle: 'Welcome to the BIOTech Futures Mentoring Portal',
    aboutP1: 'This platform helps students, mentors, supervisors, and administrators stay connected throughout the mentoring program.',
    aboutLi1: 'Access group communication and shared resources',
    aboutLi2: 'Track milestones, updates, and mentoring progress',
    aboutLi3: 'Support role-based workflows across the program',
    aboutP2: 'Use one secure portal for communication, resources, events, and progress tracking.',
    errorEnterEmail: 'Please enter your email address.',
    errorInvalidEmail: 'Please enter a valid email address.',
    errorSendLink: 'Failed to send the verification code. Please try again.',
    errorNetworkLogin: 'Network error. Please check your connection and try again.',
    errorCompleteCode: 'Please enter the complete 6-digit code.',
    errorInvalidCode: 'Invalid or expired code.',
    errorNetworkOtp: 'Network error. Please try again.',
    errorEnterEmailFirst: 'Please enter your email address first.',
    errorResendFail: 'Failed to resend the code. Please try again.',
    resendSuccess: 'A new code has been sent to your email.',
    sendingSuccess: 'Verification code sent. Please check your inbox.',
    signingIn: 'Signing you in...',
  },

  'zh-CN': {
    brandTitle: 'BIOTech Futures 平台',
    signIn: '登录',
    welcomeSubtitle: '安全进入你的导师项目平台，并继续之前的进度。',
    emailLabel: '邮箱地址',
    emailPlaceholder: '请输入你的邮箱',
    emailHelper: '我们会向你的邮箱发送一个短时有效的验证码。',
    sendVerificationCode: '发送验证码',
    otpMessage: '请输入邮件中的 6 位验证码以继续。',
    verifyCode: '验证验证码',
    resendCode: '重新发送验证码',
    resendIn: '可重发于',
    visitWebsite: '访问主网站',
    roleStudent: '学生',
    roleMentor: '导师',
    roleSupervisor: '监督老师',
    roleAdmin: '管理员',
    codeSentTo: '验证码已发送至',
    changeEmail: '更换邮箱',
    back: '返回',
    digit: '第',
    codeExpiryHint: '验证码仅可使用一次，并会在短时间后失效。',
    needHelp: '需要帮助？',
    contactSupport: '联系支持',
    aboutTitle: '欢迎来到 BIOTech Futures 导师平台',
    aboutP1: '该平台帮助学生、导师、监督老师和管理员在整个导师项目中保持连接。',
    aboutLi1: '访问小组沟通与共享资源',
    aboutLi2: '追踪里程碑、更新与辅导进展',
    aboutLi3: '支持平台中的角色化工作流程',
    aboutP2: '通过一个安全平台统一完成沟通、资源访问、活动查看与进度跟踪。',
    errorEnterEmail: '请输入你的邮箱地址。',
    errorInvalidEmail: '请输入有效的邮箱地址。',
    errorSendLink: '发送验证码失败，请重试。',
    errorNetworkLogin: '网络异常，请检查连接后重试。',
    errorCompleteCode: '请输入完整的 6 位验证码。',
    errorInvalidCode: '验证码无效或已过期。',
    errorNetworkOtp: '网络异常，请重试。',
    errorEnterEmailFirst: '请先输入邮箱地址。',
    errorResendFail: '重新发送验证码失败，请重试。',
    resendSuccess: '新的验证码已发送到你的邮箱。',
    sendingSuccess: '验证码已发送，请检查收件箱。',
    signingIn: '正在登录...',
  },

  ja: {
    brandTitle: 'BIOTech Futures ハブ',
    signIn: 'サインイン',
    welcomeSubtitle: '安全にメンタリングポータルへアクセスし、続きから再開できます。',
    emailLabel: 'メールアドレス',
    emailPlaceholder: 'メールアドレスを入力してください',
    emailHelper: '短時間のみ有効な確認コードをメールで送信します。',
    sendVerificationCode: '確認コードを送信',
    otpMessage: '続行するには、メールに届いた 6 桁のコードを入力してください。',
    verifyCode: 'コードを確認',
    resendCode: 'コードを再送信',
    resendIn: '再送信まで',
    visitWebsite: '公式サイトへ',
    roleStudent: '学生',
    roleMentor: 'メンター',
    roleSupervisor: 'スーパーバイザー',
    roleAdmin: '管理者',
    codeSentTo: 'コード送信先',
    changeEmail: 'メールを変更',
    back: '戻る',
    digit: '桁',
    codeExpiryHint: 'コードは一度だけ使用でき、短時間で失効します。',
    needHelp: 'お困りですか？',
    contactSupport: 'サポートに連絡',
    aboutTitle: 'BIOTech Futures メンタリングポータルへようこそ',
    aboutP1: 'このプラットフォームは、学生、メンター、スーパーバイザー、管理者がプログラム全体を通してつながることを支援します。',
    aboutLi1: 'グループ連絡と共有リソースにアクセス',
    aboutLi2: 'マイルストーン、更新、進捗を追跡',
    aboutLi3: '役割別ワークフローをサポート',
    aboutP2: 'コミュニケーション、リソース、イベント、進捗管理を一つの安全なポータルで行えます。',
    errorEnterEmail: 'メールアドレスを入力してください。',
    errorInvalidEmail: '有効なメールアドレスを入力してください。',
    errorSendLink: '確認コードの送信に失敗しました。もう一度お試しください。',
    errorNetworkLogin: 'ネットワークエラーです。接続を確認してもう一度お試しください。',
    errorCompleteCode: '6 桁のコードをすべて入力してください。',
    errorInvalidCode: 'コードが無効か、有効期限が切れています。',
    errorNetworkOtp: 'ネットワークエラーです。もう一度お試しください。',
    errorEnterEmailFirst: '先にメールアドレスを入力してください。',
    errorResendFail: 'コードの再送信に失敗しました。もう一度お試しください。',
    resendSuccess: '新しいコードをメールに送信しました。',
    sendingSuccess: '確認コードを送信しました。受信箱を確認してください。',
    signingIn: 'サインイン中...',
  },

  ko: {
    brandTitle: 'BIOTech Futures 허브',
    signIn: '로그인',
    welcomeSubtitle: '안전하게 멘토링 포털에 접속하고 이어서 진행하세요.',
    emailLabel: '이메일 주소',
    emailPlaceholder: '이메일을 입력하세요',
    emailHelper: '짧은 시간만 유효한 인증 코드를 이메일로 보내드립니다.',
    sendVerificationCode: '인증 코드 보내기',
    otpMessage: '계속하려면 이메일의 6자리 코드를 입력하세요.',
    verifyCode: '코드 확인',
    resendCode: '코드 다시 보내기',
    resendIn: '재전송 가능까지',
    visitWebsite: '메인 웹사이트 방문',
    roleStudent: '학생',
    roleMentor: '멘토',
    roleSupervisor: '슈퍼바이저',
    roleAdmin: '관리자',
    codeSentTo: '코드 전송 대상',
    changeEmail: '이메일 변경',
    back: '뒤로',
    digit: '자리',
    codeExpiryHint: '코드는 1회용이며 짧은 시간 후 만료됩니다.',
    needHelp: '도움이 필요하신가요?',
    contactSupport: '지원 문의',
    aboutTitle: 'BIOTech Futures 멘토링 포털에 오신 것을 환영합니다',
    aboutP1: '이 플랫폼은 학생, 멘토, 슈퍼바이저, 관리자가 멘토링 프로그램 전반에서 연결되도록 돕습니다.',
    aboutLi1: '그룹 소통 및 공유 자료 접근',
    aboutLi2: '마일스톤, 업데이트, 멘토링 진행 추적',
    aboutLi3: '역할 기반 워크플로 지원',
    aboutP2: '하나의 안전한 포털에서 소통, 자료, 이벤트, 진행 상황을 관리하세요.',
    errorEnterEmail: '이메일 주소를 입력해 주세요.',
    errorInvalidEmail: '유효한 이메일 주소를 입력해 주세요.',
    errorSendLink: '인증 코드 전송에 실패했습니다. 다시 시도해 주세요.',
    errorNetworkLogin: '네트워크 오류입니다. 연결을 확인한 뒤 다시 시도해 주세요.',
    errorCompleteCode: '6자리 코드를 모두 입력해 주세요.',
    errorInvalidCode: '코드가 잘못되었거나 만료되었습니다.',
    errorNetworkOtp: '네트워크 오류입니다. 다시 시도해 주세요.',
    errorEnterEmailFirst: '먼저 이메일 주소를 입력해 주세요.',
    errorResendFail: '코드 재전송에 실패했습니다. 다시 시도해 주세요.',
    resendSuccess: '새 코드가 이메일로 전송되었습니다.',
    sendingSuccess: '인증 코드가 전송되었습니다. 받은편지함을 확인해 주세요.',
    signingIn: '로그인 중...',
  },

  ar: {
    brandTitle: 'مركز BIOTech Futures',
    signIn: 'تسجيل الدخول',
    welcomeSubtitle: 'ادخل إلى بوابة الإرشاد بأمان وتابع من حيث توقفت.',
    emailLabel: 'البريد الإلكتروني',
    emailPlaceholder: 'أدخل بريدك الإلكتروني',
    emailHelper: 'سنرسل رمز تحقق قصير الصلاحية إلى بريدك الإلكتروني.',
    sendVerificationCode: 'إرسال رمز التحقق',
    otpMessage: 'أدخل الرمز المكوّن من 6 أرقام من بريدك الإلكتروني للمتابعة.',
    verifyCode: 'تأكيد الرمز',
    resendCode: 'إعادة إرسال الرمز',
    resendIn: 'إعادة الإرسال خلال',
    visitWebsite: 'زيارة الموقع الرئيسي',
    roleStudent: 'طالب',
    roleMentor: 'مرشد',
    roleSupervisor: 'مشرف',
    roleAdmin: 'مسؤول',
    codeSentTo: 'تم إرسال الرمز إلى',
    changeEmail: 'تغيير البريد الإلكتروني',
    back: 'رجوع',
    digit: 'الخانة',
    codeExpiryHint: 'الرموز للاستخدام مرة واحدة وتنتهي صلاحيتها بعد وقت قصير.',
    needHelp: 'هل تحتاج إلى مساعدة؟',
    contactSupport: 'التواصل مع الدعم',
    aboutTitle: 'مرحبًا بك في بوابة BIOTech Futures للإرشاد',
    aboutP1: 'تساعد هذه المنصة الطلاب والمرشدين والمشرفين والمسؤولين على البقاء متصلين طوال برنامج الإرشاد.',
    aboutLi1: 'الوصول إلى تواصل المجموعات والموارد المشتركة',
    aboutLi2: 'متابعة المراحل والتحديثات وتقدم الإرشاد',
    aboutLi3: 'دعم سير العمل حسب الدور',
    aboutP2: 'استخدم بوابة آمنة واحدة للتواصل والموارد والفعاليات وتتبع التقدم.',
    errorEnterEmail: 'يرجى إدخال بريدك الإلكتروني.',
    errorInvalidEmail: 'يرجى إدخال بريد إلكتروني صالح.',
    errorSendLink: 'فشل إرسال رمز التحقق. يرجى المحاولة مرة أخرى.',
    errorNetworkLogin: 'خطأ في الشبكة. يرجى التحقق من الاتصال والمحاولة مرة أخرى.',
    errorCompleteCode: 'يرجى إدخال الرمز الكامل المكوّن من 6 أرقام.',
    errorInvalidCode: 'الرمز غير صالح أو منتهي الصلاحية.',
    errorNetworkOtp: 'خطأ في الشبكة. يرجى المحاولة مرة أخرى.',
    errorEnterEmailFirst: 'يرجى إدخال بريدك الإلكتروني أولاً.',
    errorResendFail: 'فشل إعادة إرسال الرمز. يرجى المحاولة مرة أخرى.',
    resendSuccess: 'تم إرسال رمز جديد إلى بريدك الإلكتروني.',
    sendingSuccess: 'تم إرسال رمز التحقق. يرجى فحص بريدك الوارد.',
    signingIn: 'جارٍ تسجيل الدخول...',
  }
}

const t = (key) => {
  return messages[locale.value]?.[key] || messages.en[key] || key
}

const currentDir = computed(() => {
  return locale.value === 'ar' ? 'rtl' : 'ltr'
})

const leftHtml = computed(() => `
  <h2 class="info-title">${t('aboutTitle')}</h2>
  <p>${t('aboutP1')}</p>
  <ul class="info-list">
    <li>${t('aboutLi1')}</li>
    <li>${t('aboutLi2')}</li>
    <li>${t('aboutLi3')}</li>
  </ul>
  <p>${t('aboutP2')}</p>
`)

const isOtpComplete = computed(() => {
  return otpDigits.value.join('').length === 6
})

const maskedEmail = computed(() => {
  const value = email.value?.trim() || ''
  const parts = value.split('@')

  if (parts.length !== 2) {
    return value
  }

  const [name, domain] = parts
  if (name.length <= 2) {
    return `${name[0] || '*'}***@${domain}`
  }

  return `${name.slice(0, 2)}***@${domain}`
})

const switchLanguage = (lang) => {
  locale.value = lang
  error.value = ''
  statusMessage.value = ''
  localStorage.setItem('login-language', lang)
}

const savedLanguage = localStorage.getItem('login-language')
if (savedLanguage && languageOptions.some((item) => item.value === savedLanguage)) {
  locale.value = savedLanguage
}

watch(
  locale,
  (newLocale) => {
    document.documentElement.lang = newLocale
  },
  { immediate: true }
)

const setOtpRef = (el, index) => {
  if (el) {
    otpRefs.value[index] = el
  }
}

const handleOTPEnter = async () => {
  if (!isOtpComplete.value || verifyingCode.value) {
    return
  }
  await verifyOTP()
}

const handleOTPInput = (event, index) => {
  const value = event.target.value.replace(/[^0-9]/g, '')
  otpDigits.value[index] = value

  if (value && index < otpDigits.value.length - 1) {
    otpRefs.value[index + 1]?.focus()
  }
}

const handleOTPKeydown = (event, index) => {
  const key = event.key

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

  const allowedKeys = ['Tab', 'Shift', 'Control', 'Meta', 'Alt', 'Enter']
  if (allowedKeys.includes(key)) {
    return
  }

  if (!/^[0-9]$/.test(key)) {
    event.preventDefault()
  }
}

const handleOTPFocus = (event) => {
  event.target.select()
}

const handleOTPPaste = (event) => {
  event.preventDefault()

  const pastedText = event.clipboardData
    .getData('text')
    .replace(/[^0-9]/g, '')
    .slice(0, 6)

  if (!pastedText) {
    return
  }

  const chars = pastedText.split('')
  otpDigits.value = ['', '', '', '', '', '']

  chars.forEach((char, index) => {
    otpDigits.value[index] = char
  })

  const nextIndex = Math.min(chars.length, 5)
  otpRefs.value[nextIndex]?.focus()
}

const handleEmailInput = () => {
  if (currentStep.value === 'email' && email.value !== lastVerifiedEmailSnapshot.value) {
    hasEmailBeenModifiedAfterBack.value = true
  }
}

const isValidEmail = (value) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

const parseErrorMessage = async (response, fallbackText) => {
  try {
    const data = await response.json()
    return data.error || data.message || fallbackText
  } catch {
    return fallbackText
  }
}

const buildCallbackUrl = () => {
  return `${window.location.origin}/#/auth/callback`
}

const startResendCountdown = () => {
  resendCountdown.value = 30

  if (resendTimer) {
    clearInterval(resendTimer)
  }

  resendTimer = setInterval(() => {
    if (resendCountdown.value > 0) {
      resendCountdown.value -= 1
    } else {
      clearInterval(resendTimer)
      resendTimer = null
    }
  }, 1000)
}

const resetOtpState = async () => {
  otpDigits.value = ['', '', '', '', '', '']
  await nextTick()
  otpRefs.value[0]?.focus()
}

const canReturnToOtpStep = () => {
  return (
    lastVerifiedEmailSnapshot.value &&
    email.value === lastVerifiedEmailSnapshot.value &&
    !hasEmailBeenModifiedAfterBack.value &&
    !hasResentAfterBack.value
  )
}

const goBackToEmailStep = async () => {
  currentStep.value = 'email'
  error.value = ''
  statusMessage.value = ''

  await nextTick()
  emailInputRef.value?.focus()
}

const handleLogin = async () => {
  const normalizedEmail = email.value.trim().toLowerCase()

  if (!normalizedEmail) {
    error.value = t('errorEnterEmail')
    statusMessage.value = ''
    return
  }

  if (!isValidEmail(normalizedEmail)) {
    error.value = t('errorInvalidEmail')
    statusMessage.value = ''
    return
  }

  email.value = normalizedEmail
  error.value = ''
  statusMessage.value = ''

  if (canReturnToOtpStep()) {
    currentStep.value = 'otp'
    await nextTick()
    otpRefs.value[0]?.focus()
    return
  }

  if (resendCountdown.value > 0) {
    statusMessage.value = `${t('resendIn')} ${resendCountdown.value}s`
    return
  }

  sendingCode.value = true

  try {
    const response = await fetch(`${API_BASE_URL}/services/send-login-code/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,
        redirect_url: buildCallbackUrl(),
      }),
    })

    if (response.ok) {
      lastVerifiedEmailSnapshot.value = email.value
      hasEmailBeenModifiedAfterBack.value = false
      hasResentAfterBack.value = false
      currentStep.value = 'otp'
      statusMessage.value = t('sendingSuccess')
      await resetOtpState()
      startResendCountdown()
    } else {
      error.value = await parseErrorMessage(response, t('errorSendLink'))
    }
  } catch (err) {
    console.error('Login error:', err)
    error.value = t('errorNetworkLogin')
  } finally {
    sendingCode.value = false
  }
}

const resolvePostLoginRoute = (user) => {
  const role = user?.role || user?.user_type || user?.role_name || ''

  switch (role) {
    case 'admin':
    case 'global_admin':
    case 'local_admin':
      return '/dashboard'
    case 'supervisor':
      return '/dashboard'
    case 'mentor':
      return '/dashboard'
    case 'student':
      return '/dashboard'
    default:
      return '/dashboard'
  }
}

const verifyOTP = async () => {
  const code = otpDigits.value.join('')

  if (code.length !== 6) {
    error.value = t('errorCompleteCode')
    statusMessage.value = ''
    return
  }

  error.value = ''
  statusMessage.value = t('signingIn')
  verifyingCode.value = true

  try {
    const response = await fetch(`${API_BASE_URL}/services/verify-login-code/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,
        code,
      }),
    })

    if (response.ok) {
      await auth.fetchUserData()
      await nextTick()

      const targetRoute = resolvePostLoginRoute(auth.user || auth.currentUser || null)

      try {
        await router.replace(targetRoute)
      } catch (err) {
        window.location.href = `/#${targetRoute}`
      }
    } else {
      statusMessage.value = ''
      error.value = await parseErrorMessage(response, t('errorInvalidCode'))
    }
  } catch (err) {
    console.error('OTP verification error:', err)
    statusMessage.value = ''
    error.value = t('errorNetworkOtp')
  } finally {
    verifyingCode.value = false
  }
}

const resendCode = async () => {
  if (!email.value) {
    error.value = t('errorEnterEmailFirst')
    statusMessage.value = ''
    return
  }

  if (resendCountdown.value > 0 || resendingCode.value) {
    return
  }

  error.value = ''
  statusMessage.value = ''
  resendingCode.value = true

  try {
    const response = await fetch(`${API_BASE_URL}/services/send-login-code/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,
        redirect_url: buildCallbackUrl(),
      }),
    })

    if (response.ok) {
      hasResentAfterBack.value = true
      statusMessage.value = t('resendSuccess')
      await resetOtpState()
      startResendCountdown()
    } else {
      error.value = await parseErrorMessage(response, t('errorResendFail'))
    }
  } catch (err) {
    console.error('Resend code error:', err)
    error.value = t('errorNetworkOtp')
  } finally {
    resendingCode.value = false
  }
}

/*
  Three.js biotech hero scene
*/

let scene = null
let camera = null
let renderer = null
let animationId = 0
let sceneClock = null
let resizeObserver = null

const floatingItems = []
const mouseNdc = new THREE.Vector2(10, 10)
const mouseWorld = new THREE.Vector3(999, 999, 0)
const raycaster = new THREE.Raycaster()
const interactionPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0)

const createSoftMaterial = (color, opacity = 1) => {
  return new THREE.MeshPhysicalMaterial({
    color,
    roughness: 0.2,
    metalness: 0.05,
    transmission: opacity < 1 ? 0.45 : 0,
    transparent: opacity < 1,
    opacity,
    clearcoat: 0.7,
    clearcoatRoughness: 0.2
  })
}

const addFloatingItem = (mesh, x, y, z, force = 1) => {
  mesh.position.set(x, y, z)
  scene.add(mesh)

  floatingItems.push({
    mesh,
    basePosition: new THREE.Vector3(x, y, z),
    velocity: new THREE.Vector3(),
    force,
    noiseOffset: Math.random() * 1000
  })
}

const createMoleculeCluster = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const atomMaterial = createSoftMaterial('#eefdf5', 0.96)
  const atomAccentMaterial = createSoftMaterial('#9fe8bf', 0.96)
  const bondMaterial = new THREE.MeshStandardMaterial({
    color: '#c9e7d5',
    roughness: 0.5,
    metalness: 0.08
  })

  const positions = [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0.95, 0.5, 0.15),
    new THREE.Vector3(-0.8, 0.6, -0.1),
    new THREE.Vector3(0.45, -0.9, 0.2),
    new THREE.Vector3(-0.9, -0.55, -0.15)
  ]

  positions.forEach((pos, index) => {
    const radius = index === 0 ? 0.34 : 0.24
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(radius, 32, 32),
      index % 2 === 0 ? atomMaterial : atomAccentMaterial
    )
    sphere.position.copy(pos)
    group.add(sphere)
  })

  for (let i = 1; i < positions.length; i++) {
    const start = positions[0]
    const end = positions[i]
    const direction = new THREE.Vector3().subVectors(end, start)
    const length = direction.length()

    const bond = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.055, Math.max(0.1, length - 0.11), 6, 12),
      bondMaterial
    )

    const midpoint = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
    bond.position.copy(midpoint)
    bond.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      direction.clone().normalize()
    )

    group.add(bond)
  }

  group.scale.setScalar(scale)
  group.position.set(x, y, 0)
  return group
}

const createCapsule = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const left = new THREE.Mesh(
    new THREE.SphereGeometry(0.42, 32, 32),
    createSoftMaterial('#f8fffb', 0.94)
  )
  left.scale.x = 0.9
  left.position.x = -0.34

  const right = new THREE.Mesh(
    new THREE.SphereGeometry(0.42, 32, 32),
    createSoftMaterial('#b8f1ce', 0.95)
  )
  right.scale.x = 0.9
  right.position.x = 0.34

  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(0.36, 0.36, 0.78, 32),
    createSoftMaterial('#edfdf4', 0.92)
  )
  body.rotation.z = Math.PI / 2

  group.add(left, right, body)
  group.scale.setScalar(scale)
  group.rotation.z = -0.55
  group.position.set(x, y, 0)
  return group
}

const createPetriDish = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(0.72, 0.08, 20, 100),
    createSoftMaterial('#f4fff9', 0.6)
  )

  const core = new THREE.Mesh(
    new THREE.CircleGeometry(0.62, 48),
    new THREE.MeshPhysicalMaterial({
      color: '#dcf7e9',
      transparent: true,
      opacity: 0.38,
      roughness: 0.18,
      metalness: 0.04,
      transmission: 0.5
    })
  )

  group.add(ring, core)
  group.scale.setScalar(scale)
  group.position.set(x, y, -0.2)
  return group
}

const createCell = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(0.62, 40, 40),
    new THREE.MeshPhysicalMaterial({
      color: '#fbfffd',
      transparent: true,
      opacity: 0.42,
      roughness: 0.12,
      metalness: 0.04,
      transmission: 0.72,
      clearcoat: 0.8
    })
  )

  const nucleus = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 24, 24),
    createSoftMaterial('#8fe4b3', 0.92)
  )
  nucleus.position.set(0.12, -0.08, 0.14)

  const organelle1 = new THREE.Mesh(
    new THREE.SphereGeometry(0.08, 16, 16),
    createSoftMaterial('#d6f8e5', 0.88)
  )
  organelle1.position.set(-0.16, 0.1, 0.08)

  const organelle2 = new THREE.Mesh(
    new THREE.SphereGeometry(0.06, 16, 16),
    createSoftMaterial('#c0f1d5', 0.88)
  )
  organelle2.position.set(0.18, 0.16, -0.04)

  group.add(shell, nucleus, organelle1, organelle2)
  group.scale.setScalar(scale)
  group.position.set(x, y, 0)
  return group
}

const createDnaHelix = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const leftMaterial = new THREE.MeshStandardMaterial({
    color: '#0f7b56',
    roughness: 0.34,
    metalness: 0.08
  })
  const rightMaterial = new THREE.MeshStandardMaterial({
    color: '#b6f1cb',
    roughness: 0.28,
    metalness: 0.06
  })
  const rungMaterial = new THREE.MeshStandardMaterial({
    color: '#e8fbf1',
    roughness: 0.45,
    metalness: 0.04
  })

  const turns = 18
  const helixHeight = 3.8
  const radius = 0.42

  for (let i = 0; i < turns; i++) {
    const tValue = i / (turns - 1)
    const angle = tValue * Math.PI * 4.8
    const yPos = (tValue - 0.5) * helixHeight

    const leftPos = new THREE.Vector3(
      Math.cos(angle) * radius,
      yPos,
      Math.sin(angle) * radius * 0.55
    )
    const rightPos = new THREE.Vector3(
      Math.cos(angle + Math.PI) * radius,
      yPos,
      Math.sin(angle + Math.PI) * radius * 0.55
    )

    const leftNode = new THREE.Mesh(
      new THREE.SphereGeometry(0.085, 18, 18),
      leftMaterial
    )
    leftNode.position.copy(leftPos)

    const rightNode = new THREE.Mesh(
      new THREE.SphereGeometry(0.085, 18, 18),
      rightMaterial
    )
    rightNode.position.copy(rightPos)

    const linkDirection = new THREE.Vector3().subVectors(rightPos, leftPos)
    const linkLength = linkDirection.length()

    const rung = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.02, Math.max(0.05, linkLength - 0.04), 4, 8),
      rungMaterial
    )
    rung.position.copy(leftPos.clone().add(rightPos).multiplyScalar(0.5))
    rung.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      linkDirection.clone().normalize()
    )

    group.add(leftNode, rightNode, rung)
  }

  group.scale.setScalar(scale)
  group.rotation.z = 0.22
  group.position.set(x, y, -0.4)
  return group
}

const setupBiotechScene = () => {
  if (!biotechSceneRef.value) return

  scene = new THREE.Scene()
  scene.fog = new THREE.Fog('#eef8f2', 8, 18)

  const width = biotechSceneRef.value.clientWidth
  const height = biotechSceneRef.value.clientHeight

  camera = new THREE.PerspectiveCamera(36, width / height, 0.1, 100)
  camera.position.set(0, 0, 8.5)

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
  })

  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height)
  renderer.outputColorSpace = THREE.SRGBColorSpace

  biotechSceneRef.value.appendChild(renderer.domElement)

  const ambient = new THREE.AmbientLight('#ffffff', 1.8)
  scene.add(ambient)

  const keyLight = new THREE.DirectionalLight('#ffffff', 1.8)
  keyLight.position.set(4, 5, 6)
  scene.add(keyLight)

  const fillLight = new THREE.DirectionalLight('#c9ffd8', 0.9)
  fillLight.position.set(-5, 2, 4)
  scene.add(fillLight)

  const rimLight = new THREE.PointLight('#b7f3cf', 1.4, 20)
  rimLight.position.set(0, -2, 4)
  scene.add(rimLight)

  addFloatingItem(createDnaHelix(-1.8, 0.45, 1.12), -1.8, 0.45, -0.4, 1.15)
  addFloatingItem(createMoleculeCluster(1.85, 1.2, 0.95), 1.85, 1.2, 0, 1)
  addFloatingItem(createCapsule(2.25, -1.45, 0.9), 2.25, -1.45, 0, 0.92)
  addFloatingItem(createPetriDish(-2.2, -1.55, 0.95), -2.2, -1.55, -0.2, 0.88)
  addFloatingItem(createCell(0.65, -0.85, 1.08), 0.65, -0.85, 0, 1.05)
  addFloatingItem(createMoleculeCluster(-0.2, 1.8, 0.62), -0.2, 1.8, 0, 0.65)

  sceneClock = new THREE.Clock()
}

const updateMouseWorld = () => {
  if (!camera) return
  raycaster.setFromCamera(mouseNdc, camera)
  raycaster.ray.intersectPlane(interactionPlane, mouseWorld)
}

const animateBiotechScene = () => {
  if (!scene || !camera || !renderer || !sceneClock) return

  const elapsed = sceneClock.getElapsedTime()
  updateMouseWorld()

  for (const item of floatingItems) {
    const base = item.basePosition
    const current = item.mesh.position

    const toMouse = new THREE.Vector3().subVectors(current, mouseWorld)
    const distance = Math.max(0.0001, toMouse.length())

    const influenceRadius = 2.3
    let repelStrength = 0

    if (distance < influenceRadius) {
      repelStrength = (1 - distance / influenceRadius) * 0.18 * item.force
      toMouse.normalize()
      item.velocity.addScaledVector(toMouse, repelStrength)
    }

    const returnForce = new THREE.Vector3()
      .subVectors(base, current)
      .multiplyScalar(0.032)

    item.velocity.add(returnForce)
    item.velocity.multiplyScalar(0.9)

    current.add(item.velocity)

    const floatY = Math.sin(elapsed * 0.9 + item.noiseOffset) * 0.06
    const floatX = Math.cos(elapsed * 0.6 + item.noiseOffset * 0.7) * 0.03

    item.mesh.position.x += floatX * 0.06
    item.mesh.position.y += floatY * 0.06

    item.mesh.rotation.y += 0.0025 * item.force
    item.mesh.rotation.x = Math.sin(elapsed * 0.7 + item.noiseOffset) * 0.04

    if (repelStrength > 0.01) {
      item.mesh.rotation.z += 0.006 * item.force
    } else {
      item.mesh.rotation.z *= 0.96
    }
  }

  renderer.render(scene, camera)
  animationId = requestAnimationFrame(animateBiotechScene)
}

const handleScenePointerMove = (event) => {
  if (!leftPaneRef.value) return

  const rect = leftPaneRef.value.getBoundingClientRect()
  mouseNdc.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouseNdc.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
}

const handleScenePointerLeave = () => {
  mouseNdc.set(10, 10)
  mouseWorld.set(999, 999, 0)
}

const handleSceneResize = () => {
  if (!biotechSceneRef.value || !camera || !renderer) return

  const width = biotechSceneRef.value.clientWidth
  const height = biotechSceneRef.value.clientHeight

  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
}

onMounted(() => {
  setupBiotechScene()
  handleSceneResize()
  animateBiotechScene()

  if (leftPaneRef.value) {
    leftPaneRef.value.addEventListener('pointermove', handleScenePointerMove)
    leftPaneRef.value.addEventListener('pointerleave', handleScenePointerLeave)
  }

  if (leftPaneRef.value) {
    resizeObserver = new ResizeObserver(() => handleSceneResize())
    resizeObserver.observe(leftPaneRef.value)
  }

  window.addEventListener('resize', handleSceneResize)
})

onBeforeUnmount(() => {
  if (resendTimer) {
    clearInterval(resendTimer)
  }

  window.removeEventListener('resize', handleSceneResize)

  if (leftPaneRef.value) {
    leftPaneRef.value.removeEventListener('pointermove', handleScenePointerMove)
    leftPaneRef.value.removeEventListener('pointerleave', handleScenePointerLeave)
  }

  resizeObserver?.disconnect()
  cancelAnimationFrame(animationId)

  floatingItems.splice(0, floatingItems.length)

  if (renderer) {
    renderer.dispose()
    const canvas = renderer.domElement
    canvas.parentNode?.removeChild(canvas)
  }

  scene = null
  camera = null
  renderer = null
  sceneClock = null
})
</script>

<style scoped>
.split-login {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 520px);
  min-height: 100vh;
  background: var(--bg-light);
}

.left-pane {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(2rem, 4vw, 4rem);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  min-height: 100vh;
  background:
    radial-gradient(circle at 20% 20%, rgba(212, 248, 226, 0.9), transparent 28%),
    radial-gradient(circle at 82% 18%, rgba(190, 241, 212, 0.72), transparent 30%),
    linear-gradient(180deg, #f9fcfa 0%, #eef8f2 48%, #e7f3eb 100%);
}

.biotech-scene {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.bg-overlay {
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(circle at 18% 22%, rgba(255, 255, 255, 0.26), transparent 28%),
    radial-gradient(circle at 82% 78%, rgba(170, 237, 198, 0.16), transparent 26%),
    linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.22) 0%,
      rgba(255, 255, 255, 0.08) 45%,
      rgba(11, 69, 51, 0.12) 100%
    );
  pointer-events: none;
}

.left-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 560px;
  color: #173329;
}

.left-inner.rtl {
  text-align: right;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  margin-bottom: 1.15rem;
  flex-wrap: wrap;
}

.brand-title {
  font-size: clamp(1.65rem, 2vw, 1.95rem);
  font-weight: 750;
  color: #103126;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0;
  overflow-wrap: anywhere;
  text-shadow: 0 2px 16px rgba(255, 255, 255, 0.24);
}

.logo-icon {
  width: 52px;
  height: 52px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.52));
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.58);
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 52px;
  box-shadow:
    0 12px 30px rgba(16, 49, 38, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.logo-icon img {
  width: 72%;
  height: 72%;
  object-fit: contain;
}

.custom-content {
  max-width: 100%;
}

.custom-content :deep(h2.info-title) {
  font-size: clamp(2rem, 2.8vw, 2.45rem);
  font-weight: 760;
  margin: 0 0 0.9rem;
  color: #103126;
  line-height: 1.12;
  letter-spacing: -0.03em;
  overflow-wrap: anywhere;
  text-shadow: 0 2px 20px rgba(255, 255, 255, 0.22);
}

.custom-content :deep(p) {
  color: rgba(16, 49, 38, 0.84);
  margin: 0 0 0.9rem;
  line-height: 1.72;
  font-size: 1.03rem;
  font-weight: 400;
  overflow-wrap: anywhere;
}

.custom-content :deep(ul.info-list) {
  margin: 0.9rem 0 1.2rem 1.2rem;
  color: rgba(16, 49, 38, 0.92);
  line-height: 1.7;
  padding-inline-start: 0.9rem;
}

.left-inner.rtl .custom-content :deep(ul.info-list) {
  margin: 0.9rem 1.2rem 1.2rem 0;
  padding-inline-start: 0;
  padding-inline-end: 0.9rem;
}

.custom-content :deep(li) {
  margin-bottom: 0.45rem;
  overflow-wrap: anywhere;
}

.links {
  margin-top: 1.35rem;
}

.right-pane {
  background: var(--dark-green);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(1.5rem, 3vw, 2.5rem);
  position: relative;
}

.right-pane::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 12% 18%, rgba(255, 255, 255, 0.08), transparent 22%),
    radial-gradient(circle at 88% 82%, rgba(255, 255, 255, 0.06), transparent 26%);
  pointer-events: none;
}

.login-card {
  position: relative;
  z-index: 1;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.95));
  border-radius: 28px;
  box-shadow:
    0 30px 60px rgba(0, 0, 0, 0.18),
    0 10px 24px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.65);
  width: 100%;
  max-width: 432px;
  padding: 1.9rem 2rem 1.2rem;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.login-card.rtl {
  direction: rtl;
}

.login-card::-webkit-scrollbar {
  width: 8px;
}

.login-card::-webkit-scrollbar-thumb {
  background: rgba(16, 24, 40, 0.12);
  border-radius: 999px;
}

.login-logo {
  text-align: center;
  margin-bottom: 1rem;
}

.login-logo-icon {
  width: 74px;
  height: 74px;
  background:
    linear-gradient(180deg, #ffffff, #f5f7f8);
  border-radius: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.55rem;
  box-shadow:
    0 14px 28px rgba(10, 79, 65, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(14, 32, 28, 0.06);
}

.login-logo-icon img {
  width: 70%;
  height: 70%;
  object-fit: contain;
}

.login-title {
  color: var(--charcoal);
  margin: 0 0 0.28rem;
  line-height: 1.08;
  font-size: clamp(2rem, 4vw, 2.5rem);
  font-weight: 780;
  letter-spacing: -0.04em;
  overflow-wrap: anywhere;
}

.login-subtitle {
  color: #617184;
  margin: 0 0 1.15rem;
  line-height: 1.6;
  font-size: 1rem;
  max-width: 30ch;
  margin-left: auto;
  margin-right: auto;
}

.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: inline-block;
  margin-bottom: 0.55rem;
  color: #0f2f2a;
  font-weight: 650;
  font-size: 0.98rem;
  letter-spacing: -0.01em;
}

.form-control {
  width: 100%;
  min-height: 54px;
  padding: 0.95rem 1rem;
  border-radius: 16px;
  border: 1px solid #d7dce2;
  background: linear-gradient(180deg, #ffffff, #fbfcfd);
  color: #102a28;
  font-size: 1rem;
  transition:
    border-color 0.22s ease,
    box-shadow 0.22s ease,
    transform 0.16s ease,
    background-color 0.22s ease;
  box-shadow: inset 0 1px 2px rgba(16, 24, 40, 0.04);
}

.form-control::placeholder {
  color: #94a3b8;
}

.form-control:hover {
  border-color: #c6cdd6;
  background: #ffffff;
}

.form-control:focus {
  outline: none;
  border-color: rgba(10, 79, 65, 0.45);
  box-shadow:
    0 0 0 4px rgba(10, 79, 65, 0.12),
    0 10px 24px rgba(10, 79, 65, 0.08);
  background: #ffffff;
}

.form-text {
  display: inline-block;
  margin-top: 0.6rem;
  color: #6b7b8e;
  font-size: 0.92rem;
  line-height: 1.55;
}

.full-width {
  width: 100%;
}

.btn {
  min-height: 50px;
  border-radius: 16px;
  font-weight: 680;
  font-size: 1rem;
  letter-spacing: -0.01em;
  transition:
    transform 0.18s ease,
    box-shadow 0.2s ease,
    opacity 0.2s ease,
    background-color 0.2s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.btn:active:not(:disabled) {
  transform: translateY(0);
}

.btn-primary {
  background:
    linear-gradient(180deg, rgba(7, 128, 91, 1) 0%, rgba(7, 117, 84, 1) 100%);
  color: #ffffff;
  border: 1px solid rgba(7, 92, 67, 0.72);
  box-shadow:
    0 16px 28px rgba(7, 116, 84, 0.24),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.btn-primary:hover:not(:disabled) {
  box-shadow:
    0 18px 32px rgba(7, 116, 84, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.14);
}

.btn-primary:disabled {
  opacity: 0.72;
  cursor: not-allowed;
  box-shadow: none;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.18);
  color: #103126;
  border: 1px solid rgba(255, 255, 255, 0.38);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 10px 22px rgba(16, 49, 38, 0.08);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.28);
  box-shadow: 0 14px 28px rgba(16, 49, 38, 0.12);
}

.otp-container {
  display: flex;
  gap: 0.6rem;
  justify-content: center;
  margin: 1.9rem 0 1rem;
}

.otp-input {
  width: 48px;
  height: 56px;
  border: 1px solid #d8dee6;
  border-radius: 18px;
  text-align: center;
  font-size: 1.18rem;
  font-weight: 650;
  color: #102a28;
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.16s ease,
    background-color 0.2s ease;
  caret-color: transparent;
  user-select: none;
  background: linear-gradient(180deg, #ffffff, #fbfcfd);
  box-shadow: inset 0 1px 2px rgba(16, 24, 40, 0.03);
}

.otp-input:hover {
  border-color: #c8d0d9;
}

.otp-input:focus {
  border-color: rgba(10, 79, 65, 0.5);
  box-shadow:
    0 0 0 4px rgba(10, 79, 65, 0.12),
    0 10px 22px rgba(10, 79, 65, 0.08);
  background: #ffffff;
  transform: translateY(-1px);
}

.mt-1 {
  margin-top: 1rem;
}

.mt-small {
  margin-top: 0.8rem;
}

.text-center {
  text-align: center;
}

.error-message {
  color: #b42318;
  background: linear-gradient(180deg, #fff5f5, #fff0f0);
  border: 1px solid #f1c4c4;
  text-align: center;
  margin-top: 0.9rem;
  margin-bottom: 0;
  line-height: 1.5;
  overflow-wrap: anywhere;
  padding: 0.75rem 0.85rem;
  border-radius: 14px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.linklike {
  background: none;
  border: none;
  color: var(--dark-green);
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  padding: 0;
  text-decoration: none;
  position: relative;
  transition: color 0.18s ease, opacity 0.18s ease;
}

.linklike::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: currentColor;
  opacity: 0.5;
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.linklike:hover::after {
  opacity: 1;
  transform: scaleX(1);
}

.linklike:hover {
  color: #08664f;
}

.card-spacer {
  height: 1rem;
}

.language-switcher {
  margin-top: 0.9rem;
  padding-top: 0.95rem;
  border-top: 1px solid rgba(16, 24, 40, 0.08);
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.55rem 0.8rem;
}

.language-option {
  background: rgba(16, 24, 40, 0.03);
  border: 1px solid transparent;
  color: #7a8796;
  cursor: pointer;
  font-size: 0.92rem;
  font-weight: 560;
  padding: 0.38rem 0.78rem;
  border-radius: 999px;
  transition:
    color 0.18s ease,
    background-color 0.18s ease,
    border-color 0.18s ease,
    transform 0.18s ease;
  white-space: nowrap;
}

.language-option.active {
  color: #0f2f2a;
  font-weight: 700;
  background: rgba(10, 79, 65, 0.08);
  border-color: rgba(10, 79, 65, 0.14);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.language-option:hover {
  color: #111827;
  background: rgba(16, 24, 40, 0.05);
  transform: translateY(-1px);
}

.role-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin: 0 0 1.15rem;
}

.role-tag {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0.26rem 0.8rem;
  border-radius: 999px;
  font-size: 0.88rem;
  font-weight: 560;
  background: rgba(255, 255, 255, 0.34);
  border: 1px solid rgba(255, 255, 255, 0.38);
  color: #103126;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 8px 22px rgba(16, 49, 38, 0.08);
}

.otp-email {
  margin: 1rem 0 0;
  text-align: center;
  color: #667588;
  font-size: 0.95rem;
  line-height: 1.55;
}

.otp-email strong {
  color: #0f2f2a;
  font-weight: 700;
}

.otp-actions-top {
  margin-top: 0.7rem;
  text-align: center;
}

.otp-expiry-hint {
  margin: 1rem 0 0;
  text-align: center;
  color: #6d7b8d;
  font-size: 0.9rem;
  line-height: 1.55;
}

.status-message {
  color: #0f5132;
  background: linear-gradient(180deg, #f1fbf4, #ebf8ef);
  border: 1px solid #cfe9d7;
  border-radius: 14px;
  text-align: center;
  margin-top: 0.9rem;
  margin-bottom: 0;
  padding: 0.78rem 0.9rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.help-links {
  margin-top: 1rem;
  text-align: center;
  color: #6b7b8e;
  font-size: 0.92rem;
  line-height: 1.5;
}

.help-links a {
  margin-left: 0.35rem;
  color: var(--dark-green);
  text-decoration: none;
  font-weight: 600;
  position: relative;
}

.help-links a::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: currentColor;
  opacity: 0.45;
}

.linklike:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  text-decoration: none;
}

.linklike:disabled::after {
  display: none;
}

.step-email,
.step-otp {
  display: flex;
  flex-direction: column;
  animation: fadeSlideIn 0.28s ease;
}

.step-otp {
  flex: 1;
}

.otp-topbar {
  display: flex;
  align-items: center;
  margin-bottom: 0.75rem;
}

.back-button {
  background: rgba(10, 79, 65, 0.06);
  border: 1px solid rgba(10, 79, 65, 0.08);
  padding: 0.46rem 0.78rem;
  color: var(--dark-green);
  font: inherit;
  font-weight: 650;
  border-radius: 999px;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    transform 0.18s ease,
    border-color 0.18s ease;
}

.back-button:hover {
  background: rgba(10, 79, 65, 0.1);
  border-color: rgba(10, 79, 65, 0.14);
  transform: translateY(-1px);
}

.otp-logo-compact {
  margin-bottom: 0.35rem;
}

.otp-screen-content {
  text-align: center;
  margin-top: 0.35rem;
}

.otp-main-title {
  color: var(--charcoal);
  font-size: 1.12rem;
  font-weight: 650;
  line-height: 1.6;
  margin: 0.55rem 0 0;
  letter-spacing: -0.02em;
}

.otp-help-links {
  margin-top: 1.1rem;
}

.loading {
  display: inline-block;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: rgba(255, 255, 255, 1);
  animation: spin 0.7s linear infinite;
  vertical-align: middle;
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1100px) {
  .split-login {
    grid-template-columns: minmax(0, 1fr) minmax(380px, 460px);
  }

  .login-card {
    max-width: 410px;
  }
}

@media (max-width: 900px) {
  .split-login {
    grid-template-columns: 1fr;
  }

  .right-pane {
    order: -1;
  }

  .left-pane,
  .right-pane {
    padding: 1.5rem 1.25rem;
  }

  .left-pane {
    min-height: 58vh;
  }

  .login-card {
    max-height: none;
    overflow-y: visible;
    max-width: 460px;
    width: 100%;
  }
}

@media (max-width: 560px) {
  .login-card {
    padding: 1.25rem 1.05rem 1rem;
    border-radius: 24px;
  }

  .login-logo-icon {
    width: 66px;
    height: 66px;
    border-radius: 20px;
  }

  .otp-container {
    gap: 0.42rem;
  }

  .otp-input {
    width: 42px;
    height: 50px;
    border-radius: 16px;
  }

  .brand-title {
    font-size: 1.45rem;
  }

  .custom-content :deep(h2.info-title) {
    font-size: 1.7rem;
  }

  .custom-content :deep(p),
  .custom-content :deep(li) {
    font-size: 0.98rem;
  }

  .language-option {
    font-size: 0.88rem;
    padding: 0.34rem 0.68rem;
  }

  .role-tags {
    gap: 0.42rem;
  }

  .role-tag {
    font-size: 0.8rem;
    padding: 0.22rem 0.66rem;
  }

  .status-message,
  .error-message {
    padding-left: 0.75rem;
    padding-right: 0.75rem;
  }

  .otp-main-title {
    font-size: 1rem;
  }
}
</style>