/**
 * MeetAction AI — Frontend Script
 * Handles tab navigation, API calls, pipeline visualization,
 * analysis results display, kanban board, and meetings list.
 */

const API = "";

// ─── State ────────────────────────────────────────────────────────────────────
let selectedFile = null;
let currentMeetingId = null;
let pipelineNodes = [];

// ─── DOM Ready ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initVoiceUpload();
  initTextSubmit();
  initModal();

  pipelineNodes = [
    document.getElementById("pipe-input"),
    document.getElementById("pipe-stt"),
    document.getElementById("pipe-agent"),
    document.getElementById("pipe-delta"),
    document.getElementById("pipe-board"),
  ];
});

// ─── Tab Navigation ──────────────────────────────────────────────────────────
function initTabs() {
  const buttons = document.querySelectorAll("[data-tab]");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      document.querySelectorAll(".tab-content").forEach((s) => s.classList.add("hidden"));
      const target = document.getElementById(`section-${btn.dataset.tab}`);
      if (target) target.classList.remove("hidden");

      // Lazy-load data for tabs
      if (btn.dataset.tab === "board") loadKanban();
      if (btn.dataset.tab === "meetings") loadMeetings();
    });
  });
}

// ─── Pipeline Visualization ──────────────────────────────────────────────────
function setPipelineStep(stepIndex) {
  pipelineNodes.forEach((node, i) => {
    node.classList.remove("active", "completed");
    if (i < stepIndex) node.classList.add("completed");
    else if (i === stepIndex) node.classList.add("active");
  });
}

function resetPipeline() {
  pipelineNodes.forEach((node) => {
    node.classList.remove("active", "completed");
  });
  pipelineNodes[0]?.classList.add("active");
}

// ─── Voice Upload ────────────────────────────────────────────────────────────
function initVoiceUpload() {
  const dropZone = document.getElementById("voice-drop-zone");
  const fileInput = document.getElementById("voice-file-input");
  const transcribeBtn = document.getElementById("transcribe-btn");

  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("border-brand-purple", "bg-white/5");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("border-brand-purple", "bg-white/5");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("border-brand-purple", "bg-white/5");
    if (e.dataTransfer.files.length) {
      selectedFile = e.dataTransfer.files[0];
      showSelectedFile(dropZone, selectedFile);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      selectedFile = fileInput.files[0];
      showSelectedFile(dropZone, selectedFile);
    }
  });

  transcribeBtn.addEventListener("click", handleVoiceUpload);
}

function showSelectedFile(dropZone, file) {
  const sizeKB = (file.size / 1024).toFixed(1);
  dropZone.innerHTML = `
    <div class="text-4xl mb-4">🎵</div>
    <p class="text-sm font-semibold text-white">${file.name}</p>
    <p class="text-[11px] text-slate-500 mt-1">${sizeKB} KB</p>
    <p class="text-[11px] text-indigo-400 mt-2 underline cursor-pointer">Click to change file</p>
  `;
}

async function handleVoiceUpload() {
  if (!selectedFile) {
    showToast("Please select an audio file first", "warning");
    return;
  }

  const title = document.getElementById("voice-meeting-title").value || "Voice Meeting";
  const btn = document.getElementById("transcribe-btn");

  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin">⏳</span> Transcribing...`;
  setPipelineStep(1); // Sarvam STT

  try {
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("title", title);

    const res = await fetch(`${API}/api/meetings/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    const data = await res.json();
    currentMeetingId = data.id;
    showToast(`Transcription complete! Meeting #${data.id} created.`, "success");

    // Now trigger analysis
    await triggerAnalysis(data.id);
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
    resetPipeline();
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>🚀</span> Transcribe`;
  }
}

// ─── Text Transcript Submit ──────────────────────────────────────────────────
function initTextSubmit() {
  document.getElementById("analyze-btn").addEventListener("click", handleTextSubmit);
}

async function handleTextSubmit() {
  const transcript = document.getElementById("text-transcript-input").value.trim();
  const title = document.getElementById("text-meeting-title").value.trim();

  if (!transcript) {
    showToast("Please enter a transcript", "warning");
    return;
  }

  const btn = document.getElementById("analyze-btn");
  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin">⏳</span> Submitting...`;
  setPipelineStep(0); // Input Capture

  try {
    const formData = new FormData();
    formData.append("transcript", transcript);
    if (title) formData.append("title", title);

    const res = await fetch(`${API}/api/meetings/transcript`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Submission failed");
    }

    const data = await res.json();
    currentMeetingId = data.id;
    showToast(`Meeting #${data.id} created. Starting analysis...`, "success");

    // Trigger the analysis pipeline
    await triggerAnalysis(data.id);
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
    resetPipeline();
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>✈️</span> Submit & Analyze`;
  }
}

// ─── Analysis Pipeline ───────────────────────────────────────────────────────
async function triggerAnalysis(meetingId) {
  setPipelineStep(2); // Google ADK Agent
  showToast("AI Agents analyzing the transcript...", "info");

  try {
    const res = await fetch(`${API}/api/meetings/${meetingId}/analyze`, {
      method: "POST",
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Analysis failed");
    }

    const data = await res.json();

    setPipelineStep(3); // Delta Lake
    await sleep(400);
    setPipelineStep(4); // Board
    await sleep(400);

    showToast(`Analysis complete! ${data.action_items_count} tasks created.`, "success");

    // Show results
    displayResults(data);

    // Switch to results tab
    switchTab("results");
  } catch (err) {
    showToast(`Analysis Error: ${err.message}`, "error");
    resetPipeline();
  }
}

// ─── Display Results ─────────────────────────────────────────────────────────
function displayResults(data) {
  const container = document.getElementById("section-results");
  container.classList.remove("h-[400px]", "items-center", "justify-center", "italic");

  const decisions = (data.decisions || []).map((d) => `<li class="text-slate-300 text-sm">${escapeHtml(d)}</li>`).join("");
  const tasks = (data.tasks || []).map((t) => `
    <div class="bg-[#1e293b]/50 border border-white/5 rounded-xl p-4 flex items-start justify-between gap-4">
      <div class="flex-1">
        <p class="text-sm font-bold text-white">${escapeHtml(t.title)}</p>
        <div class="flex items-center gap-3 mt-2">
          <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${priorityColor(t.priority)}">${t.priority}</span>
          <span class="text-[11px] text-slate-500">👤 ${escapeHtml(t.assignee || "Unassigned")}</span>
          ${t.feature_area ? `<span class="text-[11px] text-slate-500">📂 ${escapeHtml(t.feature_area)}</span>` : ""}
        </div>
      </div>
      <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">${t.status}</span>
    </div>
  `).join("");

  container.innerHTML = `
    <div class="space-y-8 pb-32">
      <!-- Summary Card -->
      <div class="bg-brand-navyLight border border-brand-border rounded-2xl p-8">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">📝</div>
          <h3 class="text-lg font-bold text-white">Meeting Summary</h3>
          ${data.mock ? '<span class="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full font-bold">MOCK</span>' : ""}
        </div>
        <div class="text-sm text-slate-300 whitespace-pre-line leading-relaxed">${escapeHtml(data.summary || "No summary available.")}</div>
      </div>

      <!-- Decisions -->
      ${decisions ? `
      <div class="bg-brand-navyLight border border-brand-border rounded-2xl p-8">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-8 h-8 rounded-full bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400">⚖️</div>
          <h3 class="text-lg font-bold text-white">Key Decisions</h3>
        </div>
        <ul class="list-disc list-inside space-y-2">${decisions}</ul>
      </div>` : ""}

      <!-- Tasks -->
      <div class="bg-brand-navyLight border border-brand-border rounded-2xl p-8">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-8 h-8 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">⚡</div>
          <h3 class="text-lg font-bold text-white">Generated Action Items</h3>
          <span class="text-[11px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full">${data.action_items_count || 0} tasks</span>
        </div>
        <div class="space-y-3">${tasks || '<p class="text-sm text-slate-500 italic">No tasks extracted.</p>'}</div>
      </div>
    </div>
  `;
}

// ─── Kanban Board ────────────────────────────────────────────────────────────
async function loadKanban() {
  const container = document.getElementById("kanban-container");
  container.innerHTML = `<div class="col-span-3 text-center text-slate-500 py-12"><span class="animate-spin inline-block">⏳</span> Loading board...</div>`;

  try {
    const res = await fetch(`${API}/api/board/tasks`);
    const data = await res.json();
    const tasks = data.tasks || [];

    const columns = {
      todo: { label: "📋 To Do", color: "slate", items: [] },
      in_progress: { label: "🔨 In Progress", color: "amber", items: [] },
      done: { label: "✅ Done", color: "emerald", items: [] },
    };

    tasks.forEach((t) => {
      if (columns[t.status]) columns[t.status].items.push(t);
    });

    container.innerHTML = Object.entries(columns)
      .map(([status, col]) => `
        <div class="bg-brand-navyLight border border-brand-border rounded-2xl p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-sm font-bold text-white">${col.label}</h3>
            <span class="text-[11px] font-bold bg-${col.color}-500/10 text-${col.color}-400 border border-${col.color}-500/20 px-2 py-0.5 rounded-full">${col.items.length}</span>
          </div>
          <div class="space-y-3 min-h-[100px]">
            ${col.items.length === 0
              ? `<p class="text-[11px] text-slate-600 italic text-center py-8">No tasks</p>`
              : col.items.map((t) => renderKanbanCard(t, status)).join("")}
          </div>
        </div>
      `).join("");
  } catch (err) {
    container.innerHTML = `<div class="col-span-3 text-center text-red-400 py-12">Failed to load board: ${err.message}</div>`;
  }
}

function renderKanbanCard(task, currentStatus) {
  const moveButtons = getStatusMoveButtons(task.id, currentStatus);
  return `
    <div class="bg-brand-navy border border-white/5 rounded-xl p-4 hover:border-brand-purple/30 transition-colors group">
      <p class="text-sm font-semibold text-white mb-2">${escapeHtml(task.title)}</p>
      ${task.description ? `<p class="text-[11px] text-slate-500 mb-3 line-clamp-2">${escapeHtml(task.description)}</p>` : ""}
      <div class="flex items-center gap-2 mb-3">
        <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${priorityColor(task.priority)}">${task.priority}</span>
        <span class="text-[11px] text-slate-500">👤 ${escapeHtml(task.assignee || "Unassigned")}</span>
      </div>
      <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        ${moveButtons}
        <button onclick="deleteTaskFromBoard(${task.id})" class="text-[10px] font-bold text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-500/20 hover:bg-red-500/10 transition-all">🗑️</button>
      </div>
    </div>
  `;
}

function getStatusMoveButtons(taskId, currentStatus) {
  const btns = [];
  if (currentStatus !== "todo")
    btns.push(`<button onclick="moveTask(${taskId}, 'todo')" class="text-[10px] font-bold text-slate-400 hover:text-white px-2 py-1 rounded border border-white/10 hover:bg-white/5 transition-all">📋 To Do</button>`);
  if (currentStatus !== "in_progress")
    btns.push(`<button onclick="moveTask(${taskId}, 'in_progress')" class="text-[10px] font-bold text-amber-400 hover:text-amber-300 px-2 py-1 rounded border border-amber-500/20 hover:bg-amber-500/10 transition-all">🔨 WIP</button>`);
  if (currentStatus !== "done")
    btns.push(`<button onclick="moveTask(${taskId}, 'done')" class="text-[10px] font-bold text-emerald-400 hover:text-emerald-300 px-2 py-1 rounded border border-emerald-500/20 hover:bg-emerald-500/10 transition-all">✅ Done</button>`);
  return btns.join("");
}

async function moveTask(taskId, newStatus) {
  try {
    const res = await fetch(`${API}/api/board/tasks/${taskId}/move`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) throw new Error("Move failed");
    showToast(`Task moved to ${newStatus}`, "success");
    loadKanban();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

async function deleteTaskFromBoard(taskId) {
  if (!confirm("Delete this task?")) return;
  try {
    const res = await fetch(`${API}/api/board/tasks/${taskId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    showToast("Task deleted", "success");
    loadKanban();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// ─── Meeting History ─────────────────────────────────────────────────────────
async function loadMeetings() {
  const container = document.getElementById("meetings-list");
  container.innerHTML = `<div class="text-center text-slate-500 py-12"><span class="animate-spin inline-block">⏳</span> Loading meetings...</div>`;

  try {
    const res = await fetch(`${API}/api/meetings`);
    const data = await res.json();
    const meetings = data.meetings || [];

    if (meetings.length === 0) {
      container.innerHTML = `<div class="text-center text-slate-500 py-12 italic">No meetings yet. Upload audio or paste a transcript to get started.</div>`;
      return;
    }

    container.innerHTML = meetings.map((m) => `
      <div class="bg-brand-navyLight border border-brand-border rounded-2xl p-6 flex items-center justify-between hover:border-brand-purple/30 transition-colors">
        <div class="flex items-center gap-4">
          <div class="w-10 h-10 rounded-full ${m.source_type === "voice" ? "bg-indigo-500/10 text-indigo-400" : "bg-cyan-500/10 text-cyan-400"} flex items-center justify-center">
            ${m.source_type === "voice" ? "🎙️" : "📄"}
          </div>
          <div>
            <p class="text-sm font-bold text-white">${escapeHtml(m.title)}</p>
            <div class="flex items-center gap-3 mt-1">
              <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${statusColor(m.status)}">${m.status}</span>
              <span class="text-[11px] text-slate-500">${new Date(m.created_at).toLocaleString()}</span>
            </div>
          </div>
        </div>
        <div class="flex gap-2">
          ${m.status === "pending" ? `<button onclick="triggerAnalysisFromList(${m.id})" class="text-[11px] font-bold text-brand-purple hover:text-white px-4 py-2 rounded-xl border border-brand-purple/30 hover:bg-brand-purple/10 transition-all">⚡ Analyze</button>` : ""}
          ${m.status === "analyzed" ? `<button onclick="viewResults(${m.id})" class="text-[11px] font-bold text-emerald-400 hover:text-white px-4 py-2 rounded-xl border border-emerald-500/30 hover:bg-emerald-500/10 transition-all">📊 View Results</button>` : ""}
        </div>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div class="text-center text-red-400 py-12">Failed to load meetings: ${err.message}</div>`;
  }
}

async function triggerAnalysisFromList(meetingId) {
  showToast(`Starting analysis for Meeting #${meetingId}...`, "info");
  await triggerAnalysis(meetingId);
  loadMeetings(); // refresh list
}

async function viewResults(meetingId) {
  try {
    const res = await fetch(`${API}/api/meetings/${meetingId}/results`);
    if (!res.ok) throw new Error("Failed to fetch results");
    const data = await res.json();

    showModal(data);
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// ─── Modal ───────────────────────────────────────────────────────────────────
function initModal() {
  document.getElementById("close-modal").addEventListener("click", closeModal);
  document.getElementById("modal-overlay").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeModal();
  });
}

function showModal(data) {
  const meeting = data.meeting || {};
  const analysis = data.analysis || {};
  const tasks = data.tasks || [];

  document.getElementById("modal-header").innerHTML = `
    <h2 class="text-xl font-bold text-white">${escapeHtml(meeting.title || "Meeting Details")}</h2>
    <p class="text-[11px] text-slate-500 mt-1">${meeting.source_type === "voice" ? "🎙️ Voice" : "📄 Text"} · ${new Date(meeting.created_at).toLocaleString()}</p>
  `;

  const decisionsHtml = (analysis.decisions || []).map((d) => `<li class="text-sm text-slate-300">${escapeHtml(d)}</li>`).join("");
  const tasksHtml = tasks.map((t) => `
    <div class="bg-brand-navy border border-white/5 rounded-xl p-4">
      <p class="text-sm font-semibold text-white">${escapeHtml(t.title)}</p>
      ${t.description ? `<p class="text-[11px] text-slate-500 mt-1">${escapeHtml(t.description)}</p>` : ""}
      <div class="flex items-center gap-2 mt-2">
        <span class="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${priorityColor(t.priority)}">${t.priority}</span>
        <span class="text-[11px] text-slate-500">👤 ${escapeHtml(t.assignee || "Unassigned")}</span>
      </div>
    </div>
  `).join("");

  document.getElementById("modal-body").innerHTML = `
    ${analysis.summary ? `
    <div>
      <h4 class="text-xs font-black uppercase text-slate-500 tracking-widest mb-2">Summary</h4>
      <p class="text-sm text-slate-300 whitespace-pre-line">${escapeHtml(analysis.summary)}</p>
    </div>` : ""}
    ${decisionsHtml ? `
    <div>
      <h4 class="text-xs font-black uppercase text-slate-500 tracking-widest mb-2">Decisions</h4>
      <ul class="list-disc list-inside space-y-1">${decisionsHtml}</ul>
    </div>` : ""}
    <div>
      <h4 class="text-xs font-black uppercase text-slate-500 tracking-widest mb-2">Action Items (${tasks.length})</h4>
      <div class="space-y-3">${tasksHtml || '<p class="text-sm text-slate-500 italic">No tasks.</p>'}</div>
    </div>
  `;

  const overlay = document.getElementById("modal-overlay");
  overlay.classList.remove("hidden");
  overlay.classList.add("flex");
}

function closeModal() {
  const overlay = document.getElementById("modal-overlay");
  overlay.classList.add("hidden");
  overlay.classList.remove("flex");
}

// ─── Utilities ───────────────────────────────────────────────────────────────
function switchTab(tabName) {
  const btn = document.querySelector(`[data-tab="${tabName}"]`);
  if (btn) btn.click();
}

function priorityColor(priority) {
  const map = {
    critical: "bg-red-500/10 text-red-400 border border-red-500/20",
    high: "bg-orange-500/10 text-orange-400 border border-orange-500/20",
    medium: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
    low: "bg-slate-500/10 text-slate-400 border border-slate-500/20",
  };
  return map[priority] || map.medium;
}

function statusColor(status) {
  const map = {
    pending: "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20",
    transcribing: "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20",
    analyzing: "bg-blue-500/10 text-blue-400 border border-blue-500/20",
    analyzed: "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
    failed: "bg-red-500/10 text-red-400 border border-red-500/20",
  };
  return map[status] || map.pending;
}

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Toast Notifications ─────────────────────────────────────────────────────
function showToast(message, type = "info") {
  const colors = {
    success: "border-emerald-500/50 bg-emerald-500/10 text-emerald-400",
    error: "border-red-500/50 bg-red-500/10 text-red-400",
    warning: "border-amber-500/50 bg-amber-500/10 text-amber-400",
    info: "border-indigo-500/50 bg-indigo-500/10 text-indigo-400",
  };

  const icons = {
    success: "✅",
    error: "❌",
    warning: "⚠️",
    info: "ℹ️",
  };

  const toast = document.createElement("div");
  toast.className = `fixed top-20 right-8 z-[200] flex items-center gap-3 px-5 py-3 rounded-xl border ${colors[type]} text-sm font-medium shadow-2xl transition-all duration-300 opacity-0 translate-x-4`;
  toast.innerHTML = `<span>${icons[type]}</span> ${escapeHtml(message)}`;

  document.body.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => {
    toast.classList.remove("opacity-0", "translate-x-4");
    toast.classList.add("opacity-100", "translate-x-0");
  });

  // Animate out
  setTimeout(() => {
    toast.classList.add("opacity-0", "translate-x-4");
    toast.classList.remove("opacity-100", "translate-x-0");
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
