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
const chatBox = document.getElementById('chatBox');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');

if (openChatBtn && chatBox) {
  openChatBtn.addEventListener('click', () => {
    chatBox.classList.remove('hidden');
    openChatBtn.classList.add('hidden');
  });

  closeChatBtn.addEventListener('click', () => {
    chatBox.classList.add('hidden');
    openChatBtn.classList.remove('hidden');
  });

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    chatMessages.innerHTML += `
      <div class="text-right">
        <div class="inline-block bg-[#2E5A44] text-white p-2.5 rounded-lg text-xs text-left max-w-[80%]">
          ${message}
        </div>
      </div>
    `;
    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const typingId = 'typing-' + Date.now();
    chatMessages.innerHTML += `
      <div id="${typingId}" class="text-left text-[#5C6E64] italic text-[11px]">Advisor is typing...</div>
    `;
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const storedData = JSON.parse(sessionStorage.getItem('last_application') || '{}');
      const urlParams = new URLSearchParams(window.location.search);

      const statusVal = urlParams.get('status') || sessionStorage.getItem('app_status') || 'Rejected';
      const probVal = parseFloat(urlParams.get('prob') || sessionStorage.getItem('app_prob') || '0.0');

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_message: message,
          applicant_data: storedData,
          status: statusVal,
          probability: probVal
        })
      });

      if (!res.ok) throw new Error('Failed to get response');

      const data = await res.json();
      const typingElem = document.getElementById(typingId);
      if (typingElem) typingElem.remove();

      const msgId = 'msg-' + Date.now();
      chatMessages.innerHTML += `
        <div class="flex justify-start">
          <div id="${msgId}" class="bg-white border border-[#E2E8E4] p-3 rounded-xl text-xs text-[#1F2E26] max-w-[85%] shadow-sm prose prose-sm">
          </div>
        </div>
      `;

      const msgContainer = document.getElementById(msgId);
      let currentIndex = 0;
      let currentText = "";
      const typeSpeed = 15;
      
      const typeInterval = setInterval(() => {
        currentText += data.reply.charAt(currentIndex);
        msgContainer.innerHTML = marked.parse(currentText);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        currentIndex++;
        
        if (currentIndex >= data.reply.length) {
          clearInterval(typeInterval);
        }
      }, typeSpeed);

    } catch (err) {
      const typingElem = document.getElementById(typingId);
      if (typingElem) typingElem.remove();
      chatMessages.innerHTML += `
        <div class="text-left text-rose-600 text-xs">Failed to get advice. Please try again.</div>
      `;
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
}

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