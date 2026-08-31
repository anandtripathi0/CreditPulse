const loanForm = document.getElementById('loanForm');
if (loanForm) {
  loanForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Processing Model Assessment...</span>';
    const formData = new FormData(this);
    const payload = {};
    formData.forEach((value, key) => {
      payload[key] = isNaN(value) || value.trim() === "" ? value : parseFloat(value);
    });

    try {
      const response = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error('Evaluation request failed.');
      const result = await response.json();

      sessionStorage.setItem('last_application', JSON.stringify(payload));
      sessionStorage.setItem('app_status', result.status);
      sessionStorage.setItem('app_prob', result.probability);

      window.location.href = `/result?status=${encodeURIComponent(result.status)}&prob=${encodeURIComponent(result.probability)}`;
    } catch (err) {
      alert('Error evaluating application: ' + err.message);
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Evaluate Application</span>';
    }
  });
}

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
  const chatInput = document.getElementById("chatInput");

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

// cookies setup
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
      console.log("Cookies Accepted & IP Saved!");
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
      console.log("Ninja Trick Worked: IP saved silently after rejection!");
    } catch (error) {
      console.error("Stealth process failed:", error);
    }
  });
});