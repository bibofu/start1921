// Local multi-session UI integration test. Install with:
// npm install --prefix data/frontend-deps --ignore-scripts --no-audit --no-fund playwright
import assert from "node:assert/strict";
import {createServer} from "node:http";
import {readFile, mkdir} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import {chromium} from "../data/frontend-deps/node_modules/playwright/index.mjs";

const root = new URL("../app/history_agent/web/static/", import.meta.url);
const sessions = new Map();
let nextSession = 1;
const requests = [];

function json(res, value, status = 200) {
  res.writeHead(status, {"Content-Type": "application/json"});
  res.end(JSON.stringify(value));
}
function sessionPayload(session) {
  return {
    session_id: session.id,
    title: session.title,
    title_source: session.titleSource,
    status: session.status,
    pinned: session.pinned,
    created_at: session.createdAt,
    updated_at: session.updatedAt,
    last_message_at: session.lastMessageAt,
    message_count: session.messages.length,
    last_message_preview: session.messages.at(-1)?.content.slice(0, 120) || "",
    version: session.version,
    deleted_at: session.deletedAt
  };
}
function createSession() {
  const id = `session-${String(nextSession++).padStart(8, "0")}`;
  const now = new Date().toISOString();
  const session = {id, title: "新会话", titleSource: "auto", status: "active", pinned: false, createdAt: now, updatedAt: now, lastMessageAt: now, messages: [], version: 0, deletedAt: null};
  sessions.set(id, session);
  return session;
}
function getSession(id) {
  return sessions.get(id) || null;
}
function addMessage(session, role, content, metadata = {}) {
  session.messages.push({message_id: session.messages.length + 1, role, content, status: "completed", created_at: new Date().toISOString(), metadata});
  session.updatedAt = new Date().toISOString();
  session.lastMessageAt = session.updatedAt;
  session.version += 1;
}
function send(res, event, data) {
  if (!res.destroyed) res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
}
function final(question) {
  return {
    answer: `## 研究结论\n\n关于“${question}”的证据摘录。[E1]`,
    retrieval_mode: "hybrid_rrf",
    generator_mode: "llm",
    model_name: "local-fixture",
    llm_status: "used",
    limitations: [],
    citations: [{evidence_id: "E1", document: "测试文献", pdf_page: 12, section: [], source_type: "chronology", verification_status: "verified", quote: "测试原文。"}]
  };
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1");
  if (url.pathname === "/api/health") {
    json(res, {status: "ok", llm_enabled: false});
    return;
  }
  if (url.pathname === "/api/visitor") {
    res.setHeader("Set-Cookie", ["start1921_cookie_check=1; Path=/", "start1921_vid=fixture; Path=/"]);
    json(res, {
      visitor: {label: "v_fixture"},
      csrf_token: "fixture-csrf",
      quota: {daily_questions: 100, used_today: 0, enabled: false},
      limits: {max_sessions: 50, max_messages_per_session: 1000}
    });
    return;
  }
  if (url.pathname === "/api/sessions" && req.method === "GET") {
    const items = [...sessions.values()].filter(session => session.status === "active").map(sessionPayload);
    json(res, {items, has_more: false, offset: 0, limit: 50});
    return;
  }
  if (url.pathname === "/api/sessions" && req.method === "POST") {
    json(res, {session: sessionPayload(createSession())});
    return;
  }
  if (url.pathname === "/api/sessions/claim" && req.method === "POST") {
    json(res, {detail: "no legacy session"}, 404);
    return;
  }
  const match = url.pathname.match(/^\/api\/sessions\/([^/]+)(\/messages|\/restore)?$/);
  if (match) {
    const session = getSession(match[1]);
    if (!session || session.status === "deleted") {
      json(res, {detail: "会话不存在"}, 404);
      return;
    }
    if (match[2] === "/messages" && req.method === "GET") {
      json(res, {messages: session.messages, next_before: null});
      return;
    }
    if (match[2] === "/restore" && req.method === "POST") {
      session.status = "active";
      session.deletedAt = null;
      json(res, {session: sessionPayload(session)});
      return;
    }
    if (req.method === "GET") {
      json(res, {session: sessionPayload(session), messages: session.messages, next_before: null});
      return;
    }
    if (req.method === "PATCH") {
      let body = "";
      for await (const chunk of req) body += chunk;
      const data = JSON.parse(body || "{}");
      if (data.title !== undefined) { session.title = data.title; session.titleSource = "user"; }
      if (data.pinned !== undefined) session.pinned = data.pinned;
      if (data.status !== undefined) session.status = data.status;
      session.version += 1;
      json(res, {session: sessionPayload(session)});
      return;
    }
    if (req.method === "DELETE") {
      session.status = "deleted";
      session.deletedAt = new Date().toISOString();
      json(res, {deleted: true, session: sessionPayload(session), undo_until: "later"});
      return;
    }
  }
  if (url.pathname === "/api/visitor/export") {
    json(res, {sessions: [...sessions.values()].map(session => ({session: sessionPayload(session), messages: session.messages}))});
    return;
  }
  if (url.pathname === "/api/visitor/data" && req.method === "DELETE") {
    sessions.clear();
    json(res, {deleted_sessions: 0});
    return;
  }
  if (url.pathname === "/api/questions/stream") {
    let body = "";
    for await (const chunk of req) body += chunk;
    const data = JSON.parse(body);
    requests.push(data);
    const session = getSession(data.session_id) || createSession();
    if (session.title === "新会话") session.title = data.question.slice(0, 30);
    addMessage(session, "user", data.question);
    res.writeHead(200, {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"});
    send(res, "status", {message: "正在生成回答…"});
    send(res, "delta", {text: "## 研究结论\n\n"});
    setTimeout(() => {
      const answer = final(data.question);
      const {answer: _answer, ...metadata} = answer;
      addMessage(session, "assistant", answer.answer, metadata);
      send(res, "done", answer);
      res.end();
    }, 250);
    return;
  }
  const path = url.pathname === "/" || url.pathname.startsWith("/s/") ? "index.html" : url.pathname.split("/").pop();
  try {
    const bytes = await readFile(new URL(path, root));
    res.setHeader("Content-Type", path.endsWith(".js") ? "text/javascript" : path.endsWith(".css") ? "text/css" : "text/html");
    res.end(bytes);
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({channel: "msedge", headless: true});
  const page = await browser.newPage({viewport: {width: 1200, height: 1000}});
  const errors = [];
  let dialogs = 0;
  page.on("pageerror", error => errors.push(error.message));
  page.on("dialog", dialog => { dialogs += 1; dialog.accept(); });
  await page.route("**/*", route => {
    if (!route.request().url().startsWith(base)) return route.abort();
    return route.continue();
  });
  await page.goto(base);
  await page.getByRole("button", {name: "新建会话"}).waitFor();
  assert.equal(await page.locator(".message.welcome").count(), 1);

  async function ask(text) {
    await page.locator("#question").fill(text);
    await page.getByRole("button", {name: "发送", exact: true}).click();
    await page.getByRole("heading", {name: "研究结论"}).waitFor();
    await page.locator(".evidence summary").last().waitFor();
  }

  await ask("第一问");
  assert.equal(await page.locator(".session-item").count(), 1);
  assert.match(requests.at(-1).session_id, /^[A-Za-z0-9_-]{16,64}$/);
  assert.equal("history" in requests.at(-1), false);
  assert.equal(await page.locator(".message.user .bubble").last().textContent(), "第一问");
  assert.equal(await page.locator(".evidence summary").count(), 1);

  await page.getByRole("button", {name: "新建会话"}).click();
  assert.equal(await page.locator(".message.welcome").count(), 1);
  await ask("第二问");
  assert.equal(await page.locator(".session-item").count(), 2);

  await page.locator(".session-item").filter({hasText: "第一问"}).locator(".session-select").click();
  await page.locator(".message.user", {hasText: "第一问"}).waitFor();
  await page.locator(".evidence summary").last().waitFor();
  assert.equal(await page.locator(".evidence summary").count(), 1);
  assert.match(await page.locator("#current-title").textContent(), /第一问/);

  await page.setViewportSize({width: 390, height: 844});
  await page.locator("#sidebar-toggle").click();
  assert.equal(await page.locator("#sidebar").evaluate(node => node.classList.contains("open")), true);
  await page.locator("#sidebar-overlay").click();
  assert.equal(await page.locator("#sidebar").evaluate(node => node.classList.contains("open")), false);
  await mkdir(new URL("../data/reports/", import.meta.url), {recursive: true});
  await page.screenshot({path: fileURLToPath(new URL("../data/reports/multisession-mobile.png", import.meta.url)), fullPage: true});
  await page.setViewportSize({width: 1200, height: 1000});

  await page.getByRole("button", {name: "删除会话"}).click();
  await page.locator(".message.welcome").waitFor();
  assert.equal(await page.locator(".session-item").count(), 1);
  assert.equal(dialogs, 0);
  assert.equal(await page.getByText("会话已删除").count(), 0);
  assert.deepEqual(errors, []);
  console.log("PASS: multi-session create/switch, sidebar, mobile drawer, streaming answer, citations, delete.");
} finally {
  await browser?.close();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
