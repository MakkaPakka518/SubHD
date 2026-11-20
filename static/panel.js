"use strict";

const $ = (id) => document.getElementById(id);
let adminToken = sessionStorage.getItem("subhd-admin-token") || "";
let toastTimer;

function notify(message) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 3200);
}

function showError(id, message) {
  $(id).textContent = message || "";
  $(id).hidden = !message;
}

async function adminRequest(path, method = "GET") {
  const response = await fetch(path, { method, headers: { Authorization: "Bearer " + adminToken } });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "请求失败，请稍后重试");
    error.status = response.status;
    throw error;
  }
  return data;
}

function timeLabel(timestamp) {
  return timestamp ? new Date(timestamp * 1000).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "尚无记录";
}

function renderOverview(data) {
  $("module-url").value = data.moduleUrl;
  $("download-module").href = data.moduleUrl;
  $("copy-link").disabled = false;
  $("browser-status").textContent = data.browserInstalled ? "已安装" : "未检测到";
  $("download-status").textContent = data.busy ? "下载中" : "空闲";
  $("region").textContent = data.region;
  $("version").textContent = data.version;
  $("cache-files").textContent = data.cache.files + " / " + data.cache.capacity;
  $("last-download").textContent = timeLabel(data.lastDownload);
  $("updated-at").textContent = "更新于 " + new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  $("service-badge").textContent = data.busy ? "处理中" : "服务运行中";
  $("service-badge").classList.toggle("ready", !data.busy);
  $("clear-cache").disabled = data.busy || data.cache.files === 0;
  showError("last-error", data.lastError ? "最近下载未完成：" + data.lastError : "");
}

async function refresh() {
  $("refresh").disabled = true;
  $("refresh").setAttribute("aria-busy", "true");
  showError("workspace-error", "");
  try {
    renderOverview(await adminRequest("/api/admin/overview"));
  } catch (error) {
    if (error.status === 401) logout();
    else showError("workspace-error", error.message);
  } finally {
    $("refresh").disabled = false;
    $("refresh").removeAttribute("aria-busy");
  }
}

function logout() {
  adminToken = "";
  sessionStorage.removeItem("subhd-admin-token");
  $("workspace").hidden = true;
  $("session-actions").hidden = true;
  $("login").hidden = false;
  $("module-url").value = "";
  $("download-module").removeAttribute("href");
  $("copy-link").disabled = true;
  $("admin-token").value = "";
  $("admin-token").focus({ preventScroll: true });
}

async function login() {
  $("login-submit").disabled = true;
  $("login-submit").setAttribute("aria-busy", "true");
  $("login-submit").textContent = "正在登录…";
  showError("login-error", "");
  try {
    const data = await adminRequest("/api/admin/overview");
    sessionStorage.setItem("subhd-admin-token", adminToken);
    renderOverview(data);
    $("login").hidden = true;
    $("workspace").hidden = false;
    $("session-actions").hidden = false;
    $("admin-token").value = "";
    $("copy-link").focus({ preventScroll: true });
  } catch (error) {
    adminToken = "";
    sessionStorage.removeItem("subhd-admin-token");
    showError("login-error", error.message);
  } finally {
    $("login-submit").disabled = false;
    $("login-submit").removeAttribute("aria-busy");
    $("login-submit").textContent = "进入管理面板";
  }
}

$("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  adminToken = $("admin-token").value;
  $("admin-token").blur();
  login();
});
$("show-token").addEventListener("click", () => {
  const shown = $("admin-token").type === "password";
  $("admin-token").type = shown ? "text" : "password";
  $("show-token").setAttribute("aria-pressed", String(shown));
  $("show-token").setAttribute("aria-label", shown ? "隐藏管理口令" : "显示管理口令");
});
$("admin-token").addEventListener("focus", () => {
  if (matchMedia("(max-width: 640px)").matches) {
    setTimeout(() => $("admin-token").scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" }), 250);
  }
});
$("copy-link").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("module-url").value);
    notify("模块链接已复制");
  } catch {
    $("module-url").focus();
    $("module-url").select();
    notify("请复制已选中的模块链接");
  }
});
$("module-url").addEventListener("click", () => $("module-url").select());
$("refresh").addEventListener("click", refresh);
$("logout").addEventListener("click", logout);
$("clear-cache").addEventListener("click", async () => {
  $("clear-cache").disabled = true;
  try {
    await adminRequest("/api/admin/cache/clear", "POST");
    notify("下载缓存已清空");
    await refresh();
  } catch (error) {
    showError("workspace-error", error.message);
    $("clear-cache").disabled = false;
  }
});

fetch("/health").then((response) => response.json()).then((data) => {
  $("setup-note").hidden = data.configured;
}).catch(() => showError("login-error", "无法连接服务，请刷新页面重试"));
if (adminToken) login();
