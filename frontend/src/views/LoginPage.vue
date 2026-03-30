<template>
  <!--将整个页面分为左右两个页面的大容器-->
  <div class="split-login">
    <!--左侧动画介绍台，包裹左边的最底层容器-->
    <!--1.section表明是独立功能区，该DOM节点名字为‘leftPaneRef’，类class决定属性，比如长和宽以及位置大小等-->
    <!--2.:class=‘’表明是动态class，会随着背景值的不同而切换布局，用于切换背景，比如：activeLeftBackground = 'original'，class="left-pane bg-mode-original"-->
    <section ref="leftPaneRef" class="left-pane" :class="`bg-mode-${activeLeftBackground}`">
      <!--左侧中层容器，背景舞台层，单独一层是因为要作为最底层的背景，上面还要有文字生成，stack表明是堆叠-->
      <div class="left-bg-stack">
        <!--第一种模式的背景，即默认状态下的背景，aria那里表明是只是装饰-->
        <div
          class="bg-slideshow"
          :class="{ active: activeLeftBackground === 'original' }"
          aria-hidden="true"
          >
          <!--这里是三张图片循环播放作为第一种模式的背景，key是每个循环唯一标识，也就是index，class表明每个背景都是一张图层的样式-->
          <div
            v-for="(image, index) in backgroundImages"
            :key="index"
            class="bg-slide"
            :style="{
              backgroundImage: `url(${image})`,
              animationDelay: `${index * slideDuration}s`
            }"
          ></div>
          <!--加一层滤镜，让背景更加柔和，不然上面的文字很难看清-->
          <div class="bg-overlay bg-overlay-original"></div>
        </div>
        <!--第二种模式的背景，three.js生成的模型背景-->
        <div
          class="biotech-bg"
          :class="{ active: activeLeftBackground === 'biotech' }"
          aria-hidden="true"
        >
          <!--但不是简单的静态北京，而是js动态渲染特效的载点，在页面加载后把特效渲染进这个DOM里-->
          <!--class是为了方便css统一外观，ref这里是方便js直接定位，没有ref只是说明这个元素不需要js直接对DOM节点做操作，这里需要往这个节点直接填入里自动化-->
          <!--比如这里的biotechSceneRef的值为True，那后续可能根据这个值进行一些函数操作-->
          <div ref="biotechSceneRef" class="biotech-scene"></div>
          <!--加一层滤镜，让背景更加柔和，不然上面的文字很难看清-->
          <div class="bg-overlay bg-overlay-biotech"></div>
        </div>
      </div>

      <!--除了上述两种背景模式，还需要一个按钮来切换背景-->
      <!--@click表示是Vue的事件绑定，意思是点击这个按钮的时候，会去调用函数，调整activeLeftBackground这个变量的值，从而决定是哪一个背景-->
      <!--title=这个变量决定了鼠标悬停时候显示的文字，{{ 按钮上显示的文字 }}-->
      <button
        type="button"
        class="left-bg-toggle"
        @click="toggleLeftBackground"
        :aria-label="backgroundToggleLabel"
        :title="backgroundToggleLabel"
      >
        {{ backgroundToggleText }}
      </button>

      <!--左侧最上层，文字容器-->
      <!--:dir="currentDir"考虑国际化阿拉伯语言，动态设置文本方向-->
      <!--:class="{ rtl: currentDir === 'rtl' }"如果当前方向是rtl，就额外加上rtl样式-->
      <div class="left-inner" :dir="currentDir" :class="{ rtl: currentDir === 'rtl' }">
        <!--文字第一行标题和品牌区域-->
        <!--alt是文字替换图片，如果如片加载失败就展示文字-->
        <div class="brand">
          <div class="logo-icon">
            <img :src="logo" alt="BIOTech Futures" />
          </div>
          <h1 class="brand-title">{{ t('brandTitle') }}</h1>
        </div>

        <!--角色标签容器，一共四个小板块，快速定位用户身份-->
        <div class="role-tags" aria-label="Portal roles">
          <span class="role-tag">{{ t('roleStudent') }}</span>
          <span class="role-tag">{{ t('roleMentor') }}</span>
          <span class="role-tag">{{ t('roleSupervisor') }}</span>
          <span class="role-tag">{{ t('roleAdmin') }}</span>
        </div>

        <!--自定义文本内容容器，通过变量注入，方便更改-->
        <div class="custom-content" v-html="leftHtml"></div>

        <!--跳官网按钮-->
        <!--target="_blank"，意思是新标签页打开，用户不会离开当前系统界面。-->
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

    <!--右侧登录控制台，包裹右侧的最底层容器-->
    <section class="right-pane">
      <div class="login-card fade-in" :dir="currentDir" :class="{ rtl: currentDir === 'rtl' }">
        
        <!--邮箱入口，只有currentStep这个变量是email时，这里才显示，不然显示的就是验证码-->
        <div v-if="currentStep === 'email'" class="step-email">
          <div class="login-logo">
            <div class="login-logo-icon">
              <img :src="logo" alt="BIOTech Futures" />
            </div>
            <h2 class="login-title">{{ t('signIn') }}</h2>
            <p class="login-subtitle">{{ t('welcomeSubtitle') }}</p>
          </div>

          <!--form提交表单，填写邮箱后通过接口传输给后端进行下一步处理-->
          <!--submit.prevent阻止浏览器默认提交刷新页面，novalidate不依赖原生弹窗-->
          <form @submit.prevent="handleLogin" novalidate>
            <div class="form-group">

              <!--输入框上方的小标签，表明需要输入的内容是什么，屏幕阅读器也会读出这个内容-->
              <label class="form-label" for="login-email">
                {{ t('emailLabel') }}
              </label>

              <!--邮箱输入框-->
              <!--ref="emailInputRef"以后可以通过该变量直接访问这个DOM元素，比如页面加载好自动聚焦到这里-->
              <!--:placeholder="t('emailPlaceholder')"占位符-->
              <!--autocomplete="email"允许浏览器自动填充邮箱-->
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
                "
              />
              <small class="form-text">
                {{ t('emailHelper') }}
              </small>
            </div>

            <!--发送验证码按钮-->
            <!--type=submit说明按钮会触发表单form提交-->
            <!--:disabled说明邮箱在两种情况下是禁用的，一个取决于sandingcode的值，如果在发送验证码就是禁用，第二个取决于发送后倒计时是否归零，不然就只能等-->
            <button
              type="submit"
              class="btn btn-primary btn-lg full-width"
              :disabled="sendingCode || resendCountdown > 0"
            >
              <!--如果满足条件，显示的就是该文字，即正常状态下的发送验证码-->
              <span v-if="!sendingCode && resendCountdown === 0">
                {{ t('sendVerificationCode') }}
              </span>
              <!--如果满足正在发送，那么就是显示laoding动画-->
              <span v-else-if="sendingCode" class="loading"></span>
              <!--如果都不是，那就说明正在倒计时，显示倒计时resend in xxs动画-->
              <span v-else>
                {{ t('resendIn') }} {{ resendCountdown }}s
              </span>
            </button>
          </form>

          <!--输入框下方的提示，如果成功发送，就会提示已经发送验证码，如果邮箱格式错误，就会提示错误-->
          <p v-if="statusMessage" class="status-message" aria-live="polite">
            {{ statusMessage }}
          </p>
          <p v-if="error" class="error-message" role="alert" aria-live="assertive">
            {{ error }}
          </p>
        </div>

        <!--和之前的div if对应，如果此时的步骤不是email，说明就是到了OTP验证区，显示的是输入验证码-->
        <div v-else class="step-otp">

          <!--验证码容器第一层，网页标签图片-->
          <div class="login-logo otp-logo-compact">
            <div class="login-logo-icon">
              <img :src="logo" alt="BIOTech Futures" />
            </div>
          </div>

          <!--第二层，文字，显示已发送验证码至邮箱-->
          <div class="otp-screen-content">
            <p class="otp-email">
              {{ t('codeSentTo') }} <strong>{{ maskedEmail }}</strong>
            </p>

            <!--第三层，提供返回上一层修改邮箱的按钮-->
            <div class="otp-actions-top">
              <button type="button" class="linklike" @click="goBackToEmailStep">
                {{ t('changeEmail') }}
              </button>
            </div>

            <!--第四层，验证码输入框-->
            <!--v-for为了方便一次性生成六个input小格子，根据otpDigits的长度和里面的值决定，digit是当前值，index是当前下标，v-model捆绑在对应名字的数组里-->
            <!--:ref="(el) => setOtpRef(el, index)"：每一格输入框都被命名为响应变量，方便后续函数操作，焦点切换-->
            <!--type=‘text’表明输入的是文本数字-->
            <!--maxlength=“1”每格长度是1-->
            <!--事件对象$event，发生了什么事件就是什么事件对象，传递给相应的函数，比如@input就是键盘输入这个事件，绑定的函数可能是自动跳到下一格-->
            <!--@keydown键盘控制，比如左右移动光标切换焦点-->
            <!--@keydown.enter按回车尝试验证-->
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

            <!--验证按钮-->
            <button
              type="button"
              class="btn btn-primary full-width mt-1"
              :disabled="verifyingCode || !isOtpComplete"
              @click="verifyOTP"
            >
              <span v-if="!verifyingCode">{{ t('verifyCode') }}</span>
              <span v-else class="loading"></span>
            </button>

            <!--重新发送验证码按钮-->
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

            <!--求助链接-->
            <div class="help-links otp-help-links">
              <!--前半句提示词，没有交互，只是显示文字-->
              <span>{{ t('needHelp') }}</span>
              <!--点击后，尝试调用手机或电脑端的邮件客户端并发邮件-->
              <a href="mailto:support@biotechfutures.org">{{ t('contactSupport') }}</a>
            </div>
          </div>

          <p v-if="statusMessage" class="status-message" aria-live="polite">
            {{ statusMessage }}
          </p>
          <p v-if="error" class="error-message" role="alert" aria-live="assertive">
            {{ error }}
          </p>
        </div>

        <!--横线-->
        <div class="card-spacer"></div>

        <!--语言开关容器-->
        <div class="language-switcher" role="tablist" aria-label="Language switcher">

          <!--批量制造按钮，通过for循环，将languageOptions里的变量都拿出来生成按钮-->
          <!--比如：item = { value: 'en', label: 'English' }-->
          <!--:class="{ active: locale === item.value }"高亮开关-->
          <!--@click通过点击事件来切换语言-->
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
import { ref, nextTick, computed, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

import logo from '@/assets/btf-logo.png'
import bg1 from '@/assets/login/login-bg-1.jpg'
import bg2 from '@/assets/login/login-bg-2.jpg'
import bg3 from '@/assets/login/login-bg-3.jpg'

const router = useRouter()
const auth = useAuthStore()

const backgroundImages = [bg1, bg2, bg3]
const slideDuration = 6

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const email = ref('')

//默认状态就是输入email状态
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

const locale = ref('en')
const leftPaneRef = ref(null)
const biotechSceneRef = ref(null)
const activeLeftBackground = ref('original')

// 切换背景使用，如果是模式一就切换到模式二，
// 这是一个箭头函数arrow function，被赋值给常量，本质上是函数：function toggleLeftBackground() {......}
//用于点击事件绑定的动作（函数），目的是更改
const toggleLeftBackground = () => {
  activeLeftBackground.value = activeLeftBackground.value === 'original' ? 'biotech' : 'original'
}

// 虽然也是箭头函数，但跟上一个不一样，这个并不是直接把函数赋值，而是把computed返回结果赋值给常量
// 这是一个计算值computed，根据当前状态显示，调用的话需要使用 backgroundToggleText.value
//用于给按钮显示文字，目的是算出一个值
const backgroundToggleText = computed(() => {
  return activeLeftBackground.value === 'original' ? 'DNA' : 'IMG'
})

//用于悬停背景切换按钮显示文字，和上面同理
const backgroundToggleLabel = computed(() => {
  return activeLeftBackground.value === 'original'
    ? 'Switch to biotech 3D background'
    : 'Switch to image slideshow background'
})

//value用来告诉v-for建造几个button，label则是button的名字，{{item.label}}
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

// t('signIn')：调用函数 t，并把 'signIn' 这个字符串传进去。也就是这里的（key）是形参
// 如果messages[locale.value]存在，就取key，否则就退回英文
// ?.语法是一个判断optional chaining，如果?前的结果存在，那么取.后的值，不存在返回undifined
const t = (key) => {
  return messages[locale.value]?.[key] || messages.en[key]
}

// 这个是调整文字方向的
const currentDir = computed(() => {
  return locale.value === 'ar' ? 'rtl' : 'ltr'
})

// leftHtml是一个计算属性
// ``这是反引号，用来定义模板字符串，里面还可以用${}来引用变量
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

// 计算属性，根据email的值计算
// 如果email值存在?.trim()就删去前后空格
// 邮箱按照@分前后两部分，比如fsq136656和gmail.com
const maskedEmail = computed(() => {
  const value = email.value?.trim() || ''
  const parts = value.split('@')

  if (parts.length !== 2) {
    return value
  }

  // fsq136656和gmail.com
  const [name, domain] = parts

  if (name.length <= 2) {
    return `${name[0] || '*'}***@${domain}`
  }

  return `${name.slice(0, 2)}***@${domain}`
})

// 切换语言的函数，（lang）形参，在切换语言区域，点击对应的按钮，就会调用此函数切换语言，语言是由locale的值决定
// 最后一句，用户点击后，语言会被保存到本地浏览器里。
// 页面下次打开时，默认点亮的就不是写死的初始值，而是上次用户选过的语言。
const switchLanguage = (lang) => {
  locale.value = lang
  error.value = ''
  statusMessage.value = ''
  localStorage.setItem('login-language', lang)
}

// 从本地浏览器数据中读出‘login-language’，看上次使用的是什么语言加载
// languageOptions是那五种语言，检查数组里至少有一个满足条件
const savedLanguage = localStorage.getItem('login-language')
if (savedLanguage && languageOptions.some((item) => item.value === savedLanguage)) {
  locale.value = savedLanguage
}

// 保存验证码每一位值
const setOtpRef = (el, index) => {
  if (el) {
    otpRefs.value[index] = el
  }
}

// async异步函数，可在函数内部使用await
// 异步函数是不需要立刻出结果的动作，不能像普通代码一样立刻跑完，因为操作时间长，比如请求后端，读取文件，查询数据库
// 同步函数比如普通的a+b函数，立刻就能得到结果。
// 异步函数需要async()声明，而且返回的是一个promise，也就是未来会拿到的一个状态
// 先调用接口并使用await等待完成比如：const response = await fetch('/api/user')
// 然后等接口返回后再执行下面代码，把响应转化为JSON：const data = await response.json()
// 用户触发输入验证码完成后，检查验证码是否完整并是否正在验证，如果允许就进入验证环节
const handleOTPEnter = async () => {
  if (!isOtpComplete.value || verifyingCode.value) {
    return
  }
  await verifyOTP()
}

// 处理 OTP 输入框输入事件的函数，$event是看当前的事件是什么，对事件进行处理
// event.target表示触发这次事件的元素，比如要是在第三个OTP输入框输入内容，那么它就表示这个框的DOM元素
// event.target.value就表示这个输入框的元素
// .replace清洗字符串，把所有不是数字的字符全部换成空字符
const handleOTPInput = (event, index) => {
  const value = event.target.value.replace(/[^0-9]/g, '')
  otpDigits.value[index] = value

  // 有内容且不是最后一个输入框，就自动跳转到下一格输入框
  if (value && index < otpDigits.value.length - 1) {
    otpRefs.value[index + 1]?.focus()
  }
}

// OTP 输入框的键盘按键控制函数
// event来说，如果按1，event就是“1”这个按钮，如果回车就是回车，如果backspace就是删除等
const handleOTPKeydown = (event, index) => {

  // event.key保存的是对应键值的字符串名称
  const key = event.key

  //不依赖默认的删除行为，自定义
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

  //如果是空格就阻止输入
  if (key === ' ' || key === 'Spacebar') {
    event.preventDefault()
    return
  }

  //允许这类功能键通过，即什么都不做
  const allowedKeys = ['Tab', 'Shift', 'Control', 'Meta', 'Alt', 'Enter']
  if (allowedKeys.includes(key)) {
    return
  }

  // 正则表达式：^表示字符串开头，[0-9]表示一个数字字符，$字符串结尾
  //.test()正则方法，检验key是否匹配
  if (!/^[0-9]$/.test(key)) {
    event.preventDefault()
  }
}

//输入框只要被点击，被tab，被程序focus()到的时候，函数就会执行
// .select()代表选中文本内容
const handleOTPFocus = (event) => {
  event.target.select()
}

// 一次性粘贴验证码时，拦截默认粘贴行为，将内容清洗为纯数字，并填充进6个OTP输入框中
// 为什么拦截？因为可能会导致第一个框直接把所有验证码都接受了，然后被截断
const handleOTPPaste = (event) => {
  event.preventDefault()

  // event.clipboardData是粘贴事件里的剪贴板数据对象
  // .getData('text')获取纯文本内容
  // .slice(0,6)只保留第0-5为数字，一共六位
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

  // 如果只输入了3位那么焦点就会摆在最近一位空着的地方，也就是length = 4，第4位
  // 如果输入满了，length = 6,那么最后还是会在最后一位第五位那里
  const nextIndex = Math.min(chars.length, 5)
  otpRefs.value[nextIndex]?.focus()
}

// 判断是否是合法邮箱格式
// ^字符串开头，[]字符集合，[^]^表示取反，\s表示空白字符比如空格换行之类的，[^\s@]表示不是空白字符也不是@的任意一个字符
// +表示至少一个
// $表示字符串结尾
const isValidEmail = (value) => {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

//尝试把相应回复解析成JSON格式的数据
const parseErrorMessage = async (response, fallbackText) => {
  try {
    const data = await response.json()
    return data.error || data.message || fallbackText
  } catch {
    return fallbackText
  }
}

// 会拼出这样一个字符串https://your-site.com/#/auth/callback
// window.location.origin表示当前网页的源地址，比如：http://localhost:5173/#/login会变成http://localhost:5173
// 使用#是因为前端用的是Hash history，网页地址会变成：http://localhost:5173/#/login这种模式
// # 前面：浏览器真实访问的页面；后面：Vue 前端自己解析的路由路径
// /#/login是前端的路由地址，作用是让Vue在浏览器知道现在需要渲染哪个页面组件
// 项目本身是，前端负责路由页面，后端负责接口，认证，数据，两边给通过HTTP来请求通信
// Vue项目中，浏览器真正加载的只有一个入口，之后的页面跳转要Vue自己切换组件，比如从登陆界面到dashboard界面
// 这个是为了让后端处理完数据跳转到这个网页去
const buildCallbackUrl = () => {
  return `${window.location.origin}/#/auth/callback`
}

// 重发验证码倒计时
const startResendCountdown = () => {
  // 验证码有效时限30s
  resendCountdown.value = 30

  // 如果之前有定时器了就清除掉
  if (resendTimer) {
    clearInterval(resendTimer)
  }

  //创建一个每秒执行一次的定时器，并把它保存在resendTimer里，直到减到零位置
  // 1000ms就是一秒
  // 之哟啊调用一次，就是跑一轮30s的，而不是一秒一秒的调用，一次跑满
  // Vue会每次自动刷新渲染
  resendTimer = setInterval(() => {
    if (resendCountdown.value > 0) {
      resendCountdown.value -= 1
    } else {
      clearInterval(resendTimer)
      resendTimer = null
    }
  }, 1000)
}

// 重置OTP状态
// await nextTick()，等待 Vue 先把刚刚的数据变化更新到 DOM 上。
// 之后等待光标自动回到第一个格子里
// 修改响应式数据不代表DOM会在这一行代码执行完的瞬间立刻更新好。
// Vue 为了性能，通常会把这些更新先收集起来，然后在“下一轮 DOM 更新”里一起渲染。
// 所以如果紧接着立刻去操作页面元素，比如：focus()；读取某个 input；获取某个元素是否已经出现，这时候可能页面还没更新完。
const resetOtpState = async () => {
  otpDigits.value = ['', '', '', '', '', '']
  await nextTick()
  otpRefs.value[0]?.focus()
}

// 从change email那里返回输入邮箱的界面
const goBackToEmailStep = async () => {
  currentStep.value = 'email'
  error.value = ''
  statusMessage.value = ''
  await nextTick()
  emailInputRef.value?.focus()
}

// 邮件提交发送验证码主函数
const handleLogin = async () => {

  // 处理邮件，去除空格，小写
  const normalizedEmail = email.value.trim().toLowerCase()

  // 函数三大判断自检是否中断
  // 判断是否有邮件
  if (!normalizedEmail) {
    error.value = t('errorEnterEmail')
    statusMessage.value = ''
    return
  }

  // 邮件格式不合法
  if (!isValidEmail(normalizedEmail)) {
    error.value = t('errorInvalidEmail')
    statusMessage.value = ''
    return
  }

  email.value = normalizedEmail
  error.value = ''
  statusMessage.value = ''

  if (resendCountdown.value > 0) {
    statusMessage.value = `${t('resendIn')} ${resendCountdown.value}s`
    return
  }

  // 表示正在发送验证码
  sendingCode.value = true

  // 函数主体
  try {

    // 请求函数接口
    const response = await fetch(`${API_BASE_URL}/services/send-login-code/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,

        // 表明后端处理完后的重定向链接地址
        redirect_url: buildCallbackUrl(),
      }),
    })

    // 如果接收成功并返回信息
    if (response.ok) {
      currentStep.value = 'otp'

      // 表明发送成功
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

// 检验验证码
const verifyOTP = async () => {
  // 验证码拼接
  const code = otpDigits.value.join('')

  // 如果输入的位数不够就点击验证，报错
  if (code.length !== 6) {
    error.value = t('errorCompleteCode')
    statusMessage.value = ''
    return
  }

  error.value = ''
  statusMessage.value = t('signingIn')
  verifyingCode.value = true

  try {
    // 发送请求
    const response = await fetch(`${API_BASE_URL}/services/verify-login-code/`, {
      method: 'POST',
      // 说明请求体是 JSON 格式，后端要按 JSON 解析。
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({
        email: email.value,
        code,
      }),
    })

    // 一般ok表示200/204后端返回，进入if判断逻辑，如果错误就会返回400/401/403进入else
    if (response.ok) {
      await auth.fetchUserData()

      // nextTick() 是 Vue 里的一个工具，等 Vue 把刚刚更新的数据和页面状态处理完，再继续往下执行。
      // 有的时候需要，是因为要让Vue刷新更改页面，但有的时候只需要使用更新后的数据，那就不需要这个来刷新了
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

// 重发验证码，一样的逻辑，也是请求接口
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

let particleSystem = null
let particleMaterial = null
let particleGeometry = null

const floatingItems = []
const mouseNdc = new THREE.Vector2(10, 10)
const mouseWorld = new THREE.Vector3(999, 999, 0)
const raycaster = new THREE.Raycaster()
const interactionPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0)

const createSoftMaterial = (color, opacity = 1, emissive = '#000000') => {
  return new THREE.MeshPhysicalMaterial({
    color,
    emissive,
    emissiveIntensity: 0.08,
    roughness: 0.18,
    metalness: 0.06,
    transmission: opacity < 1 ? 0.38 : 0,
    transparent: opacity < 1,
    opacity,
    clearcoat: 0.9,
    clearcoatRoughness: 0.16,
    reflectivity: 0.5,
    ior: 1.28
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

const createBacteriaModel = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const bodyMaterial = createSoftMaterial('#7adf9d', 0.94, '#1b5e37')
  const stripeMaterial = createSoftMaterial('#bdf6cf', 0.88, '#215c3a')
  const flagellaMaterial = new THREE.MeshStandardMaterial({
    color: '#d7ffe4',
    roughness: 0.52,
    metalness: 0.04
  })

  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.42, 1.45, 14, 28),
    bodyMaterial
  )
  body.rotation.z = Math.PI / 2
  group.add(body)

  for (let i = -2; i <= 2; i++) {
    const stripe = new THREE.Mesh(
      new THREE.TorusGeometry(0.24, 0.024, 12, 40),
      stripeMaterial
    )
    stripe.rotation.y = Math.PI / 2
    stripe.position.x = i * 0.24
    stripe.scale.set(1, 1.55, 1)
    group.add(stripe)
  }

  const nucleusDots = [
    [-0.24, 0.06, 0.1],
    [0.02, -0.1, -0.08],
    [0.3, 0.12, 0.06],
    [0.12, 0.18, -0.12]
  ]

  nucleusDots.forEach(([px, py, pz], index) => {
    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(index % 2 === 0 ? 0.065 : 0.05, 18, 18),
      createSoftMaterial(index % 2 === 0 ? '#e7fff0' : '#9cf4bb', 0.95, '#275f41')
    )
    dot.position.set(px, py, pz)
    group.add(dot)
  })

  for (let i = 0; i < 6; i++) {
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.68, 0, 0),
      new THREE.Vector3(0.98 + i * 0.05, (i - 2.5) * 0.08, 0.08 * Math.sin(i)),
      new THREE.Vector3(1.28 + i * 0.08, (i - 2.5) * 0.16, 0.2 * Math.cos(i)),
      new THREE.Vector3(1.72 + i * 0.1, (i - 2.5) * 0.24, 0.26 * Math.sin(i * 1.3))
    ])

    const tail = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 48, 0.014, 8, false),
      flagellaMaterial
    )
    group.add(tail)
  }

  group.scale.setScalar(scale)
  group.rotation.z = -0.28
  group.position.set(x, y, 0)
  return group
}

const createProteinComplex = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const colors = ['#7fd0ff', '#b9e8ff', '#5db1ff', '#d9f6ff', '#86c7ff']
  const positions = [
    [0, 0, 0],
    [0.48, 0.18, 0.12],
    [-0.42, 0.26, -0.08],
    [0.16, -0.42, 0.1],
    [-0.26, -0.34, -0.12],
    [0.02, 0.52, -0.06]
  ]

  positions.forEach((pos, index) => {
    const blob = new THREE.Mesh(
      new THREE.IcosahedronGeometry(index === 0 ? 0.34 : 0.22, 2),
      createSoftMaterial(colors[index % colors.length], 0.96, '#0d3f67')
    )
    blob.position.set(pos[0], pos[1], pos[2])
    blob.rotation.set(Math.random(), Math.random(), Math.random())
    group.add(blob)
  })

  const linkMaterial = new THREE.MeshStandardMaterial({
    color: '#d8f4ff',
    roughness: 0.42,
    metalness: 0.06
  })

  for (let i = 1; i < positions.length; i++) {
    const start = new THREE.Vector3(...positions[0])
    const end = new THREE.Vector3(...positions[i])
    const direction = new THREE.Vector3().subVectors(end, start)
    const length = direction.length()

    const bond = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.038, Math.max(0.08, length - 0.06), 6, 12),
      linkMaterial
    )

    bond.position.copy(start.clone().add(end).multiplyScalar(0.5))
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
    createSoftMaterial('#fff2db', 0.95, '#7a4f12')
  )
  left.scale.x = 0.9
  left.position.x = -0.34

  const right = new THREE.Mesh(
    new THREE.SphereGeometry(0.42, 32, 32),
    createSoftMaterial('#ffb36b', 0.95, '#7a3d08')
  )
  right.scale.x = 0.9
  right.position.x = 0.34

  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(0.36, 0.36, 0.78, 32),
    createSoftMaterial('#ffe2bf', 0.92, '#7c4b14')
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
    createSoftMaterial('#d8f6ff', 0.62, '#14485b')
  )

  const core = new THREE.Mesh(
    new THREE.CircleGeometry(0.62, 48),
    new THREE.MeshPhysicalMaterial({
      color: '#72baff',
      transparent: true,
      opacity: 0.26,
      roughness: 0.12,
      metalness: 0.04,
      transmission: 0.66,
      clearcoat: 0.8
    })
  )

  const colonyPositions = [
    [-0.18, 0.14, 0.02],
    [0.12, 0.2, 0.02],
    [0.22, -0.08, 0.02],
    [-0.1, -0.2, 0.02]
  ]

  colonyPositions.forEach(([px, py, pz], index) => {
    const colony = new THREE.Mesh(
      new THREE.SphereGeometry(index % 2 === 0 ? 0.06 : 0.045, 16, 16),
      createSoftMaterial(index % 2 === 0 ? '#dbf5ff' : '#9fd8ff', 0.9, '#154662')
    )
    colony.position.set(px, py, pz)
    group.add(colony)
  })

  group.add(ring, core)
  group.scale.setScalar(scale)
  group.position.set(x, y, -0.2)
  return group
}

const createCell = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(0.66, 40, 40),
    new THREE.MeshPhysicalMaterial({
      color: '#ffd5f2',
      transparent: true,
      opacity: 0.32,
      roughness: 0.1,
      metalness: 0.03,
      transmission: 0.8,
      clearcoat: 0.95
    })
  )

  const nucleus = new THREE.Mesh(
    new THREE.SphereGeometry(0.22, 24, 24),
    createSoftMaterial('#ff78cf', 0.94, '#7a1b5a')
  )
  nucleus.position.set(0.12, -0.08, 0.14)

  const organelle1 = new THREE.Mesh(
    new THREE.SphereGeometry(0.09, 16, 16),
    createSoftMaterial('#ffd8ef', 0.92, '#772050')
  )
  organelle1.position.set(-0.16, 0.12, 0.08)

  const organelle2 = new THREE.Mesh(
    new THREE.SphereGeometry(0.07, 16, 16),
    createSoftMaterial('#ffb2e1', 0.92, '#7c2454')
  )
  organelle2.position.set(0.18, 0.16, -0.04)

  const organelle3 = new THREE.Mesh(
    new THREE.SphereGeometry(0.05, 16, 16),
    createSoftMaterial('#ffeaf8', 0.92, '#6d284f')
  )
  organelle3.position.set(-0.08, -0.16, 0.02)

  group.add(shell, nucleus, organelle1, organelle2, organelle3)
  group.scale.setScalar(scale)
  group.position.set(x, y, 0)
  return group
}

const createBreathingParticles = () => {
  const count = 260
  const positions = new Float32Array(count * 3)
  const sizes = new Float32Array(count)

  for (let i = 0; i < count; i++) {
    const i3 = i * 3
    positions[i3] = (Math.random() - 0.5) * 11
    positions[i3 + 1] = (Math.random() - 0.5) * 8
    positions[i3 + 2] = (Math.random() - 0.5) * 4 - 1.5
    sizes[i] = 0.8 + Math.random() * 1.8
  }

  particleGeometry = new THREE.BufferGeometry()
  particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  particleGeometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1))

  particleMaterial = new THREE.PointsMaterial({
    color: '#b7fff0',
    size: 0.045,
    transparent: true,
    opacity: 0.42,
    depthWrite: false,
    blending: THREE.AdditiveBlending
  })

  particleSystem = new THREE.Points(particleGeometry, particleMaterial)
  particleSystem.position.z = -1.8
  scene.add(particleSystem)
}

const animateBreathingParticles = (elapsed) => {
  if (!particleSystem || !particleGeometry) return

  const positions = particleGeometry.attributes.position.array

  for (let i = 0; i < positions.length; i += 3) {
    const baseX = positions[i]
    const baseY = positions[i + 1]

    positions[i + 2] += Math.sin(elapsed * 0.35 + baseX * 0.8 + baseY * 0.6) * 0.0009
    positions[i + 1] += Math.cos(elapsed * 0.28 + baseX * 0.5) * 0.0007
  }

  particleGeometry.attributes.position.needsUpdate = true
  particleMaterial.opacity = 0.25 + Math.sin(elapsed * 0.9) * 0.06
  particleSystem.rotation.z = elapsed * 0.012
}

const createDnaHelix = (x, y, scale = 1) => {
  const group = new THREE.Group()

  const leftMaterial = createSoftMaterial('#15c97d', 0.98, '#0b5d3b')
  const rightMaterial = createSoftMaterial('#9ef7d1', 0.98, '#16593f')
  const rungMaterial = new THREE.MeshPhysicalMaterial({
    color: '#eafff4',
    roughness: 0.26,
    metalness: 0.08,
    clearcoat: 0.95,
    clearcoatRoughness: 0.12,
    transmission: 0.12
  })

  const spineMaterial = new THREE.MeshStandardMaterial({
    color: '#d8fff0',
    roughness: 0.34,
    metalness: 0.05
  })

  const turns = 28
  const helixHeight = 5.2
  const radius = 0.54

  let previousLeft = null
  let previousRight = null

  for (let i = 0; i < turns; i++) {
    const tValue = i / (turns - 1)
    const angle = tValue * Math.PI * 6.2
    const yPos = (tValue - 0.5) * helixHeight

    const leftPos = new THREE.Vector3(
      Math.cos(angle) * radius,
      yPos,
      Math.sin(angle) * radius * 0.65
    )

    const rightPos = new THREE.Vector3(
      Math.cos(angle + Math.PI) * radius,
      yPos,
      Math.sin(angle + Math.PI) * radius * 0.65
    )

    const leftNode = new THREE.Mesh(
      new THREE.SphereGeometry(0.09, 22, 22),
      leftMaterial
    )
    leftNode.position.copy(leftPos)

    const rightNode = new THREE.Mesh(
      new THREE.SphereGeometry(0.09, 22, 22),
      rightMaterial
    )
    rightNode.position.copy(rightPos)

    group.add(leftNode, rightNode)

    const rungDirection = new THREE.Vector3().subVectors(rightPos, leftPos)
    const rungLength = rungDirection.length()

    const rung = new THREE.Mesh(
      new THREE.CapsuleGeometry(0.022, Math.max(0.05, rungLength - 0.05), 5, 10),
      rungMaterial
    )
    rung.position.copy(leftPos.clone().add(rightPos).multiplyScalar(0.5))
    rung.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0),
      rungDirection.clone().normalize()
    )
    group.add(rung)

    if (previousLeft) {
      const leftDir = new THREE.Vector3().subVectors(leftPos, previousLeft)
      const leftLen = leftDir.length()
      const leftTube = new THREE.Mesh(
        new THREE.CapsuleGeometry(0.028, Math.max(0.05, leftLen - 0.05), 5, 10),
        spineMaterial
      )
      leftTube.position.copy(previousLeft.clone().add(leftPos).multiplyScalar(0.5))
      leftTube.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        leftDir.clone().normalize()
      )
      group.add(leftTube)
    }

    if (previousRight) {
      const rightDir = new THREE.Vector3().subVectors(rightPos, previousRight)
      const rightLen = rightDir.length()
      const rightTube = new THREE.Mesh(
        new THREE.CapsuleGeometry(0.028, Math.max(0.05, rightLen - 0.05), 5, 10),
        spineMaterial
      )
      rightTube.position.copy(previousRight.clone().add(rightPos).multiplyScalar(0.5))
      rightTube.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        rightDir.clone().normalize()
      )
      group.add(rightTube)
    }

    previousLeft = leftPos.clone()
    previousRight = rightPos.clone()
  }

  group.scale.setScalar(scale)
  group.rotation.z = 0.18
  group.rotation.x = -0.14
  group.position.set(x, y, -0.55)
  return group
}

const setupBiotechScene = () => {
  if (!biotechSceneRef.value) return

  scene = new THREE.Scene()
  scene.fog = new THREE.Fog('#061816', 7.5, 18)

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

  const ambient = new THREE.AmbientLight('#d7fff4', 1.15)
  scene.add(ambient)

  const keyLight = new THREE.DirectionalLight('#aaffea', 1.45)
  keyLight.position.set(4.5, 5.5, 6.5)
  scene.add(keyLight)

  const fillLight = new THREE.DirectionalLight('#75bfff', 0.72)
  fillLight.position.set(-5, 1.5, 4)
  scene.add(fillLight)

  const rimLight = new THREE.PointLight('#4ff0c5', 1.55, 22)
  rimLight.position.set(-1.2, -1.5, 4)
  scene.add(rimLight)

  const topGlow = new THREE.PointLight('#96e9ff', 0.95, 18)
  topGlow.position.set(1.8, 2.4, 3.2)
  scene.add(topGlow)

  addFloatingItem(createDnaHelix(-1.95, 0.5, 1.18), -1.95, 0.5, -0.45, 1.18)
  addFloatingItem(createBacteriaModel(1.95, 1.08, 0.94), 1.95, 1.08, 0, 1.02)
  addFloatingItem(createCapsule(2.28, -1.46, 0.92), 2.28, -1.46, 0, 0.88)

  addFloatingItem(createCell(0.75, -0.84, 1.06), 0.75, -0.84, 0, 1.02)
  addFloatingItem(createProteinComplex(-0.1, 1.82, 0.68), -0.1, 1.82, 0, 0.66)

  createBreathingParticles()

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

    const influenceRadius = 2.35
    let repelStrength = 0

    if (distance < influenceRadius) {
      repelStrength = (1 - distance / influenceRadius) * 0.18 * item.force
      toMouse.normalize()
      item.velocity.addScaledVector(toMouse, repelStrength)
    }

    const returnForce = new THREE.Vector3()
      .subVectors(base, current)
      .multiplyScalar(0.03)

    item.velocity.add(returnForce)
    item.velocity.multiplyScalar(0.9)

    current.add(item.velocity)

    const floatY = Math.sin(elapsed * 0.85 + item.noiseOffset) * 0.075
    const floatX = Math.cos(elapsed * 0.52 + item.noiseOffset * 0.7) * 0.04

    item.mesh.position.x += floatX * 0.07
    item.mesh.position.y += floatY * 0.07

    item.mesh.rotation.y += 0.0026 * item.force
    item.mesh.rotation.x = Math.sin(elapsed * 0.55 + item.noiseOffset) * 0.05

    if (repelStrength > 0.01) {
      item.mesh.rotation.z += 0.0058 * item.force
    } else {
      item.mesh.rotation.z *= 0.965
    }
  }

  animateBreathingParticles(elapsed)

  if (camera) {
    camera.position.x = Math.sin(elapsed * 0.12) * 0.08
    camera.position.y = Math.cos(elapsed * 0.15) * 0.06
    camera.lookAt(0, 0, 0)
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
    radial-gradient(circle at 18% 16%, rgba(53, 255, 196, 0.14), transparent 20%),
    radial-gradient(circle at 82% 20%, rgba(96, 154, 255, 0.16), transparent 24%),
    radial-gradient(circle at 50% 78%, rgba(39, 255, 207, 0.08), transparent 30%),
    linear-gradient(135deg, #031110 0%, #071a18 22%, #092321 46%, #061513 72%, #030c0c 100%);
}

.left-bg-stack {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.bg-slideshow,
.biotech-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  opacity: 0;
  transition: opacity 0.35s ease;
  pointer-events: none;
}

.bg-slideshow.active,
.biotech-bg.active {
  opacity: 1;
}

.bg-slide {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center center;
  background-repeat: no-repeat;
  opacity: 0;
  transform: scale(1.06);
  animation: heroSlideshow 18s infinite;
  filter: saturate(1.04) contrast(1.03);
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
  pointer-events: none;
}

.bg-overlay-original {
  background:
    radial-gradient(circle at 20% 20%, rgba(255, 255, 255, 0.08), transparent 30%),
    linear-gradient(
      135deg,
      rgba(8, 31, 28, 0.76) 0%,
      rgba(8, 31, 28, 0.50) 45%,
      rgba(8, 31, 28, 0.66) 100%
    );
}

.bg-overlay-biotech {
  background:
    radial-gradient(circle at 18% 20%, rgba(171, 255, 228, 0.12), transparent 24%),
    radial-gradient(circle at 84% 72%, rgba(112, 178, 255, 0.1), transparent 24%),
    radial-gradient(circle at 48% 48%, rgba(255, 255, 255, 0.04), transparent 38%),
    linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.05) 0%,
      rgba(255, 255, 255, 0.015) 36%,
      rgba(10, 58, 49, 0.16) 100%
    );
  mix-blend-mode: screen;
  animation: breatheOverlay 6s ease-in-out infinite;
}

.left-bg-toggle {
  position: absolute;
  top: 1.1rem;
  left: 1.1rem;
  z-index: 2;
  min-width: 52px;
  height: 36px;
  padding: 0 0.8rem;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: #effff8;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.16);
  cursor: pointer;
  transition: transform 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
}

.left-bg-toggle:hover {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.18);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.2);
}

.left-pane[dir="rtl"] .left-bg-toggle {
  left: auto;
  right: 1.1rem;
}

.left-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 560px;
  color: #ffffff;
  padding: clamp(1.35rem, 2.6vw, 2rem);
  border-radius: 28px;
  background: linear-gradient(180deg, rgba(7, 28, 24, 0.34), rgba(7, 28, 24, 0.18));
  border: 1px solid rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(18px) saturate(145%);
  -webkit-backdrop-filter: blur(18px) saturate(145%);
  box-shadow:
    0 18px 48px rgba(0, 0, 0, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.14);
  overflow: hidden;
}

.left-inner::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 0% 0%, rgba(255, 255, 255, 0.16), transparent 34%),
    linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.08) 0%,
      rgba(255, 255, 255, 0.03) 42%,
      rgba(255, 255, 255, 0.01) 100%
    );
  pointer-events: none;
}

.left-inner > * {
  position: relative;
  z-index: 1;
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
  color: #ffffff;
  letter-spacing: -0.02em;
  line-height: 1.15;
  margin: 0;
  overflow-wrap: anywhere;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

.logo-icon {
  width: 52px;
  height: 52px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.1));
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 52px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.15);
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
  color: #ffffff;
  line-height: 1.12;
  letter-spacing: -0.03em;
  overflow-wrap: anywhere;
  text-shadow: 0 2px 16px rgba(0, 0, 0, 0.2);
}

.custom-content :deep(p) {
  color: rgba(255, 255, 255, 0.92);
  margin: 0 0 0.9rem;
  line-height: 1.72;
  font-size: 1.03rem;
  font-weight: 400;
  overflow-wrap: anywhere;
}

.custom-content :deep(ul.info-list) {
  margin: 0.9rem 0 1.2rem 1.2rem;
  color: rgba(255, 255, 255, 0.98);
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
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.95));
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
  background: linear-gradient(180deg, #ffffff, #f5f7f8);
  border-radius: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.55rem;
  box-shadow: 0 14px 28px rgba(10, 79, 65, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.9);
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
  box-shadow: 0 0 0 4px rgba(10, 79, 65, 0.12), 0 10px 24px rgba(10, 79, 65, 0.08);
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
  background: linear-gradient(180deg, rgba(7, 128, 91, 1) 0%, rgba(7, 117, 84, 1) 100%);
  color: #ffffff;
  border: 1px solid rgba(7, 92, 67, 0.72);
  box-shadow: 0 16px 28px rgba(7, 116, 84, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.btn-primary:hover:not(:disabled) {
  box-shadow: 0 18px 32px rgba(7, 116, 84, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.14);
}

.btn-primary:disabled {
  opacity: 0.72;
  cursor: not-allowed;
  box-shadow: none;
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.28);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.1);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.18);
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.14);
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
  box-shadow: 0 0 0 4px rgba(10, 79, 65, 0.12), 0 10px 22px rgba(10, 79, 65, 0.08);
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
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: #ffffff;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.08);
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

@keyframes breatheOverlay {
  0%,
  100% {
    opacity: 0.92;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.02);
  }
}

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

  .login-card {
    max-height: none;
    overflow-y: visible;
    max-width: 460px;
    width: 100%;
  }
}

@media (max-width: 560px) {
  .left-inner {
    padding: 1.1rem 1rem;
    border-radius: 22px;
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