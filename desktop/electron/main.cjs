const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

const isDev = Boolean(process.env.VITE_DEV_SERVER_URL);

function repoRoot() {
  if (app.isPackaged) {
    return path.dirname(app.getAppPath());
  }
  return path.resolve(__dirname, "../..");
}

function engineDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "engine");
  }
  return path.join(repoRoot(), "engine");
}

function userDataRoot() {
  return app.getPath("userData");
}

function outDir() {
  if (app.isPackaged) {
    return path.join(userDataRoot(), "out");
  }
  return path.join(repoRoot(), "data", "out");
}

function financeDir() {
  if (app.isPackaged) {
    return path.join(userDataRoot(), "finance");
  }
  return path.join(repoRoot(), "data", "finance");
}

function rotationDir() {
  if (app.isPackaged) {
    return path.join(userDataRoot(), "rotation");
  }
  return path.join(repoRoot(), "data", "rotation");
}

/** GitHub sync target — this repo only. Never qiao-zhen. */
const FINANCE_GH = {
  owner: "stvenfor",
  repo: "etf-68-app",
  branch: "main",
  userDataPath: "data/finance/userData.json",
  dataPath: "data/finance/data.json",
};

function financeSyncConfigPath() {
  return path.join(userDataRoot(), "finance-sync.json");
}

function readFinanceSyncConfig() {
  try {
    const p = financeSyncConfigPath();
    if (!fs.existsSync(p)) return { token: "", proxy: "" };
    const j = JSON.parse(fs.readFileSync(p, "utf8"));
    return { token: String(j.token || "").trim(), proxy: String(j.proxy || "").trim() };
  } catch {
    return { token: "", proxy: "" };
  }
}

function writeFinanceSyncConfig(cfg) {
  fs.mkdirSync(userDataRoot(), { recursive: true });
  fs.writeFileSync(
    financeSyncConfigPath(),
    JSON.stringify(
      { token: String(cfg.token || "").trim(), proxy: String(cfg.proxy || "").trim() },
      null,
      2
    ),
    "utf8"
  );
}

function ensureFinanceFiles() {
  const dir = financeDir();
  fs.mkdirSync(dir, { recursive: true });
  const ud = path.join(dir, "userData.json");
  const dj = path.join(dir, "data.json");
  if (!fs.existsSync(ud)) {
    fs.writeFileSync(
      ud,
      JSON.stringify({ assetList: [], rebalanceList: [], updatedAt: null }, null, 2) + "\n",
      "utf8"
    );
  }
  if (!fs.existsSync(dj)) {
    fs.writeFileSync(
      dj,
      JSON.stringify(
        { financeNews: [], indexTrack: [], fundQuotes: {}, updatedAt: null },
        null,
        2
      ) + "\n",
      "utf8"
    );
  }
  return { userDataPath: ud, dataPath: dj };
}

function readJsonFile(file, fallback) {
  try {
    if (!fs.existsSync(file)) return fallback;
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

function writeJsonFile(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n", "utf8");
}

let _financePushTimer = null;

function scheduleFinanceCloudPush(which) {
  const cfg = readFinanceSyncConfig();
  if (!cfg.token) return;
  if (_financePushTimer) clearTimeout(_financePushTimer);
  _financePushTimer = setTimeout(() => {
    financeCloudPush({ which: which || "both", silent: true }).catch(() => {});
  }, 1800);
}

async function githubRequest(apiPath, { method = "GET", body, token, proxy } = {}) {
  const apiBase = `https://api.github.com/repos/${FINANCE_GH.owner}/${FINANCE_GH.repo}${apiPath}`;
  const url = proxy ? `${proxy.replace(/\/$/, "")}/${apiBase}` : apiBase;
  const headers = {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "User-Agent": "etf-68-app-finance-sync",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (body) headers["Content-Type"] = "application/json";
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 25000);
  try {
    const res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    const text = await res.text();
    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = { raw: text };
    }
    return { ok: res.ok, status: res.status, json };
  } finally {
    clearTimeout(timer);
  }
}

async function financeCloudPull() {
  const cfg = readFinanceSyncConfig();
  if (!cfg.token) return { ok: false, error: "missing_github_token" };
  ensureFinanceFiles();
  const { userDataPath, dataPath } = ensureFinanceFiles();

  async function getFile(filePath) {
    const enc = encodeURIComponent(filePath).replace(/%2F/g, "/");
    const r = await githubRequest(`/contents/${enc}?ref=${FINANCE_GH.branch}`, {
      token: cfg.token,
      proxy: cfg.proxy,
    });
    if (!r.ok) return { ok: false, status: r.status, error: r.json?.message || `get_${r.status}` };
    const content = Buffer.from(r.json.content || "", "base64").toString("utf8");
    return { ok: true, sha: r.json.sha, data: JSON.parse(content) };
  }

  const udRemote = await getFile(FINANCE_GH.userDataPath);
  const djRemote = await getFile(FINANCE_GH.dataPath);
  if (!udRemote.ok && udRemote.status !== 404) {
    return { ok: false, error: `userData_pull:${udRemote.error}` };
  }
  if (!djRemote.ok && djRemote.status !== 404) {
    return { ok: false, error: `data_pull:${djRemote.error}` };
  }

  // Pull = overwrite local finance fields (整表覆盖)
  if (udRemote.ok) {
    const local = readJsonFile(userDataPath, {});
    writeJsonFile(userDataPath, {
      ...local,
      assetList: udRemote.data.assetList || [],
      rebalanceList: udRemote.data.rebalanceList || [],
      updatedAt: udRemote.data.updatedAt || new Date().toISOString(),
    });
  }
  if (djRemote.ok) {
    const local = readJsonFile(dataPath, {});
    writeJsonFile(dataPath, {
      ...local,
      financeNews: djRemote.data.financeNews || local.financeNews || [],
      indexTrack: djRemote.data.indexTrack || local.indexTrack || [],
      fundQuotes: djRemote.data.fundQuotes || local.fundQuotes || {},
      updatedAt: djRemote.data.updatedAt || new Date().toISOString(),
    });
  }
  return {
    ok: true,
    userData: readJsonFile(userDataPath, {}),
    data: readJsonFile(dataPath, {}),
  };
}

async function financeCloudPush({ which = "both", silent = false } = {}) {
  const cfg = readFinanceSyncConfig();
  if (!cfg.token) return { ok: false, error: "missing_github_token" };
  ensureFinanceFiles();
  const { userDataPath, dataPath } = ensureFinanceFiles();

  async function putFile(filePath, localObj) {
    const enc = encodeURIComponent(filePath).replace(/%2F/g, "/");
    const existing = await githubRequest(`/contents/${enc}?ref=${FINANCE_GH.branch}`, {
      token: cfg.token,
      proxy: cfg.proxy,
    });
    let remote = {};
    let sha = null;
    if (existing.ok) {
      sha = existing.json.sha;
      try {
        remote = JSON.parse(Buffer.from(existing.json.content || "", "base64").toString("utf8"));
      } catch {
        remote = {};
      }
    } else if (existing.status !== 404) {
      return { ok: false, error: existing.json?.message || `get_${existing.status}` };
    }
    // Field-level merge for data.json; userData overwrite asset/rebalance keys
    let merged;
    if (filePath === FINANCE_GH.dataPath) {
      merged = {
        ...remote,
        financeNews: localObj.financeNews ?? remote.financeNews,
        indexTrack: localObj.indexTrack ?? remote.indexTrack,
        fundQuotes: localObj.fundQuotes ?? remote.fundQuotes,
        updatedAt: localObj.updatedAt || new Date().toISOString(),
      };
    } else {
      merged = {
        ...remote,
        assetList: localObj.assetList ?? remote.assetList ?? [],
        rebalanceList: localObj.rebalanceList ?? remote.rebalanceList ?? [],
        updatedAt: localObj.updatedAt || new Date().toISOString(),
      };
    }
    const content = Buffer.from(JSON.stringify(merged, null, 2) + "\n", "utf8").toString("base64");
    const body = {
      message: `sync finance ${path.basename(filePath)} ${new Date().toISOString()}`,
      content,
      branch: FINANCE_GH.branch,
    };
    if (sha) body.sha = sha;
    const put = await githubRequest(`/contents/${enc}`, {
      method: "PUT",
      body,
      token: cfg.token,
      proxy: cfg.proxy,
    });
    if (!put.ok) {
      return { ok: false, error: put.json?.message || `put_${put.status}` };
    }
    return { ok: true };
  }

  const results = {};
  if (which === "both" || which === "userData") {
    results.userData = await putFile(
      FINANCE_GH.userDataPath,
      readJsonFile(userDataPath, { assetList: [], rebalanceList: [] })
    );
  }
  if (which === "both" || which === "data") {
    results.data = await putFile(
      FINANCE_GH.dataPath,
      readJsonFile(dataPath, { financeNews: [], indexTrack: [], fundQuotes: {} })
    );
  }
  const ok = Object.values(results).every((r) => r && r.ok);
  return { ok, results, silent };
}

function reportsDir() {
  if (app.isPackaged) {
    return path.join(userDataRoot(), "reports");
  }
  return path.join(engineDir(), "reports");
}

function staticDir() {
  if (app.isPackaged) {
    return path.join(userDataRoot(), "static");
  }
  return path.join(repoRoot(), "data", "static");
}

function pythonBin() {
  return process.env.ETF68_PYTHON || "python3.12";
}

function ensureDirs() {
  fs.mkdirSync(outDir(), { recursive: true });
  fs.mkdirSync(reportsDir(), { recursive: true });
  fs.mkdirSync(staticDir(), { recursive: true });
  fs.mkdirSync(rotationDir(), { recursive: true });
  ensureFinanceFiles();
}

function copyIfMissing(src, dest) {
  if (!fs.existsSync(src) || fs.existsSync(dest)) return;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

function bootstrapPackagedSeeds() {
  if (!app.isPackaged) return;
  const seedReports = path.join(process.resourcesPath, "seed-reports");
  const seedStatic = path.join(process.resourcesPath, "seed-static");
  if (fs.existsSync(seedReports)) {
    for (const name of fs.readdirSync(seedReports)) {
      copyIfMissing(path.join(seedReports, name), path.join(reportsDir(), name));
    }
  }
  if (fs.existsSync(seedStatic)) {
    for (const name of fs.readdirSync(seedStatic)) {
      copyIfMissing(path.join(seedStatic, name), path.join(staticDir(), name));
    }
  }
}

function runPython(args, { onLine, timeoutMs } = {}) {
  return new Promise((resolve, reject) => {
    const cwd = engineDir();
    const env = {
      ...process.env,
      NO_PROXY: "*",
      no_proxy: "*",
      PYTHONPATH: cwd,
      ETF68_OUT_DIR: outDir(),
      ETF68_REPORTS_DIR: reportsDir(),
    };
    // Point static data via symlink-like path: REPO_ROOT/data/static relative to engine parent
    // Packaged engine's parent is resources; we also set a helper env.
    env.ETF68_STATIC_DIR = staticDir();
    env.ETF68_TTS_CACHE = path.join(outDir(), "tts-cache");
    env.ETF68_FINANCE_DIR = financeDir();
    env.ETF68_ROTATION_DIR = rotationDir();

    delete env.HTTP_PROXY;
    delete env.HTTPS_PROXY;
    delete env.http_proxy;
    delete env.https_proxy;
    delete env.ALL_PROXY;
    delete env.all_proxy;

    const child = spawn(pythonBin(), args, { cwd, env });
    let stdout = "";
    let stderr = "";
    let settled = false;
    let timer = null;
    const finish = (fn, value) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      fn(value);
    };
    if (timeoutMs && timeoutMs > 0) {
      timer = setTimeout(() => {
        try {
          child.kill("SIGTERM");
          setTimeout(() => {
            try {
              if (!child.killed) child.kill("SIGKILL");
            } catch {
              /* ignore */
            }
          }, 1500);
        } catch {
          /* ignore */
        }
        finish(reject, new Error(`python_timeout_${timeoutMs}ms`));
      }, timeoutMs);
    }
    child.stdout.on("data", (buf) => {
      const text = buf.toString();
      stdout += text;
      text.split(/\r?\n/).filter(Boolean).forEach((line) => onLine && onLine(line));
    });
    child.stderr.on("data", (buf) => {
      const text = buf.toString();
      stderr += text;
      text.split(/\r?\n/).filter(Boolean).forEach((line) => onLine && onLine(`[err] ${line}`));
    });
    child.on("error", (err) => finish(reject, err));
    child.on("close", (code) => {
      if (code === 0) finish(resolve, { stdout, stderr, code });
      else finish(reject, new Error(stderr || stdout || `exit_${code}`));
    });
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 700,
    title: "ETF-68",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    win.loadURL(process.env.VITE_DEV_SERVER_URL);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(() => {
  ensureDirs();
  bootstrapPackagedSeeds();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

ipcMain.handle("check-python", async () => {
  try {
    const { stdout } = await runPython(["cli_app.py", "check-python"]);
    const line = stdout.trim().split(/\r?\n/).pop();
    return JSON.parse(line);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("load-latest", async () => {
  const latest = path.join(outDir(), "latest.json");
  if (fs.existsSync(latest)) {
    return { ok: true, bundle: JSON.parse(fs.readFileSync(latest, "utf8")) };
  }
  try {
    const { stdout } = await runPython(["cli_app.py", "load-latest"]);
    const line = stdout.trim().split(/\r?\n/).pop();
    return JSON.parse(line);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("generate-daily", async (event, payload = {}) => {
  const day = payload.date || null;
  const args = ["cli_app.py", "generate", "--workers", String(payload.workers || 6)];
  if (day) args.push("--date", day);
  const logs = [];
  try {
    await runPython(args, {
      onLine: (line) => {
        logs.push(line);
        event.sender.send("generate-log", line);
      },
    });
    const latest = path.join(outDir(), "latest.json");
    if (!fs.existsSync(latest)) {
      return { ok: false, error: "generate_ok_but_missing_latest", logs };
    }
    return { ok: true, bundle: JSON.parse(fs.readFileSync(latest, "utf8")), logs };
  } catch (err) {
    return { ok: false, error: String(err.message || err), logs };
  }
});

ipcMain.handle("assemble-latest", async (_event, payload = {}) => {
  const args = ["cli_app.py", "assemble"];
  if (payload.date) args.push("--date", payload.date);
  try {
    const { stdout } = await runPython(args);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (!parsed.ok) return parsed;
    const latest = path.join(outDir(), "latest.json");
    return { ok: true, bundle: JSON.parse(fs.readFileSync(latest, "utf8")) };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("load-funds-top30", async () => {
  const file = path.join(outDir(), "funds-top30.json");
  if (!fs.existsSync(file)) {
    return { ok: false, error: "no_funds_top30" };
  }
  try {
    return { ok: true, bundle: JSON.parse(fs.readFileSync(file, "utf8")) };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("refresh-funds-top30", async (_event, payload = {}) => {
  const args = ["cli_app.py", "funds-top30"];
  if (payload.rebuild) args.push("--rebuild");
  try {
    const { stdout } = await runPython(args);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (!parsed.ok) return parsed;
    const file = path.join(outDir(), "funds-top30.json");
    if (!fs.existsSync(file)) {
      return { ok: false, error: "funds_top30_missing_after_refresh" };
    }
    return {
      ok: true,
      bundle: JSON.parse(fs.readFileSync(file, "utf8")),
      rebuilt: Boolean(parsed.rebuilt),
    };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("load-my-holdings", async () => {
  const file = path.join(outDir(), "my-holdings.json");
  if (!fs.existsSync(file)) {
    return { ok: false, error: "no_my_holdings" };
  }
  try {
    return { ok: true, bundle: JSON.parse(fs.readFileSync(file, "utf8")) };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("refresh-my-holdings", async () => {
  try {
    const { stdout } = await runPython(["cli_app.py", "my-holdings"]);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (!parsed.ok) return parsed;
    const file = path.join(outDir(), "my-holdings.json");
    if (!fs.existsSync(file)) {
      return { ok: false, error: "my_holdings_missing_after_refresh" };
    }
    return { ok: true, bundle: JSON.parse(fs.readFileSync(file, "utf8")) };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("refresh-board", async (_event, payload = {}) => {
  const args = ["cli_app.py", "refresh-board"];
  if (payload.historical) args.push("--historical");
  if (payload.withNews) args.push("--with-news");
  try {
    const { stdout } = await runPython(args);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (!parsed.ok) return parsed;
    const latest = path.join(outDir(), "latest.json");
    if (!fs.existsSync(latest)) {
      return { ok: false, error: "latest_missing_after_refresh_board" };
    }
    return {
      ok: true,
      bundle: JSON.parse(fs.readFileSync(latest, "utf8")),
      marketBoard: parsed.marketBoard || null,
      fetchedAt: parsed.marketBoard?.fetchedAt || null,
    };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("load-finance-user-data", async () => {
  try {
    ensureFinanceFiles();
    const file = path.join(financeDir(), "userData.json");
    return { ok: true, data: readJsonFile(file, { assetList: [], rebalanceList: [] }) };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("save-finance-user-data", async (_event, payload = {}) => {
  try {
    ensureFinanceFiles();
    const file = path.join(financeDir(), "userData.json");
    const prev = readJsonFile(file, { assetList: [], rebalanceList: [] });
    const next = {
      ...prev,
      assetList: payload.assetList ?? prev.assetList ?? [],
      rebalanceList: payload.rebalanceList ?? prev.rebalanceList ?? [],
      updatedAt: new Date().toISOString(),
    };
    writeJsonFile(file, next);
    scheduleFinanceCloudPush("userData");
    return { ok: true, data: next };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("load-finance-data", async () => {
  try {
    ensureFinanceFiles();
    const file = path.join(financeDir(), "data.json");
    return {
      ok: true,
      data: readJsonFile(file, { financeNews: [], indexTrack: [], fundQuotes: {} }),
    };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("refresh-finance-news", async () => {
  try {
    const { stdout } = await runPython(["cli_app.py", "finance-news"]);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (parsed.ok) scheduleFinanceCloudPush("data");
    const file = path.join(financeDir(), "data.json");
    return { ...parsed, data: readJsonFile(file, {}) };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("refresh-index-track", async () => {
  try {
    const { stdout } = await runPython(["cli_app.py", "index-track"]);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (parsed.ok) scheduleFinanceCloudPush("data");
    const file = path.join(financeDir(), "data.json");
    return { ...parsed, data: readJsonFile(file, {}) };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("refresh-finance-quotes", async () => {
  try {
    await runPython(["cli_app.py", "finance-dca"]).catch(() => null);
    const { stdout } = await runPython(["cli_app.py", "finance-quotes"]);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (parsed.ok) scheduleFinanceCloudPush("data");
    // Also refresh my-holdings advice layer when possible
    let holdings = null;
    try {
      const h = await runPython(["cli_app.py", "my-holdings"]);
      const hl = h.stdout.trim().split(/\r?\n/).pop();
      const hp = JSON.parse(hl);
      if (hp.ok) {
        const hf = path.join(outDir(), "my-holdings.json");
        if (fs.existsSync(hf)) holdings = JSON.parse(fs.readFileSync(hf, "utf8"));
      }
    } catch {
      /* optional */
    }
    return {
      ...parsed,
      data: readJsonFile(path.join(financeDir(), "data.json"), {}),
      userData: readJsonFile(path.join(financeDir(), "userData.json"), {}),
      holdings,
    };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("finance-ocr", async (_event, payload = {}) => {
  try {
    const imagePath = String(payload.imagePath || "").trim();
    if (!imagePath || !fs.existsSync(imagePath)) {
      return { ok: false, error: "image_missing" };
    }
    const { stdout } = await runPython(["cli_app.py", "finance-ocr", "--image", imagePath]);
    const line = stdout.trim().split(/\r?\n/).pop();
    return JSON.parse(line);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("finance-pick-image", async () => {
  try {
    const { dialog } = require("electron");
    const res = await dialog.showOpenDialog({
      title: "选择基金 App 持仓截图",
      properties: ["openFile"],
      filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "webp", "bmp"] }],
    });
    if (res.canceled || !res.filePaths?.[0]) return { ok: false, cancelled: true };
    return { ok: true, imagePath: res.filePaths[0] };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("get-finance-sync-config", async () => {
  const cfg = readFinanceSyncConfig();
  return {
    ok: true,
    hasToken: Boolean(cfg.token),
    proxy: cfg.proxy,
    target: {
      owner: FINANCE_GH.owner,
      repo: FINANCE_GH.repo,
      branch: FINANCE_GH.branch,
      userDataPath: FINANCE_GH.userDataPath,
      dataPath: FINANCE_GH.dataPath,
    },
  };
});

ipcMain.handle("save-finance-sync-config", async (_event, payload = {}) => {
  try {
    const prev = readFinanceSyncConfig();
    const next = {
      token: payload.token != null ? String(payload.token) : prev.token,
      proxy: payload.proxy != null ? String(payload.proxy) : prev.proxy,
    };
    writeFinanceSyncConfig(next);
    return { ok: true, hasToken: Boolean(next.token), proxy: next.proxy };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("finance-cloud-pull", async () => {
  try {
    return await financeCloudPull();
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("finance-cloud-push", async (_event, payload = {}) => {
  try {
    return await financeCloudPush({ which: payload.which || "both", silent: false });
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

function parsePythonJson(stdout) {
  const line = String(stdout || "")
    .trim()
    .split(/\r?\n/)
    .filter(Boolean)
    .pop();
  if (!line) throw new Error("empty_python_stdout");
  return JSON.parse(line);
}

ipcMain.handle("load-rotation-strategies", async () => {
  try {
    const { stdout } = await runPython(["cli_app.py", "rotation-strategies", "list"]);
    return parsePythonJson(stdout);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("save-rotation-strategy", async (_event, payload = {}) => {
  try {
    const body = {
      id: payload.id || null,
      name: payload.name || "未命名策略",
      config: payload.config || {},
    };
    const args = [
      "cli_app.py",
      "rotation-strategies",
      "save",
      "--config-json",
      JSON.stringify(body),
    ];
    if (payload.noActivate) args.push("--no-activate");
    const { stdout } = await runPython(args);
    return parsePythonJson(stdout);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("delete-rotation-strategy", async (_event, payload = {}) => {
  try {
    const id = String(payload.id || "");
    if (!id) return { ok: false, error: "missing_id" };
    const { stdout } = await runPython(["cli_app.py", "rotation-strategies", "delete", "--id", id]);
    return parsePythonJson(stdout);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("duplicate-rotation-strategy", async (_event, payload = {}) => {
  try {
    const id = String(payload.id || "");
    if (!id) return { ok: false, error: "missing_id" };
    const args = ["cli_app.py", "rotation-strategies", "duplicate", "--id", id];
    if (payload.name) args.push("--name", String(payload.name));
    const { stdout } = await runPython(args);
    return parsePythonJson(stdout);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("activate-rotation-strategy", async (_event, payload = {}) => {
  try {
    const id = String(payload.id || "");
    if (!id) return { ok: false, error: "missing_id" };
    const { stdout } = await runPython([
      "cli_app.py",
      "rotation-strategies",
      "activate",
      "--id",
      id,
    ]);
    return parsePythonJson(stdout);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("run-rotation-backtest", async (_event, payload = {}) => {
  let tmpConfig = null;
  try {
    const args = ["cli_app.py", "rotation-run", "--workers", String(payload.workers || 4)];
    if (payload.strategyId) args.push("--strategy-id", String(payload.strategyId));
    if (payload.config) {
      // Avoid huge/fragile CLI argv; engine reads --config-file.
      tmpConfig = path.join(outDir(), `rotation-config-${Date.now()}-${process.pid}.json`);
      fs.writeFileSync(tmpConfig, JSON.stringify(payload.config), "utf8");
      args.push("--config-file", tmpConfig);
    }
    if (payload.noPublic) args.push("--no-public");
    const { stdout } = await runPython(args, { timeoutMs: 90000 });
    return parsePythonJson(stdout);
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  } finally {
    if (tmpConfig) {
      try {
        fs.unlinkSync(tmpConfig);
      } catch {
        /* ignore */
      }
    }
  }
});

ipcMain.handle("fetch-xiaoxin-public", async () => {
  try {
    const { stdout } = await runPython(["cli_app.py", "rotation-public"], { timeoutMs: 30000 });
    return parsePythonJson(stdout);
  } catch (err) {
    // Prefer cached snapshot if live fetch hangs/fails.
    try {
      const file = path.join(outDir(), "xiaoxin-public.json");
      if (fs.existsSync(file)) {
        const cached = JSON.parse(fs.readFileSync(file, "utf8"));
        return { ...cached, ok: true, cache: true, fetch_error: String(err.message || err) };
      }
    } catch {
      /* ignore */
    }
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("load-rotation-last", async () => {
  try {
    const file = path.join(outDir(), "rotation-last.json");
    if (!fs.existsSync(file)) return { ok: false, error: "rotation_last_missing" };
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});

ipcMain.handle("load-rotation-account-ref", async () => {
  try {
    const file = path.join(rotationDir(), "zhibei-reference.json");
    if (!fs.existsSync(file)) {
      return {
        ok: false,
        mode: "account",
        label: "账号策略对照",
        error: "account_reference_missing",
        rankings: [],
        equity: { dates: [], nav: [] },
        note: "缺少账号策略对照快照 data/rotation/zhibei-reference.json",
      };
    }
    const data = JSON.parse(fs.readFileSync(file, "utf8"));
    return {
      ok: true,
      mode: "account",
      label: "账号策略对照",
      ...data,
    };
  } catch (err) {
    return { ok: false, error: String(err.message || err), rankings: [], equity: { dates: [], nav: [] } };
  }
});

ipcMain.handle("speak-text", async (_event, payload = {}) => {
  const text = String(payload.text || "").trim();
  if (!text) return { ok: false, error: "empty_text" };

  const args = ["cli_app.py", "tts", "--text", text];
  if (payload.voice) args.push("--voice", String(payload.voice));
  if (payload.rate) args.push("--rate", String(payload.rate));
  if (payload.pitch) args.push("--pitch", String(payload.pitch));
  if (payload.force) args.push("--force");

  try {
    const { stdout } = await runPython(args);
    const line = stdout.trim().split(/\r?\n/).pop();
    const parsed = JSON.parse(line);
    if (!parsed.ok || !parsed.path) return parsed;
    if (!fs.existsSync(parsed.path)) {
      return { ok: false, error: "tts_file_missing" };
    }
    const audioBase64 = fs.readFileSync(parsed.path).toString("base64");
    return {
      ok: true,
      audioBase64,
      mime: "audio/mpeg",
      voice: parsed.voice,
      cached: Boolean(parsed.cached),
      bytes: parsed.bytes,
    };
  } catch (err) {
    return { ok: false, error: String(err.message || err) };
  }
});
