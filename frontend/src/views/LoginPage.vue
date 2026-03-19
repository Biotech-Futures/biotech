<template>
  <!-- 最外层创建容器，类名叫做split-login，登陆页面需要一个大的外层容器包裹全局才能用css控制 -->
  <div class="split-login">
    <!-- Left panel: background slideshow + project introduction -->
    <!-- 左侧容器，使用section标签，类名是left-pane，section表明是一个独立内容区域，类class是为了控制样式 -->
    <section class="left-pane">
      <!-- Background slideshow layer -->
      <!-- 用于承载所有背景图的容器，轮播图不是只有一张图，而是多张图叠在一起，通过 CSS 动画轮流显示。需要一个统一父容器来放这些图层 -->
      <!-- 如果没有这个容器，每一张轮播图就得单独管理，结构会混乱 -->
      <div class="bg-slideshow">
        <!-- 使用div不用imag，因为这里想把图片当“背景”来处理，而不是普通图片元素 -->
        <!-- v-for从 backgroundImages 数组里取出每一项，循环生成多个 div，图片数量可能不固定，用循环更灵活 -->
        <div
          v-for="(image, index) in backgroundImages"
          :key="index"
          class="bg-slide"
          :style="{
            backgroundImage: `url(${image})`,
            animationDelay: `${index * slideDuration}s`
          }"
        ></div>

        <!-- Dark overlay to improve text readability -->
        <!-- 因为背景图往往比较花，如果直接把白字放上去，文字可能看不清，所以通常要加一层半透明深色蒙版。 -->
        <!-- 遮罩本身也是一个图层，单独拆出来更清晰，也更容易改颜色、透明度、渐变方向 -->
        <div class="bg-overlay"></div>
      </div>

      <!-- Foreground content layer -->
      <!-- 接下来是前景文字与按钮区域 -->
      <!-- 创建左侧真正显示内容的内部容器left-inner,背景图和文字不能混在一起 -->
      <div
        class="left-inner"
        :dir="currentDir"
        :class="{ rtl: currentDir === 'rtl' }"
      >
        <!-- Brand area -->
        <!-- 把 logo 和品牌标题放在同一个横向容器里 -->
        <div class="brand">
          <div class="logo-icon">
            <img :src="logo" alt="BIOTech Futures" />
          </div>
          <h1 class="brand-title">{{ t('brandTitle') }}</h1>
        </div>

        <!-- Introductory HTML content -->
        <!-- 把变量 leftHtml 里的 HTML 字符串直接渲染到页面中,比如一个标题，几段p一个列表等等-->
        <div class="custom-content" v-html="leftHtml"></div>

        <!-- External website link -->
        <!-- 接下来是跳转到外部网站的链接按钮，创建一个包裹链接按钮的容器，a是创建一个超链接-->
        <!-- 因为这里的作用是“跳转到另一个网站”，不是触发当前页面 JS 逻辑，所以不用button-->
        <!-- 虽然它本质是链接，但视觉上希望它长得像按钮，所以加按钮样式类btn -->
        <!-- 这里 https://example.org 只是示例地址，真实项目里通常会换成正式官网 -->
        <!-- target="_blank"，表示在新标签页打开链接，如果不写，当前页面会被直接替换掉 -->
        <div class="links">
          <a
            class="btn btn-secondary"
            href="https://4399.com"
            target="_blank"
            rel="noopener"
          >
            {{ t('visitWebsite') }}
          </a>
        </div>
      </div>
    </section>

    <!-- Right panel: login card -->
    <!-- 下面这块是右边的登录卡片区域，创建右侧区域容器 -->
    <section class="right-pane">
      <!-- 创建真正的登录卡片容器，不会直接把表单裸放在背景上，而是通常放进一个“卡片”里，这样视觉更清晰 -->
      <!-- 分两个class，login-card负责外观，fade-in负责动画 -->
      <div
        class="login-card fade-in"
        :dir="currentDir"
        :class="{ rtl: currentDir === 'rtl' }"
      >
        <!-- Login header -->
        <!-- 创建登录卡片顶部的头部区域，包含logo，分化一个专门包裹logo的小容器，限制大小和位置 -->
        <div class="login-logo">
          <div class="login-logo-icon">
            <img :src="logo" alt="BIOTech Futures" />
          </div>
          <h2 class="login-title">{{ t('signIn') }}</h2>
          <p class="login-subtitle">{{ t('welcomeSubtitle') }}</p>
        </div>

        <!-- Email form -->
        <!-- 创建一个表单，并绑定提交事件：@submit：表示监听表单提交事件，.prevent：表示阻止浏览器默认提交行为 -->
        <!-- 默认情况下，HTML 表单提交会：刷新页面，跳转，发传统表单请求 -->
        <!-- 但在 Vue 单页应用里，我们通常不想刷新页面，而是想自己用 JS 发请求，所以要阻止默认行为 -->
        <!-- 提交时执行 handleLogin() 这个函数 -->
        <form @submit.prevent="handleLogin">
          <div class="form-group">
            <!-- 显示输入框对应的说明文字“Email Address” -->
            <label class="form-label">{{ t('emailLabel') }}</label>

            <!-- Email input is linked to the reactive email variable -->
            <!-- 邮箱输入框，实现输入框和email变量的双向绑定，用户输入内容时，email.value 自动更新 -->
            <!-- type="email"，把输入框声明为邮箱类型  -->
            <input
              v-model="email"
              type="email"
              class="form-control"
              :placeholder="t('emailPlaceholder')"
              required
            />

            <!-- Helper text under the input -->
            <small class="form-text">
              {{ t('emailHelper') }}
            </small>
          </div>

          <!-- Submit button for sending login link/code -->
          <!-- 提交按钮注释，type="submit"，声明这是表单提交按钮，当它在 <form> 里面时，点击它会触发表单提交事件，执行 handleLogin() -->
          <!-- disabled="loading"，在 loading 为 true 时禁用按钮，当请求已经发出时，如果不禁用按钮，用户可能连续狂点，导致：重复发请求，发多封邮件，状态混乱 -->
          <button
            type="submit"
            class="btn btn-primary btn-lg full-width"
            :disabled="loading"
          >
            <!-- Show normal text when not loading -->
            <!-- 按钮上的文字，当 loading 为 false 时，也就是常态情况下，按钮里显示“Send Login Link” -->
            <span v-if="!loading">{{ t('sendLoginLink') }}</span>

            <!-- Show loading indicator when request is running -->
            <!-- 点击后，loading切换为true，替换按钮文字，显示一个 loading 圆圈旋转的动画元素 -->
            <span v-else class="loading"></span>
          </button>
        </form>

        <!-- OTP section appears only after email is sent successfully -->
        <!-- 只有 showOTP 为 true 时，才渲染这一整块 OTP 区域 -->
        <div v-if="showOTP" class="otp-section">
          <p class="otp-message">
            {{ t('otpMessage') }}
          </p>

          <!-- OTP input boxes -->
          <!-- v-for="i in 6"-循环生成 6 个输入框 -->
          <!-- @input="handleOTPInput($event, i)"，监听输入事件，一旦输入就执行 handleOTPInput -->
          <!-- $event：当前输入事件对象，i：当前是第几个格子，为了实现“输入一位后自动跳到下一个格子”的交互 -->
          <div class="otp-container">
            <input
              v-for="i in 6"
              :key="i"
              type="text"
              maxlength="1"
              class="otp-input"
              inputmode="numeric"
              @input="handleOTPInput($event, i)"
            />
          </div>

          <!-- Verify OTP button -->
          <button
            type="button"
            class="btn btn-primary full-width mt-1"
            @click="verifyOTP"
          >
            {{ t('verifyCode') }}
          </button>

          <!-- Resend code action -->
          <div class="text-center mt-small">
            <button
              type="button"
              class="linklike"
              @click="resendCode"
            >
              {{ t('resendCode') }}
            </button>
          </div>
        </div>

        <!-- Error message area -->
        <p v-if="error" class="error-message">
          {{ error }}
        </p>

        <!-- Spacer pushes the language switcher to the bottom when there is extra space -->
        <div class="card-spacer"></div>

        <!-- Language switcher stays at the bottom of the card -->
        <!-- 语言切换按钮始终显示在登录卡片最下面，点击后切换全页面文案 -->
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
// Import reactive utilities from Vue
// 从 Vue 导入功能：ref和nextTick，这两个是 Vue 组合式 API 里常用的函数，后面会直接用到
// 从ref 用来创建响应式变量，当它变化时，页面里绑定它的地方会自动更新。
// 因为普通变量改了，Vue 模板不一定知道；但 ref 创建的变量，Vue 会自动监听。
// nextTick 的意思可以理解成：等 Vue 把这一次页面更新真正渲染完，再继续往后执行。
import { ref, nextTick, computed, watch } from 'vue'

// Import router for page navigation
// 导入路由工具，因为这个页面登录成功后要跳转到 dashboard，所以需要“路由控制器”
// const router = useRouter() 就是拿到当前页面可用的路由实例
// await router.replace('/dashboard') 让页面跳转。
import { useRouter } from 'vue-router'

// Import auth store for fetching user information after login
// 从项目里的 ../stores/auth 文件中导入 useAuthStore，统一管理：
// 当前用户是否登录，当前用户资料，登录态，获取用户信息的方法
import { useAuthStore } from '../stores/auth'

// Import logo image
import logo from '@/assets/btf-logo.png'

// Import slideshow background images
import bg1 from '@/assets/login/login-bg-1.jpg'
import bg2 from '@/assets/login/login-bg-2.jpg'
import bg3 from '@/assets/login/login-bg-3.jpg'

// Create router and auth store instances
const router = useRouter()
const auth = useAuthStore()

// Store the background images in an array for v-for rendering
const backgroundImages = [bg1, bg2, bg3]

// Duration in seconds before the next background starts
const slideDuration = 6

// Reactive state for the page
const email = ref('')
const loading = ref(false)
const showOTP = ref(false)
const error = ref('')

// Current language
// 当前页面语言，默认英文，可以改成 zh-CN 作为默认值
const locale = ref('en')

// Supported language options
// 底部显示的语言切换选项
const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: '简体中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'ar', label: 'العربية' },
]

// Translation dictionary
// 所有页面可见文案统一集中管理，后续新增语言时只需要补这里
const messages = {
  en: {
    brandTitle: 'BIOTech Futures Hub',
    signIn: 'Sign in',
    welcomeSubtitle: 'Welcome! Please sign in to continue.',
    emailLabel: 'Email Address',
    emailPlaceholder: 'Enter your email',
    emailHelper: 'We’ll send you a magic link to sign in',
    sendLoginLink: 'Send Login Link',
    otpMessage: 'Click the link in your email to sign in directly, or enter your 6-digit code below',
    verifyCode: 'Verify Code',
    resendCode: 'Resend Code',
    visitWebsite: 'Visit Main Website',
    aboutTitle: 'About the BIOTech Futures Challenge',
    aboutP1: 'The BIOTech Futures Challenge empowers students to tackle real-world problems through innovation, mentorship, and interdisciplinary collaboration.',
    aboutLi1: 'Learn from mentors across academia and industry',
    aboutLi2: 'Develop practical solutions and prototypes',
    aboutLi3: 'Present at showcase events and win awards',
    aboutP2: 'Explore key dates, eligibility, submission guidelines, and more on our website.',
    errorEnterEmail: 'Please enter your email address',
    errorSendLink: 'Failed to send login link. Please try again.',
    errorNetworkLogin: 'Network error. Please check your connection and try again.',
    errorCompleteCode: 'Please enter the complete 6-digit code',
    errorInvalidCode: 'Invalid or expired code',
    errorNetworkOtp: 'Network error. Please try again.',
    errorEnterEmailFirst: 'Please enter your email address first',
    errorResendFail: 'Failed to resend code. Please try again.',
    resendSuccess: 'New code sent to your email!'
  },

  'zh-CN': {
    brandTitle: 'BIOTech Futures 平台',
    signIn: '登录',
    welcomeSubtitle: '欢迎回来，请登录后继续。',
    emailLabel: '邮箱地址',
    emailPlaceholder: '请输入你的邮箱',
    emailHelper: '我们会向你的邮箱发送登录链接',
    sendLoginLink: '发送登录链接',
    otpMessage: '点击邮箱中的链接可直接登录，或在下方输入 6 位验证码',
    verifyCode: '验证验证码',
    resendCode: '重新发送验证码',
    visitWebsite: '访问主网站',
    aboutTitle: '关于 BIOTech Futures 挑战赛',
    aboutP1: 'BIOTech Futures 挑战赛通过创新、导师指导和跨学科协作，鼓励学生解决现实世界中的问题。',
    aboutLi1: '向学术界与产业界导师学习',
    aboutLi2: '开发实用解决方案与原型',
    aboutLi3: '在展示活动中汇报成果并争取奖项',
    aboutP2: '你可以在我们的网站上了解关键日期、资格要求、提交指南等信息。',
    errorEnterEmail: '请输入你的邮箱地址',
    errorSendLink: '发送登录链接失败，请重试。',
    errorNetworkLogin: '网络异常，请检查连接后重试。',
    errorCompleteCode: '请输入完整的 6 位验证码',
    errorInvalidCode: '验证码无效或已过期',
    errorNetworkOtp: '网络异常，请重试。',
    errorEnterEmailFirst: '请先输入你的邮箱地址',
    errorResendFail: '重新发送验证码失败，请重试。',
    resendSuccess: '新的验证码已发送到你的邮箱！'
  },

  ja: {
    brandTitle: 'BIOTech Futures ハブ',
    signIn: 'サインイン',
    welcomeSubtitle: 'ようこそ。続行するにはサインインしてください。',
    emailLabel: 'メールアドレス',
    emailPlaceholder: 'メールアドレスを入力してください',
    emailHelper: 'サインイン用のマジックリンクをメールで送信します',
    sendLoginLink: 'ログインリンクを送信',
    otpMessage: 'メール内のリンクから直接サインインするか、以下に 6 桁のコードを入力してください',
    verifyCode: 'コードを確認',
    resendCode: 'コードを再送信',
    visitWebsite: '公式サイトへ',
    aboutTitle: 'BIOTech Futures チャレンジについて',
    aboutP1: 'BIOTech Futures チャレンジは、イノベーション、メンタリング、学際的な協働を通じて、学生が現実世界の課題に取り組むことを支援します。',
    aboutLi1: '大学・業界のメンターから学ぶ',
    aboutLi2: '実用的なソリューションとプロトタイプを開発する',
    aboutLi3: '成果発表イベントでプレゼンし、表彰を目指す',
    aboutP2: '主な日程、参加資格、提出ガイドラインなどは公式サイトで確認できます。',
    errorEnterEmail: 'メールアドレスを入力してください',
    errorSendLink: 'ログインリンクの送信に失敗しました。もう一度お試しください。',
    errorNetworkLogin: 'ネットワークエラーです。接続を確認してもう一度お試しください。',
    errorCompleteCode: '6 桁のコードをすべて入力してください',
    errorInvalidCode: 'コードが無効か、有効期限が切れています',
    errorNetworkOtp: 'ネットワークエラーです。もう一度お試しください。',
    errorEnterEmailFirst: '先にメールアドレスを入力してください',
    errorResendFail: 'コードの再送信に失敗しました。もう一度お試しください。',
    resendSuccess: '新しいコードをメールに送信しました！'
  },

  ko: {
    brandTitle: 'BIOTech Futures 허브',
    signIn: '로그인',
    welcomeSubtitle: '환영합니다. 계속하려면 로그인해 주세요.',
    emailLabel: '이메일 주소',
    emailPlaceholder: '이메일을 입력하세요',
    emailHelper: '로그인용 매직 링크를 이메일로 보내드립니다',
    sendLoginLink: '로그인 링크 보내기',
    otpMessage: '이메일의 링크를 클릭해 바로 로그인하거나 아래에 6자리 코드를 입력하세요',
    verifyCode: '코드 확인',
    resendCode: '코드 다시 보내기',
    visitWebsite: '메인 웹사이트 방문',
    aboutTitle: 'BIOTech Futures 챌린지 소개',
    aboutP1: 'BIOTech Futures 챌린지는 혁신, 멘토링, 그리고 융합 협업을 통해 학생들이 실제 문제를 해결할 수 있도록 지원합니다.',
    aboutLi1: '학계와 산업계 멘토에게 배우기',
    aboutLi2: '실용적인 솔루션과 프로토타입 개발하기',
    aboutLi3: '쇼케이스 행사에서 발표하고 수상 기회 얻기',
    aboutP2: '주요 일정, 자격 요건, 제출 가이드라인 등은 공식 웹사이트에서 확인할 수 있습니다.',
    errorEnterEmail: '이메일 주소를 입력해 주세요',
    errorSendLink: '로그인 링크 전송에 실패했습니다. 다시 시도해 주세요.',
    errorNetworkLogin: '네트워크 오류입니다. 연결을 확인한 뒤 다시 시도해 주세요.',
    errorCompleteCode: '6자리 코드를 모두 입력해 주세요',
    errorInvalidCode: '코드가 잘못되었거나 만료되었습니다',
    errorNetworkOtp: '네트워크 오류입니다. 다시 시도해 주세요.',
    errorEnterEmailFirst: '먼저 이메일 주소를 입력해 주세요',
    errorResendFail: '코드 재전송에 실패했습니다. 다시 시도해 주세요.',
    resendSuccess: '새 코드가 이메일로 전송되었습니다!'
  },

  ar: {
    brandTitle: 'مركز BIOTech Futures',
    signIn: 'تسجيل الدخول',
    welcomeSubtitle: 'مرحبًا! يرجى تسجيل الدخول للمتابعة.',
    emailLabel: 'البريد الإلكتروني',
    emailPlaceholder: 'أدخل بريدك الإلكتروني',
    emailHelper: 'سنرسل لك رابط تسجيل دخول إلى بريدك الإلكتروني',
    sendLoginLink: 'إرسال رابط تسجيل الدخول',
    otpMessage: 'انقر على الرابط في بريدك الإلكتروني لتسجيل الدخول مباشرة، أو أدخل الرمز المكوّن من 6 أرقام أدناه',
    verifyCode: 'تأكيد الرمز',
    resendCode: 'إعادة إرسال الرمز',
    visitWebsite: 'زيارة الموقع الرئيسي',
    aboutTitle: 'حول تحدي BIOTech Futures',
    aboutP1: 'يمكّن تحدي BIOTech Futures الطلاب من معالجة مشكلات العالم الحقيقي من خلال الابتكار والإرشاد والتعاون متعدد التخصصات.',
    aboutLi1: 'التعلم من مرشدين من الأوساط الأكاديمية والصناعة',
    aboutLi2: 'تطوير حلول ونماذج عملية',
    aboutLi3: 'العرض في فعاليات الاستعراض والفوز بالجوائز',
    aboutP2: 'استكشف المواعيد المهمة ومتطلبات الأهلية وإرشادات التقديم والمزيد على موقعنا.',
    errorEnterEmail: 'يرجى إدخال بريدك الإلكتروني',
    errorSendLink: 'فشل إرسال رابط تسجيل الدخول. يرجى المحاولة مرة أخرى.',
    errorNetworkLogin: 'خطأ في الشبكة. يرجى التحقق من الاتصال والمحاولة مرة أخرى.',
    errorCompleteCode: 'يرجى إدخال الرمز الكامل المكوّن من 6 أرقام',
    errorInvalidCode: 'الرمز غير صالح أو منتهي الصلاحية',
    errorNetworkOtp: 'خطأ في الشبكة. يرجى المحاولة مرة أخرى.',
    errorEnterEmailFirst: 'يرجى إدخال بريدك الإلكتروني أولاً',
    errorResendFail: 'فشل إعادة إرسال الرمز. يرجى المحاولة مرة أخرى.',
    resendSuccess: 'تم إرسال رمز جديد إلى بريدك الإلكتروني!'
  }
}

// Text lookup helper
// 根据当前语言返回对应文案
const t = (key) => {
  return messages[locale.value]?.[key] || messages.en[key] || key
}

// Compute current text direction
// 阿拉伯语使用 rtl，其他语言使用 ltr
const currentDir = computed(() => {
  return locale.value === 'ar' ? 'rtl' : 'ltr'
})

// HTML content shown on the left panel
// 左侧介绍内容改成 computed，这样切换语言时会自动重新生成 HTML
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

// Switch UI language
// 切换语言时更新 locale，并把语言偏好存到浏览器
const switchLanguage = (lang) => {
  locale.value = lang
  error.value = ''
  localStorage.setItem('login-language', lang)
}

// Load saved language from localStorage on first render
// 页面首次加载时读取上一次选择的语言
const savedLanguage = localStorage.getItem('login-language')
if (savedLanguage && languageOptions.some((item) => item.value === savedLanguage)) {
  locale.value = savedLanguage
}

// Update page language metadata
// 这里只同步 lang，不再改整个 html 的 dir，避免阿拉伯语把左右布局整体翻转
watch(
  locale,
  (newLocale) => {
    document.documentElement.lang = newLocale
  },
  { immediate: true }
)

/*
  Send login link or login code to the user's email.

  Main steps:
  1. Check if email is entered
  2. Clear previous errors
  3. Start loading state
  4. Send POST request to backend
  5. If successful, show the OTP area
  6. If failed, display error message
*/
const handleLogin = async () => {
  /*
    判断邮箱是否为空
  */
  if (!email.value) {
    error.value = t('errorEnterEmail')
    return
  }

  /*
    清空旧错误，比如用户第一次没输入邮箱，显示了报错；后来补上邮箱重新提交时，
    旧报错不应该继续留在页面上，所以要先清空。
  */
  error.value = ''

  /*
    这里一旦 loading = true，页面会发生两件事：
    1.按钮变成不可点击
    2.按钮文字变成 loading 动画
    避免用户重复点击，增强交互反馈。
  */
  loading.value = true

  /*
    因为网络请求可能失败，比如：后端没开，网络断了，跨域错误，服务器异常
    所以要用 try...catch...finally 包起来。
  */
  try {
    /*
      1.向后端接口发送 HTTP 请求，并等待返回结果，把结果保存到 response
      2.await 因为请求需要时间，必须等后端返回后才能判断成功还是失败。
      3.表示访问本机 8000 端口上的后端服务里的 send-login-code 接口，即请求后端去“发送登录邮件/验证码”
      4.POST方法是为了把邮箱数据提交给后端，不是单纯的获取数据
      5.headers说明了数据的Json格式
      6.window.location.origin表示当前网站的源地址：http://localhost:5173
      最终拼出来可能是：http://localhost:5173/#/auth/callback
      因为用户点邮件链接后，通常要回到前端某个专门处理登录结果的页面，比如：/auth/callback
    */
    const response = await fetch('http://localhost:8000/services/send-login-code/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,
        redirect_url: `${window.location.origin}/#/auth/callback`,
      }),
    })

    /*
      检查 HTTP 响应是否成功。
      成功后显示 OTP 区域  showOTP.value = true，让验证码输入区域显示出来。
    */
    if (response.ok) {
      // Show the OTP input area after email is sent successfully
      showOTP.value = true
      error.value = ''
    } else {
      // Read backend error message if available
      // 读取后端返回的错误 JSON
      const data = await response.json()
      error.value = data.error || t('errorSendLink')
    }
  } catch (err) {
    // Handle network or unexpected errors
    console.error('Login error:', err)
    error.value = t('errorNetworkLogin')
  } finally {
    // Always stop loading at the end
    loading.value = false
  }
}

/*
  Move the cursor to the next OTP box after one digit is entered.

  Parameters:
  - event: the input event object
  - index: the current OTP box position, starting from 1
*/
const handleOTPInput = (event, index) => {
  const value = event.target.value.replace(/[^0-9]/g, '')
  event.target.value = value

  if (value && index < 6) {
    const inputs = event.target.parentElement.querySelectorAll('input')
    inputs[index]?.focus()
  }
}

/*
  Verify the 6-digit OTP code.

  Main steps:
  1. Read values from all OTP input boxes
  2. Join them into one string
  3. Validate code length
  4. Send verification request to backend
  5. Fetch full user data after success
  6. Navigate to dashboard
*/
const verifyOTP = async () => {
  const inputs = document.querySelectorAll('.otp-input')
  const code = Array.from(inputs).map((input) => input.value).join('')

  if (code.length !== 6) {
    error.value = t('errorCompleteCode')
    return
  }

  try {
    const response = await fetch('http://localhost:8000/services/verify-login-code/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,
        code: code,
      }),
    })

    if (response.ok) {
      // Load the current user's information after successful verification
      await auth.fetchUserData()

      // Wait for Vue to finish updating reactive state
      await nextTick()

      try {
        // Use router navigation first
        // 页面跳转
        await router.replace('/dashboard')
      } catch (err) {
        // Fallback to direct browser navigation if router fails
        window.location.href = '/#/dashboard'
      }
    } else {
      // Show backend validation error if provided
      const errorData = await response.json()
      error.value = errorData.error || t('errorInvalidCode')
    }
  } catch (err) {
    // Handle network or unexpected errors
    console.error('OTP verification error:', err)
    error.value = t('errorNetworkOtp')
  }
}

/*
  Resend the login code to the same email address.

  Main steps:
  1. Make sure email is not empty
  2. Send the same request again
  3. Show success or failure message
*/
const resendCode = async () => {
  if (!email.value) {
    error.value = t('errorEnterEmailFirst')
    return
  }

  //需要注意的一点是，后端地址写死了，这个是本地部署才会这样做，但是如果正式部署要么改成环境变量
  //要么使用统一的API base URL或者代理转发
  try {
    const response = await fetch('http://localhost:8000/services/send-login-code/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,
        redirect_url: `${window.location.origin}/#/auth/callback`,
      }),
    })

    if (response.ok) {
      error.value = ''
      alert(t('resendSuccess'))
    } else {
      error.value = t('errorResendFail')
    }
  } catch (err) {
    console.error('Resend code error:', err)
    error.value = t('errorNetworkOtp')
  }
}
</script>

<style scoped>
/* Main layout: split the page into left and right panels */
.split-login {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100vh;
  background: var(--bg-light);
}

/* Left panel container */
.left-pane {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  min-height: 100vh;
}

/* Slideshow wrapper fills only the left panel */
.bg-slideshow {
  position: absolute;
  inset: 0;
  z-index: 0;
}

/* Each background image slide */
.bg-slide {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center center;
  background-repeat: no-repeat;
  opacity: 0;
  transform: scale(1.06);
  animation: heroSlideshow 18s infinite;
}

/* Dark overlay makes text easier to read */
.bg-overlay {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(
      135deg,
      rgba(8, 31, 28, 0.72) 0%,
      rgba(8, 31, 28, 0.46) 45%,
      rgba(8, 31, 28, 0.62) 100%
    );
}

/* Foreground content sits above the slideshow */
.left-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 560px;
  color: #ffffff;
}

/* RTL support on left side only */
.left-inner.rtl {
  text-align: right;
}

/* Brand row: logo + title */
.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

/* Main brand title */
.brand-title {
  font-size: 1.7rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.2px;
  line-height: 1.2;
  margin: 0;
  overflow-wrap: anywhere;
}

/* Left-side logo container */
.logo-icon {
  width: 48px;
  height: 48px;
  background-color: rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 48px;
}

/* Left-side logo image */
.logo-icon img {
  width: 70%;
  height: 70%;
  object-fit: contain;
}

/* Intro content wrapper */
.custom-content {
  max-width: 100%;
}

/* Intro heading */
.custom-content :deep(h2.info-title) {
  font-size: 2rem;
  margin: 0 0 0.8rem;
  color: #ffffff;
  line-height: 1.2;
  overflow-wrap: anywhere;
}

/* Intro paragraph text */
.custom-content :deep(p) {
  color: rgba(255, 255, 255, 0.9);
  margin: 0 0 0.8rem;
  line-height: 1.65;
  font-size: 1.02rem;
  overflow-wrap: anywhere;
}

/* Intro list */
.custom-content :deep(ul.info-list) {
  margin: 0.7rem 0 1rem 1.2rem;
  color: rgba(255, 255, 255, 0.96);
  line-height: 1.65;
  padding-inline-start: 0.8rem;
}

/* RTL list alignment */
.left-inner.rtl .custom-content :deep(ul.info-list) {
  margin: 0.7rem 1.2rem 1rem 0;
  padding-inline-start: 0;
  padding-inline-end: 0.8rem;
}

/* Intro list items */
.custom-content :deep(li) {
  margin-bottom: 0.35rem;
  overflow-wrap: anywhere;
}

/* Link button wrapper */
.links {
  margin-top: 1.1rem;
}

/* Secondary button style on image background */
.btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.28);
  backdrop-filter: blur(8px);
}

/* Hover effect for secondary button */
.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.18);
}

/* Right panel container */
.right-pane {
  background: var(--dark-green);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

/* Main login card */
.login-card {
  background-color: var(--white);
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
  width: 100%;
  max-width: 420px;
  padding: 1.6rem 1.8rem 1.2rem;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 4rem);
  overflow-y: auto;
}

/* RTL support only inside the card */
.login-card.rtl {
  direction: rtl;
}

/* Login header area */
.login-logo {
  text-align: center;
  margin-bottom: 0.8rem;
}

/* Right-side logo container */
.login-logo-icon {
  width: 68px;
  height: 68px;
  background-color: var(--white);
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.35rem;
}

/* Right-side logo image */
.login-logo-icon img {
  width: 70%;
  height: 70%;
  object-fit: contain;
}

/* Login title */
.login-title {
  color: var(--charcoal);
  margin: 0 0 0.2rem;
  line-height: 1.2;
  overflow-wrap: anywhere;
}

/* Login subtitle */
.login-subtitle {
  color: #6c757d;
  margin: 0 0 1rem;
  line-height: 1.45;
}

/* Form group */
.form-group {
  margin-bottom: 0.9rem;
}

/* Utility class for full-width elements */
.full-width {
  width: 100%;
}

/* Button height */
.btn {
  min-height: 46px;
}

/* OTP section */
.otp-section {
  margin-top: 1rem;
}

/* OTP instruction message */
.otp-message {
  text-align: center;
  margin: 0 0 0.9rem;
  line-height: 1.55;
  color: var(--charcoal);
}

/* OTP input container */
.otp-container {
  display: flex;
  gap: 0.45rem;
  justify-content: center;
  margin-bottom: 0.9rem;
}

/* OTP input box */
.otp-input {
  width: 44px;
  height: 48px;
  border: 1px solid #d7dce2;
  border-radius: 10px;
  text-align: center;
  font-size: 1.1rem;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

/* OTP focus state */
.otp-input:focus {
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(10, 79, 65, 0.12);
}

/* Small margin helper */
.mt-1 {
  margin-top: 0.9rem;
}

/* Smaller top margin helper */
.mt-small {
  margin-top: 0.65rem;
}

/* Center alignment helper */
.text-center {
  text-align: center;
}

/* Error message style */
.error-message {
  color: #dc3545;
  text-align: center;
  margin-top: 0.7rem;
  margin-bottom: 0;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

/* Link-like button for resend action */
.linklike {
  background: none;
  border: none;
  color: var(--dark-green);
  cursor: pointer;
  font: inherit;
  padding: 0;
  text-decoration: underline;
}

/* Spacer so language bar can stay at bottom when content is short */
.card-spacer {
  flex: 1;
  min-height: 0.6rem;
}

/* Bottom language selector */
.language-switcher {
  margin-top: 0.8rem;
  padding-top: 0.8rem;
  border-top: 1px solid #e8ebef;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.45rem 0.8rem;
}

/* Each language button */
.language-option {
  background: transparent;
  border: none;
  color: #8b949e;
  cursor: pointer;
  font-size: 0.95rem;
  padding: 0;
  transition: color 0.2s ease, font-weight 0.2s ease;
  white-space: nowrap;
}

/* Active language state */
.language-option.active {
  color: #111827;
  font-weight: 700;
}

/* Hover state */
.language-option:hover {
  color: #111827;
}

/* Background slideshow animation */
@keyframes heroSlideshow {
  0% {
    opacity: 0;
    transform: scale(1.06);
  }
  8% {
    opacity: 1;
    transform: scale(1.03);
  }
  28% {
    opacity: 1;
    transform: scale(1);
  }
  36% {
    opacity: 0;
    transform: scale(1.02);
  }
  100% {
    opacity: 0;
    transform: scale(1.06);
  }
}

/* Responsive layout for smaller screens */
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

  .login-card {
    max-height: none;
    overflow-y: visible;
  }
}

@media (max-width: 560px) {
  .login-card {
    padding: 1.25rem 1.1rem 1rem;
  }

  .otp-container {
    gap: 0.35rem;
  }

  .otp-input {
    width: 40px;
    height: 44px;
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
    font-size: 0.9rem;
  }
}
</style>