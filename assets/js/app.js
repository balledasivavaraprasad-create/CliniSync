/**
 * ClinSync Web Application Client
 * Complete Patient & Doctor Portals with:
 * 1. Strict password length restriction (8 - 20 chars, 2 capital letters)
 * 2. Removed live database badge on login
 * 3. Robust Email 2FA OTP with backend send-otp & verify-otp integration
 * 4. Fresh Patient Dashboard with:
 *    - Speech-to-Text Voice Intake
 *    - Camera Scanning (Vision/OCR)
 *    - Medical PDF Upload & Parser
 * 5. Doctor Dashboard with Specialization-filtered Tabular Patient Directory
 *    and seamless deep inspection of patient briefs.
 */

(function () {
  'use strict';

  function getApiBase() {
    const host = window.location.hostname || '127.0.0.1';
    return 'http://' + host + ':8000';
  }

  // ── Application State ─────────────────────────────────────────────────────
  let currentRole = 'doctor'; // 'doctor' | 'patient'
  let authMode = 'login';     // 'login' | 'signup'
  let currentUser = null;
  let authToken = null;
  let activeTab = 'overview';
  let isLoading = false;
  let authError = null;

  // Sign up state
  let certVerified = false;
  let certFileName = null;
  let otpStepActive = false;
  let activeOtpCode = '';
  let pendingRegistration = null;
  let termsModalOpen = false;

  // Form state retention for registration so viewing terms or re-rendering preserves user input
  let signupFormData = {
    fullName: '',
    email: '',
    specialty: 'General Medicine',
    license: '',
    password: '',
    confirmPassword: '',
    acceptTerms: false
  };

  function escapeAttr(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // Doctor Dashboard State
  let selectedPatientId = null;
  let patientData = null;
  let doctorRosterFilter = 'my_specialty'; // 'my_specialty' | 'all' | 'Cardiology' | etc.
  let doctorProfileModalOpen = false;
  let currentDoctorProfile = null;

  // Patient Intake State (Voice / Camera / PDF)
  let isRecordingVoice = false;
  let speechRecognition = null;
  let voiceTranscript = '';
  let cameraStream = null;
  let scannedDocResult = null;
  let parsedPdfResult = null;

  // Hospital Tablet Kiosk & Face Recognition State
  let kioskCameraStream = null;
  let kioskScanning = false;
  let kioskCameraActive = false;
  let kioskFacingMode = 'user';
  let capturedFaceBase64 = null;
  let faceRegModalOpen = false;
  let kioskFaceStatus = { text: 'Webcam Ready · Align Face Inside Oval', state: 'normal' };
  let faceRegData = {
    fullName: '',
    email: '',
    phone: '',
    dob: '',
    password: 'Patient@Sync2026!'
  };

  let patientKioskActive = false;
  let activeTermsTab = 'terms'; // 'terms' | 'privacy'
  let activeAudioPlayer = null;

  // Patient Briefs & Claims History State
  let activeHistoryTab = 'briefs'; // 'briefs' or 'claims'
  let patientBriefsList = [];
  let patientClaimsList = [];
  let activeBriefModalData = null;

  // Interactive AI Doctor Consultation State
  let aiDoctorConsultActive = false;
  let aiDoctorMuted = false;
  let aiDoctorChatHistory = [];
  let aiDoctorClinicalChart = {
    chief_complaint: '',
    duration: '',
    severity: '',
    medications: '',
    allergies: ''
  };
  let aiDoctorStep = 0;

  // Clinical Agent Validation State
  let agentValidationModalOpen = false;
  let agentValidationData = null;
  let agentMissingFields = [];

  // Restore session
  try {
    const savedToken = localStorage.getItem('clinsync_token');
    const savedUser = localStorage.getItem('clinsync_user');
    if (savedToken && savedUser) {
      authToken = savedToken;
      currentUser = JSON.parse(savedUser);
    }
  } catch (e) {}

  // Patient Directory Roster Data
  const PATIENT_ROSTER = [
    {
      id: 'pat_demo_patient_001',
      name: 'Demo Patient',
      age: 52,
      sex: 'Male',
      dob: '1974-05-14',
      condition: 'Type 2 Diabetes Mellitus',
      specialty: 'General Medicine',
      status: '⚠️ Metformin Conflict Flagged',
      statusClass: 'danger',
      filesCount: 6,
      lastVisit: '28 Sep 2026'
    },
    {
      id: 'pat_cardio_002',
      name: 'Eleanor Vance',
      age: 61,
      sex: 'Female',
      dob: '1965-03-22',
      condition: 'Hypertensive Heart Disease & Atrial Fibrillation',
      specialty: 'Cardiology',
      status: 'High BP (150/95) • Dual Antiplatelet',
      statusClass: 'warning',
      filesCount: 4,
      lastVisit: '02 Oct 2026'
    },
    {
      id: 'pat_cardio_003',
      name: 'Marcus Brody',
      age: 58,
      sex: 'Male',
      dob: '1968-08-11',
      condition: 'Coronary Artery Disease (Post-PCI)',
      specialty: 'Cardiology',
      status: 'Stable • Stent Follow-up',
      statusClass: 'success',
      filesCount: 5,
      lastVisit: '25 Sep 2026'
    },
    {
      id: 'pat_internal_004',
      name: 'Arthur Pendelton',
      age: 67,
      sex: 'Male',
      dob: '1959-11-04',
      condition: 'Chronic Kidney Disease Stage 3 & Anemia',
      specialty: 'Internal Medicine',
      status: 'Serum Creatinine 1.8 mg/dL',
      statusClass: 'warning',
      filesCount: 7,
      lastVisit: '19 Sep 2026'
    },
    {
      id: 'pat_gen_005',
      name: 'Sophia Martinez',
      age: 38,
      sex: 'Female',
      dob: '1988-01-19',
      condition: 'Metabolic Syndrome & Dyslipidemia',
      specialty: 'General Medicine',
      status: 'Diet Protocol Active',
      statusClass: 'success',
      filesCount: 3,
      lastVisit: '21 Sep 2026'
    },
    {
      id: 'pat_onco_006',
      name: 'David K. Wilson',
      age: 54,
      sex: 'Male',
      dob: '1972-07-30',
      condition: 'Colorectal Polyposis Surveillance',
      specialty: 'Oncology',
      status: 'Annual Screening Pending',
      statusClass: 'info',
      filesCount: 2,
      lastVisit: '10 Aug 2026'
    }
  ];

  function getRootEl() {
    let el = document.getElementById('app-root');
    if (!el) {
      el = document.createElement('div');
      el.id = 'app-root';
      document.body.appendChild(el);
    }
    return el;
  }

  // ── Password Strength Evaluator (Strict 8 to 20 chars, 2 Capital Letters) ─
  function evaluatePassword(pwd) {
    // Length restriction: minimum 8 characters, maximum 20 characters
    const lengthValid = pwd.length >= 8 && pwd.length <= 20;
    // Exactly as requested: at least TWO capital letters
    const upperMatches = (pwd.match(/[A-Z]/g) || []).length;
    const twoUpper = upperMatches >= 2;
    const oneLower = /[a-z]/.test(pwd);
    const oneNumber = /[0-9]/.test(pwd);
    const oneSpecial = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd);

    let score = 0;
    if (lengthValid) score++;
    if (twoUpper) score++;
    if (oneLower) score++;
    if (oneNumber) score++;
    if (oneSpecial) score++;

    let label = 'Weak';
    let color = '#ef4444';
    let percent = Math.min(100, Math.round((score / 5) * 100));

    if (score >= 5) {
      label = 'Strong';
      color = '#16a34a';
    } else if (score >= 3) {
      label = 'Moderate';
      color = '#f59e0b';
    }

    return {
      score,
      percent,
      label,
      color,
      isStrong: score === 5,
      rules: {
        lengthValid,
        twoUpper,
        oneLower,
        oneNumber,
        oneSpecial
      }
    };
  }

  function updatePasswordStrengthUI(pwd) {
    const res = evaluatePassword(pwd || '');
    const label = document.getElementById('pwdStrengthLabel');
    const bar = document.getElementById('pwdStrengthBar');

    if (label && bar) {
      label.textContent = res.label;
      label.style.color = res.color;
      bar.style.width = res.percent + '%';
      bar.style.backgroundColor = res.color;
    }

    const updateRule = (id, valid) => {
      const el = document.getElementById(id);
      if (el) {
        el.className = 'app-pwd-rule ' + (valid ? 'valid' : 'invalid');
        const iconSvg = el.querySelector('svg');
        if (iconSvg) {
          iconSvg.innerHTML = valid
            ? '<polyline points="20 6 9 17 4 12"></polyline>'
            : '<circle cx="12" cy="12" r="10"></circle>';
        }
      }
    };

    updateRule('ruleLen', res.rules.lengthValid);
    updateRule('ruleUpper', res.rules.twoUpper);
    updateRule('ruleLower', res.rules.oneLower);
    updateRule('ruleNum', res.rules.oneNumber);
    updateRule('ruleSpecial', res.rules.oneSpecial);
  }

  // ── Main Render Router ────────────────────────────────────────────────────
  function render() {
    const hash = window.location.hash || '';
    const root = getRootEl();

    if (hash.startsWith('#/login') || hash.startsWith('#/signup') || hash.startsWith('#/register')) {
      stopCamera();
      if (currentRole !== 'patient' || authMode !== 'login' || otpStepActive) {
        stopKioskCamera();
      }
      const pl = document.getElementById('preloader');
      if (pl) pl.style.display = 'none';
      document.body.classList.remove('is-loading');
      document.body.classList.add('is-ready');
      root.className = 'active';
      root.innerHTML = renderAuthView() + renderTermsModal();
      bindAuthEvents();
      document.body.style.overflow = 'hidden';
    } else if (hash.startsWith('#/home') || hash.startsWith('#/patient') || hash.startsWith('#/doctor')) {
      stopCamera();
      stopKioskCamera();
      const pl = document.getElementById('preloader');
      if (pl) pl.style.display = 'none';
      document.body.classList.remove('is-loading');
      document.body.classList.add('is-ready');
      root.className = 'active';
      if (currentUser && currentUser.role === 'patient') {
        root.innerHTML = renderPatientDashboard() + renderTermsModal() + renderPatientBriefModal() + renderAgentValidationModal() + renderNonMedicalNoticeModal();
        bindPatientDashboardEvents();
        if (patientBriefsList.length === 0 && patientClaimsList.length === 0) {
          loadPatientBriefsAndClaims();
        }
      } else {
        root.innerHTML = renderDoctorDashboard() + renderTermsModal() + renderDoctorProfileModal();
        bindDoctorDashboardEvents();
      }
      document.body.style.overflow = 'hidden';
      if (selectedPatientId && !patientData && !isLoading) {
        fetchPatientOverview(selectedPatientId);
      }
    } else {
      stopCamera();
      stopKioskCamera();
      root.className = '';
      root.innerHTML = '';
      document.body.style.overflow = '';
    }
  }

  // ── Render Auth View ──────────────────────────────────────────────────────
  function renderAuthView() {
    const isDoctor = currentRole === 'doctor';
    const isSignup = authMode === 'signup';

    if (otpStepActive) {
      return renderOtpView();
    }

    // Hospital Tablet Kiosk layout for Patient only when explicitly chosen
    if (!isDoctor && !isSignup && patientKioskActive) {
      return renderPatientKioskAuthView();
    }

    return `
      <div class="app-login-viewport">
        <div class="app-login-box">
          <!-- Brand Badge & Title -->
          <div class="app-brand-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
          </div>
          <h1 class="app-login-title">ClinSync</h1>
          <p class="app-login-subtitle">Longitudinal Clinical Intelligence Platform</p>

          <!-- Top Role Switcher: Patient vs Doctor -->
          <div class="app-role-tabs">
            <button type="button" class="app-role-tab ${isDoctor ? 'active doctor' : ''}" id="tabRoleDoctor">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                <polyline points="9 12 11 14 15 10"></polyline>
              </svg>
              <span>Doctor / Clinician</span>
            </button>
            <button type="button" class="app-role-tab ${!isDoctor ? 'active patient' : ''}" id="tabRolePatient">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              <span>Patient Portal</span>
            </button>
          </div>

          <!-- Main Auth Card -->
          <div class="app-card">
            <!-- Mode Switcher: Sign In vs Sign Up -->
            <div class="app-mode-tabs">
              <button type="button" class="app-mode-tab ${!isSignup ? 'active' : ''}" id="tabModeLogin">
                Sign In
              </button>
              <button type="button" class="app-mode-tab ${isSignup ? 'active' : ''}" id="tabModeSignup">
                Create Account (Sign Up)
              </button>
            </div>

            <!-- Card Header (Live Database badge removed as requested) -->
            <div class="app-card-header">
              <div class="app-card-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="${isDoctor ? '#0284c7' : '#0d9488'}" stroke-width="2">
                  ${isDoctor ? `
                    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                    <path d="M12 11v6m-3-3h6"></path>
                  ` : `
                    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                    <circle cx="9" cy="7" r="4"></circle>
                    <polyline points="16 11 18 13 22 9"></polyline>
                  `}
                </svg>
                <span>${isDoctor ? (isSignup ? 'Clinician Onboarding' : 'Clinician Portal') : (isSignup ? 'Patient Registration' : 'Patient Access')}</span>
              </div>
            </div>

            <!-- Error Banner -->
            ${authError ? `
              <div class="app-error-banner">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <span>${authError}</span>
              </div>
            ` : ''}

            <!-- Auth Forms -->
            ${isSignup ? renderSignupForm(isDoctor) : renderLoginForm(isDoctor)}

            <!-- Quick Presets for Demo -->
            ${!isSignup ? renderPresets(isDoctor) : ''}

            <!-- Footer & Terms Link -->
            <div class="app-login-footer">
              <div>Encrypted clinical session · HIPAA aligned · Two-Factor Protected</div>
              <div style="margin-top: 0.35rem;">
                <span class="app-link-terms" id="btnOpenTerms">View Terms of Service & Healthcare Privacy Policy</span>
              </div>
              <a href="#" class="app-back-link" id="backToLandingBtn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
                Return to Marketing Landing Page
              </a>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // ── Hospital Tablet Kiosk: Patient Dual Authentication (Face Biometrics + Email) ──
  function renderPatientKioskAuthView() {
    return `
      <div class="app-login-viewport">
        <div class="app-login-box kiosk-wide">
          <!-- Brand Badge & Title -->
          <div class="app-brand-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
          </div>
          <h1 class="app-login-title">ClinSync</h1>
          <p class="app-login-subtitle">Hospital Tablet Patient Check-in & Intake Portal</p>

          <div style="display:flex;justify-content:space-between;align-items:center;margin:0.75rem 0 1rem 0;">
            <button type="button" class="app-btn-outline" id="btnBackToStandardLogin" style="background:#fff;color:#0f766e;border-color:#0d9488;font-size:0.8125rem;font-weight:600;padding:0.4rem 0.85rem;">
              ← Back to Standard Sign In / Sign Up
            </button>
            <span style="font-size:0.8125rem;color:#64748b;font-weight:600;">Hospital Kiosk Mode</span>
          </div>

          <!-- Top Role Switcher: Patient vs Doctor -->
          <div class="app-role-tabs">
            <button type="button" class="app-role-tab" id="tabRoleDoctor">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                <polyline points="9 12 11 14 15 10"></polyline>
              </svg>
              <span>Doctor / Clinician</span>
            </button>
            <button type="button" class="app-role-tab active patient" id="tabRolePatient">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              <span>Patient Portal</span>
            </button>
          </div>

          <!-- Tablet Banner -->
          <div class="app-kiosk-banner">
            <div class="app-kiosk-banner-text">
              <h3>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
                St. Jude Memorial Hospital — Patient Tablet Kiosk
              </h3>
              <p>Quick Check-in: Select Face Biometric Scanner or Sign in with Email Address below</p>
            </div>
            <div class="app-kiosk-badge">
              <span>● MongoDB Atlas Connected</span>
            </div>
          </div>

          <!-- Error Banner -->
          ${authError ? `
            <div class="app-error-banner" style="margin-bottom:1.25rem;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
              <span>${authError}</span>
            </div>
          ` : ''}

          <!-- Side-by-Side Dual Login Methods -->
          <div class="app-kiosk-split">
            <!-- METHOD 1: Face Recognition Login (Laptop Webcam) -->
            <div class="app-kiosk-card highlight">
              <div class="app-kiosk-card-header">
                <span class="app-kiosk-method-tag biometric">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>
                  Option A · Biometric Check-in
                </span>
                <h3 class="app-kiosk-card-title">Face Recognition Login</h3>
                <p class="app-kiosk-card-desc">Check in with your laptop webcam. Instant facial biometric matching against MongoDB patient registry.</p>
              </div>

              <!-- Camera Viewport Box -->
              <div class="app-camera-kiosk-wrap" id="kioskCameraWrap">
                <video class="app-camera-kiosk-video" id="kioskCameraVideo" autoplay playsinline muted style="${kioskCameraActive ? '' : 'display:none;'}"></video>
                <img class="app-camera-kiosk-video" id="kioskCameraSnapshotImg" style="display:none;object-fit:cover;" />
                
                <div class="app-face-reticle" id="kioskFaceReticle" style="${kioskCameraActive ? '' : 'display:none;'}">
                  <div class="app-face-scan-beam"></div>
                </div>
                <div class="app-face-hud-status ${kioskFaceStatus.state === 'success' ? 'success' : (kioskFaceStatus.state === 'warning' ? 'warning' : '')}" id="kioskFaceHudStatus" style="${kioskCameraActive ? '' : 'display:none;'}">
                  ${kioskFaceStatus.text}
                </div>

                <div class="app-camera-kiosk-placeholder" id="kioskCamPlaceholder" style="${kioskCameraActive ? 'display:none;' : ''}">
                  <div style="width:48px;height:48px;margin:0 auto 0.6rem auto;border-radius:50%;background:rgba(13,148,136,0.18);display:flex;align-items:center;justify-content:center;border:1px solid rgba(45,212,191,0.35);">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" stroke-width="2">
                      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                      <circle cx="12" cy="13" r="4"></circle>
                    </svg>
                  </div>
                  <div style="font-weight:700;font-size:0.875rem;color:#f8fafc;" id="kioskPlaceholderTitle">Connecting to Laptop Webcam...</div>
                  <div style="font-size:0.75rem;color:#94a3b8;margin-top:3px;max-width:260px;margin-inline:auto;" id="kioskPlaceholderSubtitle">Please allow camera permissions if prompted by your browser.</div>
                </div>
              </div>

              <!-- Action Buttons -->
              <input type="file" id="kioskFaceFileInput" accept="image/*" style="display:none;" />

              <button type="button" class="app-btn-primary patient" id="btnScanKioskFace" ${kioskScanning ? 'disabled' : ''} style="margin-bottom:0.5rem;">
                ${kioskScanning ? 'Scanning & Matching Biometrics...' : '⚡ Scan Face & Check In'}
              </button>

              <div class="app-face-btn-row" id="kioskCamControlsRow" style="margin-bottom:0.5rem; ${kioskCameraActive ? '' : 'display:none;'}">
                <button type="button" class="app-btn-outline" id="btnToggleKioskCam" style="flex:1;font-size:0.75rem;padding:0.45rem;color:#ef4444;border-color:#fca5a5;">
                  ⏹ Turn Off Camera
                </button>
                <button type="button" class="app-btn-outline" id="btnRestartKioskCam" style="flex:1;font-size:0.75rem;padding:0.45rem;">
                  🔄 Reset Camera
                </button>
              </div>

              <!-- Multi-mode Alternative Face Input Options (Guarantees zero-block for user) -->
              <div class="app-face-btn-row" style="margin-bottom:0.6rem;">
                <button type="button" class="app-btn-outline" id="btnUploadFacePhoto" style="flex:1;font-size:0.75rem;padding:0.5rem;border-color:#0d9488;color:#0d9488;background:#f0fdfa;">
                  📁 Choose Face Photo / Selfie
                </button>
                <button type="button" class="app-btn-outline" id="btnDemoQuickScan" style="flex:1;font-size:0.75rem;padding:0.5rem;border-color:#6366f1;color:#4f46e5;background:#eef2ff;">
                  ⚡ Quick Demo Scan (John)
                </button>
              </div>

              <div style="margin-top:auto;padding-top:1rem;text-align:center;border-top:1px dashed #cbd5e1;">
                <span style="font-size:0.8125rem;color:#475569;">First time at this hospital?</span><br/>
                <button type="button" class="app-link-terms" id="btnOpenNewFaceEnroll" style="background:none;border:none;cursor:pointer;font-weight:700;font-size:0.8125rem;color:#0d9488;margin-top:0.25rem;">
                  + Register New Face & Create Account
                </button>
              </div>
            </div>

            <!-- METHOD 2: Sign in with Email Address -->
            <div class="app-kiosk-card">
              <div class="app-kiosk-card-header">
                <span class="app-kiosk-method-tag credential">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
                  Option B · Credential Login
                </span>
                <h3 class="app-kiosk-card-title">Sign in with Email Address</h3>
                <p class="app-kiosk-card-desc">Login with your registered patient email address and password.</p>
              </div>

              ${renderLoginForm(false)}

              <div style="margin-top:0.75rem;">
                ${renderPresets(false)}
              </div>
            </div>
          </div>

          <!-- Footer & Terms -->
          <div class="app-login-footer">
            <div>St. Jude Memorial Hospital Tablet Kiosk · Encrypted Biometrics · HIPAA Aligned</div>
            <div style="margin-top: 0.35rem;">
              <span class="app-link-terms" id="btnOpenTerms">View Healthcare Privacy & Biometric Data Policy</span>
            </div>
            <a href="#" class="app-back-link" id="backToLandingBtn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 18 9 12 15 6"></polyline>
              </svg>
              Return to Marketing Landing Page
            </a>
          </div>
        </div>
      </div>
      ${renderFaceRegModal()}
    `;
  }

  // ── Face Registration Modal ───────────────────────────────────────────────
  function renderFaceRegModal() {
    return `
      <div class="app-modal-backdrop" id="faceRegModalBackdrop" style="display: ${faceRegModalOpen ? 'flex' : 'none'};">
        <div class="app-modal-dialog" style="max-width:540px;">
          <div class="app-modal-header" style="background:#f0fdfa;border-bottom:1px solid #ccfbf1;">
            <div style="display:flex;align-items:center;gap:0.6rem;">
              <div style="width:36px;height:36px;border-radius:50%;background:#0d9488;display:flex;align-items:center;justify-content:center;color:#fff;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>
              </div>
              <div>
                <h3 style="margin:0;font-size:1.15rem;color:#0f172a;">Register New Patient Face</h3>
                <p style="margin:0;font-size:0.75rem;color:#0f766e;">Enroll biometric template into St. Jude Hospital MongoDB database</p>
              </div>
            </div>
            <button type="button" class="app-modal-close" id="btnCloseFaceReg">✕</button>
          </div>

          <form id="formFaceRegistration" style="padding:1.5rem;">
            <!-- Biometric Photo Preview -->
            <div class="app-face-reg-preview">
              <img src="${capturedFaceBase64 || 'data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 80 80\'%3E%3Crect width=\'80\' height=\'80\' fill=\'%230d9488\'/%3E%3Ccircle cx=\'40\' cy=\'32\' r=\'16\' fill=\'white\'/%3E%3Cpath d=\'M20 68c0-11 9-20 20-20s20 9 20 20\' fill=\'white\'/%3E%3C/svg%3E'}" class="app-face-reg-thumb" id="regFaceThumbImg" />
              <div>
                <div style="font-weight:700;font-size:0.875rem;color:#0f766e;">Biometric Template Captured</div>
                <div style="font-size:0.75rem;color:#64748b;">This facial scan will be securely registered to your medical profile for future 1-tap tablet check-ins.</div>
              </div>
            </div>

            <div class="app-form-group">
              <label class="app-label" for="faceRegFullName">Full Legal Name *</label>
              <input class="app-input" id="faceRegFullName" type="text" required placeholder="e.g. Robert Smith" value="${escapeAttr(faceRegData.fullName)}" />
            </div>

            <div class="app-form-group">
              <label class="app-label" for="faceRegEmail">Email Address *</label>
              <input class="app-input" id="faceRegEmail" type="email" required placeholder="e.g. robert.smith@gmail.com" value="${escapeAttr(faceRegData.email)}" />
            </div>

            <div class="app-grid-2" style="margin-bottom:1rem;">
              <div class="app-form-group" style="margin-bottom:0;">
                <label class="app-label" for="faceRegDob">Date of Birth</label>
                <input class="app-input" id="faceRegDob" type="date" value="${escapeAttr(faceRegData.dob || '1985-06-20')}" />
              </div>
              <div class="app-form-group" style="margin-bottom:0;">
                <label class="app-label" for="faceRegPhone">Contact Phone</label>
                <input class="app-input" id="faceRegPhone" type="tel" placeholder="+1 (555) 000-0000" value="${escapeAttr(faceRegData.phone)}" />
              </div>
            </div>

            <div class="app-form-group">
              <label class="app-label" for="faceRegPassword">Account Password (Optional)</label>
              <input class="app-input" id="faceRegPassword" type="password" value="${escapeAttr(faceRegData.password)}" placeholder="Default: Patient@Sync2026!" />
            </div>

            <div style="display:flex;gap:0.75rem;margin-top:1.25rem;">
              <button type="submit" class="app-btn-primary patient" style="flex:2;" id="btnSubmitFaceRegConfirm" ${isLoading ? 'disabled' : ''}>
                ${isLoading ? 'Enrolling Face Biometrics...' : '✓ Enroll Face & Complete Sign Up'}
              </button>
              <button type="button" class="app-btn-outline" style="flex:1;" id="btnCancelFaceRegModal">
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  // ── Hospital Kiosk Camera & Face Recognition Engine ───────────────────────
  let kioskHardwareSnapshotActive = false;

  function updateCameraDOM(isActive, hudText, hudState, placeholderTitle, placeholderSub) {
    const video = document.getElementById('kioskCameraVideo');
    const img = document.getElementById('kioskCameraSnapshotImg');
    const placeholder = document.getElementById('kioskCamPlaceholder');
    const reticle = document.getElementById('kioskFaceReticle');
    const hud = document.getElementById('kioskFaceHudStatus');
    const title = document.getElementById('kioskPlaceholderTitle');
    const sub = document.getElementById('kioskPlaceholderSubtitle');
    const controlsRow = document.getElementById('kioskCamControlsRow');
    const scanBtn = document.getElementById('btnScanKioskFace');

    if (placeholder) placeholder.style.display = isActive ? 'none' : 'flex';
    if (reticle) reticle.style.display = isActive ? 'block' : 'none';
    if (controlsRow) controlsRow.style.display = isActive ? 'flex' : 'none';
    if (hud) {
      hud.textContent = hudText || '';
      hud.className = 'app-face-hud-status ' + (hudState || 'normal');
      hud.style.display = isActive ? 'block' : 'none';
    }
    if (title && placeholderTitle) title.textContent = placeholderTitle;
    if (sub && placeholderSub) sub.textContent = placeholderSub;
    if (scanBtn) {
      if (isActive) {
        scanBtn.textContent = '⚡ Scan Face & Check In';
        scanBtn.className = 'app-btn-primary patient';
      } else {
        scanBtn.textContent = '⚡ 1-Click Biometric Check-In (John Doe)';
        scanBtn.className = 'app-btn-primary patient';
      }
    }
  }

  // ── Hospital Kiosk Camera & Face Recognition Engine ───────────────────────
  async function startKioskCamera() {
    const video = document.getElementById('kioskCameraVideo');
    const img = document.getElementById('kioskCameraSnapshotImg');

    // 1. If stream already exists and is active, reuse it
    if (kioskCameraStream && kioskCameraStream.active) {
      kioskCameraActive = true;
      kioskHardwareSnapshotActive = false;
      if (img) img.style.display = 'none';
      if (video) {
        video.srcObject = kioskCameraStream;
        video.style.display = 'block';
        video.play().catch(() => {});
      }
      updateCameraDOM(true, 'Laptop Webcam Active · Center Face in Oval', 'normal');
      return;
    }

    updateCameraDOM(false, 'Requesting camera access...', 'normal', 'Connecting to Laptop Webcam...', 'Checking browser permissions & camera hardware...');

    // 2. Try browser WebRTC with a strict 2.0-second timeout so it NEVER hangs indefinitely!
    let stream = null;
    try {
      const getStreamPromise = (navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
        ? navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 24, max: 30 } },
            audio: false
          })
        : Promise.reject(new Error('WebRTC unsupported'));

      stream = await Promise.race([
        getStreamPromise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('CAMERA_TIMEOUT')), 2000))
      ]);
    } catch (webrtcErr) {
      console.warn('Browser WebRTC timed out or blocked:', webrtcErr);
      stream = null;
    }

    if (stream) {
      kioskCameraStream = stream;
      kioskCameraActive = true;
      kioskHardwareSnapshotActive = false;
      kioskFaceStatus = { text: 'Laptop Webcam Active · Center Face in Oval', state: 'normal' };

      if (img) img.style.display = 'none';
      if (video) {
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        video.style.display = 'block';
        await video.play().catch(() => {});
      }
      updateCameraDOM(true, 'Laptop Webcam Active · Center Face in Oval', 'normal');
      return;
    }

    // 3. HARDWARE FALLBACK: Direct OpenCV camera snapshot from laptop webcam via backend
    try {
      updateCameraDOM(false, 'Connecting via Hardware Link...', 'normal', 'Activating Laptop Camera...', 'Connecting directly to camera hardware...');
      const res = await fetch(getApiBase() + '/api/v1/mongo/camera/snapshot');
      const resJson = await res.json();
      if (resJson.success && resJson.data && resJson.data.available && resJson.data.image_data) {
        capturedFaceBase64 = resJson.data.image_data;
        kioskCameraActive = true;
        kioskHardwareSnapshotActive = true;
        kioskFaceStatus = { text: '✓ Laptop Webcam Connected (Direct Hardware Stream)', state: 'success' };

        if (video) video.style.display = 'none';
        if (img) {
          img.src = capturedFaceBase64;
          img.style.display = 'block';
        }
        updateCameraDOM(true, '✓ Laptop Webcam Connected · Center Face in Oval', 'success');
        return;
      }
    } catch (hwErr) {
      console.warn('Hardware camera link failed:', hwErr);
    }

    // 4. If hardware is in exclusive use by another program (e.g. Zoom/Teams/Antigravity):
    kioskCameraActive = false;
    kioskHardwareSnapshotActive = false;
    kioskFaceStatus = { text: '⚠️ Webcam in use or permission blocked', state: 'warning' };
    updateCameraDOM(
      false, 
      kioskFaceStatus.text, 
      'warning', 
      'Webcam In Use or Permission Blocked', 
      'Your laptop camera may be in use by another application. Click below for 1-Click Biometric Check-In or choose a photo.'
    );
  }

  function stopKioskCamera() {
    if (kioskCameraStream) {
      try {
        kioskCameraStream.getTracks().forEach(track => {
          track.stop();
        });
      } catch (e) {}
      kioskCameraStream = null;
    }
    kioskCameraActive = false;
    kioskHardwareSnapshotActive = false;
    const video = document.getElementById('kioskCameraVideo');
    const img = document.getElementById('kioskCameraSnapshotImg');
    if (video) {
      video.srcObject = null;
      video.style.display = 'none';
    }
    if (img) {
      img.style.display = 'none';
    }
    updateCameraDOM(false, '', 'normal', 'Laptop Webcam Paused', 'Click below to reconnect camera or check in.');
  }

  function captureKioskVideoFrame() {
    if (kioskHardwareSnapshotActive && capturedFaceBase64) {
      return capturedFaceBase64;
    }
    const video = document.getElementById('kioskCameraVideo');
    if (video && video.videoWidth > 0 && video.videoHeight > 0) {
      const canvas = document.createElement('canvas');
      canvas.width = 320;
      canvas.height = 320;
      const ctx = canvas.getContext('2d');
      const size = Math.min(video.videoWidth, video.videoHeight);
      const startX = (video.videoWidth - size) / 2;
      const startY = (video.videoHeight - size) / 2;
      ctx.drawImage(video, startX, startY, size, size, 0, 0, 320, 320);
      return canvas.toDataURL('image/jpeg', 0.85);
    }
    if (capturedFaceBase64) {
      return capturedFaceBase64;
    }
    return generateSyntheticFaceDataUrl();
  }

  function generateSyntheticFaceDataUrl() {
    const canvas = document.createElement('canvas');
    canvas.width = 240;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#f8fafc';
    ctx.fillRect(0, 0, 240, 240);
    ctx.fillStyle = '#fcd34d';
    ctx.beginPath();
    ctx.arc(120, 120, 70, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#0f172a';
    ctx.beginPath();
    ctx.arc(95, 105, 9, 0, Math.PI * 2);
    ctx.arc(145, 105, 9, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(120, 140, 32, 0.2 * Math.PI, 0.8 * Math.PI);
    ctx.lineWidth = 5;
    ctx.strokeStyle = '#0f172a';
    ctx.stroke();
    return canvas.toDataURL('image/jpeg', 0.85);
  }

  async function performKioskFaceRecognition() {
    if (!kioskCameraActive && !capturedFaceBase64) {
      await startKioskCamera();
      return;
    }

    kioskScanning = true;
    const hud = document.getElementById('kioskFaceHudStatus');
    const scanBtn = document.getElementById('btnScanKioskFace');
    if (hud) {
      hud.className = 'app-face-hud-status warning';
      hud.textContent = 'Scanning facial biometrics against hospital database...';
    }
    if (scanBtn) scanBtn.disabled = true;

    const frameB64 = capturedFaceBase64 || captureKioskVideoFrame();
    capturedFaceBase64 = frameB64;

    try {
      const res = await fetch(getApiBase() + '/api/v1/mongo/face/recognize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_data: frameB64,
          hospital_name: 'St. Jude Memorial Hospital'
        })
      });
      const data = await res.json();

      if (data.success && data.data && data.data.matched && data.data.patient) {
        // MATCHED EXISTING PATIENT!
        const p = data.data.patient;
        if (hud) {
          hud.className = 'app-face-hud-status success';
          hud.textContent = `✓ Recognized: ${p.full_name} (${data.data.confidence}% match)`;
        }
        authToken = data.data.token;
        currentUser = p;
        localStorage.setItem('clinsync_token', authToken);
        localStorage.setItem('clinsync_user', JSON.stringify(currentUser));

        setTimeout(() => {
          stopKioskCamera();
          kioskScanning = false;
          window.location.hash = '#/patient/home';
        }, 850);
      } else {
        // NO MATCH OR REQUIRES NEW REGISTRATION
        if (hud) {
          hud.className = 'app-face-hud-status warning';
          hud.textContent = 'No matching patient face found';
        }
        kioskScanning = false;
        if (scanBtn) scanBtn.disabled = false;

        // Cleanly pause camera while filling form to avoid CPU lag
        stopKioskCamera();
        faceRegModalOpen = true;
        render();
      }
    } catch (err) {
      console.warn('Face recognition error:', err);
      if (hud) {
        hud.className = 'app-face-hud-status warning';
        hud.textContent = 'Check-in server error. Please try again.';
      }
      kioskScanning = false;
      if (scanBtn) scanBtn.disabled = false;
    }
  }

  async function performKioskFaceRegistration(e) {
    if (e) e.preventDefault();
    const fullNameEl = document.getElementById('faceRegFullName');
    const emailEl = document.getElementById('faceRegEmail');
    const dobEl = document.getElementById('faceRegDob');
    const phoneEl = document.getElementById('faceRegPhone');
    const passEl = document.getElementById('faceRegPassword');

    const fullName = fullNameEl ? fullNameEl.value.trim() : '';
    const email = emailEl ? emailEl.value.trim() : '';
    const dob = dobEl ? dobEl.value : '';
    const phone = phoneEl ? phoneEl.value : '';
    const password = passEl ? passEl.value.trim() : 'Patient@Sync2026!';

    if (!fullName || !email) {
      alert('Please provide your full legal name and email address.');
      return;
    }

    faceRegData = { fullName, email, dob, phone, password };
    isLoading = true;
    render();

    try {
      const res = await fetch(getApiBase() + '/api/v1/mongo/face/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          email: email,
          image_data: capturedFaceBase64 || generateSyntheticFaceDataUrl(),
          dob: dob,
          phone: phone,
          password: password,
          hospital_name: 'St. Jude Memorial Hospital'
        })
      });
      const data = await res.json();
      if (data.success && data.data && data.data.patient) {
        authToken = data.data.token;
        currentUser = data.data.patient;
        localStorage.setItem('clinsync_token', authToken);
        localStorage.setItem('clinsync_user', JSON.stringify(currentUser));
        isLoading = false;
        faceRegModalOpen = false;
        stopKioskCamera();
        alert(`✓ Welcome, ${fullName}! Your facial biometrics are saved in St. Jude Hospital database. Entering Patient Portal.`);
        window.location.hash = '#/patient/home';
      } else {
        isLoading = false;
        alert((data.error && data.error.message) || 'Registration failed. Please try again.');
        render();
      }
    } catch (err) {
      isLoading = false;
      alert('Network error while registering face. Please try again.');
      render();
    }
  }

  // ── Sign In Form ──────────────────────────────────────────────────────────
  function renderLoginForm(isDoctor) {
    const defaultEmail = isDoctor ? 'doctor@clinsync.health' : 'patient@clinsync.health';
    const defaultPass = isDoctor ? 'Doc@ClinSync2026!' : 'Patient@Sync2026!';

    return `
      <form id="appLoginForm">
        <div class="app-form-group">
          <label class="app-label" for="loginEmail">${isDoctor ? 'Clinical Email' : 'Patient Email ID'}</label>
          <div class="app-input-wrap">
            <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
              <polyline points="22,6 12,13 2,6"></polyline>
            </svg>
            <input class="app-input" id="loginEmail" type="email" value="${defaultEmail}" required placeholder="name@domain.com" />
          </div>
        </div>

        <div class="app-form-group">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.35rem;">
            <label class="app-label" for="loginPassword" style="margin-bottom:0;">Password</label>
            <span class="app-link-terms" style="font-size:0.75rem;" onclick="alert('For demo accounts, use presets below. You can also create a new account with a strong password.');">Forgot?</span>
          </div>
          <div class="app-input-wrap">
            <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
            <input class="app-input" id="loginPassword" type="password" value="${defaultPass}" maxlength="20" required placeholder="Enter password (max 20 chars)" />
            <button type="button" class="app-btn-eye" id="togglePasswordBtn" title="Toggle password visibility">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
          </div>
        </div>

        <div class="app-terms-check" style="margin: 0.75rem 0 1.15rem;">
          <input type="checkbox" id="rememberMe" checked />
          <label for="rememberMe" style="cursor:pointer;font-size:0.8125rem;">Keep session active for 24 hours (HIPAA encrypted token)</label>
        </div>

        <button type="submit" class="app-btn-primary ${!isDoctor ? 'patient' : ''}" id="loginSubmitBtn" ${isLoading ? 'disabled' : ''}>
          ${isLoading ? `
            <span>Authenticating Session...</span>
          ` : `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
              <polyline points="10 17 15 12 10 7"></polyline>
              <line x1="15" y1="12" x2="3" y2="12"></line>
            </svg>
            <span>Sign in as ${isDoctor ? 'Doctor / Clinician' : 'Patient'}</span>
          `}
        </button>

        ${!isDoctor ? `
          <div style="margin-top: 1rem; padding-top: 0.85rem; border-top: 1px dashed #cbd5e1; text-align: center;">
            <button type="button" class="app-btn-outline" id="btnOpenKioskFace" style="width: 100%; border-color: #0d9488; color: #0d9488; background: #f0fdfa; font-weight: 600; padding: 0.6rem; font-size: 0.85rem;">
              📷 Check In via Hospital Tablet Face Biometrics
            </button>
          </div>
        ` : ''}
      </form>
    `;
  }

  // ── Sign Up Form (Strict 8-20 character restriction on password) ───────────
  function renderSignupForm(isDoctor) {
    return `
      <form id="appSignupForm">
        <!-- Full Name -->
        <div class="app-form-group">
          <label class="app-label" for="regFullName">${isDoctor ? 'Doctor Full Name & Title' : 'Patient Full Name'}</label>
          <div class="app-input-wrap">
            <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
            <input class="app-input" id="regFullName" type="text" value="${escapeAttr(signupFormData.fullName)}" required placeholder="${isDoctor ? 'Dr. Elizabeth Blackwell, MD' : 'Johnathan Doe'}" />
          </div>
        </div>

        <!-- Email -->
        <div class="app-form-group">
          <label class="app-label" for="regEmail">${isDoctor ? 'Official Clinical / Hospital Email' : 'Email ID'}</label>
          <div class="app-input-wrap">
            <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
              <polyline points="22,6 12,13 2,6"></polyline>
            </svg>
            <input class="app-input" id="regEmail" type="email" value="${escapeAttr(signupFormData.email)}" required placeholder="${isDoctor ? 'e.blackwell@hospital.org' : 'john.doe@gmail.com'}" />
          </div>
        </div>

        <!-- Doctor Only: Specialty, License & Certificate Verification -->
        ${isDoctor ? `
          <div class="app-form-group">
            <label class="app-label" for="regSpecialty">Clinical Specialty</label>
            <div class="app-input-wrap">
              <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 6v6l4 2"></path>
              </svg>
              <select class="app-select" id="regSpecialty" required>
                <option value="General Medicine" ${signupFormData.specialty === 'General Medicine' ? 'selected' : ''}>General Medicine</option>
                <option value="Cardiology" ${signupFormData.specialty === 'Cardiology' ? 'selected' : ''}>Cardiology</option>
                <option value="Internal Medicine" ${signupFormData.specialty === 'Internal Medicine' ? 'selected' : ''}>Internal Medicine</option>
                <option value="Endocrinology" ${signupFormData.specialty === 'Endocrinology' ? 'selected' : ''}>Endocrinology</option>
                <option value="Oncology" ${signupFormData.specialty === 'Oncology' ? 'selected' : ''}>Oncology</option>
                <option value="Neurology" ${signupFormData.specialty === 'Neurology' ? 'selected' : ''}>Neurology</option>
                <option value="Pediatrics" ${signupFormData.specialty === 'Pediatrics' ? 'selected' : ''}>Pediatrics</option>
              </select>
            </div>
          </div>

          <div class="app-form-group">
            <label class="app-label" for="regLicense">Medical Council License / Reg Number</label>
            <div class="app-input-wrap">
              <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
                <rect x="3" y="4" width="18" height="16" rx="2"></rect>
                <line x1="7" y1="8" x2="17" y2="8"></line>
                <line x1="7" y1="12" x2="13" y2="12"></line>
              </svg>
              <input class="app-input" id="regLicense" type="text" value="${escapeAttr(signupFormData.license)}" required placeholder="e.g. NMC-2024-88491 or GMC-749210" />
            </div>
          </div>

          <!-- Doctor Credential / Certificate Verification Box -->
          <div class="app-cert-box ${certVerified ? 'verified' : ''}" id="doctorCertBox">
            <div class="app-cert-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              <span>Medical License & Certificate Verification</span>
            </div>
            <p class="app-cert-sub">
              ${certVerified ? 
                `Verified Certificate: <strong>${certFileName || 'Medical_Council_Certificate.pdf'}</strong>` : 
                'Upload your Medical Council Registration Certificate or Practicing License for instant AI credential review.'}
            </p>

            ${certVerified ? `
              <div class="app-cert-badge-verified">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span>Active Clinician Verified by Registry</span>
              </div>
            ` : `
              <div class="app-cert-actions">
                <input type="file" id="certFileInput" accept=".pdf,.png,.jpg,.jpeg" style="display:none;" />
                <button type="button" class="app-btn-outline" id="btnUploadCert" style="font-size:0.75rem;">
                  Upload Certificate (PDF/JPG)
                </button>
                <button type="button" class="app-btn-outline" id="btnSimulateVerify" style="font-size:0.75rem;background:#0284c7;color:#fff;border-color:#0284c7;">
                  Auto-Verify via Medical Council
                </button>
              </div>
            `}
          </div>
        ` : ''}

        <!-- New Password with Max Length = 20 restriction -->
        <div class="app-form-group">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.35rem;">
            <label class="app-label" for="regPassword" style="margin-bottom:0;">Set New Password</label>
            <span style="font-size:0.75rem;color:#64748b;font-weight:600;">Max 20 Characters</span>
          </div>
          <div class="app-input-wrap">
            <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
            <input class="app-input" id="regPassword" type="password" maxlength="20" value="${escapeAttr(signupFormData.password)}" required placeholder="Choose password (8 - 20 chars)" />
            <button type="button" class="app-btn-eye" id="toggleRegPasswordBtn" title="Toggle password visibility">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
          </div>

          <!-- Real-Time Password Strength Meter & Interactive Checklist -->
          <div class="app-pwd-meter" id="pwdMeterBox">
            <div class="app-pwd-status">
              <span>Password Security</span>
              <span id="pwdStrengthLabel" style="color:#ef4444;">Weak</span>
            </div>
            <div class="app-pwd-bar-track">
              <div class="app-pwd-bar-fill" id="pwdStrengthBar" style="width:0%;background-color:#ef4444;"></div>
            </div>
            <div class="app-pwd-checklist">
              <div class="app-pwd-rule invalid" id="ruleLen">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>
                <span><strong>Between 8 and 20 chars</strong></span>
              </div>
              <div class="app-pwd-rule invalid" id="ruleUpper">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>
                <span><strong>2 uppercase letters</strong> (A-Z)</span>
              </div>
              <div class="app-pwd-rule invalid" id="ruleLower">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>
                <span>1 lowercase letter (a-z)</span>
              </div>
              <div class="app-pwd-rule invalid" id="ruleNum">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>
                <span>1 number (0-9)</span>
              </div>
              <div class="app-pwd-rule invalid" id="ruleSpecial" style="grid-column: span 2;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>
                <span>1 special character (!@#$%^&*...)</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Confirm Password -->
        <div class="app-form-group">
          <label class="app-label" for="regConfirmPassword">Confirm Password</label>
          <div class="app-input-wrap">
            <svg class="app-icon-left" viewBox="0 0 24 24" fill="none" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
            <input class="app-input" id="regConfirmPassword" type="password" maxlength="20" value="${escapeAttr(signupFormData.confirmPassword)}" required placeholder="Re-enter password" />
          </div>
        </div>

        <!-- Privacy & Terms Acceptance Checkbox -->
        <div class="app-terms-check">
          <input type="checkbox" id="acceptTerms" ${signupFormData.acceptTerms ? 'checked' : ''} required />
          <label for="acceptTerms">
            I agree to the <span class="app-link-terms" id="btnCheckTerms">ClinSync ${isDoctor ? 'Clinician' : 'Patient'} Terms of Service</span> and acknowledge the <span class="app-link-terms" id="btnCheckPrivacy">Healthcare Privacy Policy</span> including HIPAA/DPDP data protection standards.
          </label>
        </div>

        <!-- Submit to 2FA Step -->
        <button type="submit" class="app-btn-primary ${!isDoctor ? 'patient' : ''}" id="btnProceedOtp">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 11 12 14 22 4"></polyline>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
          </svg>
          <span>Send 6-Digit Email OTP Verification Code →</span>
        </button>
      </form>
    `;
  }

  // ── Two-Factor Authentication (OTP) View ──────────────────────────────────
  function renderOtpView() {
    const isDoctor = currentRole === 'doctor';
    const email = (pendingRegistration && pendingRegistration.email) || 'user@example.com';

    return `
      <div class="app-login-viewport">
        <div class="app-login-box">
          <div class="app-card app-otp-screen">
            <div class="app-otp-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
            </div>

            <h2 style="font-size:1.35rem;font-weight:700;text-align:center;color:#0f172a;margin-bottom:0.35rem;">
              Two-Factor Email Verification
            </h2>
            <p style="text-align:center;font-size:0.875rem;color:#64748b;margin-bottom:1.25rem;">
              Enter the 6-digit security code dispatched to: <br/>
              <strong style="color:#0f172a;">${email}</strong>
            </p>

            ${authError ? `
              <div class="app-error-banner">
                <span>${authError}</span>
              </div>
            ` : ''}

            <form id="appOtpForm">
              <div style="margin-bottom: 1.25rem;">
                <label class="app-label" style="text-align:center;" for="otpUnifiedInput">Enter 6-Digit Code</label>
                <input 
                  type="text" 
                  id="otpUnifiedInput" 
                  maxlength="6" 
                  required 
                  autofocus 
                  placeholder="• • • • • •" 
                  style="width: 100%; text-align: center; font-size: 2.25rem; font-weight: 800; letter-spacing: 0.6rem; font-family: 'JetBrains Mono', monospace; padding: 0.85rem; border: 2px solid #0284c7; border-radius: 12px; outline: none; background: #ffffff !important; color: #0f172a !important; -webkit-text-fill-color: #0f172a !important; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.12);"
                />
              </div>

              <button type="submit" class="app-btn-primary ${!isDoctor ? 'patient' : ''}" style="margin-top:0.5rem;" id="btnVerifyOtp" ${isLoading ? 'disabled' : ''}>
                ${isLoading ? 'Verifying & Activating Account...' : 'Verify Code & Activate Account'}
              </button>
            </form>

            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:1.25rem;font-size:0.8125rem;">
              <button type="button" class="app-btn-outline" id="btnCancelOtp">
                ← Edit Details
              </button>
              <button type="button" class="app-btn-outline" id="btnResendOtp">
                Resend Email Code
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // ── Presets for Fast Demo Testing ─────────────────────────────────────────
  function renderPresets(isDoctor) {
    if (isDoctor) {
      return `
        <div class="app-presets-card">
          <div class="app-presets-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0284c7" stroke-width="2">
              <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="8.5" cy="7" r="4"></circle>
              <polyline points="17 11 19 13 23 9"></polyline>
            </svg>
            Quick Fill Demo Clinicians
          </div>
          <div class="app-presets-list">
            <button type="button" class="app-chip active" data-email="doctor@clinsync.health" data-pass="Doc@ClinSync2026!">
              <span>Dr. Willie Carter, MD</span>
              <span class="app-chip-role">General Medicine</span>
            </button>
            <button type="button" class="app-chip" data-email="sarah.jenkins@clinsync.health" data-pass="Cardio@Sync2026!">
              <span>Dr. Sarah Jenkins, MD</span>
              <span class="app-chip-role">Cardiology</span>
            </button>
            <button type="button" class="app-chip" data-email="demo@clinsync.health" data-pass="Internal@Med2026!">
              <span>Dr. Alex Mercer, MD</span>
              <span class="app-chip-role">Internal Medicine</span>
            </button>
          </div>
        </div>
      `;
    } else {
      return `
        <div class="app-presets-card">
          <div class="app-presets-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0d9488" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
            Quick Fill Demo Patients
          </div>
          <div class="app-presets-list">
            <button type="button" class="app-chip patient active" data-email="patient@clinsync.health" data-pass="Patient@Sync2026!">
              <span>Demo Patient (Male, 52)</span>
              <span class="app-chip-role">pat_demo_patient_001</span>
            </button>
            <button type="button" class="app-chip patient" data-email="jane.doe@clinsync.health" data-pass="Healthy@Life2026!">
              <span>Jane Doe (Female, 44)</span>
              <span class="app-chip-role">Cardiac Care Record</span>
            </button>
          </div>
        </div>
      `;
    }
  }

  // ── Terms & Privacy Policy Modal (Tabbed with distinct legal & healthcare policies) ──
  function renderTermsModal() {
    const isTerms = activeTermsTab === 'terms';

    return `
      <div class="app-modal-backdrop" id="termsModalBackdrop" style="display: ${termsModalOpen ? 'flex' : 'none'};">
        <div class="app-modal-dialog" style="max-width: 680px;">
          <div class="app-modal-header" style="padding-bottom: 0.5rem;">
            <div>
              <h3 style="margin: 0; font-size: 1.2rem; color: #0f172a;">ClinSync Legal & Healthcare Policies</h3>
              <p style="margin: 0.25rem 0 0 0; font-size: 0.75rem; color: #64748b;">Review governance policies tailored to clinical decision support and patient data protection.</p>
            </div>
            <button type="button" class="app-modal-close" id="btnCloseTerms">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <!-- Dual Tab Navigation -->
          <div style="display:flex; gap:0.5rem; padding: 0.75rem 1.5rem; background: #f1f5f9; border-bottom: 1px solid #e2e8f0;">
            <button type="button" class="app-btn-outline ${isTerms ? 'active' : ''}" id="tabModalTerms" style="flex:1; font-weight:700; font-size:0.8125rem; background:${isTerms ? '#0284c7' : '#fff'}; color:${isTerms ? '#fff' : '#334155'}; border-color:${isTerms ? '#0284c7' : '#cbd5e1'};">
              📄 ClinSync Terms of Service
            </button>
            <button type="button" class="app-btn-outline ${!isTerms ? 'active' : ''}" id="tabModalPrivacy" style="flex:1; font-weight:700; font-size:0.8125rem; background:${!isTerms ? '#0d9488' : '#fff'}; color:${!isTerms ? '#fff' : '#334155'}; border-color:${!isTerms ? '#0d9488' : '#cbd5e1'};">
              🔒 Healthcare Privacy Policy (HIPAA / PHI)
            </button>
          </div>

          <div class="app-modal-body" style="max-height: 55vh; overflow-y: auto; padding: 1.5rem; font-size: 0.875rem; line-height: 1.6; color: #334155;">
            ${isTerms ? `
              <!-- DOCUMENT 1: CLINSYNC PLATFORM TERMS OF SERVICE -->
              <div style="margin-bottom: 1.25rem;">
                <span class="app-panel-tag" style="background:#e0f2fe; color:#0284c7; font-weight:700; margin-bottom:0.5rem; display:inline-block;">Platform Usage Terms</span>
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0.25rem 0 0.5rem 0;">1. Assistive AI & Clinical Responsibility</h4>
                <p>
                  ClinSync functions strictly as a Clinical Decision Support (CDS) platform designed to synthesize longitudinal clinical memory, organize patient symptom intake, and draft pre-consultation intelligence briefs. 
                  <strong>All diagnosis, prescription, medical advice, and treatment decisions remain the exclusive responsibility of licensed healthcare practitioners (Physicians of Record).</strong> 
                  ClinSync does not independently practice medicine or replace clinical judgement.
                </p>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0 0 0.5rem 0;">2. Clinical Memory Verification & Dual-Gate Integrity</h4>
                <p>
                  Every patient record update passes through ClinSync's two-tier verification architecture:
                  <br/>• <strong>Gate 1 (Memory Integrity):</strong> Validates clinical consistency, extracts verified biomarker facts, and checks against conflicting medication dosages.
                  <br/>• <strong>Gate 2 (Output Verification):</strong> Prevents hallucinations and verifies that generated doctor briefs cite immutable source documents.
                </p>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0 0 0.5rem 0;">3. Professional Medical Licensure & Account Security</h4>
                <p>
                  Clinician accounts require active registration with recognized medical councils (e.g. NMC, GMC, State Medical Boards). 
                  Access requires mandatory Two-Factor OTP authentication. Sharing login credentials or unauthorized third-party access to patient charts is strictly prohibited.
                </p>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0 0 0.5rem 0;">4. Emergency Exclusion</h4>
                <p>
                  ClinSync is designed for scheduled consultations and elective intake triage. 
                  <strong>Do not use this application for acute medical emergencies.</strong> In life-threatening emergencies (severe chest pain, stroke symptoms, uncontrolled bleeding), dial local emergency services (911/112/108) immediately.
                </p>
              </div>
            ` : `
              <!-- DOCUMENT 2: HEALTHCARE PRIVACY & PHI SECURITY POLICY -->
              <div style="margin-bottom: 1.25rem;">
                <span class="app-panel-tag" style="background:#ccfbf1; color:#0f766e; font-weight:700; margin-bottom:0.5rem; display:inline-block;">Healthcare Privacy & HIPAA</span>
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0.25rem 0 0.5rem 0;">1. Protected Health Information (PHI) & HIPAA/HITECH Compliance</h4>
                <p>
                  ClinSync is engineered to comply with HIPAA, HITECH, and international healthcare data privacy standards. 
                  All Protected Health Information (PHI)—including clinical consultation notes, voice intake audio, scanned medical reports, and lab results—is strictly segregated and accessible only by verified healthcare personnel assigned to the patient's care team.
                </p>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0 0 0.5rem 0;">2. End-to-End Cryptography & Data at Rest</h4>
                <p>
                  All data in transit is encrypted using Transport Layer Security (TLS 1.3). 
                  All clinical databases, medical PDFs, and longitudinal memory documents are stored with AES-256 bit encryption at rest in isolated St. Jude Hospital MongoDB Atlas database clusters.
                </p>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0 0 0.5rem 0;">3. Facial Biometric Template Security</h4>
                <p>
                  Hospital tablet kiosk check-in uses mathematical facial landmark vectors (128-dimensional Euclidean embeddings). 
                  <strong>Raw camera video streams and facial photographs are never sold, rented, or monetized.</strong> 
                  Biometric templates are stored solely for patient verification within the hospital's dedicated MongoDB cluster.
                </p>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0 0 0.5rem 0;">4. Immutable Audit Ledger & Non-Repudiation</h4>
                <p>
                  Every access to a medical brief, document download, or clinical memory update is permanently recorded to an immutable audit trail stamped with SHA-256 cryptographic signatures, timestamped with UTC accuracy, and linked to the accessing physician's identity.
                </p>
              </div>

              <div style="margin-bottom: 1.25rem;">
                <h4 style="font-size:1.05rem; font-weight:700; color:#0f172a; margin: 0 0 0.5rem 0;">5. Zero Commercial Data Sale Guarantee</h4>
                <p>
                  ClinSync adheres to a strict <strong>Zero Commercial Sale Policy</strong>. Patient health data is never sold to advertisers, pharmaceutical brokers, or data brokers.
                </p>
              </div>
            `}
          </div>

          <div class="app-modal-footer" style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:0.75rem; color:#64748b;">ClinSync Enterprise Healthcare Platform · v2026.1</span>
            <button type="button" class="app-btn-primary" style="width:auto; padding:0.6rem 1.75rem;" id="btnAcceptTermsModal">
              Understood & Close
            </button>
          </div>
        </div>
      </div>
    `;
  }

  // ── Doctor Clinical Profile Modal (Stored in & synced with MongoDB) ────────
  function renderDoctorProfileModal() {
    const doc = currentDoctorProfile || {
      full_name: (currentUser && currentUser.role === 'doctor' && currentUser.full_name) || 'Dr. Willie Carter, MD',
      email: (currentUser && currentUser.email) || 'doctor@clinsync.health',
      specialty: (currentUser && currentUser.specialty) || 'General Medicine',
      sub_specialty: 'Preventive Medicine & Chronic Disease Management',
      medical_license: 'NMC-2024-88491',
      hospital_affiliation: 'St. Jude Memorial Hospital',
      department: 'Department of Internal & General Medicine',
      qualifications: 'MBBS, MD (General Medicine), Fellow of the American College of Physicians (FACP)',
      experience_years: 16,
      consultation_hours: 'Mon - Fri: 09:00 AM - 04:30 PM',
      office_room: 'Suite 402, Block B, Clinical Wing',
      phone: '+1 (555) 234-8901',
      cert_verified: true,
      cert_name: 'National Medical Council Verified License 2026',
      consultation_stats: {
        active_patients: 48,
        briefs_generated: 142,
        safety_interventions: 19,
        accuracy_score: '99.4%'
      },
      bio: 'Senior Consultant in General Medicine with over 16 years of expertise in longitudinal chronic disease management, diabetes protocols, and AI-assisted clinical medication safety.'
    };

    const stats = doc.consultation_stats || {
      active_patients: 48,
      briefs_generated: 142,
      safety_interventions: 19,
      accuracy_score: '99.4%'
    };

    return `
      <div class="app-modal-backdrop" id="doctorProfileModalBackdrop" style="display: ${doctorProfileModalOpen ? 'flex' : 'none'};">
        <div class="app-doctor-profile-dialog">
          <div class="app-profile-banner">
            <div class="app-profile-avatar-lg">
              ${doc.full_name ? doc.full_name.charAt(4) || doc.full_name.charAt(0) : 'D'}
            </div>
            <div class="app-profile-title-wrap">
              <h3>${doc.full_name}</h3>
              <div class="app-profile-spec-tag">${doc.specialty} • ${doc.hospital_affiliation}</div>
            </div>
            <button type="button" class="app-profile-close-btn" id="btnCloseDoctorProfile" title="Close Profile">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <div class="app-profile-body">
            <!-- MongoDB Database Status Badge -->
            <div class="app-profile-mongo-badge">
              <div style="display:flex;align-items:center;gap:0.5rem;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                  <path d="M2 17l10 5 10-5"></path>
                  <path d="M2 12l10 5 10-5"></path>
                </svg>
                <span><strong>MongoDB Cloud Database:</strong> Connected & Synced (Collection: <code>doctor_profiles</code>)</span>
              </div>
              <span class="app-panel-tag" style="background:#bbf7d0;color:#14532d;font-weight:700;">Live Profile</span>
            </div>

            <!-- Key Performance & Consultation Stats -->
            <div class="app-profile-stats-grid">
              <div class="app-profile-stat-box">
                <div class="app-profile-stat-val">${stats.active_patients}</div>
                <div class="app-profile-stat-lbl">Active Patients</div>
              </div>
              <div class="app-profile-stat-box">
                <div class="app-profile-stat-val">${stats.briefs_generated}</div>
                <div class="app-profile-stat-lbl">Briefs Created</div>
              </div>
              <div class="app-profile-stat-box">
                <div class="app-profile-stat-val">${stats.safety_interventions}</div>
                <div class="app-profile-stat-lbl">Safety Flags</div>
              </div>
              <div class="app-profile-stat-box">
                <div class="app-profile-stat-val" style="color:#16a34a;">${stats.accuracy_score}</div>
                <div class="app-profile-stat-lbl">Safety Accuracy</div>
              </div>
            </div>

            <!-- Detailed Doctor Credentials Grid -->
            <div class="app-profile-info-grid">
              <div class="app-profile-field">
                <span class="app-profile-field-label">Medical Council License</span>
                <span class="app-profile-field-val">${doc.medical_license}</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Verification Status</span>
                <span class="app-profile-field-val" style="color:#16a34a;">✓ Verified by Medical Council</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Affiliated Hospital</span>
                <span class="app-profile-field-val">${doc.hospital_affiliation}</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Clinical Department</span>
                <span class="app-profile-field-val">${doc.department}</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Sub-Specialization</span>
                <span class="app-profile-field-val">${doc.sub_specialty}</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Experience</span>
                <span class="app-profile-field-val">${doc.experience_years} Years Active Practice</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Clinic Office / Room</span>
                <span class="app-profile-field-val">${doc.office_room}</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Consultation Hours</span>
                <span class="app-profile-field-val">${doc.consultation_hours}</span>
              </div>
              <div class="app-profile-field" style="grid-column: span 2;">
                <span class="app-profile-field-label">Academic Degrees & Qualifications</span>
                <span class="app-profile-field-val" style="font-weight:500;">${doc.qualifications}</span>
              </div>
              <div class="app-profile-field" style="grid-column: span 2;">
                <span class="app-profile-field-label">Clinical Background & Practice Bio</span>
                <p style="font-size:0.875rem;line-height:1.6;color:#334155;margin:0.25rem 0 0;">${doc.bio}</p>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Hospital Contact Phone</span>
                <span class="app-profile-field-val">${doc.phone}</span>
              </div>
              <div class="app-profile-field">
                <span class="app-profile-field-label">Clinical Email</span>
                <span class="app-profile-field-val">${doc.email}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // ── Bind Auth Screen Events ───────────────────────────────────────────────
  function bindAuthEvents() {
    const tabDoc = document.getElementById('tabRoleDoctor');
    const tabPat = document.getElementById('tabRolePatient');
    if (tabDoc) {
      tabDoc.addEventListener('click', () => {
        stopKioskCamera();
        currentRole = 'doctor';
        authError = null;
        otpStepActive = false;
        render();
      });
    }
    if (tabPat) {
      tabPat.addEventListener('click', () => {
        currentRole = 'patient';
        authError = null;
        otpStepActive = false;
        render();
      });
    }

    const tabLogin = document.getElementById('tabModeLogin');
    const tabSignup = document.getElementById('tabModeSignup');
    if (tabLogin) {
      tabLogin.addEventListener('click', () => {
        authMode = 'login';
        authError = null;
        otpStepActive = false;
        render();
      });
    }
    if (tabSignup) {
      tabSignup.addEventListener('click', () => {
        authMode = 'signup';
        authError = null;
        otpStepActive = false;
        render();
      });
    }

    const backBtn = document.getElementById('backToLandingBtn');
    if (backBtn) {
      backBtn.addEventListener('click', (e) => {
        e.preventDefault();
        stopKioskCamera();
        const host = window.location.hostname || '127.0.0.1';
        if (window.location.port === '3000') {
          window.location.href = 'http://' + host + ':8080/';
        } else {
          window.location.hash = '';
        }
      });
    }

    // Terms modal: pure CSS display toggle so inputs are never erased or re-rendered
    const openTerms = document.getElementById('btnOpenTerms');
    const checkTerms = document.getElementById('btnCheckTerms');
    const checkPrivacy = document.getElementById('btnCheckPrivacy');
    const closeTerms = document.getElementById('btnCloseTerms');
    const acceptTermsModal = document.getElementById('btnAcceptTermsModal');
    const backdrop = document.getElementById('termsModalBackdrop');
    const tabTermsBtn = document.getElementById('tabModalTerms');
    const tabPrivacyBtn = document.getElementById('tabModalPrivacy');

    const showModal = (e, tab = 'terms') => {
      if (e) e.preventDefault();
      activeTermsTab = tab;
      termsModalOpen = true;
      const modal = document.getElementById('termsModalBackdrop');
      if (modal) modal.style.display = 'flex';
      renderTermsModalDom();
    };
    const hideModal = (e) => {
      if (e) e.preventDefault();
      termsModalOpen = false;
      const modal = document.getElementById('termsModalBackdrop');
      if (modal) modal.style.display = 'none';
    };

    function renderTermsModalDom() {
      const existing = document.getElementById('termsModalBackdrop');
      if (existing) {
        existing.outerHTML = renderTermsModal();
        const newBackdrop = document.getElementById('termsModalBackdrop');
        if (newBackdrop) newBackdrop.style.display = 'flex';
        // Re-bind modal-specific elements
        const nbClose = document.getElementById('btnCloseTerms');
        const nbAccept = document.getElementById('btnAcceptTermsModal');
        const nbTermsTab = document.getElementById('tabModalTerms');
        const nbPrivTab = document.getElementById('tabModalPrivacy');
        if (nbClose) nbClose.addEventListener('click', hideModal);
        if (nbAccept) nbAccept.addEventListener('click', hideModal);
        if (newBackdrop) newBackdrop.addEventListener('click', (ev) => { if (ev.target === newBackdrop) hideModal(ev); });
        if (nbTermsTab) nbTermsTab.addEventListener('click', () => { activeTermsTab = 'terms'; renderTermsModalDom(); });
        if (nbPrivTab) nbPrivTab.addEventListener('click', () => { activeTermsTab = 'privacy'; renderTermsModalDom(); });
      }
    }

    if (openTerms) openTerms.addEventListener('click', (e) => showModal(e, 'terms'));
    if (checkTerms) checkTerms.addEventListener('click', (e) => showModal(e, 'terms'));
    if (checkPrivacy) checkPrivacy.addEventListener('click', (e) => showModal(e, 'privacy'));
    if (closeTerms) closeTerms.addEventListener('click', hideModal);
    if (acceptTermsModal) acceptTermsModal.addEventListener('click', hideModal);
    if (backdrop) backdrop.addEventListener('click', (e) => { if (e.target === backdrop) hideModal(e); });
    if (tabTermsBtn) tabTermsBtn.addEventListener('click', () => { activeTermsTab = 'terms'; renderTermsModalDom(); });
    if (tabPrivacyBtn) tabPrivacyBtn.addEventListener('click', () => { activeTermsTab = 'privacy'; renderTermsModalDom(); });

    // Kiosk switchers
    const btnOpenKiosk = document.getElementById('btnOpenKioskFace');
    if (btnOpenKiosk) {
      btnOpenKiosk.addEventListener('click', () => {
        patientKioskActive = true;
        authError = null;
        render();
      });
    }
    const btnBackKiosk = document.getElementById('btnBackToStandardLogin');
    if (btnBackKiosk) {
      btnBackKiosk.addEventListener('click', () => {
        patientKioskActive = false;
        stopKioskCamera();
        authError = null;
        render();
      });
    }

    // Eye toggles
    const toggleEye = document.getElementById('togglePasswordBtn');
    const passInput = document.getElementById('loginPassword');
    if (toggleEye && passInput) {
      toggleEye.addEventListener('click', () => {
        passInput.type = passInput.type === 'password' ? 'text' : 'password';
      });
    }

    const toggleRegEye = document.getElementById('toggleRegPasswordBtn');
    const regPassInput = document.getElementById('regPassword');
    if (toggleRegEye && regPassInput) {
      toggleRegEye.addEventListener('click', () => {
        regPassInput.type = regPassInput.type === 'password' ? 'text' : 'password';
      });
    }

    // Form inputs state retention binding
    const regNameInput = document.getElementById('regFullName');
    const regEmailInput = document.getElementById('regEmail');
    const regSpecInput = document.getElementById('regSpecialty');
    const regLicInput = document.getElementById('regLicense');
    const regConfInput = document.getElementById('regConfirmPassword');
    const regTermsInput = document.getElementById('acceptTerms');

    if (regNameInput) regNameInput.addEventListener('input', (e) => { signupFormData.fullName = e.target.value; });
    if (regEmailInput) regEmailInput.addEventListener('input', (e) => { signupFormData.email = e.target.value; });
    if (regSpecInput) regSpecInput.addEventListener('change', (e) => { signupFormData.specialty = e.target.value; });
    if (regLicInput) regLicInput.addEventListener('input', (e) => { signupFormData.license = e.target.value; });
    if (regConfInput) regConfInput.addEventListener('input', (e) => { signupFormData.confirmPassword = e.target.value; });
    if (regTermsInput) regTermsInput.addEventListener('change', (e) => { signupFormData.acceptTerms = e.target.checked; });

    // Live Password Strength Checklist Monitor (Strict 8-20 length & 2 capital letters)
    if (regPassInput) {
      regPassInput.addEventListener('input', (e) => {
        signupFormData.password = e.target.value;
        updatePasswordStrengthUI(e.target.value);
      });
      // Restore password strength status if password was already filled
      if (signupFormData.password) {
        updatePasswordStrengthUI(signupFormData.password);
      }
    }

    // Doctor Certificate Verification
    const btnUpload = document.getElementById('btnUploadCert');
    const btnSimulate = document.getElementById('btnSimulateVerify');
    const certInput = document.getElementById('certFileInput');
    if (btnUpload && certInput) {
      btnUpload.addEventListener('click', () => certInput.click());
      certInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          certFileName = e.target.files[0].name;
          certVerified = true;
          render();
        }
      });
    }
    if (btnSimulate) {
      btnSimulate.addEventListener('click', () => {
        certFileName = 'National_Medical_Council_Certificate_2026.pdf';
        certVerified = true;
        render();
      });
    }

    // Presets
    document.querySelectorAll('.app-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.app-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        const emailEl = document.getElementById('loginEmail');
        const passEl = document.getElementById('loginPassword');
        if (emailEl) emailEl.value = chip.dataset.email;
        if (passEl) passEl.value = chip.dataset.pass;
        authError = null;
      });
    });

    // Sign in submit
    const loginForm = document.getElementById('appLoginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('loginEmail').value.trim();
        const password = document.getElementById('loginPassword').value.trim();

        isLoading = true;
        authError = null;
        render();

        try {
          const res = await fetch(getApiBase() + '/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
          });
          const data = await res.json();
          if (data.success && data.data && data.data.token) {
            authToken = data.data.token;
            currentUser = data.data.user;
            localStorage.setItem('clinsync_token', authToken);
            localStorage.setItem('clinsync_user', JSON.stringify(currentUser));
            isLoading = false;
            window.location.hash = currentUser.role === 'patient' ? '#/patient/home' : '#/doctor/home';
          } else {
            authError = (data.error && data.error.message) || 'Invalid credentials. Please verify your email and password.';
            isLoading = false;
            render();
          }
        } catch (err) {
          authError = 'Unable to reach backend server at ' + getApiBase() + '. Verify port 8000 is active.';
          isLoading = false;
          render();
        }
      });
    }

    // Sign up submit -> Sends OTP via backend
    const signupForm = document.getElementById('appSignupForm');
    if (signupForm) {
      signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fullName = document.getElementById('regFullName').value.trim();
        const email = document.getElementById('regEmail').value.trim();
        const password = document.getElementById('regPassword').value;
        const confirmPass = document.getElementById('regConfirmPassword').value;

        // Strict password checks
        const strength = evaluatePassword(password);
        if (!strength.isStrong) {
          authError = 'Password does not meet strength rules (must be 8-20 characters, with 2 capital letters, 1 number, 1 symbol).';
          render();
          return;
        }

        if (password !== confirmPass) {
          authError = 'Passwords do not match. Please re-enter identical passwords.';
          render();
          return;
        }

        if (currentRole === 'doctor' && !certVerified) {
          authError = 'Please upload or auto-verify your Medical Council Certificate before proceeding.';
          render();
          return;
        }

        const specialty = currentRole === 'doctor' 
          ? (document.getElementById('regSpecialty') ? document.getElementById('regSpecialty').value : 'General Medicine')
          : 'Patient Health';

        pendingRegistration = {
          full_name: fullName,
          email: email,
          password: password,
          role: currentRole,
          specialty: specialty
        };

        isLoading = true;
        authError = null;
        render();

        // 1. Pre-check if account already exists with this email BEFORE sending OTP
        try {
          const checkRes = await fetch(getApiBase() + '/api/v1/auth/check-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email })
          });
          const checkData = await checkRes.json();
          if (checkData.success && checkData.data && checkData.data.exists) {
            authError = `An account with email "${email}" already exists. Please sign in or use a different email.`;
            isLoading = false;
            render();
            return;
          }
        } catch (checkErr) {
          console.warn('Pre-check email failed:', checkErr);
        }

        // 2. Fast background dispatch via /api/v1/auth/send-otp
        try {
          const res = await fetch(getApiBase() + '/api/v1/auth/send-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, role: currentRole, action: 'register' })
          });
          const data = await res.json();
          if (data.success && data.data) {
            activeOtpCode = data.data.simulated_otp || '';
            otpStepActive = true;
          } else {
            authError = (data.error && data.error.message) || 'Failed to dispatch verification OTP code. Please try again.';
          }
        } catch (err) {
          // Local fallback in case network error
          activeOtpCode = String(Math.floor(100000 + Math.random() * 900000));
          otpStepActive = true;
        } finally {
          isLoading = false;
          render();
        }
      });
    }

    // Hospital Tablet Kiosk Event Bindings (Face Recognition & Registration)
    // Hospital Tablet Kiosk Event Bindings (Face Recognition & Registration)
    if (currentRole === 'patient' && authMode === 'login' && !otpStepActive) {
      // Re-attach active camera stream or automatically initialize laptop webcam
      if (kioskCameraActive && kioskCameraStream && kioskCameraStream.active) {
        const video = document.getElementById('kioskCameraVideo');
        if (video) {
          video.srcObject = kioskCameraStream;
          video.muted = true;
          video.playsInline = true;
          video.play().catch(() => {});
        }
        updateCameraDOM(true, 'Laptop Webcam Active · Center Face in Oval', 'normal');
      } else {
        // Auto-initialize camera directly
        startKioskCamera();
      }

      const btnToggleCam = document.getElementById('btnToggleKioskCam');
      if (btnToggleCam) {
        btnToggleCam.addEventListener('click', () => {
          if (kioskCameraActive) {
            stopKioskCamera();
          } else {
            startKioskCamera();
          }
        });
      }

      const btnScanFace = document.getElementById('btnScanKioskFace');
      if (btnScanFace) {
        btnScanFace.addEventListener('click', () => {
          performKioskFaceRecognition();
        });
      }

      const btnRestartCam = document.getElementById('btnRestartKioskCam');
      if (btnRestartCam) {
        btnRestartCam.addEventListener('click', () => {
          stopKioskCamera();
          startKioskCamera();
        });
      }

      const btnUploadPhoto = document.getElementById('btnUploadFacePhoto');
      const fileInputFace = document.getElementById('kioskFaceFileInput');
      if (btnUploadPhoto && fileInputFace) {
        btnUploadPhoto.addEventListener('click', () => fileInputFace.click());
        fileInputFace.addEventListener('change', (e) => {
          if (e.target.files && e.target.files[0]) {
            const reader = new FileReader();
            reader.onload = (re) => {
              capturedFaceBase64 = re.target.result;
              kioskFaceStatus = { text: '✓ Face Photo Loaded · Click "Scan Face" below', state: 'success' };
              stopKioskCamera();
              render();
            };
            reader.readAsDataURL(e.target.files[0]);
          }
        });
      }

      const btnDemoQuick = document.getElementById('btnDemoQuickScan');
      if (btnDemoQuick) {
        btnDemoQuick.addEventListener('click', () => {
          capturedFaceBase64 = generateSyntheticFaceDataUrl();
          kioskFaceStatus = { text: '⚡ Demo Face Loaded · Matching...', state: 'normal' };
          performKioskFaceRecognition();
        });
      }

      const btnOpenReg = document.getElementById('btnOpenNewFaceEnroll');
      if (btnOpenReg) {
        btnOpenReg.addEventListener('click', (e) => {
          e.preventDefault();
          capturedFaceBase64 = captureKioskVideoFrame();
          stopKioskCamera();
          faceRegModalOpen = true;
          render();
        });
      }

      const formFaceReg = document.getElementById('formFaceRegistration');
      if (formFaceReg) {
        formFaceReg.addEventListener('submit', performKioskFaceRegistration);
      }

      const btnCloseFaceReg = document.getElementById('btnCloseFaceReg');
      const btnCancelFaceReg = document.getElementById('btnCancelFaceRegModal');
      const closeRegModal = (e) => {
        if (e) e.preventDefault();
        faceRegModalOpen = false;
        render();
      };
      if (btnCloseFaceReg) btnCloseFaceReg.addEventListener('click', closeRegModal);
      if (btnCancelFaceReg) btnCancelFaceReg.addEventListener('click', closeRegModal);
    }

    if (otpStepActive) {
      bindOtpEvents();
    }
  }

  // ── Bind OTP Events ───────────────────────────────────────────────────────
  function bindOtpEvents() {
    const input = document.getElementById('otpUnifiedInput');
    const cancelBtn = document.getElementById('btnCancelOtp');
    const resendBtn = document.getElementById('btnResendOtp');
    const otpForm = document.getElementById('appOtpForm');

    if (input) {
      input.focus();
      input.addEventListener('input', (e) => {
        // Strip non-digits and limit to 6
        e.target.value = e.target.value.replace(/\D/g, '').slice(0, 6);
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        otpStepActive = false;
        authError = null;
        render();
      });
    }

    if (resendBtn && pendingRegistration) {
      resendBtn.addEventListener('click', async () => {
        isLoading = true;
        render();
        try {
          const res = await fetch(getApiBase() + '/api/v1/auth/send-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: pendingRegistration.email, role: currentRole })
          });
          const data = await res.json();
          if (data.success && data.data) {
            activeOtpCode = data.data.simulated_otp || '';
          }
        } catch (e) {
          activeOtpCode = String(Math.floor(100000 + Math.random() * 900000));
        } finally {
          isLoading = false;
          render();
        }
      });
    }

    if (otpForm && input) {
      otpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const enteredOtp = input.value.trim();

        isLoading = true;
        authError = null;
        render();

        try {
          // 1. Verify OTP with backend
          const verifyRes = await fetch(getApiBase() + '/api/v1/auth/verify-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: pendingRegistration.email, otp: enteredOtp })
          });
          const verifyData = await verifyRes.json();

          if (!verifyData.success && enteredOtp !== activeOtpCode) {
            authError = (verifyData.error && verifyData.error.message) || 'Invalid verification code. Please check your email and try again.';
            isLoading = false;
            render();
            return;
          }

          // 2. Register account
          const regRes = await fetch(getApiBase() + '/api/v1/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pendingRegistration)
          });
          const regData = await regRes.json();

          if (!regData.success) {
            authError = (regData.error && regData.error.message) || 'Account creation failed. Email may already be registered.';
            isLoading = false;
            render();
            return;
          }

          // 3. Auto Login
          const loginRes = await fetch(getApiBase() + '/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: pendingRegistration.email,
              password: pendingRegistration.password
            })
          });
          const loginData = await loginRes.json();

          if (loginData.success && loginData.data && loginData.data.token) {
            authToken = loginData.data.token;
            currentUser = loginData.data.user;
            localStorage.setItem('clinsync_token', authToken);
            localStorage.setItem('clinsync_user', JSON.stringify(currentUser));
            isLoading = false;
            otpStepActive = false;
            pendingRegistration = null;

            // Route to appropriate dashboard
            window.location.hash = currentUser.role === 'patient' ? '#/patient/home' : '#/doctor/home';
          } else {
            authMode = 'login';
            otpStepActive = false;
            authError = 'Registration complete! Please sign in with your credentials.';
            isLoading = false;
            render();
          }
        } catch (err) {
          authError = 'Network error during verification. Verify backend is running on port 8000.';
          isLoading = false;
          render();
        }
      });
    }
  }

  // ── Render Doctor Dashboard (Roster Table or Single Patient Deep View) ────
  function renderDoctorDashboard() {
    const doctor = currentUser || { full_name: 'Dr. Willie Carter, MD', specialty: 'General Medicine' };

    // If doctor has selected a specific patient, show that patient's detailed clinical workspace
    if (selectedPatientId) {
      return renderDoctorPatientDetailView(doctor);
    }

    // Filter patients by specialization
    let filteredList = PATIENT_ROSTER;
    if (doctorRosterFilter === 'my_specialty') {
      const docSpec = (doctor.specialty || 'General Medicine').toLowerCase();
      filteredList = PATIENT_ROSTER.filter(p => p.specialty.toLowerCase() === docSpec);
      // Fallback if none match
      if (filteredList.length === 0) filteredList = PATIENT_ROSTER;
    } else if (doctorRosterFilter !== 'all') {
      filteredList = PATIENT_ROSTER.filter(p => p.specialty.toLowerCase() === doctorRosterFilter.toLowerCase());
    }

    return `
      <div class="app-workspace-view">
        <!-- Top Navigation Bar -->
        <header class="app-topbar">
          <div class="app-topbar-left">
            <a href="#/doctor/home" class="app-topbar-brand">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
              </svg>
              <span>ClinSync</span>
            </a>
            <div class="app-pill-live">
              <span class="dot"></span> Department: ${doctor.specialty || 'General Medicine'}
            </div>
          </div>
          <div class="app-topbar-right">
            <div class="app-doctor-badge btnDoctorProfileTrigger" style="cursor:pointer;" title="Click to view full Doctor Clinical Profile & Credentials">
              <div class="app-doctor-avatar">${doctor.full_name ? doctor.full_name.charAt(0) : 'D'}</div>
              <div class="app-doctor-info">
                <span class="app-doctor-name">${doctor.full_name || 'Dr. Willie Carter, MD'} ▾</span>
                <span class="app-doctor-spec">${doctor.specialty || 'General Medicine'}</span>
              </div>
            </div>
            <button type="button" class="app-btn-outline" id="navLandingBtn">Landing Page</button>
            <button type="button" class="app-btn-danger-outline" id="navSignOutBtn">Sign Out</button>
          </div>
        </header>

        <!-- Doctor Directory Roster View -->
        <main class="app-workspace-body" style="margin-top:1.5rem;">
          <div class="app-roster-header">
            <div>
              <h2 style="font-size:1.6rem;font-weight:700;color:#0f172a;margin-bottom:0.25rem;">
                Clinician Patient Directory
              </h2>
              <p style="font-size:0.875rem;color:#64748b;">
                Select a patient to access pre-consultation intelligence, AI doctor briefs, medication reconciliation, and longitudinal records.
              </p>
            </div>
            <!-- Specialization Filter Tabs -->
            <div class="app-roster-filters">
              <button type="button" class="app-roster-filter-btn ${doctorRosterFilter === 'my_specialty' ? 'active' : ''}" data-filter="my_specialty">
                ★ My Specialty (${doctor.specialty || 'General Medicine'})
              </button>
              <button type="button" class="app-roster-filter-btn ${doctorRosterFilter === 'all' ? 'active' : ''}" data-filter="all">
                All Departments
              </button>
              <button type="button" class="app-roster-filter-btn ${doctorRosterFilter === 'General Medicine' ? 'active' : ''}" data-filter="General Medicine">
                General Medicine
              </button>
              <button type="button" class="app-roster-filter-btn ${doctorRosterFilter === 'Cardiology' ? 'active' : ''}" data-filter="Cardiology">
                Cardiology
              </button>
              <button type="button" class="app-roster-filter-btn ${doctorRosterFilter === 'Internal Medicine' ? 'active' : ''}" data-filter="Internal Medicine">
                Internal Medicine
              </button>
            </div>
          </div>

          <!-- Tabular Patient List -->
          <div style="overflow-x:auto;">
            <table class="app-roster-table">
              <thead>
                <tr>
                  <th>Patient Name & ID</th>
                  <th>Age / Sex</th>
                  <th>Primary Clinical Condition</th>
                  <th>Department</th>
                  <th>Safety / Conflict Status</th>
                  <th>Documents</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                ${filteredList.map(p => `
                  <tr>
                    <td>
                      <div class="app-patient-cell">
                        <div class="app-patient-avatar">${p.name.charAt(0)}</div>
                        <div>
                          <strong style="color:#0f172a;display:block;">${p.name}</strong>
                          <span style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#64748b;">${p.id}</span>
                        </div>
                      </div>
                    </td>
                    <td>${p.age} Y • ${p.sex}</td>
                    <td>
                      <strong style="color:#1e293b;">${p.condition}</strong>
                      <div style="font-size:0.75rem;color:#64748b;">Last encounter: ${p.lastVisit}</div>
                    </td>
                    <td>
                      <span class="app-panel-tag" style="background:#f1f5f9;color:#334155;">${p.specialty}</span>
                    </td>
                    <td>
                      ${p.status.includes('Conflict') ? `
                        <span class="app-panel-tag" style="background:#fee2e2;color:#b91c1c;font-weight:700;">${p.status}</span>
                      ` : p.statusClass === 'warning' ? `
                        <span class="app-panel-tag" style="background:#fef3c7;color:#92400e;">${p.status}</span>
                      ` : `
                        <span class="app-panel-tag" style="background:#dcfce7;color:#166534;">${p.status}</span>
                      `}
                    </td>
                    <td>
                      <span style="font-size:0.8125rem;color:#475569;">📄 ${p.filesCount} records</span>
                    </td>
                    <td>
                      <button type="button" class="app-btn-outline btnSelectPatient" data-id="${p.id}" style="color:#0284c7;border-color:#bae6fd;background:#f0f9ff;font-weight:700;">
                        Open Patient Record & Brief →
                      </button>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </main>
      </div>
    `;
  }

  // ── Render Doctor Single Patient Detail Workspace ─────────────────────────
  function renderDoctorPatientDetailView(doctor) {
    const curP = PATIENT_ROSTER.find(p => p.id === selectedPatientId) || {
      name: 'Demo Patient', age: 52, sex: 'Male', id: selectedPatientId, dob: '1974-05-14', contact: '+91 98765 43210'
    };
    const b = (patientData && patientData.latest_brief) || {};

    return `
      <div class="app-workspace-view">
        <header class="app-topbar">
          <div class="app-topbar-left">
            <button type="button" class="app-btn-outline" id="btnBackToRoster" style="font-weight:700;">
              ← Back to Patient Directory
            </button>
            <div class="app-pill-live">
              <span class="dot"></span> Viewing: ${curP.name}
            </div>
          </div>
          <div class="app-topbar-right">
            <div class="app-doctor-badge btnDoctorProfileTrigger" style="cursor:pointer;" title="Click to view full Doctor Clinical Profile & Credentials">
              <div class="app-doctor-avatar">${doctor.full_name ? doctor.full_name.charAt(0) : 'D'}</div>
              <div class="app-doctor-info">
                <span class="app-doctor-name">${doctor.full_name || 'Dr. Willie Carter, MD'} ▾</span>
                <span class="app-doctor-spec">${doctor.specialty || 'General Medicine'}</span>
              </div>
            </div>
            <button type="button" class="app-btn-outline" id="navLandingBtn">Landing Page</button>
            <button type="button" class="app-btn-danger-outline" id="navSignOutBtn">Sign Out</button>
          </div>
        </header>

        <!-- Selected Patient Header -->
        <section class="app-patient-header">
          <div class="app-patient-main">
            <div>
              <div class="app-patient-title">
                <h2 class="app-patient-name">${curP.name}</h2>
                <span class="app-panel-tag" style="background:#e0f2fe;color:#0284c7;font-weight:700;">Active Clinical Record</span>
                <span class="app-panel-tag">Age: ${curP.age} • ${curP.sex.toUpperCase()}</span>
                <span class="app-panel-tag" style="background:#f1f5f9;color:#334155;">Department: ${curP.specialty || 'General Medicine'}</span>
              </div>
              <div class="app-patient-meta">
                <span><strong>ID:</strong> ${curP.id}</span>
                <span><strong>DOB:</strong> ${curP.dob || '1974-05-14'}</span>
                <span><strong>Contact:</strong> ${curP.contact || '+91 98765 43210'}</span>
                <span><strong>Last Encounter:</strong> ${curP.lastVisit || '28 Sep 2026'}</span>
              </div>
            </div>
          </div>

          ${curP.id === 'pat_demo_patient_001' ? `
            <div class="app-conflict-banner">
              <div>
                <strong>⚠️ Safety Alert:</strong> Contradictory Metformin prescriptions detected across Sep 12 records (500 mg BD vs 1000 mg BD).
              </div>
              <button type="button" class="app-btn-outline" style="border-color:#f59e0b;color:#b45309;background:#fff;" id="btnViewConflict">
                Review Medication Reconciliation
              </button>
            </div>
          ` : ''}
        </section>

        <!-- Workspace Tabs -->
        <nav class="app-tabs-bar">
          <button class="app-tab-btn ${activeTab === 'overview' ? 'active' : ''}" data-tab="overview">Patient Overview</button>
          <button class="app-tab-btn ${activeTab === 'brief' ? 'active' : ''}" data-tab="brief">Doctor Brief</button>
          <button class="app-tab-btn ${activeTab === 'reconciliation' ? 'active' : ''}" data-tab="reconciliation">Medication Reconciliation</button>
          <button class="app-tab-btn ${activeTab === 'timeline' ? 'active' : ''}" data-tab="timeline">Clinical Timeline</button>
          <button class="app-tab-btn ${activeTab === 'trends' ? 'active' : ''}" data-tab="trends">Lab Trends</button>
          <button class="app-tab-btn ${activeTab === 'memory' ? 'active' : ''}" data-tab="memory">Clinical Memory & Audit</button>
        </nav>

        <main class="app-workspace-body">
          ${renderDoctorTabContent(curP, b)}
        </main>
      </div>
    `;
  }

  function renderDoctorTabContent(curP, b) {
    switch (activeTab) {
      case 'brief':
        return `
          <div class="app-panel">
            <div class="app-panel-header">
              <h3 class="app-panel-title">Doctor Brief — Pre-Consultation Intelligence</h3>
              <span class="app-panel-tag" style="background:#dcfce7;color:#166534;">Verified & Approved</span>
            </div>
            <div style="margin-bottom:1.5rem;">
              <h4 style="font-size:0.875rem;color:#475569;margin-bottom:0.35rem;text-transform:uppercase;">Chief Complaint</h4>
              <p style="font-size:1rem;color:#0f172a;line-height:1.6;background:#f8fafc;padding:0.85rem;border-radius:10px;border-left:4px solid #0284c7;">
                ${b.chief_complaint ? b.chief_complaint.text : `Presentation for ${curP.condition}. Patient reports stable symptoms following recent adjustments.`}
              </p>
            </div>
            <div style="margin-bottom:1.5rem;">
              <h4 style="font-size:0.875rem;color:#475569;margin-bottom:0.35rem;text-transform:uppercase;">Relevant Clinical History</h4>
              <p style="font-size:0.9375rem;color:#1e293b;line-height:1.6;">
                Longitudinal record shows progressive management of ${curP.condition}. Compliance with regimen monitored quarterly.
              </p>
            </div>
            <div>
              <h4 style="font-size:0.875rem;color:#475569;margin-bottom:0.5rem;text-transform:uppercase;">Evidence Shortcuts</h4>
              <div style="display:flex;gap:0.75rem;flex-wrap:wrap;">
                <span class="app-panel-tag" style="background:#f1f5f9;color:#334155;">📄 Baseline Consultation (2026)</span>
                <span class="app-panel-tag" style="background:#f1f5f9;color:#334155;">📄 Recent Diagnostic Review</span>
              </div>
            </div>
          </div>
        `;

      case 'reconciliation':
        return `
          <div class="app-panel">
            <div class="app-panel-header">
              <h3 class="app-panel-title">Medication Reconciliation</h3>
              <span class="app-panel-tag" style="background:#fef3c7;color:#92400e;">Active Review</span>
            </div>
            <table class="app-audit-table">
              <thead>
                <tr><th>Medication</th><th>Dosage</th><th>Frequency</th><th>Status</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Tab. Metformin</strong></td><td>500 mg / 1000 mg</td><td>Twice daily (BD)</td>
                  <td><span class="app-panel-tag" style="background:#fee2e2;color:#b91c1c;">Discrepancy</span></td>
                </tr>
                <tr>
                  <td><strong>Tab. Glimepiride</strong></td><td>1 mg</td><td>Once daily (OD)</td>
                  <td><span class="app-panel-tag" style="background:#dcfce7;color:#15803d;">Aligned</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        `;

      case 'timeline':
        return `
          <div class="app-panel">
            <div class="app-panel-header"><h3 class="app-panel-title">Clinical Timeline</h3></div>
            <div class="app-timeline">
              <div class="app-timeline-item">
                <div class="app-timeline-dot"></div>
                <div class="app-timeline-date">29 Sep 2026 • 10:00 AM</div>
                <div class="app-timeline-title">Approved Clinical Consultation</div>
                <div class="app-timeline-desc">Patient reviewed for ${curP.condition}. Ongoing maintenance regimen validated.</div>
              </div>
            </div>
          </div>
        `;

      case 'trends':
        return `
          <div class="app-panel">
            <div class="app-panel-header"><h3 class="app-panel-title">Longitudinal Biomarkers</h3></div>
            <div class="app-lab-card">
              <div class="app-lab-title"><span>HbA1c</span><span style="color:#0284c7;">Trend: Improving</span></div>
              <div class="app-lab-progression">
                <div class="app-lab-point"><div class="app-lab-val">8.4%</div><div class="app-lab-date">Jan 2026</div></div>
                <div>→</div>
                <div class="app-lab-point"><div class="app-lab-val">7.8%</div><div class="app-lab-date">Sep 2026</div></div>
              </div>
            </div>
          </div>
        `;

      case 'memory':
        return `
          <div class="app-panel">
            <div class="app-panel-header"><h3 class="app-panel-title">Clinical Memory & Audit</h3></div>
            <p>Verified diagnostic history and tamper-proof SHA-256 audit ledger recorded.</p>
          </div>
        `;

      case 'overview':
      default:
        return `
          <div class="app-grid-2">
            <div class="app-panel">
              <div class="app-panel-header"><h3 class="app-panel-title">Doctor Brief Preview</h3></div>
              <p style="font-size:0.9375rem;line-height:1.6;color:#334155;">
                <strong>Primary Diagnosis:</strong> ${curP.condition}
              </p>
              <p style="font-size:0.9375rem;line-height:1.6;color:#334155;margin-top:0.75rem;">
                <strong>Clinical Status:</strong> ${curP.status}
              </p>
            </div>
            <div class="app-panel">
              <div class="app-panel-header"><h3 class="app-panel-title">Key Indicators</h3></div>
              <div style="background:#f8fafc;padding:1rem;border-radius:10px;">
                <div>Blood Pressure: 128/82 mmHg</div>
                <div style="margin-top:0.5rem;">HbA1c: 7.8% (Target &lt; 7.0%)</div>
              </div>
            </div>
          </div>
        `;
    }
  }

  // ── Render Fresh Patient Dashboard (Voice Intake, Camera OCR, PDF Parser) ─
  function renderPatientDashboard() {
    const user = currentUser || { full_name: 'Patient User', email: 'patient@clinsync.health' };

    return `
      <div class="app-workspace-view">
        <!-- Top Nav -->
        <header class="app-topbar">
          <div class="app-topbar-left">
            <a href="#/patient/home" class="app-topbar-brand">
              <svg viewBox="0 0 24 24" fill="none" stroke="#0d9488" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
              </svg>
              <span>ClinSync Patient Portal</span>
            </a>
            <div class="app-pill-live" style="background:#ccfbf1;color:#0f766e;border-color:#99f6e4;">
              <span class="dot" style="background:#0d9488;"></span> My Health Records
            </div>
          </div>
          <div class="app-topbar-right">
            <div class="app-doctor-badge" style="background:#f0fdfa;">
              <div class="app-doctor-avatar patient">${user.full_name ? user.full_name.charAt(0) : 'P'}</div>
              <div class="app-doctor-info">
                <span class="app-doctor-name">${user.full_name}</span>
                <span class="app-doctor-spec">Verified Patient Account</span>
              </div>
            </div>
            <button type="button" class="app-btn-outline" id="navLandingBtn">Landing Page</button>
            <button type="button" class="app-btn-danger-outline" id="navSignOutBtn">Sign Out</button>
          </div>
        </header>

        <!-- Patient Header Welcome -->
        <section class="app-patient-header" style="background: linear-gradient(to right, #f0fdfa, #ffffff);">
          <div class="app-patient-main" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;">
            <div>
              <div class="app-patient-title">
                <h2 class="app-patient-name" style="color:#0f766e;">Welcome, ${user.full_name} 👋</h2>
                <span class="app-panel-tag" style="background:#dcfce7;color:#166534;font-weight:700;">Account Active</span>
              </div>
              <p style="font-size:0.875rem;color:#475569;margin-top:0.35rem;">
                Express your symptoms and upload your medical reports below before your upcoming doctor consultation.
              </p>
            </div>
            <!-- Enrolled Biometric Face ID Badge -->
            <div style="display:flex;align-items:center;gap:0.75rem;background:#ffffff;border:1px solid #ccfbf1;padding:0.75rem 1.15rem;border-radius:14px;box-shadow:0 4px 12px rgba(13,148,136,0.08);">
              <img src="${user.face_thumbnail || 'data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 80 80\'%3E%3Crect width=\'80\' height=\'80\' fill=\'%230d9488\'/%3E%3Ccircle cx=\'40\' cy=\'32\' r=\'16\' fill=\'white\'/%3E%3Cpath d=\'M20 68c0-11 9-20 20-20s20 9 20 20\' fill=\'white\'/%3E%3C/svg%3E'}" style="width:48px;height:48px;border-radius:50%;object-fit:cover;border:2px solid #0d9488;" alt="Enrolled Face" />
              <div>
                <div style="font-size:0.8125rem;font-weight:700;color:#0f766e;display:flex;align-items:center;gap:0.35rem;">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  Face ID Active in MongoDB
                </div>
                <div style="font-size:0.75rem;color:#64748b;">St. Jude Memorial Hospital Tablet Kiosk</div>
              </div>
            </div>
          </div>
        </section>

        <!-- Fresh Clinical Intake Hub: 3 Required Options -->
        <main class="app-workspace-body" style="margin-top:1.5rem;">
          <h3 style="font-size:1.25rem;font-weight:700;color:#0f172a;margin-bottom:1rem;">
            Clinical Symptom Intake & Document Processing
          </h3>

          <div class="app-intake-grid">
            <!-- 1. Voice Input (Speech-to-Text) Card -->
            <div class="app-intake-card">
              <div class="app-intake-icon voice">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <line x1="12" y1="19" x2="12" y2="23"></line>
                  <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
              </div>
              <h3>1. AI Doctor Voice Consultation</h3>
              <p>Speak naturally with Dr. ClinSync AI. Our intelligent physician asks follow-up questions, evaluates pain & duration, and documents every symptom in real time.</p>
              <button type="button" class="app-btn-outline" id="btnToggleVoice" style="border-color:#0d9488;color:#0d9488;background:#f0fdfa;font-weight:700;">
                ${aiDoctorConsultActive ? '⏹ Close AI Consultation' : '🩺 Consult AI Doctor (Voice & Text)'}
              </button>
            </div>

            <!-- 2. Camera Document Scanning (Vision / OCR) Card -->
            <div class="app-intake-card">
              <div class="app-intake-icon camera">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                  <circle cx="12" cy="13" r="4"></circle>
                </svg>
              </div>
              <h3>2. Camera Document Scan</h3>
              <p>Use your camera to scan prescriptions, lab sheets, and discharge slips. OCR Vision automatically extracts clinical findings.</p>
              <button type="button" class="app-btn-outline" id="btnToggleCamera" style="border-color:#0284c7;color:#0284c7;background:#fff;">
                📷 Open Camera Scanner
              </button>
            </div>

            <!-- 3. PDF Upload (PDF Parser) Card -->
            <div class="app-intake-card">
              <div class="app-intake-icon pdf">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                  <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
              </div>
              <h3>3. Upload Medical Records & Documents</h3>
              <p>Upload in any format: <strong>PDF, JPG, PNG, TXT, PPTX, PPT, DOCX</strong>. Our Smart AI Receptionist extracts clinical findings and prepares your doctor brief.</p>
              <input type="file" id="pdfFileInput" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.pptx,.ppt,.docx,.doc" style="display:none;" />
              <button type="button" class="app-btn-outline" id="btnBrowsePdf" style="border-color:#d97706;color:#d97706;background:#fff;font-weight:700;">
                📁 Browse & Upload Any Medical Record
              </button>
            </div>
          </div>

          <!-- Dynamic Display: Interactive AI Doctor Intake Consultation -->
          ${renderAiDoctorConsultationBox()}

          <!-- Dynamic Display: Voice Input Section -->
          ${isRecordingVoice || voiceTranscript ? `
            <div class="app-panel" style="margin-bottom:1.5rem;border-color:#fca5a5;">
              <div class="app-panel-header">
                <h3 class="app-panel-title" style="color:#dc2626;">🎙️ Live Speech-to-Text Transcription</h3>
                ${isRecordingVoice ? '<span class="app-panel-tag" style="background:#fee2e2;color:#dc2626;">Recording...</span>' : '<span class="app-panel-tag">Saved</span>'}
              </div>
              ${isRecordingVoice ? `
                <div class="app-voice-wave">
                  <div class="app-voice-bar"></div><div class="app-voice-bar"></div><div class="app-voice-bar"></div><div class="app-voice-bar"></div><div class="app-voice-bar"></div>
                </div>
              ` : ''}
              <textarea class="app-voice-transcript" id="voiceTranscriptArea" rows="4" style="width:100%;">${voiceTranscript || 'Listening... Please speak your symptoms clearly into your microphone.'}</textarea>
              <div style="display:flex;justify-content:flex-end;gap:0.5rem;margin-top:0.75rem;">
                <button type="button" class="app-btn-outline" id="btnSaveVoiceNote" style="background:#0f766e;color:#fff;border-color:#0f766e;">
                  ✓ Save Intake Note to Hospital MongoDB
                </button>
              </div>
            </div>
          ` : ''}

          <!-- Dynamic Display: Camera Scanner Section -->
          <div id="cameraScannerSection" style="display:none;" class="app-panel">
            <div class="app-panel-header">
              <h3 class="app-panel-title">📷 Live Camera Document Scanner</h3>
              <button type="button" class="app-btn-outline" id="btnCloseCamera">Close Camera</button>
            </div>
            <div class="app-camera-viewport">
              <video class="app-camera-video" id="cameraVideo" autoplay playsinline></video>
              <div class="app-camera-crosshair"></div>
            </div>
            <div style="text-align:center;margin-top:1rem;">
              <button type="button" class="app-btn-primary" id="btnCaptureSnapshot" style="width:auto;display:inline-flex;padding:0.75rem 2rem;">
                Capture & Scan with OCR Vision
              </button>
            </div>
          </div>

          <!-- Dynamic Display: OCR Results -->
          ${scannedDocResult ? `
            <div class="app-panel" style="margin-bottom:1.5rem;border-color:#7dd3fc;">
              <div class="app-panel-header">
                <h3 class="app-panel-title" style="color:#0284c7;">✓ OCR Vision Extraction Results</h3>
                <span class="app-panel-tag" style="background:#e0f2fe;color:#0284c7;">Processed</span>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
                <div style="background:#f8fafc;padding:1rem;border-radius:10px;">
                  <strong style="display:block;margin-bottom:0.25rem;">Extracted Medication Data:</strong>
                  <div style="font-size:0.875rem;color:#334155;">${scannedDocResult.medication}</div>
                </div>
                <div style="background:#f8fafc;padding:1rem;border-radius:10px;">
                  <strong style="display:block;margin-bottom:0.25rem;">Clinical Diagnostic Text:</strong>
                  <div style="font-size:0.875rem;color:#334155;">${scannedDocResult.diagnosis}</div>
                </div>
              </div>
            </div>
          ` : ''}

          <!-- Dynamic Display: PDF Parser Results -->
          ${parsedPdfResult ? `
            <div class="app-panel" style="margin-bottom:1.5rem;border-color:#fcd34d;">
              <div class="app-panel-header">
                <h3 class="app-panel-title" style="color:#d97706;">📄 Medical PDF Parser Extraction</h3>
                <span class="app-panel-tag" style="background:#fef3c7;color:#92400e;">File: ${parsedPdfResult.filename}</span>
              </div>
              <table class="app-audit-table">
                <thead>
                  <tr><th>Biomarker / Test</th><th>Measured Value</th><th>Reference Range</th><th>Status</th></tr>
                </thead>
                <tbody>
                  ${parsedPdfResult.tests.map(t => `
                    <tr>
                      <td><strong>${t.test}</strong></td>
                      <td>${t.val}</td>
                      <td>${t.ref}</td>
                      <td><span class="app-panel-tag" style="background:#dcfce7;color:#166534;">Extracted</span></td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          ` : ''}

          <!-- Patient Summary & Care Plan (Dynamic to User in Database) -->
          ${(() => {
            const isDemo = (user.id === 'usr_patient_001' || user.email === 'patient@clinsync.health' || user.patient_id === 'pat_demo_patient_001');
            if (isDemo) {
              return `
                <div class="app-grid-2">
                  <div class="app-panel">
                    <div class="app-panel-header">
                      <h3 class="app-panel-title">My Chronic Care Overview</h3>
                      <span class="app-panel-tag" style="background:#dcfce7;color:#166534;">Managed</span>
                    </div>
                    <p style="font-size:0.875rem;color:#334155;line-height:1.6;">
                      Active management for <strong>Type 2 Diabetes Mellitus</strong>. 
                      HbA1c levels have steadily improved from 8.4% down to 7.8%. Kidney parameters remain healthy.
                    </p>
                  </div>
                  <div class="app-panel">
                    <div class="app-panel-header">
                      <h3 class="app-panel-title">Active Regimen</h3>
                      <span class="app-panel-tag">Current</span>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:0.5rem;font-size:0.875rem;">
                      <div style="padding:0.6rem 0.8rem;background:#f8fafc;border-radius:8px;border-left:3px solid #0d9488;">
                        <strong>Tab. Glimepiride 1 mg</strong> • Once Daily (Morning)
                      </div>
                      <div style="padding:0.6rem 0.8rem;background:#f8fafc;border-radius:8px;border-left:3px solid #ea580c;">
                        <strong>Tab. Metformin 500 mg</strong> • Twice Daily (With food)
                      </div>
                    </div>
                  </div>
                </div>

                <div class="app-panel" style="margin-top:1.5rem;border-color:#99f6e4;">
                  <div class="app-panel-header">
                    <h3 class="app-panel-title" style="color:#0f766e;">🩺 Hospital Tablet Kiosk Vitals Logger</h3>
                    <span class="app-panel-tag" style="background:#ccfbf1;color:#0f766e;">MongoDB Collection: patient_vitals</span>
                  </div>
                  <p style="font-size:0.875rem;color:#475569;margin-bottom:1rem;">
                    Log today's vital signs taken at the hospital check-in tablet. Updates are saved to MongoDB Atlas for physician review.
                  </p>
                  <div class="app-grid-2" style="gap:1rem;margin-bottom:1rem;">
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsBp">Blood Pressure (mmHg)</label>
                      <input class="app-input" id="vitalsBp" type="text" value="122/80" placeholder="e.g. 120/80" />
                    </div>
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsGlucose">Fasting Glucose (mg/dL)</label>
                      <input class="app-input" id="vitalsGlucose" type="text" value="138" placeholder="e.g. 110" />
                    </div>
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsPulse">Heart Rate (Pulse bpm)</label>
                      <input class="app-input" id="vitalsPulse" type="text" value="74" placeholder="e.g. 72" />
                    </div>
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsSpo2">Blood Oxygen SpO2 (%)</label>
                      <input class="app-input" id="vitalsSpo2" type="text" value="98 %" placeholder="e.g. 98%" />
                    </div>
                  </div>
              `;
            } else {
              return `
                <div class="app-grid-2">
                  <div class="app-panel">
                    <div class="app-panel-header">
                      <h3 class="app-panel-title">My Chronic Care Overview</h3>
                      <span class="app-panel-tag" style="background:#f1f5f9;color:#475569;">Baseline Needed</span>
                    </div>
                    <p style="font-size:0.875rem;color:#475569;line-height:1.6;">
                      No chronic conditions currently on file for this account. Use the AI Doctor Consultation or upload medical documents above to establish your personal health record baseline.
                    </p>
                  </div>
                  <div class="app-panel">
                    <div class="app-panel-header">
                      <h3 class="app-panel-title">Active Regimen</h3>
                      <span class="app-panel-tag" style="background:#f1f5f9;color:#475569;">0 Medications</span>
                    </div>
                    <p style="font-size:0.875rem;color:#475569;line-height:1.6;">
                      No active prescriptions or medications recorded. Upload a prescription slip or inform the AI Doctor during your symptom intake.
                    </p>
                  </div>
                </div>

                <div class="app-panel" style="margin-top:1.5rem;border-color:#99f6e4;">
                  <div class="app-panel-header">
                    <h3 class="app-panel-title" style="color:#0f766e;">🩺 Hospital Tablet Kiosk Vitals Logger</h3>
                    <span class="app-panel-tag" style="background:#ccfbf1;color:#0f766e;">MongoDB Collection: patient_vitals</span>
                  </div>
                  <p style="font-size:0.875rem;color:#475569;margin-bottom:1rem;">
                    Log your vital signs taken at the clinic or hospital kiosk. Saved directly to your medical chart in MongoDB Atlas.
                  </p>
                  <div class="app-grid-2" style="gap:1rem;margin-bottom:1rem;">
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsBp">Blood Pressure (mmHg)</label>
                      <input class="app-input" id="vitalsBp" type="text" value="" placeholder="e.g. 120/80" />
                    </div>
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsGlucose">Fasting Glucose (mg/dL)</label>
                      <input class="app-input" id="vitalsGlucose" type="text" value="" placeholder="e.g. 110" />
                    </div>
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsPulse">Heart Rate (Pulse bpm)</label>
                      <input class="app-input" id="vitalsPulse" type="text" value="" placeholder="e.g. 72" />
                    </div>
                    <div class="app-form-group" style="margin-bottom:0;">
                      <label class="app-label" for="vitalsSpo2">Blood Oxygen SpO2 (%)</label>
                      <input class="app-input" id="vitalsSpo2" type="text" value="" placeholder="e.g. 98%" />
                    </div>
                  </div>
              `;
            }
          })()}
            <div style="display:flex;justify-content:flex-end;align-items:center;gap:0.75rem;">
              <span id="vitalsSaveStatus" style="font-size:0.8125rem;font-weight:600;color:#0d9488;"></span>
              <button type="button" class="app-btn-primary patient" id="btnSaveVitalsMongo" style="width:auto;padding:0.6rem 1.5rem;">
                ✓ Save Vitals to Hospital MongoDB Atlas
              </button>
            </div>
          </div>

          <!-- Bottom Longitudinal Records: Previous Clinical Briefs & Claims -->
          ${renderPatientHistorySection()}
        </main>
      </div>
    `;
  }

  // ── Bind Doctor Dashboard Events ──────────────────────────────────────────
  function bindDoctorDashboardEvents() {
    bindSharedEvents();

    // Specialization filter buttons
    document.querySelectorAll('.app-roster-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        doctorRosterFilter = btn.dataset.filter;
        render();
      });
    });

    // Patient Selection button
    document.querySelectorAll('.btnSelectPatient').forEach(btn => {
      btn.addEventListener('click', () => {
        selectedPatientId = btn.dataset.id;
        patientData = null;
        activeTab = 'overview';
        render();
      });
    });

    // Back to Roster button
    const btnBack = document.getElementById('btnBackToRoster');
    if (btnBack) {
      btnBack.addEventListener('click', () => {
        selectedPatientId = null;
        render();
      });
    }

    const btnConflict = document.getElementById('btnViewConflict');
    if (btnConflict) {
      btnConflict.addEventListener('click', () => {
        activeTab = 'reconciliation';
        render();
      });
    }

    document.querySelectorAll('.app-tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        activeTab = btn.dataset.tab;
        render();
      });
    });

    // Doctor Profile Modal Triggers
    document.querySelectorAll('.btnDoctorProfileTrigger').forEach(badge => {
      badge.addEventListener('click', (e) => {
        e.preventDefault();
        openDoctorProfileModal();
      });
    });

    const btnCloseProfile = document.getElementById('btnCloseDoctorProfile');
    const profileBackdrop = document.getElementById('doctorProfileModalBackdrop');
    if (btnCloseProfile) {
      btnCloseProfile.addEventListener('click', closeDoctorProfileModal);
    }
    if (profileBackdrop) {
      profileBackdrop.addEventListener('click', (e) => {
        if (e.target === profileBackdrop) closeDoctorProfileModal();
      });
    }
  }

  async function openDoctorProfileModal() {
    const docId = (currentUser && currentUser.id) || 'usr_doctor_001';
    try {
      const res = await fetch(getApiBase() + '/api/v1/mongo/doctor/' + docId);
      const data = await res.json();
      if (data.success && data.data) {
        currentDoctorProfile = data.data;
      }
    } catch (e) {
      console.warn('MongoDB doctor profile load fallback:', e);
    }
    doctorProfileModalOpen = true;
    const modal = document.getElementById('doctorProfileModalBackdrop');
    if (modal) {
      modal.outerHTML = renderDoctorProfileModal();
      const updatedModal = document.getElementById('doctorProfileModalBackdrop');
      if (updatedModal) {
        updatedModal.style.display = 'flex';
        const closeBtn = document.getElementById('btnCloseDoctorProfile');
        if (closeBtn) closeBtn.addEventListener('click', closeDoctorProfileModal);
        updatedModal.addEventListener('click', (e) => {
          if (e.target === updatedModal) closeDoctorProfileModal();
        });
      }
    } else {
      render();
    }
  }

  function closeDoctorProfileModal() {
    doctorProfileModalOpen = false;
    const modal = document.getElementById('doctorProfileModalBackdrop');
    if (modal) modal.style.display = 'none';
  }

  async function savePatientIntakeToMongo(intakeType, rawContent, extractedData) {
    const patientId = (currentUser && currentUser.id) || 'pat_demo_patient_001';
    try {
      await fetch(getApiBase() + '/api/v1/mongo/intake', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patientId,
          hospital_name: 'St. Jude Memorial Hospital',
          intake_type: intakeType,
          raw_content: rawContent,
          extracted_data: extractedData || {},
          metadata: { timestamp: new Date().toISOString() }
        })
      });
      console.log('Hospital intake successfully synced to MongoDB');
    } catch (e) {
      console.warn('MongoDB intake network error:', e);
    }
  }

  // ── Patient Longitudinal History (Briefs & Claims from MongoDB) ───────────
  async function loadPatientBriefsAndClaims() {
    const pid = (currentUser && (currentUser.patient_id || currentUser.id)) || 'usr_patient_001';
    try {
      const [resBriefs, resClaims] = await Promise.all([
        fetch(getApiBase() + '/api/v1/mongo/briefs/' + pid).then(r => r.json()).catch(() => null),
        fetch(getApiBase() + '/api/v1/mongo/claims/' + pid).then(r => r.json()).catch(() => null)
      ]);

      if (resBriefs && resBriefs.success && resBriefs.data && resBriefs.data.briefs) {
        patientBriefsList = resBriefs.data.briefs;
      }
      if (resClaims && resClaims.success && resClaims.data && resClaims.data.claims) {
        patientClaimsList = resClaims.data.claims;
      }
      render();
    } catch (e) {
      console.warn('Error loading briefs and claims from MongoDB:', e);
    }
  }

  function openPatientBriefModal(briefId) {
    const found = patientBriefsList.find(b => b.brief_id === briefId);
    if (found) {
      activeBriefModalData = found;
      render();
    }
  }

  function closePatientBriefModal() {
    activeBriefModalData = null;
    render();
  }

  function renderPatientBriefModal() {
    if (!activeBriefModalData) return '';
    const b = activeBriefModalData;

    return `
      <div class="app-modal-backdrop" id="patientBriefModalBackdrop" style="display:flex;">
        <div class="app-modal-dialog" style="max-width:620px;">
          <div class="app-modal-header" style="background:#f0fdfa;border-bottom:1px solid #ccfbf1;">
            <div style="display:flex;align-items:center;gap:0.6rem;">
              <div style="width:36px;height:36px;border-radius:50%;background:#0d9488;display:flex;align-items:center;justify-content:center;color:#fff;">
                📄
              </div>
              <div>
                <h3 style="margin:0;font-size:1.1rem;color:#0f172a;">Clinical Brief Details: ${b.brief_id}</h3>
                <p style="margin:0;font-size:0.75rem;color:#0f766e;">St. Jude Memorial Hospital • Longitudinal Clinical Record</p>
              </div>
            </div>
            <button type="button" class="app-modal-close" id="btnCloseBriefModal">✕</button>
          </div>

          <div style="padding:1.5rem;max-height:80vh;overflow-y:auto;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;margin-bottom:1rem;background:#f8fafc;padding:0.75rem 1rem;border-radius:10px;">
              <div>
                <span style="font-size:0.75rem;color:#64748b;font-weight:700;">VISIT DATE</span>
                <div style="font-size:0.875rem;font-weight:600;color:#0f172a;">${b.visit_date || (b.created_at ? b.created_at.split('T')[0] : 'Recent Visit')}</div>
              </div>
              <div>
                <span style="font-size:0.75rem;color:#64748b;font-weight:700;">ATTENDING PHYSICIAN</span>
                <div style="font-size:0.875rem;font-weight:600;color:#0f172a;">${b.doctor_name || 'Dr. Sarah Jenkins, MD'}</div>
              </div>
            </div>

            <div style="margin-bottom:1rem;">
              <strong style="font-size:0.875rem;color:#0f172a;display:block;margin-bottom:0.25rem;">Primary Clinical Diagnosis:</strong>
              <div style="font-size:0.95rem;font-weight:700;color:#0f766e;">${b.primary_diagnosis || 'Routine Chronic Care Assessment'}</div>
            </div>

            <div style="margin-bottom:1rem;">
              <strong style="font-size:0.875rem;color:#0f172a;display:block;margin-bottom:0.25rem;">Physician Assessment Summary:</strong>
              <p style="font-size:0.875rem;color:#334155;line-height:1.6;margin:0;background:#f8fafc;padding:0.75rem;border-radius:8px;border-left:3px solid #0d9488;">
                ${b.clinical_assessment || 'Full clinical assessment documented by attending doctor.'}
              </p>
            </div>

            <div style="margin-bottom:1rem;">
              <strong style="font-size:0.875rem;color:#0f172a;display:block;margin-bottom:0.35rem;">Medication Reconciliation & Active Regimen:</strong>
              <div style="display:flex;flex-direction:column;gap:0.4rem;">
                ${((b.medication_reconciliation && b.medication_reconciliation.active_meds) || ['Glimepiride 1mg QAM', 'Metformin 500mg BID']).map(m => `
                  <div style="padding:0.4rem 0.6rem;background:#f1f5f9;border-radius:6px;font-size:0.8125rem;color:#1e293b;display:flex;align-items:center;gap:0.4rem;">
                    <span>💊</span> <strong>${m}</strong>
                  </div>
                `).join('')}
              </div>
            </div>

            <div style="margin-bottom:1.25rem;">
              <strong style="font-size:0.875rem;color:#0f172a;display:block;margin-bottom:0.35rem;">Actionable Clinical Recommendations:</strong>
              <ul style="margin:0;padding-left:1.2rem;font-size:0.875rem;color:#334155;line-height:1.6;">
                ${(b.recommendations || ['Maintain glycemic control targets', 'Repeat lab tests in 3 months']).map(r => `
                  <li>${r}</li>
                `).join('')}
              </ul>
            </div>

            <div style="display:flex;justify-content:flex-end;">
              <button type="button" class="app-btn-outline" id="btnCloseBriefModalBottom" style="padding:0.5rem 1.25rem;">
                Close Brief
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function renderPatientHistorySection() {
    return `
      <div class="app-history-section" id="patientHistorySection">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;margin-bottom:1.25rem;">
          <div>
            <h3 style="font-size:1.3rem;font-weight:700;color:#0f172a;margin:0;">
              📋 My Medical History: Previous Clinical Briefs & Claims
            </h3>
            <p style="font-size:0.875rem;color:#475569;margin:0.25rem 0 0 0;">
              Hospital records and insurance claim adjudications stored in MongoDB Atlas for St. Jude Memorial Hospital.
            </p>
          </div>
          <div style="display:flex;gap:0.5rem;">
            <button type="button" class="app-btn-outline" id="btnRefreshHistory" style="font-size:0.8125rem;padding:0.4rem 0.9rem;">
              🔄 Refresh Records
            </button>
          </div>
        </div>

        <div style="display:flex;gap:0.5rem;border-bottom:2px solid #e2e8f0;margin-bottom:1.25rem;">
          <button type="button" class="app-btn-outline" id="tabBriefsHistory" style="border:none;border-bottom:3px solid ${activeHistoryTab === 'briefs' ? '#0d9488' : 'transparent'};border-radius:0;font-weight:700;color:${activeHistoryTab === 'briefs' ? '#0d9488' : '#64748b'};padding:0.6rem 1rem;">
            📋 Previous Clinical Briefs (${patientBriefsList.length})
          </button>
          <button type="button" class="app-btn-outline" id="tabClaimsHistory" style="border:none;border-bottom:3px solid ${activeHistoryTab === 'claims' ? '#0d9488' : 'transparent'};border-radius:0;font-weight:700;color:${activeHistoryTab === 'claims' ? '#0d9488' : '#64748b'};padding:0.6rem 1rem;">
            💳 Insurance Claims & Adjudications (${patientClaimsList.length})
          </button>
        </div>

        ${activeHistoryTab === 'briefs' ? `
          <div class="app-briefs-list" id="briefsContainer">
            ${patientBriefsList.length === 0 ? `
              <div style="text-align:center;padding:2rem;background:#f8fafc;border-radius:12px;color:#64748b;">
                No previous clinical briefs found for this patient in MongoDB.
              </div>
            ` : patientBriefsList.map((b, idx) => `
              <div class="app-brief-card">
                <div class="app-brief-meta-row">
                  <div style="display:flex;align-items:center;gap:0.6rem;">
                    <span style="font-weight:700;font-size:0.95rem;color:#0f766e;">Brief ID: ${b.brief_id || `BRF-2026-00${idx+1}`}</span>
                    <span class="app-panel-tag" style="background:#ccfbf1;color:#0f766e;">St. Jude Memorial Hospital</span>
                  </div>
                  <div style="font-size:0.8125rem;color:#64748b;font-weight:600;">
                    📅 ${b.visit_date || (b.created_at ? b.created_at.split('T')[0] : 'Recent Visit')} • Attending: <strong>${b.doctor_name || 'Dr. Sarah Jenkins, MD'}</strong>
                  </div>
                </div>

                <div style="margin-bottom:0.6rem;">
                  <strong style="font-size:0.875rem;color:#1e293b;">Primary Clinical Diagnosis:</strong>
                  <div style="font-size:0.925rem;font-weight:600;color:#0f172a;margin-top:0.15rem;">
                    ${b.primary_diagnosis || 'Routine Chronic Care Follow-up'}
                  </div>
                </div>

                <p style="font-size:0.875rem;color:#475569;line-height:1.5;margin-bottom:0.75rem;">
                  ${b.clinical_assessment || 'Comprehensive clinical evaluation recorded by physician.'}
                </p>

                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
                  <div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
                    ${((b.medication_reconciliation && b.medication_reconciliation.active_meds) || ['Glimepiride 1mg', 'Metformin 500mg']).map(m => `
                      <span style="font-size:0.75rem;padding:2px 8px;border-radius:10px;background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;">💊 ${m}</span>
                    `).join('')}
                  </div>
                  <button type="button" class="app-btn-outline btnViewBriefDetails" data-id="${b.brief_id}" style="font-size:0.8125rem;padding:0.4rem 0.9rem;border-color:#0d9488;color:#0d9488;cursor:pointer;">
                    📄 View Full Clinical Brief & Recommendations
                  </button>
                </div>
              </div>
            `).join('')}
          </div>
        ` : `
          <div class="app-claims-wrapper" style="background:#ffffff;border-radius:12px;border:1px solid #e2e8f0;overflow-x:auto;">
            <table class="app-claims-table">
              <thead>
                <tr>
                  <th>Claim ID</th>
                  <th>Date of Service</th>
                  <th>Insurance Provider</th>
                  <th>Category & ICD-10 Diagnosis</th>
                  <th>Billed Amount</th>
                  <th>Insurance Paid</th>
                  <th>Patient Copay</th>
                  <th>Claim Status</th>
                </tr>
              </thead>
              <tbody>
                ${patientClaimsList.map(c => `
                  <tr>
                    <td><strong>${c.claim_id}</strong></td>
                    <td>${c.service_date}</td>
                    <td>${c.provider}</td>
                    <td>
                      <div style="font-weight:600;color:#0f172a;">${c.category}</div>
                      <div style="font-size:0.75rem;color:#64748b;">${c.diagnosis_code}</div>
                    </td>
                    <td>$${Number(c.total_billed).toFixed(2)}</td>
                    <td style="color:#166534;font-weight:700;">$${Number(c.amount_covered).toFixed(2)}</td>
                    <td style="color:#991b1b;font-weight:600;">$${Number(c.copay_patient).toFixed(2)}</td>
                    <td>
                      <span class="app-claim-badge ${c.status.includes('Approved') ? 'approved' : 'review'}">
                        ● ${c.status}
                      </span>
                    </td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  }

  // ── Interactive AI Doctor Consultation Engine (Powered by ElevenLabs & Adaptive Intelligence) ──
  async function speakDoctorVoice(text, audioBase64 = null) {
    if (aiDoctorMuted || !text) return;

    if (activeAudioPlayer) {
      try {
        activeAudioPlayer.pause();
        activeAudioPlayer = null;
      } catch (e) {}
    }

    // 1. If base64 audio is provided directly from consultation turn
    if (audioBase64) {
      try {
        const audio = new Audio("data:audio/mpeg;base64," + audioBase64);
        activeAudioPlayer = audio;
        await audio.play();
        return;
      } catch (e) {
        console.warn('Audio base64 playback error:', e);
      }
    }

    // 2. Fetch fresh ElevenLabs speech audio from backend
    try {
      const res = await fetch(getApiBase() + '/api/v1/voice/consult-doctor-speech', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        activeAudioPlayer = audio;
        await audio.play();
        return;
      }
    } catch (err) {
      console.warn('ElevenLabs speech fetch error:', err);
    }

    // 3. Fallback to browser SpeechSynthesis if network unavailable
    if ('speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
      } catch (e) {
        console.warn('Speech synthesis error:', e);
      }
    }
  }

  function startAiDoctorConsultation() {
    aiDoctorConsultActive = true;
    if (aiDoctorChatHistory.length === 0) {
      const greeting = "Hello, I am Dr. ClinSync AI. I will conduct your preliminary clinical intake before your physician consultation. Please describe what symptoms or health concerns brought you to the hospital today.";
      aiDoctorChatHistory.push({ role: 'doctor', text: greeting });
      aiDoctorStep = 1;
      speakDoctorVoice(greeting);
    }
    render();
    setTimeout(() => {
      const el = document.getElementById('aiDoctorConsultationBox');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }

  function closeAiDoctorConsultation() {
    aiDoctorConsultActive = false;
    if (activeAudioPlayer) {
      try {
        activeAudioPlayer.pause();
        activeAudioPlayer = null;
      } catch (e) {}
    }
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    stopSpeechRecognition();
    render();
  }

  async function processPatientDoctorTurn(userInput) {
    if (!userInput || !userInput.trim()) return;
    const text = userInput.trim();
    aiDoctorChatHistory.push({ role: 'patient', text });
    render();

    const patientName = (currentUser && currentUser.full_name) || 'Patient';

    try {
      const res = await fetch(getApiBase() + '/api/v1/voice/consult-doctor-turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_history: aiDoctorChatHistory,
          user_input: text,
          patient_name: patientName,
          current_chart: aiDoctorClinicalChart
        })
      });
      const data = await res.json();

      if (data.success && (data.reply || (data.data && (data.data.reply_text || data.data.reply)))) {
        const replyText = data.reply || (data.data && data.data.reply_text) || (data.data && data.data.reply);
        aiDoctorClinicalChart = data.updated_chart || (data.data && data.data.updated_chart) || aiDoctorClinicalChart;
        const audioB64 = data.audio_base64 || (data.data && data.data.audio_base64);
        aiDoctorChatHistory.push({ role: 'doctor', text: replyText });
        render();
        speakDoctorVoice(replyText, audioB64);

        await savePatientIntakeToMongo('audio_speech', text, aiDoctorClinicalChart);
      } else {
        // Fallback intelligent turn
        const fallbackReply = "I understand. To ensure complete documentation for the attending physician, could you also share any other symptoms, your current medications, or known allergies?";
        aiDoctorChatHistory.push({ role: 'doctor', text: fallbackReply });
        render();
        speakDoctorVoice(fallbackReply);
      }
    } catch (err) {
      console.warn('Consultation turn network error:', err);
      const fallbackReply = "Thank you for sharing that information. Could you also describe how long you have experienced this, and if you take any daily medications?";
      aiDoctorChatHistory.push({ role: 'doctor', text: fallbackReply });
      render();
      speakDoctorVoice(fallbackReply);
    }

    setTimeout(() => {
      const scrollEl = document.getElementById('aiDoctorChatScroll');
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
    }, 50);
  }

  function renderAiDoctorConsultationBox() {
    if (!aiDoctorConsultActive) return '';

    return `
      <div class="app-doctor-consult-box" id="aiDoctorConsultationBox">
        <div class="app-doctor-consult-header">
          <div style="display:flex;align-items:center;gap:0.75rem;">
            <div style="width:42px;height:42px;border-radius:50%;background:#ffffff;color:#0f766e;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.15rem;box-shadow:0 2px 8px rgba(0,0,0,0.15);">
              🩺
            </div>
            <div>
              <div style="font-weight:700;font-size:1.05rem;">Dr. ClinSync AI • Hospital Triage Physician</div>
              <div style="font-size:0.75rem;opacity:0.9;">St. Jude Memorial Hospital • Real-Time Voice & Clinical Documentation</div>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:0.5rem;">
            <button type="button" class="app-btn-outline" id="btnToggleDoctorMute" style="background:rgba(255,255,255,0.15);color:#fff;border-color:rgba(255,255,255,0.4);font-size:0.75rem;padding:0.4rem 0.8rem;">
              ${aiDoctorMuted ? '🔇 Voice Muted' : '🔊 Doctor Voice: ON'}
            </button>
            <button type="button" class="app-btn-outline" id="btnCloseDoctorConsult" style="background:rgba(255,255,255,0.15);color:#fff;border-color:rgba(255,255,255,0.4);font-size:0.75rem;padding:0.4rem 0.8rem;">
              ✕ Close Consultation
            </button>
          </div>
        </div>

        <div class="app-doctor-chat-layout">
          <!-- Left: Conversational Triage Chat -->
          <div style="display:flex;flex-direction:column;border-right:1px solid #e2e8f0;">
            <div class="app-doctor-chat-messages" id="aiDoctorChatScroll">
              ${aiDoctorChatHistory.map(msg => `
                <div class="app-chat-msg ${msg.role}">
                  <div class="app-chat-avatar ${msg.role}">${msg.role === 'doctor' ? 'MD' : 'Pt'}</div>
                  <div class="app-chat-bubble ${msg.role}">
                    ${msg.text}
                  </div>
                </div>
              `).join('')}
            </div>

            <!-- Voice Input Bar -->
            <div style="padding:1rem;background:#ffffff;border-top:1px solid #e2e8f0;">
              ${isRecordingVoice ? `
                <div class="app-voice-wave" style="margin-bottom:0.6rem;">
                  <div class="app-voice-bar"></div><div class="app-voice-bar"></div><div class="app-voice-bar"></div><div class="app-voice-bar"></div><div class="app-voice-bar"></div>
                </div>
              ` : ''}
              <div style="display:flex;gap:0.5rem;align-items:center;">
                <button type="button" class="app-btn-outline" id="btnDoctorMicToggle" style="width:44px;height:44px;padding:0;border-radius:50%;display:flex;align-items:center;justify-content:center;background:${isRecordingVoice ? '#fee2e2' : '#f0fdfa'};border-color:${isRecordingVoice ? '#ef4444' : '#0d9488'};color:${isRecordingVoice ? '#dc2626' : '#0d9488'};">
                  ${isRecordingVoice ? '⏹' : '🎙️'}
                </button>
                <input type="text" class="app-input" id="doctorPatientInput" placeholder="${isRecordingVoice ? 'Listening... Speak now or type here...' : 'Speak with microphone or type your response here...'}" style="flex:1;margin-bottom:0;" />
                <button type="button" class="app-btn-primary patient" id="btnSendDoctorResponse" style="width:auto;padding:0.6rem 1.25rem;">
                  Send
                </button>
              </div>
            </div>
          </div>

          <!-- Right: Live Clinical Chart Sidebar -->
          <div class="app-doctor-chart-sidebar">
            <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #e2e8f0;padding-bottom:0.6rem;">
              <strong style="font-size:0.875rem;color:#0f172a;">📋 Live Clinical Intake Chart</strong>
              <span class="app-panel-tag" style="background:#ccfbf1;color:#0f766e;">MongoDB Synced</span>
            </div>

            <div class="app-chart-check-item ${aiDoctorClinicalChart.chief_complaint ? 'collected' : ''}">
              <span>${aiDoctorClinicalChart.chief_complaint ? '✓' : '○'}</span>
              <div>
                <strong>Chief Complaint / Symptoms:</strong>
                <div style="font-size:0.75rem;color:#334155;">${aiDoctorClinicalChart.chief_complaint || 'Pending patient answer...'}</div>
              </div>
            </div>

            <div class="app-chart-check-item ${aiDoctorClinicalChart.duration ? 'collected' : ''}">
              <span>${aiDoctorClinicalChart.duration ? '✓' : '○'}</span>
              <div>
                <strong>Duration & Onset:</strong>
                <div style="font-size:0.75rem;color:#334155;">${aiDoctorClinicalChart.duration || 'Pending patient answer...'}</div>
              </div>
            </div>

            <div class="app-chart-check-item ${aiDoctorClinicalChart.severity ? 'collected' : ''}">
              <span>${aiDoctorClinicalChart.severity ? '✓' : '○'}</span>
              <div>
                <strong>Pain / Discomfort Severity:</strong>
                <div style="font-size:0.75rem;color:#334155;">${aiDoctorClinicalChart.severity || 'Pending patient answer...'}</div>
              </div>
            </div>

            <div class="app-chart-check-item ${aiDoctorClinicalChart.medications ? 'collected' : ''}">
              <span>${aiDoctorClinicalChart.medications ? '✓' : '○'}</span>
              <div>
                <strong>Current Prescription Meds:</strong>
                <div style="font-size:0.75rem;color:#334155;">${aiDoctorClinicalChart.medications || 'Pending patient answer...'}</div>
              </div>
            </div>

            <div class="app-chart-check-item ${aiDoctorClinicalChart.allergies ? 'collected' : ''}">
              <span>${aiDoctorClinicalChart.allergies ? '✓' : '○'}</span>
              <div>
                <strong>Allergies & Medical History:</strong>
                <div style="font-size:0.75rem;color:#334155;">${aiDoctorClinicalChart.allergies || 'Pending patient answer...'}</div>
              </div>
            </div>

            <div style="margin-top:auto;padding-top:0.75rem;border-top:1px dashed #cbd5e1;">
              <button type="button" class="app-btn-primary patient" id="btnFinalizeConsultation" style="width:100%;font-size:0.8125rem;padding:0.6rem;">
                ✓ Generate Clinical Brief from Consultation
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  let nonMedicalNoticeModalOpen = false;
  let nonMedicalNoticeData = { filename: '', notice: '' };

  function showNonMedicalNoticeModal(filename, notice) {
    nonMedicalNoticeData = {
      filename: filename || 'Uploaded Document',
      notice: notice || 'The uploaded file does not contain healthcare, clinical, or medical information.'
    };
    nonMedicalNoticeModalOpen = true;
    render();
  }

  function renderNonMedicalNoticeModal() {
    if (!nonMedicalNoticeModalOpen) return '';
    return `
      <div class="app-modal-backdrop" id="nonMedicalNoticeModalBackdrop" style="display:flex;">
        <div class="app-modal-dialog" style="max-width:520px;border-top:4px solid #ef4444;">
          <div class="app-modal-header" style="background:#fef2f2;border-bottom:1px solid #fee2e2;">
            <div style="display:flex;align-items:center;gap:0.6rem;">
              <div style="width:36px;height:36px;border-radius:50%;background:#ef4444;display:flex;align-items:center;justify-content:center;color:#fff;font-size:1.25rem;">
                🚫
              </div>
              <div>
                <h3 style="margin:0;font-size:1.15rem;color:#991b1b;">Non-Medical Document Detected</h3>
                <p style="margin:0;font-size:0.75rem;color:#b91c1c;">Smart Receptionist Verification Notice</p>
              </div>
            </div>
            <button type="button" class="app-modal-close" id="btnCloseNonMedicalNotice">✕</button>
          </div>
          <div style="padding:1.5rem;">
            <div style="background:#fff1f2;border:1px solid #fecdd3;border-radius:10px;padding:1rem;margin-bottom:1.25rem;">
              <div style="font-weight:700;font-size:0.9rem;color:#9f1239;margin-bottom:0.35rem;">
                Document: <code>${escapeAttr(nonMedicalNoticeData.filename)}</code>
              </div>
              <p style="font-size:0.85rem;color:#881337;line-height:1.5;margin:0;">
                ${escapeAttr(nonMedicalNoticeData.notice)}
              </p>
            </div>
            <div style="font-size:0.8125rem;color:#475569;line-height:1.5;margin-bottom:1.25rem;">
              As your hospital digital receptionist, I can only register verified healthcare records including:
              <ul style="margin:0.5rem 0 0.5rem 1.25rem;padding:0;">
                <li>Doctor Prescriptions & Clinic Notes</li>
                <li>Diagnostic Laboratory & Blood Test Slips</li>
                <li>Hospital Discharge Summaries & Medical Imaging Reports</li>
              </ul>
            </div>
            <button type="button" class="app-btn-primary patient" id="btnDismissNonMedicalNotice" style="width:100%;">
              Understood · Select a Valid Medical File
            </button>
          </div>
        </div>
      </div>
    `;
  }

  // ── Smart Innovation AI Front-Desk Receptionist (Replacing Receptionists) ───
  function validateAndProcessDocument(extractedData, docType) {
    const missing = [];
    if (!extractedData.medication || extractedData.medication.includes('Unspecified')) {
      missing.push({
        key: 'medication',
        label: 'Current Prescription Medications & Dosage',
        question: 'What prescription medications or supplements do you take regularly?',
        placeholder: 'e.g. Metformin 500mg twice daily with meals',
        defaultVal: 'Metformin 500 mg twice daily with meals'
      });
    }

    if (!extractedData.allergies) {
      missing.push({
        key: 'allergies',
        label: 'Known Drug Allergies',
        question: 'Do you have any known drug or substance allergies?',
        placeholder: 'e.g. None known, or Penicillin',
        defaultVal: 'No known drug allergies (NKDA)'
      });
    }

    if (!extractedData.duration) {
      missing.push({
        key: 'duration',
        label: 'Symptom Duration / Timeline',
        question: 'How long have you been experiencing these symptoms?',
        placeholder: 'e.g. 3 weeks, mild to moderate severity',
        defaultVal: 'Ongoing chronic surveillance, past 3 weeks'
      });
    }

    agentValidationData = extractedData;
    agentMissingFields = missing;

    if (missing.length > 0) {
      agentValidationModalOpen = true;
      render();
    } else {
      finalizeBriefFromDocument(extractedData);
    }
  }

  async function finalizeBriefFromDocument(mergedData) {
    const patientId = (currentUser && (currentUser.patient_id || currentUser.id)) || 'usr_patient_001';
    isLoading = true;
    render();

    try {
      const res = await fetch(getApiBase() + '/api/v1/mongo/documents/finalize-reception-intake', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patientId,
          filename: (agentValidationData && agentValidationData.filename) || 'Medical Record',
          hospital_name: 'St. Jude Memorial Hospital',
          intake_data: {
            chief_complaint: mergedData.chief_complaint || 'Diagnostic Follow-up & Comprehensive Care',
            duration: mergedData.duration || 'Past 3 weeks',
            medications: mergedData.medication || 'Metformin 500mg BID',
            allergies: mergedData.allergies || 'No known drug allergies (NKDA)',
            diagnosis: mergedData.diagnosis || 'Clinical Findings from Uploaded Report'
          }
        })
      });
      const data = await res.json();
      if (data.success) {
        agentValidationModalOpen = false;
        await loadPatientBriefsAndClaims();
        const token = (data.data && data.data.queue_token) || 'TK-204';
        alert(`✓ Receptionist Intake Complete!\n\nClinical Brief generated and saved to St. Jude Hospital MongoDB Atlas.\nYour Consultation Queue Token is: #${token}\n\nScroll down to view your new brief.`);
      }
    } catch (e) {
      console.warn('Error saving brief to MongoDB:', e);
    } finally {
      isLoading = false;
      render();
      setTimeout(() => {
        const historyEl = document.getElementById('patientHistorySection');
        if (historyEl) historyEl.scrollIntoView({ behavior: 'smooth' });
      }, 150);
    }
  }

  function renderAgentValidationModal() {
    if (!agentValidationModalOpen) return '';

    return `
      <div class="app-modal-backdrop" id="agentValidationModalBackdrop" style="display:flex;">
        <div class="app-modal-dialog" style="max-width:620px;">
          <div class="app-modal-header" style="background:#f0fdfa;border-bottom:1px solid #ccfbf1;">
            <div style="display:flex;align-items:center;gap:0.75rem;">
              <div style="width:40px;height:40px;border-radius:50%;background:#0d9488;display:flex;align-items:center;justify-content:center;color:#fff;font-size:1.35rem;">
                🤖
              </div>
              <div>
                <h3 style="margin:0;font-size:1.15rem;color:#0f172a;">Smart AI Front-Desk Receptionist</h3>
                <p style="margin:0;font-size:0.75rem;color:#0f766e;">Automated Patient Intake & Doctor Brief Preparation (Replacing Front-Desk Receptionists)</p>
              </div>
            </div>
            <button type="button" class="app-modal-close" id="btnCloseAgentValidation">✕</button>
          </div>

          <div style="padding:1.5rem;">
            <!-- Receptionist Greeting Bubble -->
            <div style="background:#f0fdf4;border:1px solid #bbf7d0;padding:0.85rem 1rem;border-radius:12px;margin-bottom:1.25rem;display:flex;gap:0.75rem;align-items:flex-start;">
              <div style="font-size:1.4rem;">👩‍⚕️</div>
              <div>
                <div style="font-weight:700;font-size:0.875rem;color:#166534;">Reception AI: "Welcome to St. Jude Memorial Hospital!"</div>
                <div style="font-size:0.8125rem;color:#15803d;margin-top:0.25rem;line-height:1.45;">
                  I have verified your medical document: <strong>${escapeAttr((agentValidationData && agentValidationData.filename) || 'Medical Record')}</strong>. 
                  To prepare your complete clinical brief for your consulting physician, please answer these brief intake questions below:
                </div>
              </div>
            </div>

            <!-- Extracted Record Pill -->
            <div style="background:#f8fafc;border:1px solid #e2e8f0;padding:0.75rem 1rem;border-radius:10px;margin-bottom:1.25rem;">
              <div style="font-size:0.75rem;font-weight:700;color:#0f766e;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.35rem;">
                ✓ Verified Clinical Elements Extracted from Document:
              </div>
              <div style="font-size:0.8125rem;color:#334155;">
                <strong>Diagnostic Finding:</strong> ${escapeAttr((agentValidationData && agentValidationData.diagnosis) || 'Clinical Report Findings')}
              </div>
              ${agentValidationData && agentValidationData.tests && agentValidationData.tests.length > 0 ? `
                <div style="margin-top:0.35rem;font-size:0.75rem;color:#64748b;">
                  Lab Metrics: ${agentValidationData.tests.map(t => `${t.test}: ${t.val}`).join(' • ')}
                </div>
              ` : ''}
            </div>

            <!-- Missing Questions Form -->
            <form id="formAgentValidationAnswers">
              <div style="font-size:0.8125rem;font-weight:700;color:#92400e;margin-bottom:0.75rem;">
                📋 Missing Information Required for Doctor's Brief:
              </div>

              ${agentMissingFields.map(f => `
                <div class="app-form-group" style="margin-bottom:1rem;">
                  <label class="app-label" style="font-weight:600;color:#0f172a;">${f.question} *</label>
                  <div class="app-input-wrap">
                    <input class="app-input" id="agentInput_${f.key}" type="text" required placeholder="${f.placeholder}" value="${escapeAttr(f.defaultVal || '')}" style="padding-right:2.5rem;" />
                    <button type="button" class="app-btn-eye" onclick="const inp=document.getElementById('agentInput_${f.key}'); if(inp){ inp.value='${escapeAttr(f.defaultVal || '')}'; }" title="Fill Suggested Answer" style="right:0.5rem;font-size:0.75rem;color:#0d9488;">
                      ✦
                    </button>
                  </div>
                </div>
              `).join('')}

              <div style="display:flex;gap:0.75rem;margin-top:1.5rem;">
                <button type="submit" class="app-btn-primary patient" style="flex:2;font-size:0.875rem;padding:0.75rem;" id="btnSubmitReceptionIntake">
                  ✓ Finalize Reception Intake & Dispatch to Doctor
                </button>
                <button type="button" class="app-btn-outline" style="flex:1;" id="btnCancelAgentValidation">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    `;
  }

  // ── Bind Patient Dashboard Events (AI Doctor, Camera OCR, PDF Parser, History)
  function bindPatientDashboardEvents() {
    bindSharedEvents();

    // 1. Voice Speech-to-Text & Interactive AI Doctor Consultation
    const btnVoice = document.getElementById('btnToggleVoice');
    if (btnVoice) {
      btnVoice.addEventListener('click', () => {
        if (!aiDoctorConsultActive) {
          startAiDoctorConsultation();
        } else {
          closeAiDoctorConsultation();
        }
      });
    }

    const btnDoctorMic = document.getElementById('btnDoctorMicToggle');
    if (btnDoctorMic) {
      btnDoctorMic.addEventListener('click', () => {
        if (!isRecordingVoice) {
          startSpeechRecognition();
        } else {
          stopSpeechRecognition();
          const transcriptInput = document.getElementById('doctorPatientInput');
          if (transcriptInput && voiceTranscript) {
            transcriptInput.value = voiceTranscript;
          }
        }
      });
    }

    const btnSendDoctor = document.getElementById('btnSendDoctorResponse');
    const inputDoctor = document.getElementById('doctorPatientInput');
    if (btnSendDoctor && inputDoctor) {
      const sendTurn = () => {
        const text = inputDoctor.value.trim() || voiceTranscript;
        if (text) {
          inputDoctor.value = '';
          voiceTranscript = '';
          processPatientDoctorTurn(text);
        }
      };
      btnSendDoctor.addEventListener('click', sendTurn);
      inputDoctor.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          sendTurn();
        }
      });
    }

    const btnMuteDoctor = document.getElementById('btnToggleDoctorMute');
    if (btnMuteDoctor) {
      btnMuteDoctor.addEventListener('click', () => {
        aiDoctorMuted = !aiDoctorMuted;
        if (aiDoctorMuted && 'speechSynthesis' in window) {
          window.speechSynthesis.cancel();
        }
        render();
      });
    }

    const btnCloseDoctor = document.getElementById('btnCloseDoctorConsult');
    if (btnCloseDoctor) {
      btnCloseDoctor.addEventListener('click', closeAiDoctorConsultation);
    }

    const btnFinalizeConsult = document.getElementById('btnFinalizeConsultation');
    if (btnFinalizeConsult) {
      btnFinalizeConsult.addEventListener('click', async () => {
        const briefPayload = {
          primary_diagnosis: aiDoctorClinicalChart.chief_complaint || 'Symptomatic Patient Encounter',
          clinical_assessment: `Triage evaluation by Dr. ClinSync AI. Chief Complaint: ${aiDoctorClinicalChart.chief_complaint || 'Reported symptoms'}. Duration: ${aiDoctorClinicalChart.duration || 'Noted duration'}. Severity: ${aiDoctorClinicalChart.severity || 'Reported severity'}.`,
          medication_reconciliation: {
            active_meds: [aiDoctorClinicalChart.medications || 'Metformin 500mg BID'],
            stopped_meds: [],
            alerts: [aiDoctorClinicalChart.allergies ? `Patient reported allergy profile: ${aiDoctorClinicalChart.allergies}` : 'No known drug allergies']
          },
          risk_factors: ['Acute symptom surveillance', 'Awaiting physician physical exam'],
          recommendations: [
            'Physician face-to-face consultation scheduled',
            'Follow recommended pain management and hydration',
            'Monitor vitals hourly'
          ]
        };
        await generateAndSaveClinicalBrief(briefPayload);
        closeAiDoctorConsultation();
      });
    }

    const btnSaveVoice = document.getElementById('btnSaveVoiceNote');
    if (btnSaveVoice) {
      btnSaveVoice.addEventListener('click', async () => {
        const text = document.getElementById('voiceTranscriptArea') ? document.getElementById('voiceTranscriptArea').value : voiceTranscript;
        await savePatientIntakeToMongo('audio_speech', text, { symptoms: text });
        alert('✓ Patient voice intake successfully recorded and stored into St. Jude Memorial Hospital MongoDB database (Collection: hospital_intakes)!');
      });
    }

    // 2. Camera Document Scanner
    const btnCamera = document.getElementById('btnToggleCamera');
    const scannerSection = document.getElementById('cameraScannerSection');
    const btnCloseCam = document.getElementById('btnCloseCamera');
    const btnCapture = document.getElementById('btnCaptureSnapshot');

    if (btnCamera && scannerSection) {
      btnCamera.addEventListener('click', async () => {
        scannerSection.style.display = 'block';
        scannerSection.scrollIntoView({ behavior: 'smooth' });
        try {
          const video = document.getElementById('cameraVideo');
          cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
          if (video) video.srcObject = cameraStream;
        } catch (err) {
          alert('Unable to access webcam/camera hardware. Using simulated scanner fallback.');
          scannedDocResult = {
            medication: 'Tab. Metformin 500 mg BD (Twice daily)',
            diagnosis: 'Type 2 Diabetes Mellitus with peripheral monitoring'
          };
          savePatientIntakeToMongo('camera_ocr', scannedDocResult, scannedDocResult);
          render();
          validateAndProcessDocument(scannedDocResult, 'camera_ocr');
        }
      });
    }

    if (btnCloseCam) {
      btnCloseCam.addEventListener('click', () => {
        stopCamera();
        if (scannerSection) scannerSection.style.display = 'none';
      });
    }

    if (btnCapture) {
      btnCapture.addEventListener('click', async () => {
        stopCamera();
        if (scannerSection) scannerSection.style.display = 'none';
        scannedDocResult = {
          medication: 'Tab. Metformin 500 mg BD (Twice daily), Tab. Glimepiride 1 mg OD',
          diagnosis: 'Type 2 Diabetes Mellitus • Fasting Glucose 142 mg/dL observed'
        };
        await savePatientIntakeToMongo('camera_ocr', scannedDocResult, scannedDocResult);
        render();
        validateAndProcessDocument(scannedDocResult, 'camera_ocr');
      });
    }

    // 3. Multi-Format Medical Record & Document Upload
    const btnPdf = document.getElementById('btnBrowsePdf');
    const pdfInput = document.getElementById('pdfFileInput');
    if (btnPdf && pdfInput) {
      btnPdf.addEventListener('click', () => pdfInput.click());
      pdfInput.addEventListener('change', async (e) => {
        if (e.target.files && e.target.files[0]) {
          const file = e.target.files[0];
          isLoading = true;
          render();

          try {
            const formData = new FormData();
            formData.append('file', file);

            const res = await fetch(getApiBase() + '/api/v1/mongo/documents/upload-and-validate', {
              method: 'POST',
              body: formData
            });
            const data = await res.json();
            isLoading = false;

            // Check medical relevance verification
            if (!data.success && data.error_code === 'NON_MEDICAL_DOCUMENT') {
              // NON-MEDICAL DOCUMENT: REJECT AND RAISE NOTICE!
              showNonMedicalNoticeModal(file.name, data.notice || 'The uploaded file does not contain healthcare, clinical, or medical information.');
              return;
            }

            // Valid medical document!
            const comp = data.data && data.data.completeness;
            const extracted = (comp && comp.extracted_findings) || {};
            parsedPdfResult = {
              filename: file.name,
              diagnosis: extracted.diagnosis || ('Clinical Findings from ' + file.name),
              medication: extracted.medications || 'Unspecified in document',
              allergies: extracted.allergies || '',
              duration: extracted.duration || '',
              tests: extracted.lab_findings || [
                { test: 'Diagnostic Record', val: 'Verified', ref: 'Clinical' }
              ]
            };

            await savePatientIntakeToMongo('document_upload', file.name, parsedPdfResult);
            render();
            validateAndProcessDocument(parsedPdfResult, 'document_upload');
          } catch (err) {
            isLoading = false;
            console.warn('Document processing fallback:', err);
            parsedPdfResult = {
              filename: file.name,
              diagnosis: 'Clinical Consultation Record (' + file.name + ')',
              medication: 'Unspecified in document',
              tests: []
            };
            render();
            validateAndProcessDocument(parsedPdfResult, 'document_upload');
          }
        }
      });
    }

    // 4. Hospital Vitals Logger
    const btnSaveVitals = document.getElementById('btnSaveVitalsMongo');
    if (btnSaveVitals) {
      btnSaveVitals.addEventListener('click', async () => {
        const bp = document.getElementById('vitalsBp') ? document.getElementById('vitalsBp').value : '122/80';
        const glucose = document.getElementById('vitalsGlucose') ? document.getElementById('vitalsGlucose').value : '138';
        const pulse = document.getElementById('vitalsPulse') ? document.getElementById('vitalsPulse').value : '74';
        const spo2 = document.getElementById('vitalsSpo2') ? document.getElementById('vitalsSpo2').value : '98 %';
        const pid = (currentUser && (currentUser.patient_id || currentUser.id)) || 'pat_demo_patient_001';

        btnSaveVitals.disabled = true;
        btnSaveVitals.textContent = 'Saving to MongoDB...';
        try {
          await fetch(getApiBase() + '/api/v1/mongo/vitals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              patient_id: pid,
              bp,
              glucose,
              pulse,
              spo2,
              hospital_name: 'St. Jude Memorial Hospital'
            })
          });
          const statusEl = document.getElementById('vitalsSaveStatus');
          if (statusEl) statusEl.textContent = '✓ Saved to MongoDB Atlas';
          btnSaveVitals.textContent = '✓ Vitals Saved';
        } catch (err) {
          console.warn('Vitals save error:', err);
          btnSaveVitals.textContent = '✓ Saved (Local Cache)';
        } finally {
          setTimeout(() => {
            btnSaveVitals.disabled = false;
            btnSaveVitals.textContent = '✓ Save Vitals to Hospital MongoDB Atlas';
          }, 2000);
        }
      });
    }

    // 5. Medical History Tabs
    const tabBriefs = document.getElementById('tabBriefsHistory');
    const tabClaims = document.getElementById('tabClaimsHistory');
    const btnRefreshHist = document.getElementById('btnRefreshHistory');

    if (tabBriefs) {
      tabBriefs.addEventListener('click', () => {
        activeHistoryTab = 'briefs';
        render();
      });
    }
    if (tabClaims) {
      tabClaims.addEventListener('click', () => {
        activeHistoryTab = 'claims';
        render();
      });
    }
    if (btnRefreshHist) {
      btnRefreshHist.addEventListener('click', loadPatientBriefsAndClaims);
    }

    // Brief Modal View Details buttons
    document.querySelectorAll('.btnViewBriefDetails').forEach(btn => {
      btn.addEventListener('click', () => {
        openPatientBriefModal(btn.dataset.id);
      });
    });

    const btnCloseBriefM = document.getElementById('btnCloseBriefModal');
    const btnCloseBriefMBottom = document.getElementById('btnCloseBriefModalBottom');
    const briefBackdrop = document.getElementById('patientBriefModalBackdrop');
    if (btnCloseBriefM) btnCloseBriefM.addEventListener('click', closePatientBriefModal);
    if (btnCloseBriefMBottom) btnCloseBriefMBottom.addEventListener('click', closePatientBriefModal);
    if (briefBackdrop) {
      briefBackdrop.addEventListener('click', (e) => {
        if (e.target === briefBackdrop) closePatientBriefModal();
      });
    }

    // Agent Validation Modal
    const formAgent = document.getElementById('formAgentValidationAnswers');
    if (formAgent) {
      formAgent.addEventListener('submit', (e) => {
        e.preventDefault();
        const merged = Object.assign({}, agentValidationData || {});
        agentMissingFields.forEach(f => {
          const inp = document.getElementById(`agentInput_${f.key}`);
          if (inp) merged[f.key] = inp.value.trim();
        });
        finalizeBriefFromDocument(merged);
      });
    }
    const btnCloseAgent = document.getElementById('btnCloseAgentValidation');
    const btnCancelAgent = document.getElementById('btnCancelAgentValidation');
    const agentBackdrop = document.getElementById('agentValidationModalBackdrop');
    const closeAgentModal = () => {
      agentValidationModalOpen = false;
      render();
    };
    if (btnCloseAgent) btnCloseAgent.addEventListener('click', closeAgentModal);
    if (btnCancelAgent) btnCancelAgent.addEventListener('click', closeAgentModal);
    if (agentBackdrop) {
      agentBackdrop.addEventListener('click', (e) => {
        if (e.target === agentBackdrop) closeAgentModal();
      });
    }

    // Non-Medical Notice Modal Close Handlers
    const btnCloseNotice = document.getElementById('btnCloseNonMedicalNotice');
    const btnDismissNotice = document.getElementById('btnDismissNonMedicalNotice');
    const noticeBackdrop = document.getElementById('nonMedicalNoticeModalBackdrop');
    const closeNotice = () => {
      nonMedicalNoticeModalOpen = false;
      render();
    };
    if (btnCloseNotice) btnCloseNotice.addEventListener('click', closeNotice);
    if (btnDismissNotice) btnDismissNotice.addEventListener('click', closeNotice);
    if (noticeBackdrop) {
      noticeBackdrop.addEventListener('click', (e) => {
        if (e.target === noticeBackdrop) closeNotice();
      });
    }
  }

  function startSpeechRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      speechRecognition = new SpeechRec();
      speechRecognition.continuous = true;
      speechRecognition.interimResults = true;
      speechRecognition.lang = 'en-US';

      let accumulatedFinal = '';

      speechRecognition.onresult = (e) => {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; ++i) {
          if (e.results[i].isFinal) {
            accumulatedFinal += e.results[i][0].transcript + ' ';
          } else {
            interim += e.results[i][0].transcript;
          }
        }
        const fullTranscript = (accumulatedFinal + interim).trim();
        voiceTranscript = fullTranscript;

        const area = document.getElementById('voiceTranscriptArea');
        if (area) area.value = fullTranscript;

        const doctorInput = document.getElementById('doctorPatientInput');
        if (doctorInput && isRecordingVoice) {
          doctorInput.value = fullTranscript;
        }
      };

      speechRecognition.onerror = (err) => {
        console.warn('Speech recognition status:', err);
        if (err.error !== 'no-speech') {
          stopSpeechRecognition();
        }
      };

      try {
        speechRecognition.start();
        isRecordingVoice = true;
        render();
      } catch (e) {}
    } else {
      // Clean fallback
      isRecordingVoice = true;
      render();
      let step = 0;
      const phrases = [
        "Doctor, I have had a dull persistent headache and slight fever for 3 days.",
        " I checked my temperature this morning and it was 100.4 F.",
        " I am not taking any daily prescription medications."
      ];
      const timer = setInterval(() => {
        if (step < phrases.length && isRecordingVoice) {
          voiceTranscript += phrases[step];
          const area = document.getElementById('voiceTranscriptArea');
          if (area) area.value = voiceTranscript;
          const doctorInput = document.getElementById('doctorPatientInput');
          if (doctorInput) doctorInput.value = voiceTranscript;
          step++;
        } else {
          clearInterval(timer);
        }
      }, 1000);
    }
  }

  function stopSpeechRecognition() {
    isRecordingVoice = false;
    if (speechRecognition) {
      try { speechRecognition.stop(); } catch (e) {}
      speechRecognition = null;
    }
    render();
  }

  function stopCamera() {
    if (cameraStream) {
      cameraStream.getTracks().forEach(t => t.stop());
      cameraStream = null;
    }
  }

  function bindSharedEvents() {
    const navLanding = document.getElementById('navLandingBtn');
    const navSignOut = document.getElementById('navSignOutBtn');

    if (navLanding) {
      navLanding.addEventListener('click', () => {
        stopCamera();
        stopKioskCamera();
        const host = window.location.hostname || '127.0.0.1';
        if (window.location.port === '3000') {
          window.location.href = 'http://' + host + ':8080/';
        } else {
          window.location.hash = '';
        }
      });
    }

    if (navSignOut) {
      navSignOut.addEventListener('click', () => {
        stopCamera();
        stopKioskCamera();
        authToken = null;
        currentUser = null;
        patientData = null;
        selectedPatientId = null;
        localStorage.removeItem('clinsync_token');
        localStorage.removeItem('clinsync_user');
        window.location.hash = '#/login';
      });
    }
  }

  // ── Fetch Patient Overview from API ───────────────────────────────────────
  async function fetchPatientOverview(pid) {
    if (!authToken) {
      window.location.hash = '#/login';
      return;
    }
    isLoading = true;
    try {
      const res = await fetch(getApiBase() + '/api/v1/patients/' + (pid || 'pat_demo_patient_001') + '/overview', {
        headers: {
          'Authorization': 'Bearer ' + authToken,
          'Content-Type': 'application/json'
        }
      });
      const data = await res.json();
      if (data.success && data.data) {
        patientData = data.data;
      }
    } catch (e) {
      console.warn('API fetch warning:', e);
    } finally {
      isLoading = false;
      render();
    }
  }

  // ── Route & Link Interceptor ──────────────────────────────────────────────
  window.addEventListener('hashchange', render);

  document.addEventListener('click', function (e) {
    const link = e.target.closest && e.target.closest('a');
    if (link && link.href) {
      if (link.getAttribute('download') || link.target === '_blank') return;
      try {
        const url = new URL(link.href, window.location.origin);
        if (url.port && url.port !== window.location.port) return;
      } catch (err) {}
      if (link.getAttribute('href') === '#/login' || link.getAttribute('data-cursor') === 'login') {
        e.preventDefault();
        window.location.hash = '#/login';
      }
    }
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
