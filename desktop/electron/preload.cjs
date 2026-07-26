const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("etf68", {
  checkPython: () => ipcRenderer.invoke("check-python"),
  loadLatest: () => ipcRenderer.invoke("load-latest"),
  generateDaily: (payload) => ipcRenderer.invoke("generate-daily", payload || {}),
  assembleLatest: (payload) => ipcRenderer.invoke("assemble-latest", payload || {}),
  speakText: (payload) => ipcRenderer.invoke("speak-text", payload || {}),
  loadFundsTop30: () => ipcRenderer.invoke("load-funds-top30"),
  refreshFundsTop30: (payload) => ipcRenderer.invoke("refresh-funds-top30", payload || {}),
  onGenerateLog: (cb) => {
    const handler = (_e, line) => cb(line);
    ipcRenderer.on("generate-log", handler);
    return () => ipcRenderer.removeListener("generate-log", handler);
  },
});
