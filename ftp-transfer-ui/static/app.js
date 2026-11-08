"use strict";
/* FTP 远程文件传输 —— 前端逻辑 */

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const el = {
  apiStatus: $("#apiStatus"),
  host: $("#host"), port: $("#port"), user: $("#user"), pass: $("#pass"),
  remoteDir: $("#remoteDir"), createDirs: $("#createDirs"), overwrite: $("#overwrite"),
  remember: $("#remember"), btnTest: $("#btnTest"), connMsg: $("#connMsg"),
  dropzone: $("#dropzone"), fileInput: $("#fileInput"), dirInput: $("#dirInput"),
  btnFiles: $("#btnFiles"), btnDir: $("#btnDir"), pickMsg: $("#pickMsg"),
  queueSummary: $("#queueSummary"), totalBar: $("#totalBar"), totalPct: $("#totalPct"),
  queue: $("#queue"), queueEmpty: $("#queueEmpty"),
  btnStart: $("#btnStart"), btnCancel: $("#btnCancel"), btnClear: $("#btnClear"),
  log: $("#log"), btnClearLog: $("#btnClearLog"), togglePw: $("#togglePw"),
};

const state = {
  entries: [], // {id, relPath, file, size, status, progress, error, attempts}
  running: false,
  cancelFlag: false,
  nextId: 1,
};

/* ---------------- 工具 ---------------- */
function b64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}
function fmtSize(n) {
  if (n == null || isNaN(n)) return "0 B";
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
  return (n / 1024 / 1024 / 1024).toFixed(2) + " GB";
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const now = () => {
  const d = new Date();
  const p = (x) => String(x).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};

function log(level, msg) {
  const div = document.createElement("div");
  const t = document.createElement("span");
  t.className = "t";
  t.textContent = now();
  const m = document.createElement("span");
  m.className = level;
  m.textContent = msg;
  div.appendChild(t);
  div.appendChild(m);
  el.log.appendChild(div);
  el.log.scrollTop = el.log.scrollHeight;
}

/* ---------------- 连接配置 ---------------- */
function collectCfg() {
  const cfg = {
    host: el.host.value.trim(),
    port: parseInt(el.port.value, 10) || 21,
    user: el.user.value.trim(),
    password: el.pass.value,
    remote_dir: el.remoteDir.value.trim() || "/",
    create_missing: el.createDirs.checked,
    overwrite: el.overwrite.checked,
  };
  return cfg;
}
const CFG_KEY = "ftpui.remembered";

function saveCfg(cfg) {
  try { localStorage.setItem(CFG_KEY, JSON.stringify(cfg)); } catch (e) { /* ignore */ }
}
function loadCfg() {
  try {
    const raw = localStorage.getItem(CFG_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
}
function fillCfg(cfg) {
  if (!cfg) return;
  el.host.value = cfg.host || "";
  el.port.value = cfg.port || 21;
  el.user.value = cfg.user || "anonymous";
  el.pass.value = cfg.password || "";
  el.remoteDir.value = cfg.remote_dir || "/";
  el.createDirs.checked = cfg.create_missing !== false;
  el.overwrite.checked = cfg.overwrite !== false;
  el.remember.checked = true;
}

async function healthCheck() {
  try {
    const res = await fetch("/api/health", { cache: "no-store" });
    const data = await res.json();
    if (res.ok && data.ok) {
      el.apiStatus.textContent = "本地服务正常";
      el.apiStatus.className = "badge badge-ok";
      return true;
    }
    throw new Error("bad");
  } catch (e) {
    el.apiStatus.textContent = "本地服务未连接";
    el.apiStatus.className = "badge badge-err";
    return false;
  }
}

async function testConnect() {
  const cfg = collectCfg();
  if (!cfg.host) { setMsg("err", "请先填写主机 IP"); return; }
  setMsg("", "");
  el.btnTest.disabled = true;
  const old = el.btnTest.textContent;
  el.btnTest.textContent = "连接中…";
  try {
    const res = await fetch("/api/probe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    });
    const data = await res.json();
    if (data.ok) {
      setMsg("ok", "✔ " + data.message);
      log("ok", "测试连接成功: " + data.message);
      if (el.remember.checked) saveCfg(cfg);
    } else {
      setMsg("err", "✘ " + (data.error || "连接失败"));
      log("err", "测试连接失败: " + (data.error || "未知错误"));
    }
  } catch (e) {
    setMsg("err", "✘ 无法连接本地服务: " + e.message);
  } finally {
    el.btnTest.disabled = false;
    el.btnTest.textContent = old;
  }
}
function setMsg(cls, text) {
  el.connMsg.className = "msg " + cls;
  el.connMsg.textContent = text;
}

/* ---------------- 添加文件/文件夹 ---------------- */
function addEntry(relPath, file) {
  if (state.running) return;
  const exist = state.entries.find((e) => e.relPath === relPath);
  if (exist) {
    if (exist.status === "uploading") {
      log("warn", "已忽略重复项(正在上传中): " + relPath);
      return;
    }
    exist.file = file;
    exist.size = file.size;
    exist.status = "queued";
    exist.error = "";
    exist.progress = 0;
    log("info", "已更新队列项: " + relPath);
    render();
    return;
  }
  state.entries.push({
    id: state.nextId++,
    relPath, file, size: file.size,
    status: "queued", progress: 0, error: "", attempts: 0,
  });
  render();
}

function addFiles(fileList, getRel) {
  let added = 0;
  for (const file of fileList) {
    const rel = getRel(file);
    if (!rel) continue;
    addEntry(rel, file);
    added++;
  }
  if (added) {
    flash("已添加 " + added + " 个文件,共 " + fmtSize(totalBytes()));
    log("info", "添加 " + added + " 个文件");
  }
}
function flash(text) {
  el.pickMsg.textContent = text;
  clearTimeout(flash._t);
  flash._t = setTimeout(() => (el.pickMsg.textContent = ""), 4000);
}

/* 拖拽目录树遍历(webkitGetAsEntry) */
function walkEntry(entry, prefix) {
  return new Promise((resolve, reject) => {
    if (entry.isFile) {
      entry.file(
        (f) => {
          const rel = prefix ? prefix + "/" + f.name : f.name;
          resolve({ rel, file: f });
        },
        reject
      );
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      const all = [];
      const readBatch = () => {
        reader.readEntries(
          async (entries) => {
            if (!entries.length) {
              const out = [];
              for (const e of all) {
                const base = prefix ? prefix + "/" + entry.name : entry.name;
                out.push(...(await walkEntry(e, base)));
              }
              resolve(out);
            } else {
              all.push(...entries);
              readBatch();
            }
          },
          reject
        );
      };
      readBatch();
    } else {
      resolve([]);
    }
  });
}

async function handleDrop(e) {
  e.preventDefault();
  el.dropzone.classList.remove("dragover");
  if (state.running) { flash("传输进行中,无法添加新文件"); return; }
  const dt = e.dataTransfer;
  const items = dt && dt.items ? Array.from(dt.items) : [];
  const entries = items.map((it) => it.webkitGetAsEntry && it.webkitGetAsEntry()).filter(Boolean);
  try {
    if (entries.length) {
      const found = [];
      for (const en of entries) {
        const res = await walkEntry(en, "");
        found.push(...res);
      }
      if (found.length) addFiles(found, (x) => x.rel);
      else flash("未发现可上传的文件(空文件夹不会被创建)");
    } else if (dt.files && dt.files.length) {
      const anyRel = Array.from(dt.files).some((f) => f.webkitRelativePath);
      addFiles(dt.files, (f) => f.webkitRelativePath || f.name);
      if (!anyRel) log("warn", "当前浏览器不支持拖入文件夹,请使用「选择文件夹」");
    } else {
      flash("未识别到拖入内容");
    }
  } catch (err) {
    flash("读取拖入内容失败: " + err.message);
  }
}

/* ---------------- 渲染 ---------------- */
const STATUS_TEXT = {
  queued: "等待中", uploading: "上传中", done: "已完成",
  skipped: "已跳过", error: "失败", cancelled: "已取消",
};
function totalBytes() {
  return state.entries.reduce((s, e) => s + (e.status === "cancelled" ? 0 : e.size), 0);
}
function iconOf(relPath) {
  return relPath.indexOf("/") >= 0 ? "🗀" : "📄";
}

function render() {
  // 清空重建
  el.queue.textContent = "";
  const rows = state.entries.map((e) => makeRow(e));
  rows.forEach((r) => el.queue.appendChild(r));
  el.queueEmpty.style.display = state.entries.length ? "none" : "block";

  const n = state.entries.length;
  el.queueSummary.textContent = n ? `(${n} 项 · ${fmtSize(totalBytes())})` : "";

  const hasTodo = state.entries.some((e) => ["queued", "error", "cancelled"].includes(e.status));
  el.btnStart.disabled = state.running || !hasTodo || !el.host.value.trim();
  el.btnCancel.disabled = !state.running;
  el.btnClear.disabled = state.running || !state.entries.length;
  updateTotal();
}

function makeRow(e) {
  const row = document.createElement("div");
  row.className = "qrow";
  row.dataset.id = e.id;

  const icon = document.createElement("span");
  icon.className = "qicon";
  icon.textContent = iconOf(e.relPath);

  const main = document.createElement("div");
  main.className = "qmain";
  const name = document.createElement("div");
  name.className = "qname";
  name.textContent = e.relPath;
  name.title = e.relPath;
  if (e.error) {
    const errTip = document.createElement("span");
    errTip.className = "qsub";
    errTip.textContent = e.error;
    name.appendChild(errTip);
  }
  main.appendChild(name);
  if (e.status === "uploading" || e.status === "done" || e.status === "error") {
    const bar = document.createElement("div");
    bar.className = "qbar";
    const fill = document.createElement("i");
    const pct = e.size ? Math.min(100, Math.round((e.progress / e.size) * 100)) : 100;
    fill.style.width = pct + "%";
    if (e.status === "done") fill.classList.add("done");
    if (e.status === "error") fill.classList.add("errbar");
    bar.appendChild(fill);
    main.appendChild(bar);
  }

  const size = document.createElement("span");
  size.className = "qsize";
  size.textContent = fmtSize(e.size);

  const chip = document.createElement("span");
  chip.className = "chip " + e.status;
  chip.textContent = STATUS_TEXT[e.status] || e.status;

  row.appendChild(icon);
  row.appendChild(main);
  row.appendChild(size);
  row.appendChild(chip);

  if (e.status === "error") {
    const retry = document.createElement("button");
    retry.className = "qbtn retry";
    retry.textContent = "↻";
    retry.title = "重新传输该文件";
    retry.addEventListener("click", () => {
      e.status = "queued";
      e.error = "";
      e.progress = 0;
      log("info", "已加入重试队列: " + e.relPath);
      render();
    });
    row.appendChild(retry);
  }
  if (e.status !== "uploading" && (e.status !== "queued" || !state.running)) {
    const del = document.createElement("button");
    del.className = "qbtn";
    del.textContent = "✕";
    del.title = "从队列移除";
    del.addEventListener("click", () => {
      state.entries = state.entries.filter((x) => x.id !== e.id);
      render();
    });
    row.appendChild(del);
  }
  return row;
}

function updateTotal() {
  let total = 0, done = 0;
  for (const e of state.entries) {
    if (e.status === "cancelled") continue;
    total += e.size;
    if (e.status === "done" || e.status === "skipped") done += e.size;
    else if (e.status === "uploading") done += e.progress;
  }
  const pct = total ? Math.round((done / total) * 100) : 0;
  el.totalBar.style.width = pct + "%";
  el.totalPct.textContent = pct + "%";
}

/* ---------------- 上传执行 ---------------- */
function uploadOne(entry, cfg) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    entry._xhr = xhr;
    xhr.open("POST", "/api/upload");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.setRequestHeader("X-Ftp-Cfg", b64(JSON.stringify(cfg)));
    xhr.setRequestHeader("X-Ftp-Rel", b64(entry.relPath));
    xhr.responseType = "json";
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) {
        entry.progress = ev.loaded;
        updateTotal();
      }
    };
    xhr.onload = () => {
      if (xhr.status === 0) {
        reject(Object.assign(new Error("本地服务连接中断"), { retryable: true }));
        return;
      }
      const r = xhr.response;
      if (xhr.status >= 200 && xhr.status < 300 && r && r.ok) {
        resolve(r);
      } else {
        const msg = (r && r.error) ? r.error : ("HTTP " + xhr.status);
        const retryable = !!(r && r.retryable);
        reject(Object.assign(new Error(msg), { retryable }));
      }
    };
    xhr.onerror = () => reject(Object.assign(new Error("网络错误,无法连接本地服务"), { retryable: true }));
    xhr.onabort = () => reject(Object.assign(new Error("已取消"), { aborted: true }));
    xhr.send(entry.file);
  });
}

async function runQueue() {
  if (state.running) return;
  const cfg = collectCfg();
  if (!cfg.host) { log("err", "请先填写主机 IP"); return; }

  for (const e of state.entries) {
    if (e.status === "error" || e.status === "cancelled") {
      e.status = "queued"; e.error = ""; e.progress = 0;
    }
  }
  const todo = state.entries.filter((e) => e.status === "queued");
  if (!todo.length) { log("warn", "没有待传输的文件"); return; }

  state.running = true;
  state.cancelFlag = false;
  render();

  const target = cfg.remote_dir && cfg.remote_dir !== "/" ? cfg.remote_dir : "/";
  const totalSize = todo.reduce((s, e) => s + e.size, 0);
  log("info", `开始传输 ${todo.length} 个文件,合计 ${fmtSize(totalSize)} → ${cfg.host}:${cfg.port}${target}`);
  if (!cfg.overwrite) log("warn", "已开启「跳过远程同名文件」:同名文件不会覆盖");
  log("info", "提示:空的文件夹不会被上传,请确保文件夹内至少包含一个文件");

  let ok = 0, skipped = 0, failed = 0, i = 0;
  for (const entry of todo) {
    if (state.cancelFlag) break;
    i++;
    entry.status = "uploading";
    entry.progress = 0;
    entry.error = "";
    render();
    log("info", `[${i}/${todo.length}] 上传 ${entry.relPath} (${fmtSize(entry.size)})`);

    let doneFlag = false;
    for (let attempt = 1; attempt <= 3 && !doneFlag; attempt++) {
      if (state.cancelFlag) break;
      try {
        const res = await uploadOne(entry, cfg);
        if (res.action === "skipped") {
          entry.status = "skipped";
          skipped++;
          log("warn", `跳过(远程已有同名文件): ${entry.relPath}`);
        } else {
          entry.status = "done";
          entry.progress = entry.size;
          ok++;
          log("ok", `完成: ${entry.relPath}`);
        }
        doneFlag = true;
      } catch (err) {
        if (err.aborted || state.cancelFlag) {
          entry.status = "cancelled";
          log("warn", "已取消: " + entry.relPath);
          break;
        }
        if (attempt < 3 && err.retryable === true) {
          log("warn", `${entry.relPath} 传输中断,${attempt * 1}s 后重试(${attempt}/2)…`);
          await sleep(attempt * 1000);
        } else {
          entry.status = "error";
          entry.error = err.message;
          failed++;
          log("err", `失败: ${entry.relPath} → ${err.message}`);
          doneFlag = true;
        }
      }
    }
    if (entry.status === "cancelled") break;
    updateTotal();
    render();
  }

  state.running = false;
  render();
  const tail = state.cancelFlag ? "已取消。" : "";
  log("info", `传输结束:成功 ${ok} 个,跳过 ${skipped} 个,失败 ${failed} 个。${tail}`);
}

function cancelRun() {
  if (!state.running) return;
  state.cancelFlag = true;
  const cur = state.entries.find((e) => e.status === "uploading");
  if (cur && cur._xhr) cur._xhr.abort();
  for (const e of state.entries) {
    if (e.status === "queued") e.status = "cancelled";
  }
  render();
  log("warn", "正在取消…");
}

/* ---------------- 事件绑定 ---------------- */
function bind() {
  el.btnTest.addEventListener("click", testConnect);

  el.btnFiles.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", () => {
    addFiles(el.fileInput.files, (f) => f.name);
    el.fileInput.value = "";
  });

  el.btnDir.addEventListener("click", () => el.dirInput.click());
  el.dirInput.addEventListener("change", () => {
    addFiles(el.dirInput.files, (f) => f.webkitRelativePath || f.name);
    el.dirInput.value = "";
  });

  el.dropzone.addEventListener("click", () => {
    if (!state.running) el.fileInput.click();
  });
  ["dragenter", "dragover"].forEach((ev) =>
    el.dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      el.dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "dragend"].forEach((ev) =>
    el.dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      el.dropzone.classList.remove("dragover");
    })
  );
  el.dropzone.addEventListener("drop", handleDrop);

  el.togglePw.addEventListener("click", () => {
    el.pass.type = el.pass.type === "password" ? "text" : "password";
  });

  el.btnStart.addEventListener("click", runQueue);
  el.btnCancel.addEventListener("click", cancelRun);
  el.btnClear.addEventListener("click", () => {
    state.entries = [];
    render();
  });
  el.btnClearLog.addEventListener("click", () => (el.log.textContent = ""));

  // 主机填写后允许开始
  el.host.addEventListener("input", render);
  // 记住配置:输入即存(避免泄露给明文存储,仅当用户勾选)
  ["host", "port", "user", "pass", "remoteDir"].forEach((id) => {
    const node = $(`#${id}`);
    node.addEventListener("change", () => {
      if (el.remember.checked && el.host.value.trim()) saveCfg(collectCfg());
    });
  });
  el.remember.addEventListener("change", () => {
    if (el.remember.checked && el.host.value.trim()) saveCfg(collectCfg());
    else localStorage.removeItem(CFG_KEY);
  });
}

/* ---------------- 启动 ---------------- */
(async function init() {
  bind();
  const ok = await healthCheck();
  if (!ok) log("err", "本地后端服务未连接,请确认已运行: python server.py");
  const saved = loadCfg();
  if (saved) fillCfg(saved);
  render();
  log("info", "界面就绪。填写服务器连接信息 → 测试连接 → 添加文件 → 开始传输。");
})();
