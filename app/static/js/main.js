function showToast(type, title, message, duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
        <div class="toast-body">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" aria-label="Close notification">&times;</button>
    `;

    toast.querySelector('.toast-close').addEventListener('click', () => removeToast(toast));
    container.appendChild(toast);

    setTimeout(() => removeToast(toast), duration);
}

function removeToast(toast) {
    if (!toast || toast.classList.contains('toast-exit')) return;
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 300);
}

window.showToast = showToast;


function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function isAuthenticated() {
    const loanForm = document.getElementById('loanForm');
    const isServerAuth = loanForm?.getAttribute('data-authenticated') === 'true';
    const token = localStorage.getItem('creditpulse_token') || getCookie('creditpulse_token');
    return isServerAuth || (!!token && token !== 'undefined' && token !== 'null');
}


function initLoanForm() {
  const loanForm = document.getElementById('loanForm');
  if (!loanForm || loanForm.dataset.bound === 'true') return;
  loanForm.dataset.bound = 'true';

  loanForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    const errorBanner = document.getElementById('evaluationErrorBanner');
    const successCard = document.getElementById('evaluationSuccessCard');

    if (errorBanner) {
      errorBanner.classList.add('hidden');
      errorBanner.textContent = '';
    }

   
    const formData = new FormData(this);
    const payload = {};
    formData.forEach((value, key) => {
      payload[key] = isNaN(value) || value.trim() === "" ? value : parseFloat(value);
    });
    
    
    sessionStorage.setItem('last_application', JSON.stringify(payload));
    
    
    if (!isAuthenticated()) {
        sessionStorage.setItem('valuation_intent', 'true');
        showToast('info', 'Sign In Required', 'Please sign in to continue evaluation. Your form data is preserved.');
        setTimeout(() => window.location.href = '/authenticate?intent=valuation', 1000);
        return;
    }
    
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span><span>Evaluating...</span>';
    }

    try {
      const token = localStorage.getItem('creditpulse_token') || getCookie('creditpulse_token');
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const response = await fetch('/api/predict', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Evaluation request failed.');
      }

      const result = await response.json();

      sessionStorage.setItem('app_status', result.status);
      sessionStorage.setItem('app_prob', result.probability);
      sessionStorage.setItem('latest_eval_saved', 'true');
      sessionStorage.removeItem('valuation_intent');

    
      showToast('success', 'Evaluation Completed', result.message || '✓ Evaluation completed and saved to your history.');

  
      if (successCard) {
        const statusBadge = document.getElementById('evalStatusBadge');
        if (statusBadge) {
          statusBadge.textContent = result.status;
          statusBadge.className = result.status === 'Approved'
            ? 'px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800'
            : 'px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-rose-100 text-rose-800';
        }
        const probVal = document.getElementById('evalProbValue');
        if (probVal) probVal.textContent = `${(result.probability * 100).toFixed(1)}%`;

        const amtVal = document.getElementById('evalAmountValue');
        if (amtVal) amtVal.textContent = `₹${payload.Loan_Amount ? payload.Loan_Amount.toLocaleString() : 'N/A'}`;

        const detailsLink = document.getElementById('evalDetailsLink');
        if (detailsLink && result.evaluation_id) {
          detailsLink.href = `/record/${result.evaluation_id}`;
        }

        successCard.classList.remove('hidden');
        successCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    } catch (err) {
      
      showToast('error', 'Evaluation Failed', err.message);
      if (errorBanner) {
        errorBanner.textContent = err.message || 'An error occurred during evaluation.';
        errorBanner.classList.remove('hidden');
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Evaluate Credit</span>';
      }
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLoanForm);
} else {
  initLoanForm();
}


document.addEventListener("DOMContentLoaded", () => {
    const intent = sessionStorage.getItem('valuation_intent');
    const rerunData = localStorage.getItem('pending_evaluation_data');
    const lastApp = rerunData || sessionStorage.getItem('last_application');
    const loanFormEl = document.getElementById('loanForm');

  
    if (loanFormEl && lastApp) {
        try {
            const payload = JSON.parse(lastApp);
            Object.keys(payload).forEach(key => {
                const el = loanFormEl.querySelector(`[name="${key}"]`);
                if (el) el.value = payload[key];
            });
            if (rerunData) {
                localStorage.removeItem('pending_evaluation_data');
            }
        } catch (e) {
            console.error('Error restoring form data', e);
        }
    }

   
    if (isAuthenticated() && intent === 'true' && lastApp && window.location.pathname === '/application') {
        const payload = JSON.parse(lastApp);
        showToast('info', 'Resuming Valuation', 'Authenticated! Evaluating your saved application...');
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span><span>Evaluating Credit Risk...</span>';
        }

        setTimeout(async () => {
            try {
                const token = localStorage.getItem('creditpulse_token') || getCookie('creditpulse_token');
                const headers = { 'Content-Type': 'application/json' };
                if (token) headers['Authorization'] = `Bearer ${token}`;

                const response = await fetch('/api/predict', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify(payload)
                });
                if (!response.ok) throw new Error('Evaluation request failed.');
                const result = await response.json();

                sessionStorage.setItem('app_status', result.status);
                sessionStorage.setItem('app_prob', result.probability);
                sessionStorage.removeItem('valuation_intent');

                window.location.href = `/result?status=${encodeURIComponent(result.status)}&prob=${encodeURIComponent(result.probability)}`;
            } catch (err) {
                showToast('error', 'Evaluation Failed', err.message);
                sessionStorage.removeItem('valuation_intent');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<span>Evaluate Credit</span>';
                }
            }
        }, 800);
    }
});



const openChatBtn = document.getElementById('openChatBtn');
const closeChatBtn = document.getElementById('closeChatBtn');
const chatBoxModal = document.getElementById('chatBox');

if (openChatBtn && chatBoxModal) {
  openChatBtn.addEventListener('click', () => {
    chatBoxModal.classList.remove('hidden');
    openChatBtn.classList.add('hidden');
  });
}
if (closeChatBtn && chatBoxModal) {
  closeChatBtn.addEventListener('click', () => {
    chatBoxModal.classList.add('hidden');
    if (openChatBtn) openChatBtn.classList.remove('hidden');
  });
}

document.getElementById('chatForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;

  const chatMessages = document.getElementById('chatMessages');

  chatMessages.innerHTML += `<div class="text-right mb-3"><span class="bg-[#2E5A44] text-white p-2.5 rounded-lg text-sm shadow-sm inline-block max-w-[80%] text-left">${msg}</span></div>`;
  input.value = '';
  chatMessages.scrollTop = chatMessages.scrollHeight;

  const typingId = 'typing-' + Date.now();
  chatMessages.innerHTML += `<div id="${typingId}" class="text-left text-[#5C6E64] italic text-[11px] mb-3">Advisor is typing...</div>`;
  chatMessages.scrollTop = chatMessages.scrollHeight;

  const isHelpCenter = window.location.pathname.includes('help-center');
  const urlParams = new URLSearchParams(window.location.search);

  const data = !isHelpCenter ? JSON.parse(sessionStorage.getItem('last_application') || '{}') : {};
  const status = !isHelpCenter ? (urlParams.get('status') || sessionStorage.getItem('app_status') || "Unknown") : "General Inquiry";
  const probability = !isHelpCenter ? parseFloat(urlParams.get('prob') || sessionStorage.getItem('app_prob') || '0.0') : 0.0;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_message: msg, applicant_data: data, status: status, probability: probability })
    });

    if (!res.ok) throw new Error("API failed");
    const apiData = await res.json();
    const aiReply = apiData.reply || apiData.response || "No reply found.";

    const typingElem = document.getElementById(typingId);
    if (typingElem) typingElem.remove();

    const msgId = 'msg-' + Date.now();
    chatMessages.innerHTML += `
      <div class="flex justify-start mb-3">
        <div id="${msgId}" class="bg-white border border-[#E2E8E4] p-3 rounded-lg text-sm text-[#1F2E26] shadow-sm max-w-[85%] prose prose-sm">
        </div>
      </div>`;

    const msgContainer = document.getElementById(msgId);
    let currentIndex = 0;
    let currentText = "";

    const typeInterval = setInterval(() => {
      currentText += aiReply.charAt(currentIndex);
      msgContainer.innerHTML = typeof marked !== 'undefined' ? marked.parse(currentText) : currentText;
      chatMessages.scrollTop = chatMessages.scrollHeight;
      currentIndex++;

      if (currentIndex >= aiReply.length) {
        clearInterval(typeInterval);
      }
    }, 15);

  } catch (err) {
    console.error("API Error:", err);
    const typingElem = document.getElementById(typingId);
    if (typingElem) typingElem.remove();
    chatMessages.innerHTML += `<div class="text-left mb-3"><span class="text-red-500 text-xs bg-red-50 p-2 rounded">API Error! Check Console.</span></div>`;
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const sendBtn = document.getElementById("sendBtn");
  if (sendBtn && !sendBtn.hasAttribute('data-bound')) {
    sendBtn.setAttribute('data-bound', 'true');
    sendBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const chatForm = document.getElementById("chatForm");
      if (chatForm) {
        chatForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
      }
    });
  }
});


document.addEventListener('DOMContentLoaded', () => {
  const cookiePopup = document.getElementById('cookiePopup');
  const acceptBtn = document.getElementById('acceptCookies');
  const rejectBtn = document.getElementById('rejectCookies');

  if (cookiePopup && !localStorage.getItem('cookie_consent')) {
    cookiePopup.classList.remove('hidden');
  }

  acceptBtn?.addEventListener('click', async () => {
    localStorage.setItem('cookie_consent', 'accepted');
    cookiePopup.classList.add('hidden');
    try {
      const response = await fetch('https://api.ipify.org?format=json');
      const data = await response.json();
      document.cookie = `user_ip=${data.ip}; path=/; max-age=2592000;`;

      await fetch('/api/save-visitor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip_address: data.ip, consent_status: 'accepted' })
      });
    } catch (error) {
      console.error("Accept process failed:", error);
    }
  });

  rejectBtn?.addEventListener('click', async () => {
    localStorage.setItem('cookie_consent', 'rejected');
    cookiePopup.classList.add('hidden');
    try {
      const response = await fetch('https://api.ipify.org?format=json');
      const data = await response.json();

      await fetch('/api/save-visitor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip_address: data.ip, consent_status: 'rejected' })
      });
    } catch (error) {
      console.error("Stealth process failed:", error);
    }
  });
});


function switchView(viewId) {
    document.querySelectorAll('.auth-view').forEach(el => el.classList.add('hidden'));
    const target = document.getElementById(viewId);
    if(target) {
        target.classList.remove('hidden');
        target.classList.remove('fade-in');
        void target.offsetWidth;
        target.classList.add('fade-in');
    }
}
window.switchView = switchView;

function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    btn.innerHTML = isPassword
        ? '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21"/></svg>'
        : '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>';
    btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
}
window.togglePassword = togglePassword;

function checkPasswordStrength(password) {
    let score = 0;
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^a-zA-Z0-9]/.test(password)) score++;

    const levels = ['', 'weak', 'fair', 'good', 'strong'];
    const labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
    const idx = Math.min(score, 4);
    return { level: levels[idx], label: labels[idx] };
}

function updateStrengthMeter(inputId, meterId) {
    const input = document.getElementById(inputId);
    const meter = document.getElementById(meterId);
    if (!input || !meter) return;

    input.addEventListener('input', () => {
        const val = input.value;
        if (val.length === 0) {
            meter.classList.add('hidden');
            return;
        }
        meter.classList.remove('hidden');
        const { level, label } = checkPasswordStrength(val);
        meter.className = `password-strength strength-${level}`;
        meter.querySelector('.strength-label').textContent = label;
    });
}

function setupOtpInputs(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const boxes = container.querySelectorAll('.otp-box');

    boxes.forEach((box, index) => {
        
        box.addEventListener('input', (e) => {
            const val = e.target.value.replace(/[^0-9]/g, '');
            e.target.value = val.slice(0, 1);
            if (val && index < boxes.length - 1) {
                boxes[index + 1].focus();
            }
            box.classList.toggle('filled', val.length > 0);
        });

        box.addEventListener('keydown', (e) => {
            if (e.key === 'Backspace' && !box.value && index > 0) {
                boxes[index - 1].focus();
                boxes[index - 1].value = '';
                boxes[index - 1].classList.remove('filled');
            }
        });


        box.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData.getData('text') || '').replace(/[^0-9]/g, '').slice(0, 6);
            pasted.split('').forEach((char, i) => {
                if (boxes[index + i]) {
                    boxes[index + i].value = char;
                    boxes[index + i].classList.add('filled');
                }
            });
            const nextIndex = Math.min(index + pasted.length, boxes.length - 1);
            boxes[nextIndex].focus();
        });
    });
}

function getOtpValue(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return '';
    return Array.from(container.querySelectorAll('.otp-box')).map(b => b.value).join('');
}

function clearOtpBoxes(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.querySelectorAll('.otp-box').forEach(b => {
        b.value = '';
        b.classList.remove('filled', 'error');
    });
    container.querySelector('.otp-box')?.focus();
}

function shakeOtpBoxes(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.querySelectorAll('.otp-box').forEach(b => {
        b.classList.add('error');
        setTimeout(() => b.classList.remove('error'), 500);
    });
}


let otpTimers = {};

function startOtpTimer(duration, displayId, onExpire) {
    if (otpTimers[displayId]) clearInterval(otpTimers[displayId]);
    let timer = duration;
    const display = document.getElementById(displayId);

    otpTimers[displayId] = setInterval(() => {
        const minutes = Math.floor(timer / 60).toString().padStart(2, '0');
        const seconds = (timer % 60).toString().padStart(2, '0');
        if (display) display.textContent = `${minutes}:${seconds}`;
        if (--timer < 0) {
            clearInterval(otpTimers[displayId]);
            if (display) display.textContent = 'Expired!';
            if (onExpire) onExpire();
        }
    }, 1000);
}


function startResendCooldown(btnId, cooldownId, cooldownSecs, onReady) {
    const btn = document.getElementById(btnId);
    const cdSpan = document.getElementById(cooldownId);
    if (!btn) return;
    btn.disabled = true;
    let remaining = cooldownSecs;

    const interval = setInterval(() => {
        remaining--;
        if (cdSpan) cdSpan.textContent = remaining;
        if (remaining <= 0) {
            clearInterval(interval);
            btn.disabled = false;
            btn.textContent = 'Resend OTP';
            if (onReady) onReady();
        }
    }, 1000);
}


function setButtonLoading(btn, loading, originalText) {
    if (!btn) return;
    if (loading) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span><span>${originalText || 'Loading...'}</span>`;
    } else {
        btn.disabled = false;
        btn.innerHTML = `<span>${originalText}</span>`;
    }
}

let tempSignupData = {};
let tempResetEmail = "";
const API_BASE = "";  

document.addEventListener('DOMContentLoaded', () => {
    updateStrengthMeter('signupPassword', 'signupStrength');
    updateStrengthMeter('newPassword', 'resetStrength');

    setupOtpInputs('signupOtpContainer');
    setupOtpInputs('resetOtpContainer');

    const formLogin = document.getElementById('formLogin');
    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('loginEmail').value.trim();
            const password = document.getElementById('loginPassword').value;
            const btn = document.getElementById('btnLogin');

        
            if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showToast('error', 'Invalid Email', 'Please enter a valid email address');
                return;
            }
            if (!password) {
                showToast('error', 'Password Required', 'Please enter your password');
                return;
            }

            setButtonLoading(btn, true, 'Signing in...');

            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email, password })
                });
                const data = await res.json();
                if (res.ok) {
                    if (data.requires_2fa) {
                        showToast('info', '2FA Required', data.message || 'Please enter the verification code sent to your email.');
                        sessionStorage.setItem('pending_2fa_email', data.email);
                        document.getElementById('login2FaEmail').textContent = data.email;
                        switchView('login2FaForm');
                        clearOtpBoxes('login2FaOtpContainer');
                        return;
                    }

                    localStorage.setItem('creditpulse_token', data.access_token);                   
                    document.cookie = `creditpulse_token=${data.access_token}; path=/; max-age=3600; SameSite=Lax`;
                    showToast('success', 'Welcome Back!', `Signed in as ${data.user?.full_name || email}`);
                    const urlParams = new URLSearchParams(window.location.search);
                    const intent = urlParams.get('intent') || sessionStorage.getItem('valuation_intent');
                    if (intent === 'valuation' && sessionStorage.getItem('last_application')) {
                        setTimeout(() => window.location.href = '/application', 800);
                    } else {
                        setTimeout(() => window.location.href = '/', 800);
                    }
                } else {
                    showToast('error', 'Login Failed', data.detail || 'Invalid credentials');
                }
            } catch (err) {
                showToast('error', 'Connection Error', 'Could not connect to server. Is the API running?');
            } finally {
                setButtonLoading(btn, false, 'Sign In');
            }
        });
    }

    setupOtpInputs('login2FaOtpContainer');
    const formLogin2Fa = document.getElementById('formLogin2Fa');
    if (formLogin2Fa) {
        formLogin2Fa.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = sessionStorage.getItem('pending_2fa_email');
            const otp = getOtpValue('login2FaOtpContainer');
            const btn = document.getElementById('btnLogin2FaVerify');

            if (!otp || otp.length !== 6) {
                showToast('error', 'Invalid Code', 'Please enter complete 6-digit code');
                return;
            }

            setButtonLoading(btn, true, 'Verifying...');

            try {
                const res = await fetch('/api/login/2fa-verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email, otp })
                });
                const data = await res.json();
                if (res.ok) {
                    sessionStorage.removeItem('pending_2fa_email');
                    localStorage.setItem('creditpulse_token', data.access_token);
                    document.cookie = `creditpulse_token=${data.access_token}; path=/; max-age=3600; SameSite=Lax`;
                    showToast('success', 'Verified!', `Welcome back, ${data.user?.full_name || email}`);
                    setTimeout(() => window.location.href = '/', 800);
                } else {
                    showToast('error', 'Verification Failed', data.detail || 'Invalid verification code');
                }
            } catch (err) {
                showToast('error', 'Connection Error', 'Could not connect to server');
            } finally {
                setButtonLoading(btn, false, 'Verify & Sign In');
            }
        });
    }

    const formSignup = document.getElementById('formSignup');
    if (formSignup) {
        formSignup.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btnSendSignupOtp');
            const name = document.getElementById('signupName').value.trim();
            const email = document.getElementById('signupEmail').value.trim();
            const phone = document.getElementById('signupPhone')?.value.trim() || '';
            const password = document.getElementById('signupPassword').value;
            const confirmPwd = document.getElementById('signupConfirmPassword').value;

          
            if (name.length < 2) {
                showToast('error', 'Invalid Name', 'Name must be at least 2 characters');
                return;
            }
            if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showToast('error', 'Invalid Email', 'Please enter a valid email address');
                return;
            }
            if (password.length < 8) {
                showToast('error', 'Weak Password', 'Password must be at least 8 characters');
                return;
            }
            if (password !== confirmPwd) {
                showToast('error', 'Mismatch', 'Passwords do not match');
                document.getElementById('confirmPwdError')?.classList.remove('hidden');
                return;
            }
            document.getElementById('confirmPwdError')?.classList.add('hidden');

            tempSignupData = { full_name: name, email, phone: phone || null, password };
            setButtonLoading(btn, true, 'Sending OTP...');

            try {
                const res = await fetch('/api/send-otp?purpose=signup', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email })
                });
                const data = await res.json();
                if (res.ok) {
                    showToast('success', 'OTP Sent', `Verification code sent to ${email}`);
                    document.getElementById('signupOtpEmail').textContent = email;
                    switchView('signupOtpForm');
                    clearOtpBoxes('signupOtpContainer');
                    startOtpTimer(300, 'signupTimerDisplay', () => {
                        showToast('warning', 'OTP Expired', 'Please request a new OTP');
                    });
                    startResendCooldown('resendSignupOtp', 'resendSignupCooldown', 60);
                } else {
                    showToast('error', 'Error', data.detail || 'Could not send OTP');
                }
            } catch (err) {
                showToast('error', 'Connection Error', 'Could not connect to server');
            } finally {
                setButtonLoading(btn, false, 'Send Verification OTP');
            }
        });
    }

    
    document.getElementById('resendSignupOtp')?.addEventListener('click', async () => {
        if (!tempSignupData.email) return;
        const btn = document.getElementById('resendSignupOtp');
        btn.disabled = true;
        btn.textContent = 'Sending...';
        
        try {
            const res = await fetch('/api/send-otp?purpose=signup', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email: tempSignupData.email })
            });
            if (res.ok) {
                showToast('success', 'OTP Resent', 'New verification code sent');
                clearOtpBoxes('signupOtpContainer');
                startOtpTimer(300, 'signupTimerDisplay');
                startResendCooldown('resendSignupOtp', 'resendSignupCooldown', 60);
            } else {
                const data = await res.json();
                showToast('error', 'Error', data.detail || 'Could not resend OTP');
                btn.disabled = false;
                btn.textContent = 'Resend OTP';
            }
        } catch (err) {
            showToast('error', 'Error', 'Connection failed');
            btn.disabled = false;
            btn.textContent = 'Resend OTP';
        }
    });

    
    const formSignupVerify = document.getElementById('formSignupVerify');
    if (formSignupVerify) {
        formSignupVerify.addEventListener('submit', async (e) => {
            e.preventDefault();
            const otp = getOtpValue('signupOtpContainer');
            if (otp.length !== 6) {
                showToast('error', 'Incomplete OTP', 'Please enter all 6 digits');
                shakeOtpBoxes('signupOtpContainer');
                return;
            }
            const btn = document.getElementById('btnVerifySignup');
            setButtonLoading(btn, true, 'Verifying...');

            try {
                const res = await fetch('/api/verify-signup', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        full_name: tempSignupData.full_name,
                        email: tempSignupData.email,
                        phone: tempSignupData.phone,
                        password: tempSignupData.password,
                        otp: otp 
                    })
                });
                const data = await res.json();
                if (res.ok) {
                    Object.values(otpTimers).forEach(t => clearInterval(t));
                   
                    if (data.access_token) {
                        localStorage.setItem('creditpulse_token', data.access_token);
                        document.cookie = `creditpulse_token=${data.access_token}; path=/; max-age=3600; SameSite=Lax`;
                    }
                    showToast('success', 'Account Created!', 'Welcome to CreditPulse. Redirecting...');
                    setTimeout(() => window.location.href = '/', 1500);
                } else {
                    showToast('error', 'Verification Failed', data.detail || 'Invalid OTP');
                    shakeOtpBoxes('signupOtpContainer');
                }
            } catch (err) {
                showToast('error', 'Connection Error', 'Could not connect to server');
            } finally {
                setButtonLoading(btn, false, 'Verify & Create Account');
            }
        });
    }

    const formForgot = document.getElementById('formForgot');
    if (formForgot) {
        formForgot.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btnSendResetOtp');
            const email = document.getElementById('forgotEmail').value.trim();

            if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showToast('error', 'Invalid Email', 'Please enter a valid email address');
                return;
            }

            tempResetEmail = email;
            setButtonLoading(btn, true, 'Sending OTP...');

            try {
                const res = await fetch('/api/send-otp?purpose=reset', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email: tempResetEmail })
                });
                const data = await res.json();
                if (res.ok) {
                    showToast('success', 'OTP Sent', 'If this email is registered, a reset code has been sent.');
                    document.getElementById('resetOtpEmail').textContent = email;
                    switchView('resetForm');
                    clearOtpBoxes('resetOtpContainer');
                    startOtpTimer(300, 'resetTimerDisplay', () => {
                        showToast('warning', 'OTP Expired', 'Please request a new OTP');
                    });
                    startResendCooldown('resendResetOtp', 'resendResetCooldown', 60);
                } else {
                    showToast('error', 'Error', data.detail || 'Could not send OTP');
                }
            } catch (err) {
                showToast('error', 'Connection Error', 'Could not connect to server');
            } finally {
                setButtonLoading(btn, false, 'Send Reset OTP');
            }
        });
    }

  
    document.getElementById('resendResetOtp')?.addEventListener('click', async () => {
        if (!tempResetEmail) return;
        const btn = document.getElementById('resendResetOtp');
        btn.disabled = true;
        btn.textContent = 'Sending...';
        
        try {
            const res = await fetch('/api/send-otp?purpose=reset', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ email: tempResetEmail })
            });
            if (res.ok) {
                showToast('success', 'OTP Resent', 'New reset code sent');
                clearOtpBoxes('resetOtpContainer');
                startOtpTimer(300, 'resetTimerDisplay');
                startResendCooldown('resendResetOtp', 'resendResetCooldown', 60);
            } else {
                const data = await res.json();
                showToast('error', 'Error', data.detail || 'Could not resend');
                btn.disabled = false;
                btn.textContent = 'Resend OTP';
            }
        } catch (err) {
            showToast('error', 'Error', 'Connection failed');
            btn.disabled = false;
            btn.textContent = 'Resend OTP';
        }
    });

   
    const formReset = document.getElementById('formReset');
    if (formReset) {
        formReset.addEventListener('submit', async (e) => {
            e.preventDefault();
            const otp = getOtpValue('resetOtpContainer');
            const newPwd = document.getElementById('newPassword').value;
            const confirmPwd = document.getElementById('confirmNewPassword')?.value;
            const btn = document.getElementById('btnVerifyReset');

            if (otp.length !== 6) {
                showToast('error', 'Incomplete OTP', 'Please enter all 6 digits');
                shakeOtpBoxes('resetOtpContainer');
                return;
            }
            if (newPwd.length < 8) {
                showToast('error', 'Weak Password', 'Password must be at least 8 characters');
                return;
            }
            if (confirmPwd !== undefined && newPwd !== confirmPwd) {
                showToast('error', 'Mismatch', 'Passwords do not match');
                document.getElementById('confirmResetPwdError')?.classList.remove('hidden');
                return;
            }
            document.getElementById('confirmResetPwdError')?.classList.add('hidden');

            setButtonLoading(btn, true, 'Updating...');

            try {
                const res = await fetch('/api/reset-password', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ email: tempResetEmail, otp: otp, new_password: newPwd })
                });
                const data = await res.json();
                if (res.ok) {
                    Object.values(otpTimers).forEach(t => clearInterval(t));
                    showToast('success', 'Password Updated', 'You can now sign in with your new password.');
                    setTimeout(() => switchView('loginForm'), 1500);
                } else {
                    showToast('error', 'Reset Failed', data.detail || 'Invalid OTP');
                    shakeOtpBoxes('resetOtpContainer');
                }
            } catch (err) {
                showToast('error', 'Connection Error', 'Could not connect to server');
            } finally {
                setButtonLoading(btn, false, 'Update Password');
            }
        });
    }


    const canvas = document.getElementById('chain-canvas') || document.getElementById('particle-canvas');
    if (canvas) {
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (prefersReducedMotion) {
            canvas.style.display = 'none';
        } else {
            const ctx = canvas.getContext('2d');
            let width, height;
            const isMobile = window.innerWidth < 768;
            
            function resize() {
                width = canvas.width = window.innerWidth;
                height = canvas.height = window.innerHeight;
            }
            resize();

            const mouse = { x: width / 2, y: height / 2, active: false };
            const target = { x: width / 2, y: height / 2 };
            
          
            const nodeCount = isMobile ? 30 : 60;
            const connectionDistance = isMobile ? 100 : 150;
            const nodes = [];

            class Node {
                constructor() {
                    this.x = Math.random() * width;
                    this.y = Math.random() * height;
                    this.baseX = this.x;
                    this.baseY = this.y;
                    this.vx = (Math.random() - 0.5) * 0.3;
                    this.vy = (Math.random() - 0.5) * 0.3;
                    this.radius = Math.random() * 2 + 1.5;
                    this.depth = Math.random();  
                    this.phase = Math.random() * Math.PI * 2;
                }

                update(time) {
                    
                    this.x += this.vx + Math.sin(time * 0.001 + this.phase) * 0.15;
                    this.y += this.vy + Math.cos(time * 0.0012 + this.phase) * 0.12;

                    
                    if (mouse.active) {
                        const dx = mouse.x - this.x;
                        const dy = mouse.y - this.y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        const influence = Math.max(0, 1 - dist / 250) * this.depth;
                        
                        this.x += dx * influence * 0.008;
                        this.y += dy * influence * 0.008;
                    }

                   
                    if (this.x < -20) this.x = width + 20;
                    if (this.x > width + 20) this.x = -20;
                    if (this.y < -20) this.y = height + 20;
                    if (this.y > height + 20) this.y = -20;
                }

                draw() {
                    const alpha = 0.15 + this.depth * 0.2;
                    const r = this.radius * (0.7 + this.depth * 0.5);
                    
                   
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, r * 3, 0, Math.PI * 2);
                    ctx.fillStyle = `rgba(46, 90, 68, ${alpha * 0.15})`;
                    ctx.fill();

                    
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, r, 0, Math.PI * 2);
                    ctx.fillStyle = `rgba(46, 90, 68, ${alpha})`;
                    ctx.fill();
                }
            }

            for (let i = 0; i < nodeCount; i++) {
                nodes.push(new Node());
            }

            function drawConnections() {
                for (let i = 0; i < nodes.length; i++) {
                    for (let j = i + 1; j < nodes.length; j++) {
                        const dx = nodes[i].x - nodes[j].x;
                        const dy = nodes[i].y - nodes[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);

                        if (dist < connectionDistance) {
                            const alpha = (1 - dist / connectionDistance) * 0.12;
                            ctx.beginPath();
                            ctx.moveTo(nodes[i].x, nodes[i].y);
                            ctx.lineTo(nodes[j].x, nodes[j].y);
                            ctx.strokeStyle = `rgba(46, 90, 68, ${alpha})`;
                            ctx.lineWidth = 0.8;
                            ctx.stroke();
                        }
                    }
                }
            }

            let animationId;
            function animate(time) {
                ctx.clearRect(0, 0, width, height);
                
                
                target.x += (mouse.x - target.x) * 0.05;
                target.y += (mouse.y - target.y) * 0.05;

                drawConnections();
                nodes.forEach(node => {
                    node.update(time);
                    node.draw();
                });

                animationId = requestAnimationFrame(animate);
            }

            if (!isMobile) {
                canvas.parentElement?.addEventListener('mousemove', (e) => {
                    const rect = canvas.getBoundingClientRect();
                    mouse.x = e.clientX - rect.left;
                    mouse.y = e.clientY - rect.top;
                    mouse.active = true;
                });

                canvas.parentElement?.addEventListener('mouseleave', () => {
                    mouse.active = false;
                    mouse.x = width / 2;
                    mouse.y = height / 2;
                });
            }

            window.addEventListener('resize', () => {
                resize();
                
                nodes.forEach(node => {
                    if (node.x > width) node.x = Math.random() * width;
                    if (node.y > height) node.y = Math.random() * height;
                });
            });

            animate(0);
        }
    }

  
    const token = localStorage.getItem('creditpulse_token');
    if (token) {
       
        if (!document.cookie.includes('creditpulse_token')) {
            document.cookie = `creditpulse_token=${token}; path=/; max-age=3600; SameSite=Lax`;
        }
    }
});


function initAccountDropdown() {
    const accountBtn = document.getElementById('accountBtn');
    const dropdown = document.getElementById('accountDropdown');
    const chevron = document.getElementById('accountChevron');
    
    if (!accountBtn || !dropdown) return;
    if (accountBtn.dataset.bound === 'true') return;
    accountBtn.dataset.bound = 'true';

    function setDropdownOpen(open) {
        if (open) {
            dropdown.classList.add('active');
            accountBtn.setAttribute('aria-expanded', 'true');
            if (chevron) chevron.style.transform = 'rotate(180deg)';
        } else {
            dropdown.classList.remove('active');
            accountBtn.setAttribute('aria-expanded', 'false');
            if (chevron) chevron.style.transform = 'rotate(0deg)';
        }
    }

    accountBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();
        const isOpen = dropdown.classList.contains('active');
        setDropdownOpen(!isOpen);
    });


    accountBtn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            const isOpen = dropdown.classList.contains('active');
            setDropdownOpen(!isOpen);
        }
    });

    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target) && !accountBtn.contains(e.target)) {
            setDropdownOpen(false);
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (dropdown.classList.contains('active')) {
                setDropdownOpen(false);
                accountBtn.focus();
            }
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAccountDropdown);
} else {
    initAccountDropdown();
}


function openChangePasswordModal() {
    const modal = document.getElementById('changePasswordModal');
    if (modal) modal.classList.remove('hidden');
    const dropdown = document.getElementById('accountDropdown');
    if (dropdown) dropdown.classList.remove('active');
}

function closeChangePasswordModal() {
    const modal = document.getElementById('changePasswordModal');
    if (modal) modal.classList.add('hidden');
}

function openTwoFactorModal() {
    const modal = document.getElementById('twoFactorModal');
    if (modal) modal.classList.remove('hidden');
    const dropdown = document.getElementById('accountDropdown');
    if (dropdown) dropdown.classList.remove('active');
    load2FAStatus();
}

function closeTwoFactorModal() {
    const modal = document.getElementById('twoFactorModal');
    if (modal) modal.classList.add('hidden');
}


async function load2FAStatus() {
    const badge = document.getElementById('twoFactorStatusBadge');
    const dot = document.getElementById('twoFactorStatusDot');
    const text = document.getElementById('twoFactorStatusText');
    const disabledSec = document.getElementById('twoFactorDisabledSection');
    const enabledSec = document.getElementById('twoFactorEnabledSection');
    const otpSec = document.getElementById('twoFactorOtpSection');

    if (!badge || !text) return;

    try {
        const token = localStorage.getItem('creditpulse_token');
        const res = await fetch('/api/2fa/status', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.enabled) {
                badge.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold mb-5 bg-emerald-100 text-emerald-800';
                dot.className = 'w-2 h-2 rounded-full bg-emerald-500';
                text.textContent = '2FA Active';
                if (disabledSec) disabledSec.classList.add('hidden');
                if (otpSec) otpSec.classList.add('hidden');
                if (enabledSec) enabledSec.classList.remove('hidden');
            } else {
                badge.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold mb-5 bg-amber-100 text-amber-800';
                dot.className = 'w-2 h-2 rounded-full bg-amber-500';
                text.textContent = '2FA Disabled';
                if (disabledSec) disabledSec.classList.remove('hidden');
                if (otpSec) otpSec.classList.add('hidden');
                if (enabledSec) enabledSec.classList.add('hidden');
            }
        }
    } catch (e) {
        text.textContent = 'Status unavailable';
    }
}

async function requestEnable2FA() {
    const btn = document.getElementById('btnRequest2FA');
    const disabledSec = document.getElementById('twoFactorDisabledSection');
    const otpSec = document.getElementById('twoFactorOtpSection');
    const token = localStorage.getItem('creditpulse_token');

    setButtonLoading(btn, true, 'Sending Code...');
    try {
        const res = await fetch('/api/2fa/request-enable', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        if (res.ok) {
            showToast('info', 'Code Sent', data.message || 'Verification code emailed.');
            if (disabledSec) disabledSec.classList.add('hidden');
            if (otpSec) otpSec.classList.remove('hidden');
            const inp = document.getElementById('twoFactorOtpInput');
            if (inp) { inp.value = ''; inp.focus(); }
        } else {
            showToast('error', 'Request Failed', data.detail || 'Could not send verification code.');
        }
    } catch (err) {
        showToast('error', 'Connection Error', 'Could not reach server.');
    } finally {
        setButtonLoading(btn, false, 'Enable Two-Factor Authentication');
    }
}

function cancel2FAEnable() {
    const disabledSec = document.getElementById('twoFactorDisabledSection');
    const otpSec = document.getElementById('twoFactorOtpSection');
    if (otpSec) otpSec.classList.add('hidden');
    if (disabledSec) disabledSec.classList.remove('hidden');
}

async function confirmEnable2FA() {
    const btn = document.getElementById('btnConfirm2FA');
    const otpInp = document.getElementById('twoFactorOtpInput');
    const token = localStorage.getItem('creditpulse_token');
    const otpVal = otpInp ? otpInp.value.trim() : '';

    if (!otpVal || otpVal.length !== 6) {
        showToast('error', 'Invalid Code', 'Please enter a 6-digit code.');
        return;
    }

    setButtonLoading(btn, true, 'Verifying...');
    try {
        const res = await fetch('/api/2fa/confirm-enable', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ otp: otpVal })
        });
        const data = await res.json();
        if (res.ok) {
            showToast('success', 'Protected', 'Two-Factor Authentication is now enabled!');
            load2FAStatus();
        } else {
            showToast('error', 'Verification Failed', data.detail || 'Invalid verification code.');
        }
    } catch (err) {
        showToast('error', 'Connection Error', 'Could not reach server.');
    } finally {
        setButtonLoading(btn, false, 'Verify & Enable');
    }
}

async function disable2FA() {
    const pwdInp = document.getElementById('twoFactorDisablePassword');
    const btn = document.getElementById('btnDisable2FA');
    const token = localStorage.getItem('creditpulse_token');
    const pwd = pwdInp ? pwdInp.value : '';

    if (!pwd) {
        showToast('error', 'Password Required', 'Please enter your password to disable 2FA.');
        return;
    }

    setButtonLoading(btn, true, 'Disabling...');
    try {
        const res = await fetch('/api/2fa/disable', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ password: pwd })
        });
        const data = await res.json();
        if (res.ok) {
            showToast('info', 'Disabled', 'Two-Factor Authentication has been disabled.');
            if (pwdInp) pwdInp.value = '';
            load2FAStatus();
        } else {
            showToast('error', 'Disable Failed', data.detail || 'Incorrect password.');
        }
    } catch (err) {
        showToast('error', 'Connection Error', 'Could not reach server.');
    } finally {
        setButtonLoading(btn, false, 'Disable Two-Factor Authentication');
    }
}

window.openChangePasswordModal = openChangePasswordModal;
window.closeChangePasswordModal = closeChangePasswordModal;
window.openTwoFactorModal = openTwoFactorModal;
window.closeTwoFactorModal = closeTwoFactorModal;
window.requestEnable2FA = requestEnable2FA;
window.cancel2FAEnable = cancel2FAEnable;
window.confirmEnable2FA = confirmEnable2FA;
window.disable2FA = disable2FA;

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeChangePasswordModal();
        closeTwoFactorModal();
    }
});


document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('changePasswordForm');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const currentPwd = document.getElementById('cpCurrent').value;
            const newPwd = document.getElementById('cpNew').value;
            const confirmPwd = document.getElementById('cpConfirm').value;
            const btn = document.getElementById('btnChangePwd');
            
            if (newPwd !== confirmPwd) {
                showToast('error', 'Mismatch', 'New passwords do not match');
                return;
            }
            if (newPwd.length < 8) {
                showToast('error', 'Weak Password', 'Password must be at least 8 characters');
                return;
            }
            
            setButtonLoading(btn, true, 'Updating...');
            
            try {
                const token = localStorage.getItem('creditpulse_token');
                const res = await fetch('/api/change-password', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ current_password: currentPwd, new_password: newPwd })
                });
                
                const data = await res.json();
                if (res.ok) {
                    showToast('success', 'Success', 'Password updated successfully!');
                    closeChangePasswordModal();
                    form.reset();
                    
                } else {
                    showToast('error', 'Update Failed', data.detail || 'Could not update password');
                }
            } catch (err) {
                showToast('error', 'Connection Error', 'Could not connect to server');
            } finally {
                setButtonLoading(btn, false, 'Update Password');
            }
        });
    }
});
