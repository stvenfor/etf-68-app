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

function runPython(args, { onLine } = {}) {
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

    delete env.HTTP_PROXY;
    delete env.HTTPS_PROXY;
    delete env.http_proxy;
    delete env.https_proxy;
    delete env.ALL_PROXY;
    delete env.all_proxy;

    const child = spawn(pythonBin(), args, { cwd, env });
    let stdout = "";
    let stderr = "";
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
    child.on("error", (err) => reject(err));
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr, code });
      else reject(new Error(stderr || stdout || `exit_${code}`));
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
