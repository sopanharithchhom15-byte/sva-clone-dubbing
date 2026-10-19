// SVA Clone Dubbing - Frontend Controller
let gSubtitles = [];
let gVoices = [];
let gSettings = {};

// Unique Session Isolation per Device/Browser
function initUserSession() {
  const urlParams = new URLSearchParams(window.location.search);
  let sId = urlParams.get("session") || urlParams.get("s");
  if (!sId) {
    sId = localStorage.getItem("sva_user_session_id");
  }
  if (!sId || sId === "default") {
    sId = "user_" + Date.now().toString(36) + "_" + Math.random().toString(36).substring(2, 7);
  }
  localStorage.setItem("sva_user_session_id", sId);
  return sId;
}

let gSessionId = initUserSession();
let gCurrentTtsMode = "edge_tts";

// Audio Preview Player
const gAudio = document.getElementById("globalAudioPlayer");

let gCurrentNetworkUrl = "";

async function startNewProject() {
  if (confirm("តើអ្នកចង់ចាប់ផ្តើមគម្រោងថ្មី (New Project) មែនទេ?\nកុំព្យូទ័រនេះនឹងទទួលបាន Workspace ថ្មីដាច់ដោយឡែកពីគេ។")) {
    try {
      const res = await fetch("/api/new_session", { method: "POST" });
      const data = await res.json();
      localStorage.setItem("sva_user_session_id", data.session_id);
    } catch (e) {
      const sId = "user_" + Date.now().toString(36) + "_" + Math.random().toString(36).substring(2, 7);
      localStorage.setItem("sva_user_session_id", sId);
    }
    window.location.href = window.location.pathname;
  }
}

// Global Refresh Data Controller
async function refreshAppData() {
  const btn = document.getElementById("btnAppRefresh");
  if (btn) btn.classList.add("is-refreshing");
  
  showToast("🔄 កំពុងទាញយកទិន្នន័យថ្មី (Refreshing)...", "info", 1800);
  
  try {
    await Promise.all([
      loadNetworkInfo(),
      loadSettings(),
      loadVoices(),
      loadSessionState()
    ]);
    updateWorkflowStepper();
    showToast("✅ ធ្វើបច្ចុប្បន្នភាពជោគជ័យ (Refreshed)!", "success", 2500);
  } catch (e) {
    console.error("Refresh error:", e);
    showToast("⚠️ កំហុសពេល Refresh: " + e.message, "warning", 3000);
  } finally {
    if (btn) {
      setTimeout(() => {
        btn.classList.remove("is-refreshing");
      }, 600);
    }
  }
}

// PWA & Mobile Native App Installation Manager
let gDeferredInstallPrompt = null;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(err => {
      console.log('SW note:', err);
    });
  });
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  gDeferredInstallPrompt = e;
  const btn = document.getElementById('btnInstallApp');
  if (btn) btn.style.display = 'flex';
});

window.addEventListener('appinstalled', () => {
  gDeferredInstallPrompt = null;
  const btn = document.getElementById('btnInstallApp');
  if (btn) btn.style.display = 'none';
  showToast("🎉 ដំឡើងកម្មវិធីជោគជ័យ!", "success", 4000);
});

async function triggerPwaInstall() {
  if (gDeferredInstallPrompt) {
    gDeferredInstallPrompt.prompt();
    const choice = await gDeferredInstallPrompt.userChoice;
    if (choice.outcome === 'accepted') {
      showToast("✅ កំពុងដំឡើង App លើទូរស័ព្ទរបស់អ្នក...", "success");
    }
    gDeferredInstallPrompt = null;
  } else {
    openInstallGuideModal();
  }
}

function openInstallGuideModal() {
  const m = document.getElementById('installGuideModal');
  if (m) m.style.display = 'flex';
}

function closeInstallGuideModal() {
  const m = document.getElementById('installGuideModal');
  if (m) m.style.display = 'none';
}

document.addEventListener("DOMContentLoaded", async () => {
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  const btnInstall = document.getElementById('btnInstallApp');
  if (btnInstall && !isStandalone) {
    btnInstall.style.display = 'flex';
  }

  await loadNetworkInfo();
  await loadSettings();
  await loadVoices();
  await loadSessionState();
  initDragAndDrop();
  updateWorkflowStepper();
});

// Modern Animated Toast Notification Engine
function showToast(message, type = "info", duration = 3800) {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    container.className = "toast-stack-container";
    document.body.appendChild(container);
  }
  
  const toast = document.createElement("div");
  toast.className = `toast-pill toast-${type}`;
  
  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  else if (type === "error") icon = "❌";
  else if (type === "warning") icon = "⚠️";
  
  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-text">${message}</span>
    <span class="toast-close" onclick="this.parentElement.remove()">✕</span>
  `;
  
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(50px) scale(0.9)";
    setTimeout(() => { if (toast.parentElement) toast.remove(); }, 350);
  }, duration);
}

function showToastNotification(msg) {
  showToast(msg, "success");
}

// 4-Step Stepper Wizard & Floating Guide Manager
let gNextStepTarget = null;

function updateWorkflowStepper() {
  const hasMedia = document.getElementById("videoPreviewWrap") && 
                    document.getElementById("videoPreviewWrap").style.display !== "none";
  const subCount = gSubtitles ? gSubtitles.length : 0;
  const hasSub = subCount > 0;
  const voicedCount = hasSub ? gSubtitles.filter(s => s.has_audio).length : 0;
  const hasVoice = hasSub && voicedCount > 0;
  const isAllVoiced = hasSub && (voicedCount === subCount);
  const hasRender = document.getElementById("renderedResultWrap") && 
                    document.getElementById("renderedResultWrap").style.display !== "none";

  // Step 1: Media
  const step1 = document.getElementById("stepIndicator1");
  const badge1 = document.getElementById("stepBadgeMedia");
  const conn1 = document.getElementById("connector1");
  if (step1 && badge1) {
    if (hasMedia) {
      step1.classList.add("completed");
      badge1.innerText = "✅ វីដេអូរួចរាល់";
      if (conn1) conn1.classList.add("active");
    } else {
      step1.classList.remove("completed");
      badge1.innerText = "⏳ រង់ចាំវីដេអូ";
      if (conn1) conn1.classList.remove("active");
    }
  }

  // Step 2: Subtitle
  const step2 = document.getElementById("stepIndicator2");
  const badge2 = document.getElementById("stepBadgeSub");
  const conn2 = document.getElementById("connector2");
  if (step2 && badge2) {
    if (hasSub) {
      step2.classList.add("completed");
      badge2.innerText = `✅ ${subCount} បន្ទាត់`;
      if (conn2) conn2.classList.add("active");
    } else {
      step2.classList.remove("completed");
      badge2.innerText = "⏳ មិនទាន់មាន";
      if (conn2) conn2.classList.remove("active");
    }
  }

  // Step 3: Voice
  const step3 = document.getElementById("stepIndicator3");
  const badge3 = document.getElementById("stepBadgeVoice");
  const conn3 = document.getElementById("connector3");
  if (step3 && badge3) {
    if (isAllVoiced) {
      step3.classList.add("completed");
      badge3.innerText = `✅ សំឡេងរួចរាល់ (${voicedCount}/${subCount})`;
      if (conn3) conn3.classList.add("active");
    } else if (hasVoice) {
      step3.classList.remove("completed");
      step3.classList.add("active");
      badge3.innerText = `⚡ ${voicedCount}/${subCount} បន្ទាត់`;
      if (conn3) conn3.classList.remove("active");
    } else {
      step3.classList.remove("completed");
      badge3.innerText = "⏳ មិនទាន់បង្កើត";
      if (conn3) conn3.classList.remove("active");
    }
  }

  // Step 4: Render
  const step4 = document.getElementById("stepIndicator4");
  const badge4 = document.getElementById("stepBadgeRender");
  if (step4 && badge4) {
    if (hasRender) {
      step4.classList.add("completed");
      badge4.innerText = "🎉 វីដេអូសម្រេច";
    } else {
      step4.classList.remove("completed");
      badge4.innerText = isAllVoiced ? "✨ រួចរាល់ Render" : "⏳ រង់ចាំ";
    }
  }

  // Floating Action Next-Step Guide Bar
  const guideBar = document.getElementById("floatingNextGuide");
  const guideIcon = document.getElementById("floatingGuideIcon");
  const guideText = document.getElementById("floatingGuideText");

  if (guideBar && guideIcon && guideText) {
    if (!hasMedia) {
      guideBar.style.display = "flex";
      guideIcon.innerText = "🎥";
      guideText.innerText = "ជំហានទី ១៖ សូម Upload វីដេអូ ឬសម្លេងដើម្បីចាប់ផ្តើម";
      gNextStepTarget = () => {
        switchTab("tabSubtitles");
        triggerVideoFileInput();
      };
    } else if (!hasSub) {
      guideBar.style.display = "flex";
      guideIcon.innerText = "📝";
      guideText.innerText = "ជំហានទី ២៖ សូមបញ្ចូល ឬ Import Subtitle SRT";
      gNextStepTarget = () => {
        switchTab("tabSubtitles");
        const srtInput = document.getElementById("srtFileInput");
        if (srtInput) srtInput.click();
      };
    } else if (!isAllVoiced) {
      guideBar.style.display = "flex";
      guideIcon.innerText = "🎙️";
      guideText.innerText = `ជំហានទី ៣៖ បង្កើតសំឡេងក្លូន (${voicedCount}/${subCount} រួចរាល់) →`;
      gNextStepTarget = () => {
        switchTab("tabVoice");
        const btnAll = document.querySelector("button[onclick*='startBatchTts']");
        if (btnAll) btnAll.scrollIntoView({ behavior: 'smooth', block: 'center' });
      };
    } else if (!hasRender) {
      guideBar.style.display = "flex";
      guideIcon.innerText = "🎬";
      guideText.innerText = "ជំហានទី ៤៖ សំឡេងរួចរាល់ ១០០%! ចុចដើម្បី Render វីដេអូ →";
      gNextStepTarget = () => {
        switchTab("tabRender");
        const btnRender = document.querySelector("button[onclick*='startRenderProcess']");
        if (btnRender) btnRender.scrollIntoView({ behavior: 'smooth', block: 'center' });
      };
    } else {
      guideBar.style.display = "none";
      gNextStepTarget = null;
    }
  }
}

function triggerNextStepAction() {
  if (typeof gNextStepTarget === "function") {
    gNextStepTarget();
  }
}

// Celebration Confetti (60fps canvas particles)
function fireCelebrationConfetti() {
  const canvas = document.getElementById("confettiCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.style.display = "block";
  canvas.style.opacity = "1";

  const confettiPieces = [];
  const colors = ["#38bdf8", "#818cf8", "#10b981", "#f59e0b", "#ec4899", "#a855f7", "#ffffff"];

  for (let i = 0; i < 110; i++) {
    confettiPieces.push({
      x: Math.random() * canvas.width,
      y: Math.random() * -canvas.height * 0.4,
      size: Math.random() * 8 + 4,
      color: colors[Math.floor(Math.random() * colors.length)],
      speedY: Math.random() * 4 + 2.5,
      speedX: (Math.random() - 0.5) * 3,
      rotation: Math.random() * 360,
      rotationSpeed: (Math.random() - 0.5) * 8
    });
  }

  const startTime = Date.now();

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const elapsed = Date.now() - startTime;

    confettiPieces.forEach(p => {
      p.y += p.speedY;
      p.x += p.speedX;
      p.rotation += p.rotationSpeed;

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate((p.rotation * Math.PI) / 180);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
      ctx.restore();
    });

    if (elapsed < 4000) {
      requestAnimationFrame(animate);
    } else {
      canvas.style.transition = "opacity 0.6s ease";
      canvas.style.opacity = "0";
      setTimeout(() => {
        canvas.style.display = "none";
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }, 600);
    }
  }

  animate();
}

// Tab Switcher with entrance animation and stepper sync
function switchTab(tabId) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".nav-tab").forEach(el => el.classList.remove("active"));
  
  const target = document.getElementById(tabId);
  if (target) {
    target.classList.add("active");
    target.style.animation = 'none';
    target.offsetHeight; // trigger reflow
    target.style.animation = 'tabEntrance 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards';
  }
  
  const btn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
  if (btn) btn.classList.add("active");
  
  // Highlight corresponding stepper step
  document.querySelectorAll(".step-item").forEach(s => s.classList.remove("active"));
  if (tabId === "tabSubtitles") {
    const s1 = document.getElementById("stepIndicator1");
    const s2 = document.getElementById("stepIndicator2");
    if (s1 && !s1.classList.contains("completed")) s1.classList.add("active");
    else if (s2) s2.classList.add("active");
  } else if (tabId === "tabVoice") {
    const s3 = document.getElementById("stepIndicator3");
    if (s3) s3.classList.add("active");
  } else if (tabId === "tabRender") {
    const s4 = document.getElementById("stepIndicator4");
    if (s4) s4.classList.add("active");
  }
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

let gNetworkPollInterval = null;

// 1. Network & Phone / Tablet / PC Access
async function loadNetworkInfo() {
  try {
    const res = await fetch("/api/network_info");
    const data = await res.json();
    const activeUrl = data.public_url || data.url;
    gCurrentNetworkUrl = activeUrl;
    
    const ipBadge = document.getElementById("ipBadge");
    if (ipBadge) {
      if (data.is_online) {
        ipBadge.innerText = "🌐 Online 4G/5G";
        ipBadge.style.background = "var(--success-color)";
      } else {
        ipBadge.innerText = "📶 WiFi";
        ipBadge.style.background = "#0284c7";
      }
    }
    
    // Set link in settings tab
    const phoneLink = document.getElementById("phoneUrlLink");
    if (phoneLink) {
      phoneLink.href = activeUrl;
      phoneLink.innerText = activeUrl;
    }
    
    // Set QR code in settings tab
    const qrContainer = document.getElementById("qrcodePhone");
    if (qrContainer && typeof QRCode !== "undefined") {
      qrContainer.innerHTML = "";
      new QRCode(qrContainer, {
        text: activeUrl,
        width: 170,
        height: 170
      });
    }
    
    // Modal QR
    const qrText = document.getElementById("qrModalUrlText");
    if (qrText) qrText.innerText = activeUrl;
    
    const modalQr = document.getElementById("qrcodeModal");
    if (modalQr && typeof QRCode !== "undefined") {
      modalQr.innerHTML = "";
      new QRCode(modalQr, {
        text: activeUrl,
        width: 210,
        height: 210
      });
    }

    // If not online yet, poll until tunnel establishes
    if (!data.is_online && !gNetworkPollInterval) {
      gNetworkPollInterval = setInterval(async () => {
        try {
          const checkRes = await fetch("/api/network_info");
          const checkData = await checkRes.json();
          if (checkData.is_online) {
            clearInterval(gNetworkPollInterval);
            gNetworkPollInterval = null;
            await loadNetworkInfo();
          }
        } catch (pollErr) {}
      }, 3000);
    }
  } catch (e) {
    console.error("Error loading network info:", e);
  }
}

function copyNetworkUrl() {
  const url = gCurrentNetworkUrl || (document.getElementById("qrModalUrlText") ? document.getElementById("qrModalUrlText").innerText : window.location.href);
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(() => {
      showCopyToast("បានចម្លងរួចរាល់! ✅");
    }).catch(() => fallbackCopy(url));
  } else {
    fallbackCopy(url);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
  showCopyToast("បានចម្លងរួចរាល់! ✅");
}

function showCopyToast(msg) {
  const btn = document.getElementById("btnCopyUrl");
  if (btn) {
    const orig = btn.innerHTML;
    btn.innerHTML = `✅ បានចម្លង!`;
    btn.style.background = "var(--success-color)";
    btn.style.color = "#fff";
    setTimeout(() => {
      btn.innerHTML = orig;
      btn.style.background = "";
      btn.style.color = "";
    }, 2500);
  }
}

function openQrModal() {
  const modal = document.getElementById("qrModal");
  if (modal) modal.style.display = "flex";
}

function closeQrModal() {
  const modal = document.getElementById("qrModal");
  if (modal) modal.style.display = "none";
}

// Drag and drop support for PC/Laptop/Tablet users
function initDragAndDrop() {
  const uploadBox = document.querySelector(".upload-box");
  if (!uploadBox) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    uploadBox.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
    }, false);
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    uploadBox.addEventListener(eventName, () => {
      uploadBox.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    uploadBox.addEventListener(eventName, () => {
      uploadBox.classList.remove('drag-active');
    }, false);
  });

  uploadBox.addEventListener('drop', e => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type.startsWith('video/') || file.type.startsWith('audio/') || file.name.match(/\.(mp4|mkv|mov|avi|webm|mp3|wav)$/i)) {
        const input = document.getElementById('videoFileInput');
        if (input) {
          input.files = files;
          handleVideoUpload(input);
        }
      } else if (file.name.endsWith('.srt')) {
        const input = document.getElementById('srtFileInput');
        if (input) {
          input.files = files;
          handleSrtUpload(input);
        }
      }
    }
  }, false);
}

// 2. Settings
function syncModelSelection(val) {
  if (document.getElementById("selectGeminiModel")) document.getElementById("selectGeminiModel").value = val;
  if (document.getElementById("quickGeminiModel")) document.getElementById("quickGeminiModel").value = val;
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gemini_model: val })
  });
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    gSettings = await res.json();
    
    if (gSettings.gemini_api_key) {
      document.getElementById("inputGeminiKey").value = gSettings.gemini_api_key;
    }
    if (gSettings.gemini_model) {
      const m = gSettings.gemini_model;
      if (document.getElementById("selectGeminiModel")) document.getElementById("selectGeminiModel").value = m;
      if (document.getElementById("quickGeminiModel")) document.getElementById("quickGeminiModel").value = m;
    }
    if (gSettings.voxcpm_space_id) {
      document.getElementById("inputVoxcpmUrl").value = gSettings.voxcpm_space_id;
    }
    if (gSettings.hf_token) {
      document.getElementById("inputHfToken").value = gSettings.hf_token;
    }
    if (gSettings.tts_provider) {
      selectTtsMode(gSettings.tts_provider);
    }
  } catch (e) {
    console.error("Error loading settings:", e);
  }
}

function parseTimeToSec(tStr) {
  if (!tStr) return 0;
  const parts = tStr.replace(',', '.').split(':');
  if (parts.length === 3) return parseFloat(parts[0]) * 3600 + parseFloat(parts[1]) * 60 + parseFloat(parts[2]);
  if (parts.length === 2) return parseFloat(parts[0]) * 60 + parseFloat(parts[1]);
  return parseFloat(parts[0]) || 0;
}

async function saveAppSettings() {
  const selectedModel = document.getElementById("selectGeminiModel").value;
  const payload = {
    gemini_api_key: document.getElementById("inputGeminiKey").value.trim(),
    gemini_model: selectedModel,
    voxcpm_space_id: document.getElementById("inputVoxcpmUrl").value.trim(),
    hf_token: document.getElementById("inputHfToken").value.trim(),
    tts_provider: gCurrentTtsMode
  };
  
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ រក្សាទុកការកំណត់ជោគជ័យ!");
      gSettings = data.settings;
    }
  } catch (e) {
    alert("❌ បរាជ័យក្នុងការរក្សាទុក: " + e.message);
  }
}

// 3. Voices & Voice Bank
async function loadVoices() {
  try {
    const res = await fetch("/api/voices");
    gVoices = await res.json();
    renderVoiceBank();
    renderSubtitles(); // re-render subtitle dropdowns
  } catch (e) {
    console.error("Error loading voices:", e);
  }
}

let gActiveEditCharId = null;
let gCharMode = "edge_tts";

function renderVoiceBank() {
  const container = document.getElementById("voiceBankGrid");
  container.innerHTML = "";
  
  gVoices.forEach(v => {
    const card = document.createElement("div");
    card.className = "voice-card";
    
    const isCloned = v.provider === "voxcpm" && v.ref_audio;
    const isCustomProfile = v.is_custom_profile;
    const isCustomized = v.is_customized;
    
    let badgeHtml = "";
    if (isCloned) {
      badgeHtml = `<span class="badge-clone-neon">⚡ VoxCPM Cloned</span>`;
    } else {
      badgeHtml = `<span class="badge-edge-clean">🌐 Edge-TTS</span>`;
    }
    
    let infoHtml = "";
    if (isCloned) {
      infoHtml = `<div class="voice-card-meta">🎵 គំរូ៖ <strong style="color:var(--accent-color)" title="${v.ref_audio}">${v.ref_audio.length > 22 ? v.ref_audio.substring(0, 20) + '...' : v.ref_audio}</strong></div>`;
    } else {
      const vSpeaker = v.voice_code ? (v.voice_code.includes('Piseth') ? 'Piseth (ប្រុស)' : 'Sreymom (ស្រី)') : 'Standard';
      infoHtml = `<div class="voice-card-meta">${vSpeaker} | Speed: ${v.rate || '+0%'} | Pitch: ${v.pitch || '+0Hz'}</div>`;
    }
    
    let previewBtn = "";
    if (isCloned) {
      previewBtn = `<button class="btn btn-sm btn-secondary" onclick="playRefAudio('${v.ref_audio}')" title="ស្តាប់សំឡេងគំរូ">▶️ ស្តាប់គំរូ</button>`;
    } else {
      previewBtn = `<button class="btn btn-sm btn-secondary" onclick="quickPreviewCharacter('${v.id}')" title="សាកល្បងស្តាប់">▶️ ស្តាប់</button>`;
    }
    
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; gap:6px;">
        <div class="voice-card-header">${v.name}</div>
        ${badgeHtml}
      </div>
      ${infoHtml}
      <div class="voice-card-actions" style="display:flex; gap:6px; margin-top:8px; flex-wrap:wrap;">
        <button class="btn btn-sm btn-primary" onclick="openEditCharModal('${v.id}')" style="flex:1;">
          ⚡ ផ្លាស់ប្តូរ / ក្លូន
        </button>
        ${previewBtn}
        ${isCustomized ? `<button class="btn btn-sm btn-outline" style="color:var(--danger-color)" onclick="resetCharacterToDefault('${v.id}')" title="កំណត់ទៅសភាពដើម">🔄 Reset</button>` : ''}
        ${isCustomProfile ? `<button class="btn btn-sm btn-outline" style="color:var(--danger-color)" onclick="deleteVoice('${v.id}')" title="លុបសំឡេង">🗑️</button>` : ''}
      </div>
    `;
    container.appendChild(card);
  });
}

async function openEditCharModal(charId) {
  gActiveEditCharId = charId;
  const v = gVoices.find(x => x.id === charId);
  if (!v) return;
  
  document.getElementById("editCharId").value = charId;
  document.getElementById("editCharTitle").innerText = `🎭 កែប្រែសំឡេង៖ ${v.name}`;
  
  // Load available samples into select
  const select = document.getElementById("charSelectRefSample");
  select.innerHTML = '<option value="">-- ជ្រើសរើសសំឡេងគំរូក្នុង Voice Bank --</option>';
  try {
    const res = await fetch("/api/voice_bank/samples");
    const samples = await res.json();
    samples.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.filename;
      opt.innerText = s.filename;
      if (v.ref_audio === s.filename) opt.selected = true;
      select.appendChild(opt);
    });
  } catch (e) {
    console.error(e);
  }
  
  // Set current mode
  const mode = v.provider === "voxcpm" ? "voxcpm" : "edge_tts";
  selectCharMode(mode);
  
  // Set Edge TTS fields
  if (v.voice_code) document.getElementById("charVoiceCode").value = v.voice_code;
  if (v.rate) {
    const rNum = parseInt(v.rate.replace('%', '').replace('+', '')) || 0;
    document.getElementById("inputCharRate").value = rNum;
    document.getElementById("valCharRate").innerText = (rNum >= 0 ? '+' : '') + rNum + '%';
  }
  if (v.pitch) {
    const pNum = parseInt(v.pitch.replace('Hz', '').replace('+', '')) || 0;
    document.getElementById("inputCharPitch").value = pNum;
    document.getElementById("valCharPitch").innerText = (pNum >= 0 ? '+' : '') + pNum + 'Hz';
  }
  
  // If has ref_audio, setup audio player
  if (v.ref_audio) {
    onCharSampleSelected(v.ref_audio);
  } else {
    document.getElementById("charAudioPreviewBox").style.display = "none";
  }
  
  document.getElementById("editCharModal").style.display = "flex";
}

function closeEditCharModal() {
  const p = document.getElementById("charSampleAudioPlayer");
  p.pause();
  document.getElementById("editCharModal").style.display = "none";
}

function selectCharMode(mode) {
  gCharMode = mode;
  document.getElementById("charModeClone").classList.toggle("active", mode === "voxcpm");
  document.getElementById("charModeEdge").classList.toggle("active", mode === "edge_tts");
  
  document.getElementById("charCloneSection").style.display = mode === "voxcpm" ? "block" : "none";
  document.getElementById("charEdgeSection").style.display = mode === "edge_tts" ? "block" : "none";
}

function onCharSampleSelected(val) {
  const box = document.getElementById("charAudioPreviewBox");
  const player = document.getElementById("charSampleAudioPlayer");
  if (val) {
    player.src = `/api/voice_bank/audio/${encodeURIComponent(val)}?t=${Date.now()}`;
    box.style.display = "block";
  } else {
    box.style.display = "none";
    player.pause();
  }
}

function previewUploadedSample(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    const url = URL.createObjectURL(file);
    const box = document.getElementById("charAudioPreviewBox");
    const player = document.getElementById("charSampleAudioPlayer");
    player.src = url;
    box.style.display = "block";
    player.play().catch(e => console.log(e));
  }
}

function playRefAudio(filename) {
  if (!filename) {
    alert("ពុំមានឯកសារសំឡេងគំរូឡើយ");
    return;
  }
  gAudio.src = `/api/voice_bank/audio/${encodeURIComponent(filename)}?t=${Date.now()}`;
  gAudio.play().catch(e => {
    alert("មិនអាចចាក់សំឡេងគំរូបានឡើយ៖ ឯកសារសំឡេងគំរូ (" + filename + ") មិនមាននៅលើ Server នេះទេ។ ប្រសិនបើអ្នកកំពុងប្រើប្រាស់ Render.com សូមប្តូរមកប្រើតាម Link Cloudflare លើកុំព្យូទ័រផ្ទាល់របស់អ្នកវិញ ព្រោះឯកសារសំឡេងទាំងអស់ស្ថិតនៅលើកុំព្យូទ័រនេះ។");
  });
}

async function quickPreviewCharacter(charId) {
  const v = gVoices.find(x => x.id === charId);
  const text = v ? `សួស្តី នេះជាសំឡេង ${v.name}` : "សួស្តី នេះជាសំឡេងគំរូរបស់ខ្ញុំ";
  
  try {
    const res = await fetch("/api/voice_bank/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ char_id: charId, text })
    });
    const data = await res.json();
    if (data.success) {
      gAudio.src = data.audio_url;
      gAudio.play();
    } else {
      alert("❌ " + (data.error || "បរាជ័យ"));
    }
  } catch (e) {
    alert("កំហុស: " + e.message);
  }
}

async function testCharacterPreview() {
  const charId = gActiveEditCharId || "narrator_male";
  const text = document.getElementById("charPreviewText").value.trim() || "សួស្តី នេះជាការសាកល្បងសំឡេងរបស់ខ្ញុំ";
  const btn = document.getElementById("btnTestCharVoice");
  btn.innerText = "⏳ កំពុងបង្កើត...";
  
  const payload = {
    char_id: charId,
    text: text,
    provider: gCharMode
  };
  
  if (gCharMode === "voxcpm") {
    payload.ref_audio = document.getElementById("charSelectRefSample").value;
  } else {
    payload.voice_code = document.getElementById("charVoiceCode").value;
    const r = parseInt(document.getElementById("inputCharRate").value) || 0;
    const p = parseInt(document.getElementById("inputCharPitch").value) || 0;
    payload.rate = (r >= 0 ? '+' : '') + r + '%';
    payload.pitch = (p >= 0 ? '+' : '') + p + 'Hz';
  }
  
  try {
    const res = await fetch("/api/voice_bank/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      const p = document.getElementById("charSampleAudioPlayer");
      document.getElementById("charAudioPreviewBox").style.display = "block";
      p.src = data.audio_url;
      p.play().catch(e => console.log(e));
    } else {
      alert("❌ បរាជ័យក្នុងការសាកល្បង: " + (data.error || ""));
    }
  } catch (e) {
    alert("កំហុស: " + e.message);
  } finally {
    btn.innerText = "▶️ សាកល្បងស្តាប់";
  }
}

async function saveCharacterChanges() {
  const charId = gActiveEditCharId;
  const fd = new FormData();
  fd.append("char_id", charId);
  fd.append("provider", gCharMode);
  
  if (gCharMode === "voxcpm") {
    const refSelect = document.getElementById("charSelectRefSample").value;
    const fileInput = document.getElementById("charUploadRefAudio");
    
    if (fileInput.files.length) {
      fd.append("audio_file", fileInput.files[0]);
    } else if (refSelect) {
      fd.append("ref_audio", refSelect);
    } else {
      alert("សូមជ្រើសរើស ឬ Upload សំឡេងគំរូសម្រាប់ Clone!");
      return;
    }
  } else {
    fd.append("voice_code", document.getElementById("charVoiceCode").value);
    const r = parseInt(document.getElementById("inputCharRate").value) || 0;
    const p = parseInt(document.getElementById("inputCharPitch").value) || 0;
    fd.append("rate", (r >= 0 ? '+' : '') + r + '%');
    fd.append("pitch", (p >= 0 ? '+' : '') + p + 'Hz');
  }
  
  try {
    const res = await fetch("/api/voice_bank/update_character", {
      method: "POST",
      body: fd
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ បានផ្លាស់ប្តូរសំឡេងតួអង្គជោគជ័យ!");
      closeEditCharModal();
      await loadVoices();
    }
  } catch (e) {
    alert("❌ បរាជ័យ: " + e.message);
  }
}

async function resetCharacterToDefault(charIdParam) {
  const charId = charIdParam || gActiveEditCharId;
  if (!confirm("តើអ្នកចង់កំណត់សំឡេងតួអង្គនេះត្រឡប់ទៅសភាពដើមវិញមែនទេ?")) return;
  
  try {
    const res = await fetch("/api/voice_bank/reset_character", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ char_id: charId })
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ បានកំណត់ត្រឡប់ទៅសភាពដើមវិញជោគជ័យ!");
      closeEditCharModal();
      await loadVoices();
    }
  } catch (e) {
    alert("❌ " + e.message);
  }
}

function openAddVoiceModal() {
  document.getElementById("addVoiceModal").style.display = "flex";
}

function closeAddVoiceModal() {
  document.getElementById("addVoiceModal").style.display = "none";
}

async function submitNewClonedVoice() {
  const name = document.getElementById("newVoiceName").value.trim();
  const vid = document.getElementById("newVoiceId").value.trim() || `voice_${Date.now()}`;
  const fileInput = document.getElementById("newVoiceAudio");
  
  if (!name) {
    alert("សូមបញ្ចូលឈ្មោះសំឡេង!");
    return;
  }
  if (!fileInput.files.length) {
    alert("សូមជ្រើសរើសឯកសារសំឡេងគំរូ!");
    return;
  }
  
  const fd = new FormData();
  fd.append("name", name);
  fd.append("voice_id", vid);
  fd.append("audio_file", fileInput.files[0]);
  
  try {
    const res = await fetch("/api/voice_bank/upload", {
      method: "POST",
      body: fd
    });
    const data = await res.json();
    if (data.success) {
      alert("✅ បញ្ចូលសំឡេងគំរូជោគជ័យ!");
      closeAddVoiceModal();
      await loadVoices();
    }
  } catch (e) {
    alert("❌ បរាជ័យ: " + e.message);
  }
}

async function deleteVoice(vid) {
  if (!confirm("តើអ្នកពិតជាចង់លុបសំឡេងនេះមែនទេ?")) return;
  try {
    const res = await fetch(`/api/voice_bank/${vid}`, { method: "DELETE" });
    const data = await res.json();
    if (data.success) {
      await loadVoices();
    }
  } catch (e) {
    alert("កំហុស: " + e.message);
  }
}

// 4. Session State & Video Upload
async function loadSessionState() {
  try {
    const res = await fetch(`/api/session_state?session_id=${gSessionId}`);
    const state = await res.json();
    
    if (state.video_name) {
      document.getElementById("videoFileName").innerText = state.video_name;
      document.getElementById("videoDuration").innerText = `ប្រវែង: ${Math.round(state.duration || 0)} វិនាទី`;
      
      const vPlayer = document.getElementById("sourceVideoPlayer");
      vPlayer.src = `/api/media/video?session_id=${gSessionId}`;
      document.getElementById("videoPreviewWrap").style.display = "block";
    }
    
    if (state.subtitles && state.subtitles.length > 0) {
      gSubtitles = state.subtitles;
      renderSubtitles();
    }

    if (state.logo_url) {
      const wrap = document.getElementById("logoPreviewWrap");
      const img = document.getElementById("logoPreviewImg");
      const fn = document.getElementById("logoFileName");
      if (wrap && img && fn) {
        img.src = state.logo_url;
        fn.innerText = state.logo_name || "Logo";
        wrap.style.display = "flex";
      }
    }

    if (state.has_rendered_video) {
      const vPlayer = document.getElementById("renderedVideoPlayer");
      if (vPlayer) {
        const vUrl = `/api/media/rendered_video?session_id=${gSessionId}&t=${Date.now()}`;
        const aUrl = `/api/media/master_dub?session_id=${gSessionId}&t=${Date.now()}`;
        vPlayer.src = vUrl;
        const btnV = document.getElementById("btnDownloadVideo");
        const btnA = document.getElementById("btnDownloadAudio");
        if (btnV) btnV.href = vUrl;
        if (btnA) btnA.href = aUrl;
        const resWrap = document.getElementById("renderedResultWrap");
        if (resWrap) resWrap.style.display = "block";
      }

      // Master Dub Card in Voice Tab
      const masterCard = document.getElementById("masterAudioCard");
      const masterPlayer = document.getElementById("masterDubAudioPlayer");
      const masterDownload = document.getElementById("btnDownloadMasterDub");
      if (masterCard && masterPlayer && masterDownload) {
        const aUrl = `/api/media/master_dub?session_id=${gSessionId}&t=${Date.now()}`;
        masterPlayer.src = aUrl;
        masterDownload.href = aUrl;
        masterCard.style.display = "block";
      }
    }

    if (state.has_bgm) {
      updateBgmUI({
        has_bgm: true,
        bgm_url: state.bgm_url,
        vocals_url: state.vocals_url,
        video_bgm_url: state.video_bgm_url
      });
    }

    updateWorkflowStepper();
  } catch (e) {
    console.error("Error loading session:", e);
  }
}

function triggerVideoFileInput() {
  const box = document.getElementById("videoUploadBox");
  if (box && box.classList.contains("is-uploading")) return;
  const input = document.getElementById("videoFileInput");
  if (input) input.click();
}

function handleVideoUpload(input) {
  if (!input.files || !input.files.length) return;
  const file = input.files[0];
  
  if (file.size > 98 * 1024 * 1024 && window.location.hostname.includes("trycloudflare.com")) {
    alert("⚠️ ឯកសារវីដេអូនេះមានទំហំធំជាង 100MB (កម្រិតកំណត់របស់ Cloudflare)។ សូមបញ្ចូលវីដេអូក្រោម 100MB ឬប្រើប្រាស់តាម WiFi IP!");
    input.value = "";
    return;
  }
  
  const uploadBox = document.getElementById("videoUploadBox");
  const uploadIcon = document.getElementById("videoUploadIcon");
  const fileNameEl = document.getElementById("videoFileName");
  const fileDurEl = document.getElementById("videoDuration");
  const progressWrap = document.getElementById("videoUploadProgressWrap");
  const progressMsg = document.getElementById("videoUploadProgressMsg");
  const progressBar = document.getElementById("videoUploadProgressBar");
  const progressPct = document.getElementById("videoUploadProgressPct");
  
  const fileSizeMb = (file.size / (1024 * 1024)).toFixed(1);

  // Set UI to loading state
  if (uploadBox) uploadBox.classList.add("is-uploading");
  if (uploadIcon) uploadIcon.innerHTML = `<span class="spinner-inline" style="width:26px; height:26px; border-width:3px; margin:0;"></span>`;
  if (fileNameEl) fileNameEl.innerText = "⏳ កំពុង Upload: " + file.name;
  if (fileDurEl) fileDurEl.innerText = `ទំហំឯកសារ៖ ${fileSizeMb} MB`;
  
  if (progressWrap) progressWrap.style.display = "block";
  if (progressBar) progressBar.style.width = "0%";
  if (progressPct) progressPct.innerText = "0%";
  if (progressMsg) progressMsg.innerHTML = `<span class="spinner-inline"></span> កំពុងចាប់ផ្តើម Upload (${fileSizeMb} MB)...`;
  
  const fd = new FormData();
  fd.append("file", file);
  fd.append("session_id", gSessionId);
  
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload_media");
  
  xhr.upload.onprogress = function(e) {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      const loadedMb = (e.loaded / (1024 * 1024)).toFixed(1);
      const totalMb = (e.total / (1024 * 1024)).toFixed(1);
      
      if (progressBar) progressBar.style.width = pct + "%";
      if (progressPct) progressPct.innerText = pct + "%";
      
      if (pct < 100) {
        if (progressMsg) {
          progressMsg.innerHTML = `<span class="spinner-inline"></span> កំពុង Upload វីដេអូ (${loadedMb}MB / ${totalMb}MB)...`;
        }
      } else {
        if (progressMsg) {
          progressMsg.innerHTML = `<span class="spinner-inline"></span> ទទួលបានទិន្នន័យពេញលេញ កំពុងពិនិត្យវីដេអូលើ Server...`;
        }
      }
    }
  };
  
  xhr.onload = function() {
    if (uploadBox) uploadBox.classList.remove("is-uploading");
    if (uploadIcon) uploadIcon.innerHTML = "🎥";
    
    if (xhr.status === 200) {
      try {
        const data = JSON.parse(xhr.responseText);
        if (data.success) {
          if (progressBar) progressBar.style.width = "100%";
          if (progressPct) progressPct.innerText = "100%";
          if (progressMsg) progressMsg.innerHTML = "✅ Upload វីដេអូជោគជ័យ!";
          
          if (fileNameEl) fileNameEl.innerText = data.filename;
          if (fileDurEl) fileDurEl.innerText = `ប្រវែង: ${Math.round(data.duration)} វិនាទី (${fileSizeMb} MB)`;
          
          const vPlayer = document.getElementById("sourceVideoPlayer");
          if (vPlayer) vPlayer.src = data.media_url;
          const previewWrap = document.getElementById("videoPreviewWrap");
          if (previewWrap) previewWrap.style.display = "block";
          
          showToast("✅ Upload វីដេអូជោគជ័យ!", "success");
          resetVocalSepUI();
          updateWorkflowStepper();
          
          setTimeout(() => {
            if (progressWrap) progressWrap.style.display = "none";
          }, 2000);
        } else {
          if (progressWrap) progressWrap.style.display = "none";
          showToast("❌ " + (data.error || "បរាជ័យក្នុងការ Upload"), "error");
          if (fileNameEl) fileNameEl.innerText = "ជ្រើសរើសវីដេអូ (MP4 / MKV)";
        }
      } catch (err) {
        if (progressWrap) progressWrap.style.display = "none";
        showToast("❌ កំហុសឆ្លើយតបពី Server: " + err.message, "error");
        if (fileNameEl) fileNameEl.innerText = "ជ្រើសរើសវីដេអូ (MP4 / MKV)";
      }
    } else {
      if (progressWrap) progressWrap.style.display = "none";
      if (xhr.status === 413) {
        showToast("⚠️ ទំហំវីដេអូធំជាង 100MB (Cloudflare Limit)។ សូម Upload វីដេអូក្រោម 100MB ឬប្រើប្រាស់តាម WiFi IP!", "warning", 6000);
      } else if (xhr.status === 502 || xhr.status === 530) {
        showToast("⚠️ តំណភ្ជាប់ Tunnel ចាស់បានផុតកំណត់ដោយសារ Server បាន Restart។ សូម Refresh ទំព័រឡើងវិញ!", "warning", 6000);
      } else {
        showToast(`❌ Server error: Status ${xhr.status}`, "error");
      }
      if (fileNameEl) fileNameEl.innerText = "ជ្រើសរើសវីដេអូ (MP4 / MKV)";
    }
    input.value = "";
  };
  
  xhr.onerror = function() {
    if (uploadBox) uploadBox.classList.remove("is-uploading");
    if (uploadIcon) uploadIcon.innerHTML = "🎥";
    if (progressWrap) progressWrap.style.display = "none";
    showToast("❌ បរាជ័យក្នុងការតភ្ជាប់បណ្តាញពេល Upload វីដេអូ!", "error");
    if (fileNameEl) fileNameEl.innerText = "ជ្រើសរើសវីដេអូ (MP4 / MKV)";
    input.value = "";
  };
  
  xhr.send(fd);
}

async function handleSrtUpload(input) {
  if (!input.files.length) return;
  const file = input.files[0];
  
  const fd = new FormData();
  fd.append("file", file);
  fd.append("session_id", gSessionId);
  
  try {
    const res = await fetch("/api/upload_srt", {
      method: "POST",
      body: fd
    });
    if (!res.ok) {
      const errText = await res.text();
      if (errText.includes("<html>") || res.status === 502 || res.status === 530) {
        throw new Error("តំណភ្ជាប់ Tunnel ចាស់បានផុតកំណត់។ សូម Refresh ទំព័រឡើងវិញ ឬបើកតាម Link ថ្មី!");
      }
      throw new Error(`Server code ${res.status}`);
    }
    const data = await res.json();
    if (data.success) {
      gSubtitles = data.subtitles;
      renderSubtitles();
      showToast(`✅ បានបញ្ចូល Subtitle ចំនួន ${data.count} បន្ទាត់!`, "success");
      updateWorkflowStepper();
    } else {
      showToast("❌ " + (data.error || "បរាជ័យ"), "error");
    }
  } catch (e) {
    showToast("❌ កំហុសបញ្ចូល SRT: " + e.message, "error");
  }
}

// 5. Raw Text Modal
function openRawTextModal() {
  document.getElementById("rawTextModal").style.display = "flex";
}

function closeRawTextModal() {
  document.getElementById("rawTextModal").style.display = "none";
}

async function submitRawText() {
  const text = document.getElementById("rawTextContent").value.trim();
  if (!text) {
    alert("សូមបញ្ចូលអត្ថបទជាមុនសិន!");
    return;
  }
  
  const submitBtn = document.querySelector("#rawTextModal .btn-primary");
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerText = "⏳ កំពុងដំណើរការ...";
  }
  
  try {
    const res = await fetch("/api/parse_text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: gSessionId, text })
    });
    
    if (!res.ok) {
      if (res.status === 502 || res.status === 503 || res.status === 530) {
        throw new Error("តំណភ្ជាប់ចាស់នេះបានផុតកំណត់ ឬ Server ត្រូវបាន Restart។ សូមបើក Link ថ្មី ឬ Refresh ទំព័រឡើងវិញ!");
      }
      const errText = await res.text();
      if (errText.includes("<html") || errText.includes("<!DOCTYPE")) {
        throw new Error("តំណភ្ជាប់ចាស់នេះបានផុតកំណត់។ សូមបើក Link ថ្មី ឬ Refresh ទំព័រឡើងវិញ!");
      }
      throw new Error(`Server Error (${res.status}): ${errText}`);
    }

    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      const rawBody = await res.text();
      if (rawBody.includes("<html") || rawBody.includes("<!DOCTYPE")) {
        throw new Error("តំណភ្ជាប់ចាស់នេះបានផុតកំណត់ ឬ Server ត្រូវបាន Restart។ សូមបើក Link ថ្មី ឬ Refresh ទំព័រឡើងវិញ!");
      }
      throw new Error("ការឆ្លើយតបពី Server មិនត្រឹមត្រូវ!");
    }

    const data = await res.json();
    if (data.success) {
      gSubtitles = data.subtitles;
      renderSubtitles();
      closeRawTextModal();
      alert(`✅ បង្កើតបាន ${data.count} បន្ទាត់ Subtitle!`);
    } else {
      alert("❌ " + (data.error || "មិនអាចបំប្លែងអត្ថបទបានឡើយ"));
    }
  } catch (e) {
    const msg = e.message || String(e);
    if (msg.includes("pattern") || msg.includes("token") || msg.includes("JSON") || msg.includes("SyntaxError")) {
      alert("❌ តំណភ្ជាប់ Public Link ចាស់នេះបានផុតកំណត់ហើយ! សូមប្រើប្រាស់តំណភ្ជាប់ Public Link ថ្មីចុងក្រោយ ឬ Refresh ទំព័រឡើងវិញ។");
    } else {
      alert("❌ កំហុស: " + msg);
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = "យល់ព្រម បញ្ចូល";
    }
  }
}

// 6. AI Transcribe with Gemini
async function triggerAiTranscribe() {
  if (!confirm("តើអ្នកចង់ឱ្យ AI Transcribe និងបកប្រែជាភាសាខ្មែរដោយស្វ័យប្រវត្តិមែនទេ?")) return;
  
  const progressWrap = document.getElementById("transcribeProgressWrap");
  const progressMsg = document.getElementById("transcribeProgressMsg");
  const progressBar = document.getElementById("transcribeProgressBar");
  const progressPct = document.getElementById("transcribeProgressPct");
  
  progressWrap.style.display = "block";
  progressBar.style.width = "10%";
  progressMsg.innerText = "កំពុងចាប់ផ្តើម AI Transcribe...";
  progressPct.innerText = "10%";
  
  const selectedModel = document.getElementById("quickGeminiModel") ? document.getElementById("quickGeminiModel").value : "gemini-3.8-flash";

  try {
    const res = await fetch("/api/transcribe_ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: gSessionId, mode: "dubbing", model: selectedModel })
    });
    const data = await res.json();
    if (!data.success) {
      alert("❌ " + (data.error || "បរាជ័យក្នុងការចាប់ផ្តើម"));
      progressWrap.style.display = "none";
      return;
    }
    
    // Poll progress
    const pollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`/api/transcribe_progress?session_id=${encodeURIComponent(gSessionId)}`);
        const pData = await pRes.json();
        
        progressBar.style.width = pData.percent + "%";
        progressPct.innerText = pData.percent + "%";
        progressMsg.innerText = pData.message;
        
        if (!pData.is_running) {
          clearInterval(pollInterval);
          if (pData.percent === 100) {
            await loadSessionState();
            setTimeout(() => { progressWrap.style.display = "none"; }, 3000);
          }
        }
      } catch (err) {
        clearInterval(pollInterval);
      }
    }, 1500);
    
  } catch (e) {
    alert("❌ កំហុស: " + e.message);
    progressWrap.style.display = "none";
  }
}

// 7. Subtitles List Rendering & Editing
function renderSubtitles() {
  const container = document.getElementById("subtitlesList");
  document.getElementById("subCount").innerText = gSubtitles.length;
  
  if (!gSubtitles.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📝</div>
        <p>មិនទាន់មាន Subtitle ឡើយ</p>
        <span>សូមបញ្ចូលវីដេអូ រួចចុច "AI Transcribe" ឬចុច "បិទភ្ជាប់ Raw Text"</span>
      </div>
    `;
    updateWorkflowStepper();
    return;
  }
  
  container.innerHTML = "";
  
  gSubtitles.forEach((seg, idx) => {
    const card = document.createElement("div");
    card.className = `sub-item-card ${seg.has_audio ? 'has-audio' : ''}`;
    card.id = `subCard_${idx}`;
    
    // Generate voice options
    let voiceOptions = "";
    gVoices.forEach(v => {
      const isCloned = v.provider === "voxcpm" && v.ref_audio;
      const cloneBadge = isCloned ? "⚡ [Clone] " : "";
      const sel = (seg.voice === v.id) ? "selected" : "";
      voiceOptions += `<option value="${v.id}" ${sel}>${cloneBadge}${v.name}</option>`;
    });
    
    card.innerHTML = `
      <div class="sub-header-row">
        <div style="display:flex; align-items:center;">
          <span class="sub-num-badge">#${idx + 1}</span>
        </div>
        <div class="sub-times">
          <input type="text" class="sub-time-input" value="${seg.start}" onchange="updateSubTime(${idx}, 'start', this.value)">
          <span>➔</span>
          <input type="text" class="sub-time-input" value="${seg.end}" onchange="updateSubTime(${idx}, 'end', this.value)">
        </div>
      </div>
      <textarea class="sub-text-input" rows="2" onchange="updateSubText(${idx}, this.value)">${seg.text}</textarea>
      <div class="sub-footer-row">
        <select class="voice-select" onchange="updateSubVoice(${idx}, this.value)">
          ${voiceOptions}
        </select>
        <div class="sub-actions">
          <button class="btn btn-sm btn-secondary" onclick="playVoiceAudio(${idx})" id="btnPlay_${idx}">
            ${seg.has_audio ? '▶️ ស្តាប់' : '🔇 គ្មានសំឡេង'}
          </button>
          <button class="btn btn-sm btn-outline" onclick="generateSingleVoice(${idx})" title="បង្កើតសំឡេងបន្ទាត់នេះ">
            ⚡ បង្កើត
          </button>
          <button class="btn btn-sm btn-outline" style="color:var(--danger-color)" onclick="deleteSubLine(${idx})" title="លុបបន្ទាត់">
            ✕
          </button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
  updateWorkflowStepper();
}

function updateSubText(idx, val) {
  if (gSubtitles[idx]) {
    gSubtitles[idx].text = val;
    gSubtitles[idx].has_audio = false; // reset audio when text changes
    saveSubtitlesToServer();
  }
}

function updateSubTime(idx, field, val) {
  if (gSubtitles[idx]) {
    gSubtitles[idx][field] = val;
    saveSubtitlesToServer();
  }
}

function updateSubVoice(idx, val) {
  if (gSubtitles[idx]) {
    gSubtitles[idx].voice = val;
    gSubtitles[idx].has_audio = false;
    saveSubtitlesToServer();
  }
}

function deleteSubLine(idx) {
  gSubtitles.splice(idx, 1);
  // re-index
  gSubtitles.forEach((s, i) => s.index = i);
  renderSubtitles();
  saveSubtitlesToServer();
}

function addNewSubtitleLine() {
  const last = gSubtitles[gSubtitles.length - 1];
  const newStart = last ? last.end : "00:00:00,000";
  const newSeg = {
    index: gSubtitles.length,
    start: newStart,
    end: "00:00:03,000",
    text: "...",
    voice: "narrator_male",
    has_audio: false
  };
  gSubtitles.push(newSeg);
  renderSubtitles();
  saveSubtitlesToServer();
}

async function saveSubtitlesToServer() {
  try {
    await fetch("/api/update_subtitles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: gSessionId, subtitles: gSubtitles })
    });
  } catch (e) {
    console.error("Save subtitles error:", e);
  }
}

function downloadSrtFile() {
  window.open(`/api/export_srt?session_id=${gSessionId}`, "_blank");
}

function playVoiceAudio(idx) {
  gAudio.src = `/api/media/voice/${idx}?session_id=${gSessionId}&t=${Date.now()}`;
  gAudio.play().catch(e => {
    alert("មិនទាន់បានបង្កើតសំឡេងបន្ទាត់នេះទេ! សូមចុច '⚡ បង្កើត'");
  });
}

async function generateSingleVoice(idx) {
  const btn = document.getElementById(`btnPlay_${idx}`);
  if (btn) btn.innerText = "⏳ កំពុងបង្កើត...";
  
  try {
    const res = await fetch("/api/generate_voice_single", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: gSessionId,
        index: idx,
        text: gSubtitles[idx].text,
        voice: gSubtitles[idx].voice
      })
    });
    const data = await res.json();
    if (data.success) {
      gSubtitles[idx].has_audio = true;
      renderSubtitles();
      playVoiceAudio(idx);
      showToast(`✅ បង្កើតសំឡេងបន្ទាត់ #${idx + 1} ជោគជ័យ!`, "success");
      updateWorkflowStepper();
    } else {
      showToast("❌ បរាជ័យ: " + (data.error || "Unknown error"), "error");
      renderSubtitles();
    }
  } catch (e) {
    showToast("កំហុស: " + e.message, "error");
    renderSubtitles();
  }
}

// 8. TTS Modes & Batch Generation
function selectTtsMode(mode) {
  gCurrentTtsMode = mode;
  document.querySelectorAll(".mode-card").forEach(el => el.classList.remove("active"));
  
  if (mode === "voxcpm") {
    document.getElementById("modeVoxcpm").classList.add("active");
  } else {
    document.getElementById("modeEdgeTts").classList.add("active");
  }
  
  // Update setting on server
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tts_provider: mode })
  });
}

async function startBatchTts(force = false) {
  if (!gSubtitles.length) {
    alert("មិនទាន់មាន Subtitle ទេ! សូមបញ្ចូល Subtitle ជាមុនសិន។");
    return;
  }
  
  const progressWrap = document.getElementById("ttsProgressWrap");
  const progressMsg = document.getElementById("ttsProgressMsg");
  const progressBar = document.getElementById("ttsProgressBar");
  const progressPct = document.getElementById("ttsProgressPct");
  
  progressWrap.style.display = "block";
  progressBar.style.width = "5%";
  progressPct.innerText = "5%";
  progressMsg.innerText = "កំពុងចាប់ផ្តើមបង្កើតសំឡេង...";
  
  try {
    const res = await fetch("/api/generate_voice_batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: gSessionId, force })
    });
    
    if (!res.ok) {
      if (res.status === 502 || res.status === 503 || res.status === 530) {
        throw new Error("⚠️ តំណភ្ជាប់បានផុតកំណត់ ឬ Server ត្រូវបានផ្អាក។ សូមបើក Link ថ្មី ឬ Refresh ទំព័រឡើងវិញ!");
      }
      const errTxt = await res.text().catch(() => "");
      if (errTxt.includes("<html") || errTxt.includes("<!DOCTYPE")) {
        throw new Error("⚠️ តំណភ្ជាប់នេះបានផុតកំណត់។ សូមបើក Link ថ្មី ឬ Refresh ទំព័រឡើងវិញ!");
      }
      throw new Error(`Server Error (${res.status}): ${errTxt}`);
    }

    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error("⚠️ ការឆ្លើយតបពី Server មិនត្រឹមត្រូវ។ សូម Refresh ទំព័រឡើងវិញ!");
    }

    const data = await res.json();
    if (!data.success) {
      alert("❌ " + (data.error || "បរាជ័យ"));
      progressWrap.style.display = "none";
      return;
    }
    
    // Poll progress
    const pollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`/api/tts_progress?session_id=${encodeURIComponent(gSessionId)}`);
        if (!pRes.ok) return;
        const pData = await pRes.json();
        
        progressBar.style.width = pData.percent + "%";
        progressPct.innerText = pData.percent + "%";
        progressMsg.innerText = pData.message;
        
        // Highlight active card
        if (pData.active_index >= 0) {
          const card = document.getElementById(`subCard_${pData.active_index}`);
          if (card) {
            document.querySelectorAll(".sub-item-card").forEach(c => c.style.boxShadow = "none");
            card.style.boxShadow = "0 0 12px var(--accent-color)";
          }
        }
        
        if (!pData.is_running) {
          clearInterval(pollInterval);
          await loadSessionState();
          showToast("🎉 បង្កើតសំឡេងក្លូនរួចរាល់ទាំងអស់!", "success", 4500);
          updateWorkflowStepper();
          setTimeout(() => { progressWrap.style.display = "none"; }, 3500);
        }
      } catch (err) {
        clearInterval(pollInterval);
      }
    }, 1200);
    
  } catch (e) {
    const msg = e.message || String(e);
    if (msg.includes("pattern") || msg.includes("token") || msg.includes("JSON") || msg.includes("SyntaxError")) {
      showToast("⚠️ តំណភ្ជាប់ Public Link បានផុតកំណត់ហើយ! សូម Refresh ទំព័រឡើងវិញ។", "warning", 6000);
    } else {
      showToast("កំហុស: " + msg, "error");
    }
    progressWrap.style.display = "none";
  }
}

// 9. Video Effects Controls
function toggleEffectOption(effectType) {
  if (effectType === "blur") {
    const chk = document.getElementById("checkEffectBlur");
    const body = document.getElementById("effectBodyBlur");
    const card = document.getElementById("effectCardBlur");
    if (chk && body && card) {
      body.style.display = chk.checked ? "block" : "none";
      card.classList.toggle("active", chk.checked);
    }
  } else if (effectType === "text") {
    const chk = document.getElementById("checkEffectText");
    const body = document.getElementById("effectBodyText");
    const card = document.getElementById("effectCardText");
    if (chk && body && card) {
      body.style.display = chk.checked ? "block" : "none";
      card.classList.toggle("active", chk.checked);
    }
  } else if (effectType === "logo") {
    const chk = document.getElementById("checkEffectLogo");
    const body = document.getElementById("effectBodyLogo");
    const card = document.getElementById("effectCardLogo");
    if (chk && body && card) {
      body.style.display = chk.checked ? "block" : "none";
      card.classList.toggle("active", chk.checked);
    }
  }
}

async function handleLogoUpload(input) {
  if (!input.files || !input.files.length) return;
  const file = input.files[0];
  const fd = new FormData();
  fd.append("file", file);
  fd.append("session_id", gSessionId);
  
  try {
    const res = await fetch("/api/upload_logo", {
      method: "POST",
      body: fd
    });
    const data = await res.json();
    if (data.success) {
      const wrap = document.getElementById("logoPreviewWrap");
      const img = document.getElementById("logoPreviewImg");
      const fn = document.getElementById("logoFileName");
      if (wrap && img && fn) {
        img.src = data.logo_url;
        fn.innerText = data.logo_name;
        wrap.style.display = "flex";
      }
      const chk = document.getElementById("checkEffectLogo");
      if (chk && !chk.checked) {
        chk.checked = true;
        toggleEffectOption("logo");
      }
    } else {
      alert("❌ " + (data.error || "មិនអាច Upload Logo បានទេ"));
    }
  } catch (err) {
    alert("❌ កំហុស Upload Logo: " + err.message);
  }
}

async function removeLogo() {
  try {
    await fetch(`/api/delete_logo?session_id=${gSessionId}`, { method: "DELETE" });
    const wrap = document.getElementById("logoPreviewWrap");
    const img = document.getElementById("logoPreviewImg");
    const input = document.getElementById("inputLogoFile");
    if (wrap) wrap.style.display = "none";
    if (img) img.src = "";
    if (input) input.value = "";
  } catch (err) {
    console.error("Error removing logo:", err);
  }
}

// 10. Video Rendering
async function startRenderVideo() {
  const progressWrap = document.getElementById("renderProgressWrap");
  const progressMsg = document.getElementById("renderProgressMsg");
  const progressBar = document.getElementById("renderProgressBar");
  const progressPct = document.getElementById("renderProgressPct");
  
  // 1. Validate if video is uploaded
  const videoPlayer = document.getElementById("sourceVideoPlayer");
  const videoFileName = document.getElementById("videoFileName")?.innerText || "";
  const isVideoLoaded = videoPlayer && videoPlayer.src && 
                        !videoPlayer.src.endsWith("#") && 
                        document.getElementById("videoPreviewWrap") && 
                        document.getElementById("videoPreviewWrap").style.display !== "none" &&
                        !videoFileName.includes("មិនទាន់");

  if (!isVideoLoaded) {
    alert("⚠️ សូមបញ្ចូលឯកសារវីដេអូដើម (Upload Video) នៅផ្ទាំងទី ១ ជាមុនសិន មុននឹងចាប់ផ្តើម Render!");
    if (typeof switchTab === "function") {
      switchTab("tabMedia");
    }
    const upBox = document.getElementById("videoUploadBox");
    if (upBox) upBox.scrollIntoView({ behavior: 'smooth' });
    return;
  }

  // 2. Validate if subtitles exist
  if (!gSubtitles || !gSubtitles.length) {
    alert("⚠️ មិនទាន់មាន Subtitle សម្រាប់បញ្ចូលក្នុងវីដេអូឡើយ! សូមបញ្ចូល Subtitle ជាមុនសិន។");
    if (typeof switchTab === "function") {
      switchTab("tabSubtitle");
    }
    return;
  }

  progressWrap.style.display = "block";
  progressBar.style.width = "10%";
  progressPct.innerText = "10%";
  progressMsg.innerText = "កំពុងរៀបចំ Render វីដេអូ និង Effect...";
  
  const effectsPayload = {
    blur: {
      enabled: document.getElementById("checkEffectBlur")?.checked || false,
      strength: parseInt(document.getElementById("inputBlurStrength")?.value) || 5
    },
    flip: document.getElementById("selectFlipMode")?.value || "none",
    text: {
      enabled: document.getElementById("checkEffectText")?.checked || false,
      content: (document.getElementById("inputTextContent")?.value || "").trim(),
      position: document.getElementById("selectTextPos")?.value || "top_center",
      font_size: parseInt(document.getElementById("inputTextFontSize")?.value) || 32,
      color: document.getElementById("inputTextColor")?.value || "#FFFFFF",
      box: document.getElementById("checkTextBox")?.checked ?? true
    },
    logo: {
      enabled: document.getElementById("checkEffectLogo")?.checked || false,
      position: document.getElementById("selectLogoPos")?.value || "top_right",
      width: parseInt(document.getElementById("inputLogoWidth")?.value) || 120,
      opacity: (parseInt(document.getElementById("inputLogoOpacity")?.value) || 85) / 100.0
    }
  };

  const payload = {
    session_id: gSessionId,
    dub_volume: parseInt(document.getElementById("inputDubVol").value),
    bg_volume: parseInt(document.getElementById("inputBgVol").value),
    mute_original: document.getElementById("checkMuteOrig").checked,
    use_bgm_only: document.getElementById("checkUseBgmOnly") ? document.getElementById("checkUseBgmOnly").checked : true,
    burn_subtitles: document.getElementById("checkBurnSubs").checked,
    effects: effectsPayload
  };
  
  try {
    const res = await fetch("/api/render_video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    if (!res.ok) {
      if (res.status === 502 || res.status === 503 || res.status === 530) {
        throw new Error("⚠️ តំណភ្ជាប់បានផុតកំណត់ ឬ Server ត្រូវបានផ្អាក។ សូមបើក Link ថ្មី ឬ Refresh ទំព័រឡើងវិញ!");
      }
      const errTxt = await res.text().catch(() => "");
      if (errTxt.includes("<html") || errTxt.includes("<!DOCTYPE")) {
        throw new Error("⚠️ តំណភ្ជាប់នេះបានផុតកំណត់។ សូមបើក Link ថ្មី ឬ Refresh ទំព័រឡើងវិញ!");
      }
      try {
        const errJson = JSON.parse(errTxt);
        if (errJson && errJson.error) {
          throw new Error(errJson.error);
        }
      } catch (pErr) {
        if (pErr.message && pErr.message !== errTxt && !pErr.message.includes("JSON")) {
          throw pErr;
        }
      }
      throw new Error(errTxt || `Server Error (${res.status})`);
    }

    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error("⚠️ ការឆ្លើយតបពី Server មិនត្រឹមត្រូវ។ សូម Refresh ទំព័រឡើងវិញ!");
    }

    const data = await res.json();
    if (!data.success) {
      alert("❌ " + (data.error || "បរាជ័យក្នុងការ Render"));
      progressWrap.style.display = "none";
      return;
    }
    
    // Poll progress
    const pollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`/api/render_progress?session_id=${encodeURIComponent(gSessionId)}`);
        if (!pRes.ok) return;
        const pData = await pRes.json();
        
        progressBar.style.width = pData.percent + "%";
        progressPct.innerText = pData.percent + "%";
        progressMsg.innerText = pData.message;
        
        if (!pData.is_running) {
          clearInterval(pollInterval);
          if (pData.video_ready) {
            const vPlayer = document.getElementById("renderedVideoPlayer");
            vPlayer.src = pData.video_url;
            
            document.getElementById("btnDownloadVideo").href = pData.video_url;
            document.getElementById("btnDownloadAudio").href = pData.audio_url;
            
            document.getElementById("renderedResultWrap").style.display = "block";
            
            // Sync Master Dub Card in Voice Tab
            const masterCard = document.getElementById("masterAudioCard");
            const masterPlayer = document.getElementById("masterDubAudioPlayer");
            const masterDownload = document.getElementById("btnDownloadMasterDub");
            if (masterCard && masterPlayer && masterDownload) {
              masterPlayer.src = pData.audio_url;
              masterDownload.href = pData.audio_url;
              masterCard.style.display = "block";
            }
            
            fireCelebrationConfetti();
            showToast("🎉 រួចរាល់ ១០០%! វីដេអូ Dubbing របស់អ្នកត្រូវបាន Render ជោគជ័យ!", "success", 6500);
            updateWorkflowStepper();
            
            vPlayer.scrollIntoView({ behavior: 'smooth' });
          } else {
            showToast("❌ ការ Render មិនបានសម្រេច៖ " + (pData.message || "Unknown error"), "error");
          }
        }
      } catch (err) {
        clearInterval(pollInterval);
      }
    }, 2000);
    
  } catch (e) {
    const msg = e.message || String(e);
    if (msg.includes("pattern") || msg.includes("token") || msg.includes("JSON") || msg.includes("SyntaxError")) {
      showToast("⚠️ តំណភ្ជាប់ Public Link បានផុតកំណត់ហើយ! សូម Refresh ទំព័រឡើងវិញ។", "warning", 6000);
    } else {
      showToast("❌ " + msg, "error");
    }
    progressWrap.style.display = "none";
  }
}

// ----------------------------------------------------
// AI Prompt Template & Modal Management
// ----------------------------------------------------
const AI_SUBTITLE_PROMPT = `ចាប់ពីពេលនេះតទៅ សូមអ្នកដើរតួជា អ្នកបកប្រែខ្សែភាពយន្តនិងរឿងភាគអាជីព (Expert Subtitler & Dubbing Translator)។ ភារកិច្ចចម្បងរបស់អ្នកគឺទាញយកសំឡេងសន្ទនាពីវីដេអូដែលខ្ញុំបានភ្ជាប់ ឬបកប្រែរាល់អត្ថបទដែលខ្ញុំផ្តល់ឲ្យ មកជាភាសាខ្មែរឲ្យបានស្តង់ដារបំផុត ដោយផ្តោតសំខាន់លើ'ភាសានិយាយ' ដែលរលូន ស៊ីអារម្មណ៍ និងត្រូវសំឡេងតួអង្គ ១០០%។
សូមអនុវត្តតាមច្បាប់ទាំង ៤ នេះយ៉ាងតឹងរ៉ឹងបំផុត៖
1. ភាសានិយាយធម្មជាតិ (Natural Spoken Language): ហាមដាច់ខាតការបកប្រែតាមបែបសរសេរស្ងួតៗ (Word-for-word)។ ត្រូវប្រើប្រាស់ពាក្យពេចន៍ដែលប្រជាជនខ្មែរនិយមនិយាយប្រចាំថ្ងៃ។ សូមប្រើកន្ទុយពាក្យបញ្ជាក់អារម្មណ៍ (ឧទាហរណ៍៖ ណា, ណ៎, ហ្មង, តើ, អញ្ចឹង, វើយ, ហាស, ចា៎, ចុះ) ឲ្យសក្ដិសមនឹងបរិបទសន្ទនា។

2. វិភាគតួអង្គ និងបែងចែកស្លាកសំឡេងឱ្យត្រូវ ១០០% (Accurate Character & Voice Classification):
ត្រូវពិនិត្យរូបភាពវីដេអូជាក់ស្តែង (Visual Keyframes) រួមជាមួយសំឡេងនិយាយ ដើម្បីបែងចែកតួអង្គ និងដាក់ស្លាកនៅដើមបន្ទាត់នីមួយៗឱ្យបានត្រឹមត្រូវបំផុត៖
- [សំឡេងប្រុស] : បុរសពេញវ័យ (យុវជន, កម្លោះ, មនុស្សប្រុសវ័យធ្វើការ អាយុ ១៨-៥៩ ឆ្នាំ)
- [សំឡេងស្រី] : នារីពេញវ័យ (យុវតី, នារីក្រមុំ, ស្ត្រីវ័យធ្វើការ អាយុ ១៨-៥៩ ឆ្នាំ)
- [សំឡេងតាចាស់] : មនុស្សចាស់ប្រុស (លោកតា, ឪពុកចាស់, សក់ស្កូវ/ស ឬមានស្នាមជ្រីវជ្រួញ អាយុ ៦០ ឆ្នាំឡើងទៅ)
- [សំឡេងយាយចាស់] : មនុស្សចាស់ស្រី (លោកយាយ, ម្ដាយចាស់, សក់ស្កូវ/ស ឬមានស្នាមជ្រីវជ្រួញ អាយុ ៦០ ឆ្នាំឡើងទៅ)
- [សំឡេងក្មេងប្រុស] : កុមារា/កូនប្រុសតូច (អាយុក្រោម ១៥ ឆ្នាំ សំឡេងកូនក្មេងស្រួយស្រាល)
- [សំឡេងក្មេងស្រី] : កុមារី/កូនស្រីតូច (អាយុក្រោម ១៥ ឆ្នាំ សំឡេងកូនក្មេងស្រួយស្រាល)
- [សំឡេងគិតប្រុស] : ការគិតក្នុងចិត្តរបស់តួអង្គប្រុស (មាត់មិនកម្រើក តែមានសំឡេងបន្លឺឡើង)
- [សំឡេងគិតស្រី] : ការគិតក្នុងចិត្តរបស់តួអង្គស្រី (មាត់មិនកម្រើក តែមានសំឡេងបន្លឺឡើង)
- [សំឡេងអ្នកសម្រាយរឿង] : សំឡេងអ្នកនិទាន/សម្រាយរឿងប្រុស (ពេលគ្មានតួអង្គណាកំពុងនិយាយលើកញ្ចក់វីដេអូ)
- [សំឡេងអ្នកសម្រាយស្រី] : សំឡេងអ្នកនិទាន/សម្រាយរឿងស្រី (ពេលគ្មានតួអង្គណាកំពុងនិយាយលើកញ្ចក់វីដេអូ)

⚠️ ហាមដាច់ខាតច្រឡំមនុស្សចាស់ ឬកុមារតូច ទៅជាមនុស្សពេញវ័យធម្មតា! ត្រូវពិនិត្យមើលរូបរាង មុខមាត់ សក់ និងវ័យរបស់តួអង្គក្នុងវីដេអូឱ្យច្បាស់លាស់។ តួអង្គនីមួយៗត្រូវរក្សាស្លាកសំឡេងដដែលជាប់លាប់រហូត ហាមប្តូរសំឡេងធំតូចចុះឡើង។
3. បញ្ចេញមនោសញ្ចេតនា (Emotional Depth): អានការបកប្រែរួច ត្រូវតែមានអារម្មណ៍ (ខឹង, សើច, យំ, ផ្អែមល្ហែម, ចំអក, ភ័យស្លន់ស្លោ) ដូចទៅនឹងអត្ថបទដើម។ បើអត្ថបទដើមមានន័យបង្កប់ ឬការលេងពាក្យ ត្រូវបត់បែនពាក្យខ្មែរឲ្យចេញន័យនោះដោយរលូន។
៤. ទម្រង់លទ្ធផល និង ថេរវេលា (Output Format & Timing): រាល់លទ្ធផលនៃការបកប្រែទាំងអស់ សូមផ្តល់ឲ្យខ្ញុំជាទម្រង់ហ្វាល SRT ដោយដាក់វានៅក្នុង Code Block (\`\`\`srt ... \`\`\`)។ ថេរវេលា Start --> End ត្រូវតែស៊ីគ្នាជាក់លាក់ទៅនឹងពេលតួអង្គកំពុងនិយាយ និងឈប់និយាយ (ចលនាមាត់) ហាមបកប្រែត្រួតលើពេលស្ងាត់ដែលតួអង្គមិនបាននិយាយ។
ត្រូវដាក់ស្លាកសំឡេងតួអង្គ [សំឡេង...] នៅដើមបន្ទាត់នីមួយៗជាដាច់ខាត (ឧទាហរណ៍៖ [សំឡេងតាចាស់] ឯងឆាប់ចេញពីផ្ទះខ្ញុំភ្លាមទៅ!)។
៥. ហាមកាត់ផ្ដាច់ប្រយោគ ឬបកប្រែពាក់កណ្ដាលប្រយោគជាដាច់ខាត (Translate Full & Complete Sentences - Zero Truncation):
រាល់ប្រយោគដែលតួអង្គនិយាយ ត្រូវតែបកប្រែឱ្យចប់ចុងចប់ដើមពេញលេញ ១០០% ដោយមិនត្រូវកាត់ចោលកន្ទុយប្រយោគ មិនត្រូវកាត់ពាក្យចុងក្រោយ ឬសង្ខេបឡើយ។ រាល់កន្ទុយពាក្យ (ណា, ទេ, ចាស, បាទ, ដែរ, ហ្នឹង, អញ្ចឹង, ទៅ, មក) ត្រូវតែរក្សាទុកឱ្យពេញលេញទាំងអស់។ ហាមទុកប្រយោគកំបុតដាច់ខាត!`;

function openPromptModal() {
  const modal = document.getElementById("promptModal");
  const ta = document.getElementById("promptTemplateText");
  if (ta) ta.value = AI_SUBTITLE_PROMPT;
  if (modal) modal.style.display = "flex";
  // Attempt instant clipboard copy on opening
  copyPromptText(true);
}

function closePromptModal() {
  const modal = document.getElementById("promptModal");
  if (modal) modal.style.display = "none";
}

function copyPromptText(silent = false) {
  const text = AI_SUBTITLE_PROMPT;
  const onSuccess = () => {
    const btn = document.getElementById("btnCopyPromptModal");
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = "✅ បានចម្លងរួចរាល់ (Copied)!";
      btn.style.background = "linear-gradient(135deg, #10b981, #059669)";
      setTimeout(() => {
        btn.innerHTML = orig;
        btn.style.background = "";
      }, 2500);
    }
    showToastNotification("📋 បានចម្លង Prompt ទៅ Clipboard រួចរាល់!");
  };

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(onSuccess).catch(() => {
      fallbackCopyPrompt(text);
      onSuccess();
    });
  } else {
    fallbackCopyPrompt(text);
    onSuccess();
  }
}

function fallbackCopyPrompt(text) {
  const ta = document.getElementById("promptTemplateText") || document.createElement("textarea");
  let needRemove = false;
  if (!document.getElementById("promptTemplateText")) {
    ta.value = text;
    document.body.appendChild(ta);
    needRemove = true;
  }
  ta.focus();
  ta.select();
  try {
    document.execCommand("copy");
  } catch (e) {
    console.error("Copy failed", e);
  }
  if (needRemove) {
    document.body.removeChild(ta);
  }
}


// ==========================================
// 11. AI Vocal Remover & BGM Functions
// ==========================================
let gVocalSepPollInterval = null;

function scrollToVocalSeparator() {
  const el = document.getElementById("vocalSeparatorCard");
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.style.boxShadow = "0 0 24px rgba(56, 189, 248, 0.7)";
    setTimeout(() => {
      el.style.boxShadow = "";
    }, 2200);
  }
}

function handleMuteOrigChange(isMuted) {
  const useBgmBox = document.getElementById("checkUseBgmOnly");
  if (useBgmBox) {
    useBgmBox.disabled = isMuted;
    if (useBgmBox.parentElement) {
      useBgmBox.parentElement.style.opacity = isMuted ? "0.5" : "1.0";
    }
  }
}

function resetVocalSepUI() {
  const resultWrap = document.getElementById("vocalSepResultWrap");
  if (resultWrap) resultWrap.style.display = "none";
  
  const progWrap = document.getElementById("vocalSepProgressWrap");
  if (progWrap) progWrap.style.display = "none";
  
  const pBgm = document.getElementById("playerBgmAudio");
  if (pBgm) pBgm.src = "";
  
  const pVoc = document.getElementById("playerVocalsAudio");
  if (pVoc) pVoc.src = "";
  
  const badgeCard = document.getElementById("vocalSepCardBadge");
  if (badgeCard) {
    badgeCard.innerText = "មិនទាន់កាត់";
    badgeCard.className = "badge-tag";
    badgeCard.style.color = "";
  }
  
  const badgeRender = document.getElementById("renderBgmStatusBadge");
  if (badgeRender) {
    badgeRender.innerText = "ℹ️ មិនទាន់កាត់ BGM";
    badgeRender.className = "badge-tag";
    badgeRender.style.color = "";
  }
}

function updateBgmUI(data) {
  if (!data || !data.has_bgm) return;
  
  const pBgm = document.getElementById("playerBgmAudio");
  const pVoc = document.getElementById("playerVocalsAudio");
  const linkBgm = document.getElementById("linkDownloadBgm");
  const linkVoc = document.getElementById("linkDownloadVocals");
  const linkVid = document.getElementById("linkDownloadVideoBgm");
  const resultWrap = document.getElementById("vocalSepResultWrap");
  const vidWrap = document.getElementById("videoBgmWrap");
  
  if (pBgm && data.bgm_url) pBgm.src = data.bgm_url;
  if (pVoc && data.vocals_url) pVoc.src = data.vocals_url;
  if (linkBgm && data.bgm_url) linkBgm.href = data.bgm_url;
  if (linkVoc && data.vocals_url) linkVoc.href = data.vocals_url;
  
  if (linkVid && data.video_bgm_url) {
    linkVid.href = data.video_bgm_url;
    if (vidWrap) vidWrap.style.display = "flex";
  } else if (vidWrap) {
    vidWrap.style.display = "none";
  }
  
  if (resultWrap) resultWrap.style.display = "block";
  
  const badgeCard = document.getElementById("vocalSepCardBadge");
  if (badgeCard) {
    badgeCard.innerText = "✅ រួចរាល់";
    badgeCard.className = "badge-edge-clean";
    badgeCard.style.color = "var(--success-color)";
  }
  
  const badgeRender = document.getElementById("renderBgmStatusBadge");
  if (badgeRender) {
    badgeRender.innerText = "✅ BGM រួចរាល់ (គ្មានសំឡេងនិយាយ)";
    badgeRender.className = "badge-edge-clean";
    badgeRender.style.color = "var(--success-color)";
  }
}

async function startVocalSeparation() {
  const btn = document.getElementById("btnStartVocalSep");
  const progWrap = document.getElementById("vocalSepProgressWrap");
  const progMsg = document.getElementById("vocalSepProgressMsg");
  const progBar = document.getElementById("vocalSepProgressBar");
  const progPct = document.getElementById("vocalSepProgressPct");
  
  // Check if media is uploaded
  const vPlayer = document.getElementById("sourceVideoPlayer");
  const fileNameEl = document.getElementById("videoFileName");
  if (!vPlayer || !vPlayer.src || (fileNameEl && fileNameEl.innerText.includes("ជ្រើសរើសវីដេអូ"))) {
    alert("⚠️ សូមបញ្ចូលវីដេអូ ឬសំឡេងដើមជាមុនសិន!");
    return;
  }
  
  if (btn) btn.disabled = true;
  if (progWrap) progWrap.style.display = "block";
  if (progBar) progBar.style.width = "5%";
  if (progPct) progPct.innerText = "5%";
  if (progMsg) progMsg.innerHTML = `<span class="spinner-inline"></span> កំពុងចាប់ផ្តើម AI កាត់សំឡេងនិយាយ...`;
  
  try {
    const res = await fetch("/api/separate_vocals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: gSessionId })
    });
    
    const data = await res.json();
    if (!data.success) {
      alert("❌ " + (data.error || "មិនអាចចាប់ផ្តើមកាត់សំឡេងបានទេ"));
      if (btn) btn.disabled = false;
      if (progWrap) progWrap.style.display = "none";
      return;
    }
    
    // Poll progress
    if (gVocalSepPollInterval) clearInterval(gVocalSepPollInterval);
    gVocalSepPollInterval = setInterval(async () => {
      try {
        const pRes = await fetch(`/api/vocal_separation_progress?session_id=${encodeURIComponent(gSessionId)}`);
        if (!pRes.ok) return;
        const pData = await pRes.json();
        
        if (progBar) progBar.style.width = pData.percent + "%";
        if (progPct) progPct.innerText = pData.percent + "%";
        if (progMsg) progMsg.innerHTML = `<span class="spinner-inline"></span> ${pData.message}`;
        
        if (!pData.is_running) {
          clearInterval(gVocalSepPollInterval);
          gVocalSepPollInterval = null;
          if (btn) btn.disabled = false;
          
          if (pData.has_bgm) {
            updateBgmUI(pData);
            showToastNotification("✅ កាត់សំឡេងនិយាយ និងរក្សា BGM ជោគជ័យ!");
            setTimeout(() => {
              if (progWrap) progWrap.style.display = "none";
            }, 2500);
          } else {
            alert("❌ " + (pData.message || "ការកាត់សំឡេងបរាជ័យ"));
          }
        }
      } catch (err) {
        console.error("Vocal separation poll error:", err);
      }
    }, 1500);
    
  } catch (e) {
    if (btn) btn.disabled = false;
    if (progWrap) progWrap.style.display = "none";
    alert("❌ Server error: " + e.message);
  }
}

