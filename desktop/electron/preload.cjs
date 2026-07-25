const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("etf68", {
  checkPython: () => ipcRenderer.invoke("check-python"),
  loadLatest: () => ipcRenderer.invoke("load-latest"),
  generateDaily: (payload) => ipcRenderer.invoke("generate-daily", payload || {}),
  assembleLatest: (payload) => ipcRenderer.invoke("assemble-latest", payload || {}),
  onGenerateLog: (cb) => {
    const handler = (_e, line) => cb(line);
    ipcRenderer.on("generate-log", handler);
    return () => ipcRenderer.removeListener("generate-log", handler);
  },
});
