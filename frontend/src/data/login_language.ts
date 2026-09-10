import { BRAND_CONNECT, BRAND_NAME } from '@/constants/brand'

export const LOGIN_LANGUAGE_OPTIONS = [
  { value: 'en', label: 'English' },
]

export const LOGIN_ROLE_PREVIEW_ITEMS = [
  { key: 'student', labelKey: 'roleStudent' },
  { key: 'mentor', labelKey: 'roleMentor' },
  { key: 'supervisor', labelKey: 'roleSupervisor' },
  { key: 'admin', labelKey: 'roleAdmin' }
]

export const LOGIN_MESSAGES = {
  en: {
    brandTitle: BRAND_CONNECT,
    signIn: 'Sign in',
    welcomeSubtitle: 'Access your mentoring portal securely and continue where you left off.',
    emailLabel: 'Email Address',
    emailPlaceholder: 'Enter your email',
    emailHelper: 'We will send a short-lived verification code to your email.',
    passwordLabel: 'Password',
    passwordPlaceholder: 'Enter your password',
    passwordHelper: 'Use your account email and password to sign in.',
    passwordStep: 'Password',
    passwordSignIn: 'Password Sign-in',
    loginMethod: 'Login method',
    emailCodeSignIn: 'Magic Link',
    sendingCode: 'Sending code...',
    sendVerificationCode: 'Send verification code',
    verifyCode: 'Verify code',
    resendCode: 'Resend code',
    resendIn: 'Resend in',
    visitWebsite: 'Visit Main Web',
    roleStudent: 'Student',
    roleMentor: 'Mentor',
    roleSupervisor: 'Supervisor',
    roleAdmin: 'Admin',
    codeSentTo: 'Code sent to',
    changeEmail: 'Change email',
    digit: 'Digit',
    codeExpiryHint:
      'Codes are single-use and last 10 minutes. Resending sends you the same code, so any of these emails will work.',
    codeExpiresIn: 'This code expires in',
    codeExpiredHint: 'This code has expired. Request a new one.',
    codeSpamHint: "Didn't get it? Check your spam folder.",
    confirmTitle: 'Confirm sign-in',
    confirmBody: 'Press continue to finish signing in as',
    confirmAction: 'Continue to sign in',
    confirmWorking: 'Signing you in...',
    needHelp: 'Need help?',
    contactSupport: 'Contact support',
    backToSignIn: 'Back to sign in',
    accountInactiveTitle: 'Account inactive',
    accountInactiveBody:
      'This account has been suspended or deactivated, so it cannot be used to sign in. An administrator must reactivate it before you can access the portal.',
    accountInactiveContact: 'Email us to request reactivation:',
    aboutTitle: `Welcome to the ${BRAND_NAME} Mentoring Portal`,
    aboutP1: 'This platform helps students, mentors, supervisors, and administrators stay connected throughout the mentoring program.',
    aboutLi1: 'Access group communication and shared resources',
    aboutLi2: 'Track tasks, updates, and mentoring progress',
    aboutLi3: 'Support role-based workflows across the program',
    aboutP2: 'Use one secure portal for communication, resources, events, and progress tracking.',
    errorEnterEmail: 'Please enter your email address.',
    errorEnterPassword: 'Please enter your password.',
    errorInvalidEmail: 'Please enter a valid email address.',
    errorCsrfFailed: 'Could not prepare a secure request. Please refresh and try again.',
    errorUserLoadFailed: 'Signed in, but your profile could not be loaded. Please try again.',
    errorSendLink: 'Failed to send the verification code. Please try again.',
    errorNetworkLogin: 'Network error. Please check your connection and try again.',
    errorCompleteCode: 'Please enter the complete 6-digit code.',
    errorInvalidCode: 'Invalid or expired code.',
    errorNetworkOtp: 'Network error. Please try again.',
    errorEnterEmailFirst: 'Please enter your email address first.',
    errorResendFail: 'Failed to resend the code. Please try again.',
    errorMagicLinkExpired:
      'This sign-in link is no longer valid. Links expire and can only be used once. Please request a new code.',
    errorMagicLinkThrottled:
      'Too many sign-in attempts. Please wait a few minutes before requesting another code.',
    errorMagicLinkFailed: 'We could not complete that sign-in link. Please request a new code.',
    resendSuccess: 'If an account exists for that email, a new code has been sent.',
    sendingSuccess: 'If an account exists for that email, a verification code has been sent.',
    signingIn: 'Loading dashboard',
    loadingDashboard: 'Loading dashboard',
    accessMode: 'Access mode',
    chooseRoleTitle: 'Choose your workspace role',
    selectedAccess: 'Selected access',
    platformOverview: 'Platform overview',
    experienceTitle: 'Designed for a polished program workflow',
    platformGlanceTitle: 'Platform at a glance',
    visualMode: 'Visual mode',
    imageMode: 'Image',
    emeraldMode: 'Green',
    passwordless: 'Passwordless',
    enterpriseReady: 'Enterprise UI',
    secureAccess: 'Secure access',
    secureOtp: 'OTP verification',
    emailStep: 'Email',
    otpStep: 'Verification',
    verifyHeading: 'Verify your code',
    statsUsers: 'Access roles',
    statsWorkflow: 'Workflow areas',
    statsSecurity: 'Verification flow',
    statsRoles: 'Roles',
    statsWeeks: 'Weeks',
    statsSecureAccess: 'Access',
    programFlowLabel: 'Program flow',
    capabilityGroupSpacesTitle: 'Group spaces',
    capabilityGroupSpacesSubtitle: 'Team discussion and updates',
    capabilityResourcesTitle: 'Resource library',
    capabilityResourcesSubtitle: 'Shared learning materials',
    capabilityProgressTitle: 'Progress tracking',
    capabilityProgressSubtitle: 'Tasks and outcomes',
    capabilityEventsTitle: 'Event updates',
    capabilityEventsSubtitle: 'Sessions and notifications',
    capabilityMatchingTitle: 'Mentor matching',
    capabilityMatchingSubtitle: 'Structured team allocation',
    capabilityAdminTitle: 'Admin tools',
    capabilityAdminSubtitle: 'Role-based program control',
    flowJoin: 'Join',
    flowMatch: 'Match',
    flowCommunicate: 'Communicate',
    flowTrack: 'Track',
    flowComplete: 'Complete',
    previewRolesTitle: 'Preview portal roles',
    rolePreviewLabel: 'Role preview',
    portalPreviewLabel: 'Before sign-in',
    portalPreviewTitle: 'Role will be identified after verification',
    portalPreviewSummary: 'Enter your email and complete OTP verification first. After sign-in, the platform will automatically detect your account role and show the correct role view, tasks, and access.',
    portalPreviewPoint1: 'Enter your email and request a verification code.',
    portalPreviewPoint2: 'Complete OTP verification to confirm your account.',
    portalPreviewPoint3: 'Your role-specific tasks and access will appear after sign-in.',
    roleAssignedAfterSignIn: 'Role shown after verification'

  },
}

export const LOGIN_ROLE_PREVIEW_CONTENT = {
  en: {
    student: {
      title: 'Student Portal Preview',
      summary: 'Browse resources, track task progress, and stay connected with your mentor group.',
      points: [
        'Browse learning resources and event updates',
        'Join group communication and share project progress',
        'View tasks and deliverable requirements'
      ]
    },
    mentor: {
      title: 'Mentor Portal Preview',
      summary: 'Support student teams as projects move forward with ongoing guidance and feedback.',
      points: [
        'Review team progress and staged outcomes',
        'Communicate with students in the group space',
        'Provide advice, feedback, and task support'
      ]
    },
    supervisor: {
      title: 'Supervisor Portal Preview',
      summary: 'Monitor overall progress and mentoring quality while supporting key checkpoints.',
      points: [
        'Review group progress and mentoring activity',
        'Track key updates and points needing intervention',
        'Provide oversight, coordination, and quality support'
      ]
    },
    admin: {
      title: 'Admin Portal Preview',
      summary: 'Coordinate platform operations, users, and workflows to support overall program delivery.',
      points: [
        'Manage users, groups, and platform settings',
        'Handle screening, notifications, and bulk communication',
        'Support cross-region and multi-program coordination'
      ]
    }
  },
} 

export const LOGIN_ROLE_HINT_PREFIX_MAP = {
  en: 'Selected access',
}
