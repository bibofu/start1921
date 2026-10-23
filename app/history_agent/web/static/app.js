import {renderMarkdown} from "/assets/markdown.js";
import {consumeEventStream} from "/assets/stream.js";

const messagesEl = document.querySelector("#messages");
const form = document.querySelector("#composer");
const input = document.querySelector("#question");
const send = document.querySelector("#send");
const statusText = document.querySelector("#status");
const statusDot = document.querySelector("#status-dot");
const sidebar = document.querySelector("#sidebar");
const sidebarOverlay = document.querySelector("#sidebar-overlay");
const sidebarToggle = document.querySelector("#sidebar-toggle");
const newSessionButton = document.querySelector("#new-session");
const sessionList = document.querySelector("#session-list");
const sessionSearch = document.querySelector("#session-search");
const loadMoreSessions = document.querySelector("#load-more-sessions");
const currentTitle = document.querySelector("#current-title");
const renameSessionButton = document.querySelector("#rename-session");
const deleteSessionButton = document.querySelector("#delete-session");
const visitorLabel = document.querySelector("#visitor-label");
const quotaLabel = document.querySelector("#quota");
const cookieWarning = document.querySelector("#cookie-warning");
const exportData = document.querySelector("#export-data");
const deleteAllDataButton = document.querySelector("#delete-all-data");
const toggleArchived = document.querySelector("#toggle-archived");
const toast = document.querySelector("#toast");

const CURRENT_SESSION_KEY = "start1921-current-session-v2";
const LEGACY_SESSION_KEY = "history-agent-session-v1";
const CHANNEL_NAME = "start1921-sessions";

const state = {
  csrf: "",
  visitorLabel: "",
  sessions: [],
  hasMore: false,
  offset: 0,
  query: "",
  status: "active",
  currentSessionId: null,
  currentSession: null,
  messages: [],
  nextBefore: null,
  activeRun: null,
  loadingSessions: false,
  loadingSession: false
};

let channel = null;
let toastTimer = null;

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[char]));
}

function uuid() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("zh-CN", {month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"});
}

function currentSession() {
  return state.currentSession;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (options.method && options.method !== "GET" && state.csrf) {
    headers.set("X-CSRF-Token", state.csrf);
  }
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "请求失败");
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function showToast(message, actionLabel = "", action = null) {
  if (!toast) return;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  if (actionLabel && action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "toast-action";
    button.textContent = actionLabel;
    button.addEventListener("click", async () => {
      hideToast();
      try { await action(); } catch (error) { showToast(error.message || "操作失败"); }
    }, {once: true});
    toast.appendChild(button);
  }
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, 8000);
}

function hideToast() {
  if (!toast) return;
  toast.hidden = true;
  clearTimeout(toastTimer);
}

function notifySessionsChanged() {
  if (channel) {
    channel.postMessage({type: "changed"});
  }
}

function openSidebar() {
  sidebar?.classList.add("open");
  if (sidebarOverlay) sidebarOverlay.hidden = false;
}

function closeSidebar() {
  sidebar?.classList.remove("open");
  if (sidebarOverlay) sidebarOverlay.hidden = true;
}

function addMessage(role, html, {scroll = true} = {}) {
  const item = document.createElement("article");
  item.className = `message ${role}`;
  item.innerHTML = `<div class="avatar">${role === "user" ? "问" : "史"}</div><div class="bubble">${html}</div>`;
  messagesEl.appendChild(item);
  if (scroll) item.scrollIntoView({behavior: "smooth", block: "end"});
  return item;
}

function renderAnswer(data) {
  const structured = String(data.retrieval_mode || "").startsWith("structured_");
  const mode = data.generator_mode === "llm"
    ? `DeepSeek ${escapeHtml(data.model_name || "V4")} · 证据约束生成`
    : structured ? "结构化研究 · 候选与原文核查" : "本地证据摘录";
  const planner = data.query_planner_status === "used"
    ? ` · ${escapeHtml(data.query_planner_model || "DeepSeek")} 查询理解`
    : data.query_planner_status === "fallback" ? " · 原问题降级检索" : "";
  const execution = data.execution_summary;
  const research = execution
    ? ` · ${escapeHtml(execution.task_results.length)} 项研究任务${execution.replan_count ? ` · ${escapeHtml(execution.replan_count)} 次计划更新` : ""}`
    : "";
  const taskStatus = {completed: "完成", empty: "未找到材料", unavailable: "服务不可用", not_applicable: "不适用", ambiguous: "待澄清", failed: "未完成", skipped: "未执行"};
  const tasks = execution ? `<details class="research-tasks"><summary>查看研究过程</summary><ol>${execution.plan.tasks.map(task => {
    const result = execution.task_results.find(item => item.task_id === task.task_id);
    const gaps = result?.missing_aspects?.length ? `；尚缺：${result.missing_aspects.map(escapeHtml).join("、")}` : "";
    return `<li>${escapeHtml(task.objective)} — ${escapeHtml(taskStatus[result?.status] || "未执行")}${gaps}</li>`;
  }).join("")}</ol></details>` : "";
  const citations = Array.isArray(data.citations) ? data.citations : [];
  const evidence = citations.map(item => `
    <details>
      <summary>[${escapeHtml(item.evidence_id)}] 《${escapeHtml(item.document)}》PDF 第 ${item.pdf_page}${item.pdf_page_end && item.pdf_page_end !== item.pdf_page ? `—${item.pdf_page_end}` : ""} 页</summary>
      <p class="meta">${escapeHtml((item.section || []).join(" › ") || "章节未识别")} · ${escapeHtml(item.source_type)} · ${escapeHtml(item.verification_status)}</p>
      <p class="quote">${escapeHtml(item.quote)}</p>
    </details>`).join("");
  const limits = Array.isArray(data.limitations) && data.limitations.length ? `<p class="limits">${data.limitations.map(escapeHtml).join(" · ")}</p>` : "";
  const removedClaims = data.llm_error_code === "removed_uncited_claims";
  const uncited = Array.isArray(data.uncited_claims) ? data.uncited_claims : [];
  const diagnostics = uncited.length ? `<details class="citation-diagnostics"><summary>${removedClaims ? "哪些草稿内容已移除" : "哪些语句缺少引用"}</summary><p class="meta">以下是未通过引用校验的草稿语句，不作为答案依据。</p><ul>${uncited.map(claim => `<li>${escapeHtml(claim)}</li>`).join("")}</ul></details>` : "";
  return `<p class="meta">${mode}${planner}${research}</p><div class="markdown-body">${renderMarkdown(data.answer || "")}</div>${tasks}<div class="evidence">${evidence}</div>${limits}${diagnostics}`;
}

function renderRestoredAnswer(content) {
  return `<p class="meta">已恢复的回答 · 历史引用未保存</p><div class="markdown-body">${renderMarkdown(content)}</div>`;
}

function welcomeHtml() {
  return `<p>可以问我人物经历、人物交集或政治观点。比如：</p>
    <div class="suggestions">
      <button type="button">周恩来在1956年主要有哪些经历？</button>
      <button type="button">毛泽东和周恩来在长征期间有哪些交集？</button>
      <button type="button">毛泽东关于调查研究有哪些观点？</button>
    </div>`;
}

function showWelcome() {
  state.currentSessionId = null;
  state.currentSession = null;
  state.messages = [];
  state.nextBefore = null;
  messagesEl.innerHTML = "";
  const item = document.createElement("article");
  item.className = "message assistant welcome";
  item.innerHTML = `<div class="avatar">史</div><div class="bubble">${welcomeHtml()}</div>`;
  messagesEl.appendChild(item);
  updateHeader();
}

function renderHistory({keepScroll = false} = {}) {
  const beforeHeight = messagesEl.scrollHeight;
  messagesEl.innerHTML = "";
  if (!state.currentSession) {
    showWelcome();
    return;
  }
  if (state.nextBefore) {
    const older = document.createElement("button");
    older.type = "button";
    older.id = "load-older";
    older.className = "ghost load-older";
    older.textContent = "加载更早消息";
    older.addEventListener("click", loadOlderMessages);
    messagesEl.appendChild(older);
  }
  if (!state.messages.length) {
    addMessage("assistant", '<p class="meta">这个会话还没有消息。可以直接提问。</p>', {scroll: false});
  }
  for (const message of state.messages) {
    if (message.role === "user") {
      const pending = message.status === "pending" ? '<p class="meta">正在生成，回答尚未完成。</p>' : "";
      const aborted = message.status === "aborted" || message.status === "failed"
        ? `<p class="meta">${message.status === "failed" ? "生成失败" : "已停止"}，这个问题未完成。</p>` : "";
      addMessage("user", `<p>${escapeHtml(message.content)}</p>${pending}${aborted}`, {scroll: false});
    } else {
      addMessage("assistant", renderRestoredAnswer(message.content), {scroll: false});
    }
  }
  if (keepScroll) {
    window.scrollBy(0, messagesEl.scrollHeight - beforeHeight);
  } else {
    messagesEl.lastElementChild?.scrollIntoView({block: "end"});
  }
}

function updateHeader() {
  const session = currentSession();
  currentTitle.textContent = session?.title || "新会话";
  document.title = session?.title ? `${session.title} · start1921` : "start1921 · 近现代史研究 Agent";
  if (renameSessionButton) renameSessionButton.hidden = !session;
  if (deleteSessionButton) deleteSessionButton.hidden = !session;
}

function sessionItemHtml(session) {
  const active = session.session_id === state.currentSessionId;
  const pinned = session.pinned ? '<span class="session-pin">置顶</span>' : "";
  const preview = session.last_message_preview || "还没有消息";
  return `<article class="session-item${active ? " active" : ""}" data-session-id="${escapeHtml(session.session_id)}">
    <button class="session-select" type="button">
      <span class="session-title">${pinned}${escapeHtml(session.title || "未命名会话")}</span>
      <span class="session-preview">${escapeHtml(preview)}</span>
      <span class="session-meta">${escapeHtml(formatTime(session.last_message_at))}${session.message_count ? ` · ${session.message_count} 条` : ""}</span>
    </button>
    <details class="session-more">
      <summary aria-label="会话操作">⋯</summary>
      <div class="session-menu">
        <button type="button" data-action="rename">重命名</button>
        <button type="button" data-action="${session.pinned ? "unpin" : "pin"}">${session.pinned ? "取消置顶" : "置顶"}</button>
        <button type="button" data-action="${state.status === "archived" ? "unarchive" : "archive"}">${state.status === "archived" ? "移回会话" : "归档"}</button>
        <button type="button" data-action="delete">删除</button>
      </div>
    </details>
  </article>`;
}

function renderSessions() {
  if (!sessionList) return;
  if (!state.sessions.length) {
    sessionList.innerHTML = `<p class="sidebar-empty">${state.query ? "没有匹配的会话" : state.status === "archived" ? "没有归档会话" : "还没有会话"}</p>`;
    return;
  }
  sessionList.innerHTML = state.sessions.map(sessionItemHtml).join("");
  if (loadMoreSessions) loadMoreSessions.hidden = !state.hasMore;
}

async function loadSessions({append = false} = {}) {
  if (state.loadingSessions) return;
  state.loadingSessions = true;
  try {
    if (!append) state.offset = 0;
    const params = new URLSearchParams({limit: "50", offset: String(state.offset), status: state.status});
    if (state.query) params.set("q", state.query);
    const data = await api(`/api/sessions?${params.toString()}`);
    const items = Array.isArray(data.items) ? data.items : [];
    state.sessions = append ? [...state.sessions, ...items] : items;
    state.hasMore = Boolean(data.has_more);
    state.offset = state.sessions.length;
    renderSessions();
  } catch (error) {
    showToast(error.message || "会话列表加载失败");
  } finally {
    state.loadingSessions = false;
  }
}

function routeSessionId() {
  const match = window.location.pathname.match(/^\/s\/([A-Za-z0-9_-]+)$/);
  return match ? match[1] : null;
}

async function selectSession(sessionId, {push = true} = {}) {
  if (!sessionId || state.loadingSession) return;
  if (state.currentSessionId === sessionId && state.currentSession) return;
  if (state.activeRun && state.activeRun.sessionId !== sessionId) {
    if (!window.confirm("当前会话正在生成，切换会停止生成。继续？")) return;
    stopGeneration();
  }
  state.loadingSession = true;
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(sessionId)}?limit=50`);
    state.currentSessionId = sessionId;
    state.currentSession = data.session;
    state.messages = Array.isArray(data.messages) ? data.messages : [];
    state.nextBefore = data.next_before || null;
    renderHistory();
    updateHeader();
    if (push) {
      history.pushState({sessionId}, "", `/s/${sessionId}`);
    }
    try { localStorage.setItem(CURRENT_SESSION_KEY, sessionId); } catch { /* ignore */ }
    closeSidebar();
    renderSessions();
  } catch (error) {
    if (error.status === 404) {
      state.sessions = state.sessions.filter(item => item.session_id !== sessionId);
      renderSessions();
      showToast("会话不存在或已删除");
      if (state.currentSessionId === sessionId) newSession();
    } else {
      showToast(error.message || "会话加载失败");
    }
  } finally {
    state.loadingSession = false;
  }
}

async function refreshCurrentSessionMetadata() {
  if (!state.currentSessionId) return;
  await loadSessions();
  const found = state.sessions.find(item => item.session_id === state.currentSessionId);
  if (found) {
    state.currentSession = found;
    updateHeader();
  }
}

async function ensureSession() {
  if (state.currentSessionId && state.currentSession) return state.currentSession;
  const data = await api("/api/sessions", {method: "POST", body: JSON.stringify({})});
  const session = data.session;
  state.currentSessionId = session.session_id;
  state.currentSession = session;
  state.sessions = [session, ...state.sessions.filter(item => item.session_id !== session.session_id)];
  renderSessions();
  updateHeader();
  history.pushState({sessionId: session.session_id}, "", `/s/${session.session_id}`);
  try { localStorage.setItem(CURRENT_SESSION_KEY, session.session_id); } catch { /* ignore */ }
  notifySessionsChanged();
  return session;
}

function setBusy(busy) {
  input.disabled = busy;
  send.textContent = busy ? "停止生成" : "发送";
  send.type = busy ? "button" : "submit";
  document.querySelectorAll(".suggestions button").forEach(button => { button.disabled = busy; });
}

function stopGeneration() {
  if (!state.activeRun) return;
  const run = state.activeRun;
  run.completed = false;
  run.controller.abort();
  cancelAnimationFrame(run.frame);
  run.status = "已停止，回答未完成核查。";
  renderDraft(run);
  run.pending.removeAttribute("aria-busy");
  state.activeRun = null;
  setBusy(false);
  input.focus();
}

function renderDraft(run) {
  if (!run) return;
  const follow = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 220;
  run.bubble.innerHTML = `<p class="meta stream-status" role="status">${escapeHtml(run.status)}</p><div class="markdown-body">${renderMarkdown(run.text)}</div>`;
  if (follow) run.pending.scrollIntoView({block: "end"});
}

function scheduleDraft(run) {
  if (run.frame) return;
  run.frame = requestAnimationFrame(() => {
    run.frame = null;
    renderDraft(run);
  });
}

async function ask(question) {
  if (state.activeRun || !question.trim()) return;
  try {
    await ensureSession();
  } catch (error) {
    showToast(error.message || "无法创建会话");
    return;
  }
  addMessage("user", `<p>${escapeHtml(question)}</p>`);
  const pending = addMessage("assistant", '<p class="meta" role="status">正在检索本地史料…</p>');
  pending.setAttribute("aria-busy", "true");
  const run = {
    controller: new AbortController(),
    pending,
    bubble: pending.querySelector(".bubble"),
    text: "",
    status: "正在检索本地史料…",
    frame: null,
    completed: false,
    sessionId: state.currentSessionId,
    question
  };
  state.activeRun = run;
  setBusy(true);
  let completed = false;
  try {
    const response = await fetch("/api/questions/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-CSRF-Token": state.csrf
      },
      body: JSON.stringify({
        question,
        top_k: 12,
        session_id: state.currentSessionId,
        client_request_id: uuid()
      }),
      signal: run.controller.signal
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(typeof data.detail === "string" ? data.detail : "问答服务暂时不可用");
    }
    await consumeEventStream(response, (event, data) => {
      if (state.activeRun !== run) return false;
      if (event === "status") {
        run.status = data.message;
        scheduleDraft(run);
      } else if (event === "delta") {
        run.text += data.text;
        scheduleDraft(run);
      } else if (event === "reset") {
        cancelAnimationFrame(run.frame);
        run.frame = null;
        run.text = "";
        run.status = data.message;
        renderDraft(run);
      } else if (event === "error") {
        throw new Error(data.message || "问答服务暂时不可用");
      } else if (event === "done") {
        cancelAnimationFrame(run.frame);
        run.frame = null;
        run.bubble.innerHTML = renderAnswer(data);
        run.completed = true;
        completed = true;
        return false;
      }
      return true;
    });
    if (!completed && state.activeRun === run) throw new Error("连接中断，回答未完成，请重新发送问题");
  } catch (error) {
    if (error.name === "AbortError") {
      run.bubble.innerHTML = `<p class="meta">${escapeHtml(run.status || "已停止，回答未完成核查。")}</p>`;
    } else if (state.activeRun === run) {
      cancelAnimationFrame(run.frame);
      run.frame = null;
      run.bubble.innerHTML = `<p>暂时无法回答：${escapeHtml(error.message)}</p>`;
    }
  } finally {
    cancelAnimationFrame(run.frame);
    pending.removeAttribute("aria-busy");
    if (state.activeRun === run) {
      state.activeRun = null;
      setBusy(false);
      input.focus();
    }
    if (completed) {
      await refreshCurrentSessionMetadata();
      notifySessionsChanged();
      refreshVisitorInfo();
    }
  }
}

async function refreshVisitorInfo() {
  try {
    const info = await api("/api/visitor");
    state.visitorLabel = info.visitor?.label || "";
    if (visitorLabel) visitorLabel.textContent = `本浏览器工作区 · ${state.visitorLabel}`;
    if (quotaLabel && info.quota) {
      quotaLabel.textContent = info.quota.enabled
        ? `今日提问 ${info.quota.used_today}/${info.quota.daily_questions}`
        : "配额限制未启用";
    }
  } catch { /* best effort */ }
}

async function loadOlderMessages() {
  if (!state.currentSessionId || !state.nextBefore) return;
  const button = document.querySelector("#load-older");
  if (button) button.disabled = true;
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(state.currentSessionId)}/messages?before=${state.nextBefore}&limit=50`);
    state.messages = [...(data.messages || []), ...state.messages];
    state.nextBefore = data.next_before || null;
    renderHistory({keepScroll: true});
  } catch (error) {
    showToast(error.message || "更早消息加载失败");
    if (button) button.disabled = false;
  }
}

async function renameCurrentSession() {
  const session = currentSession();
  if (!session) return;
  const title = window.prompt("会话标题", session.title || "");
  if (title === null) return;
  const trimmed = title.trim();
  if (!trimmed) return;
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(session.session_id)}`, {
      method: "PATCH",
      body: JSON.stringify({title: trimmed, version: session.version})
    });
    state.currentSession = data.session;
    updateHeader();
    await loadSessions();
    notifySessionsChanged();
  } catch (error) {
    showToast(error.message || "重命名失败");
  }
}

async function pinSession(sessionId, pinned) {
  try {
    await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: "PATCH",
      body: JSON.stringify({pinned})
    });
    await loadSessions();
    notifySessionsChanged();
  } catch (error) {
    showToast(error.message || "操作失败");
  }
}

async function archiveSession(sessionId, archived) {
  if (archived && state.currentSessionId === sessionId && state.activeRun) {
    if (!window.confirm("当前会话正在生成，归档会停止生成。继续？")) return;
    stopGeneration();
  }
  try {
    await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: "PATCH",
      body: JSON.stringify({status: archived ? "archived" : "active"})
    });
    await loadSessions();
    notifySessionsChanged();
    if (archived && state.currentSessionId === sessionId) newSession();
  } catch (error) {
    showToast(error.message || "操作失败");
  }
}

async function deleteSession(sessionId) {
  if (!window.confirm("删除这个会话？30 天内可以撤销。")) return;
  if (state.currentSessionId === sessionId && state.activeRun) stopGeneration();
  try {
    await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {method: "DELETE"});
    const wasCurrent = state.currentSessionId === sessionId;
    state.sessions = state.sessions.filter(item => item.session_id !== sessionId);
    renderSessions();
    if (wasCurrent) newSession();
    notifySessionsChanged();
    showToast("会话已删除", "撤销", async () => {
      await api(`/api/sessions/${encodeURIComponent(sessionId)}/restore`, {method: "POST"});
      await loadSessions();
      await selectSession(sessionId);
      notifySessionsChanged();
    });
  } catch (error) {
    showToast(error.message || "删除失败");
  }
}

function newSession({push = true} = {}) {
  if (state.activeRun) {
    if (!window.confirm("当前会话正在生成，新建会话会停止生成。继续？")) return;
    stopGeneration();
  }
  if (push) history.pushState({}, "", "/");
  try { localStorage.removeItem(CURRENT_SESSION_KEY); } catch { /* ignore */ }
  showWelcome();
  input.focus();
}

async function deleteAllData() {
  if (!window.confirm("删除本浏览器工作区的全部会话？此操作不可撤销。")) return;
  if (state.activeRun) stopGeneration();
  try {
    await api("/api/visitor/data", {method: "DELETE"});
    state.sessions = [];
    state.hasMore = false;
    renderSessions();
    newSession();
    notifySessionsChanged();
    showToast("全部会话已删除");
  } catch (error) {
    showToast(error.message || "删除失败");
  }
}

async function claimLegacySession() {
  let legacy = null;
  try { legacy = localStorage.getItem(LEGACY_SESSION_KEY); } catch { return; }
  if (!legacy) return;
  try {
    const data = await api("/api/sessions/claim", {
      method: "POST",
      body: JSON.stringify({legacy_session_id: legacy})
    });
    if (data.session?.session_id) {
      try { localStorage.setItem(CURRENT_SESSION_KEY, data.session.session_id); } catch { /* ignore */ }
    }
  } catch {
    // A stale legacy id should not block the new workspace.
  } finally {
    try { localStorage.removeItem(LEGACY_SESSION_KEY); } catch { /* ignore */ }
  }
}

async function bootstrap() {
  try {
    const info = await api("/api/visitor");
    state.csrf = info.csrf_token || "";
    state.visitorLabel = info.visitor?.label || "";
    if (visitorLabel) visitorLabel.textContent = `本浏览器工作区 · ${state.visitorLabel}`;
    if (quotaLabel && info.quota) {
      quotaLabel.textContent = info.quota.enabled
        ? `今日提问 ${info.quota.used_today}/${info.quota.daily_questions}`
        : "配额限制未启用";
    }
  } catch (error) {
    statusDot.className = "bad";
    statusText.textContent = error.message || "无法连接会话服务";
    showToast("无法连接会话服务，请刷新重试");
    return;
  }
  const cookieEnabled = document.cookie.split("; ").some(item => item.startsWith("start1921_cookie_check="));
  if (!cookieEnabled && cookieWarning) cookieWarning.hidden = false;
  await claimLegacySession();
  await loadSessions();
  const target = routeSessionId() || (() => {
    try { return localStorage.getItem(CURRENT_SESSION_KEY); } catch { return null; }
  })();
  if (target) {
    try {
      await selectSession(target, {push: Boolean(routeSessionId())});
    } catch {
      newSession();
    }
  } else {
    newSession();
  }
  refreshVisitorInfo();
}

function bindEvents() {
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (state.activeRun) return;
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    input.style.height = "auto";
    ask(question);
  });
  send.addEventListener("click", event => {
    if (state.activeRun) {
      event.preventDefault();
      stopGeneration();
    }
  });
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
  });
  messagesEl.addEventListener("click", event => {
    const button = event.target.closest(".suggestions button");
    if (button && !state.activeRun) ask(button.textContent);
  });
  newSessionButton?.addEventListener("click", newSession);
  sidebarToggle?.addEventListener("click", openSidebar);
  sidebarOverlay?.addEventListener("click", closeSidebar);
  renameSessionButton?.addEventListener("click", renameCurrentSession);
  deleteSessionButton?.addEventListener("click", () => {
    if (state.currentSessionId) deleteSession(state.currentSessionId);
  });
  exportData?.addEventListener("click", () => closeSidebar());
  deleteAllDataButton?.addEventListener("click", deleteAllData);
  toggleArchived?.addEventListener("click", async () => {
    state.status = state.status === "active" ? "archived" : "active";
    toggleArchived.textContent = state.status === "active" ? "查看归档" : "返回会话";
    await loadSessions();
  });
  sessionSearch?.addEventListener("input", () => {
    clearTimeout(sessionSearch._timer);
    sessionSearch._timer = setTimeout(async () => {
      state.query = sessionSearch.value.trim();
      await loadSessions();
    }, 250);
  });
  loadMoreSessions?.addEventListener("click", () => loadSessions({append: true}));
  sessionList?.addEventListener("click", async event => {
    const actionButton = event.target.closest("button[data-action]");
    if (actionButton) {
      event.preventDefault();
      event.stopPropagation();
      const item = actionButton.closest(".session-item");
      const sessionId = item?.dataset.sessionId;
      if (!sessionId) return;
      const action = actionButton.dataset.action;
      if (action === "rename") {
        if (state.currentSessionId !== sessionId) await selectSession(sessionId);
        await renameCurrentSession();
      } else if (action === "pin" || action === "unpin") {
        await pinSession(sessionId, action === "pin");
      } else if (action === "archive" || action === "unarchive") {
        await archiveSession(sessionId, action === "archive");
      } else if (action === "delete") {
        await deleteSession(sessionId);
      }
      return;
    }
    const select = event.target.closest(".session-select");
    if (select) {
      const item = select.closest(".session-item");
      if (item?.dataset.sessionId) await selectSession(item.dataset.sessionId);
    }
  });
  window.addEventListener("popstate", () => {
    const target = routeSessionId();
    if (target) {
      selectSession(target, {push: false});
    } else {
      newSession({push: false});
    }
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeSidebar();
  });
  if ("BroadcastChannel" in window) {
    channel = new BroadcastChannel(CHANNEL_NAME);
    channel.onmessage = async event => {
      if (event.data?.type !== "changed") return;
      await loadSessions();
      if (state.currentSessionId && !state.activeRun) {
        const found = state.sessions.find(item => item.session_id === state.currentSessionId);
        if (!found) {
          newSession();
        } else if (!state.messages.length) {
          await selectSession(state.currentSessionId, {push: false});
        }
      }
    };
  }
}

bindEvents();
bootstrap();

fetch("/api/health").then(result => result.json()).then(data => {
  const ready = data.status === "ok";
  statusDot.className = ready ? "ok" : "bad";
  statusText.textContent = ready
    ? `本地双索引已就绪 · ${data.llm_enabled ? `DeepSeek ${data.llm_model}` : "DeepSeek 密钥未配置 · 证据摘录模式"}`
    : "索引尚未完成，请先执行构建命令";
}).catch(() => {
  statusDot.className = "bad";
  statusText.textContent = "无法读取服务状态";
});
