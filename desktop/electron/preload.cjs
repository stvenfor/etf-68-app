const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("etf68", {
  checkPython: () => ipcRenderer.invoke("check-python"),
  loadLatest: () => ipcRenderer.invoke("load-latest"),
  generateDaily: (payload) => ipcRenderer.invoke("generate-daily", payload || {}),
  assembleLatest: (payload) => ipcRenderer.invoke("assemble-latest", payload || {}),
  speakText: (payload) => ipcRenderer.invoke("speak-text", payload || {}),
  loadFundsTop30: () => ipcRenderer.invoke("load-funds-top30"),
  refreshFundsTop30: (payload) => ipcRenderer.invoke("refresh-funds-top30", payload || {}),
  loadMyHoldings: () => ipcRenderer.invoke("load-my-holdings"),
  refreshMyHoldings: () => ipcRenderer.invoke("refresh-my-holdings"),
  refreshBoard: (payload) => ipcRenderer.invoke("refresh-board", payload || {}),
  loadFinanceUserData: () => ipcRenderer.invoke("load-finance-user-data"),
  saveFinanceUserData: (payload) => ipcRenderer.invoke("save-finance-user-data", payload || {}),
  loadFinanceData: () => ipcRenderer.invoke("load-finance-data"),
  refreshFinanceNews: () => ipcRenderer.invoke("refresh-finance-news"),
  refreshIndexTrack: () => ipcRenderer.invoke("refresh-index-track"),
  refreshFinanceQuotes: () => ipcRenderer.invoke("refresh-finance-quotes"),
  financeOcr: (payload) => ipcRenderer.invoke("finance-ocr", payload || {}),
  financePickImage: () => ipcRenderer.invoke("finance-pick-image"),
  getFinanceSyncConfig: () => ipcRenderer.invoke("get-finance-sync-config"),
  saveFinanceSyncConfig: (payload) => ipcRenderer.invoke("save-finance-sync-config", payload || {}),
  financeCloudPull: () => ipcRenderer.invoke("finance-cloud-pull"),
  financeCloudPush: (payload) => ipcRenderer.invoke("finance-cloud-push", payload || {}),
  loadRotationStrategies: () => ipcRenderer.invoke("load-rotation-strategies"),
  saveRotationStrategy: (payload) => ipcRenderer.invoke("save-rotation-strategy", payload || {}),
  deleteRotationStrategy: (payload) => ipcRenderer.invoke("delete-rotation-strategy", payload || {}),
  duplicateRotationStrategy: (payload) =>
    ipcRenderer.invoke("duplicate-rotation-strategy", payload || {}),
  activateRotationStrategy: (payload) =>
    ipcRenderer.invoke("activate-rotation-strategy", payload || {}),
  fetchXiaoxinPublic: () => ipcRenderer.invoke("fetch-xiaoxin-public"),
  runRotationBacktest: (payload) => ipcRenderer.invoke("run-rotation-backtest", payload || {}),
  loadRotationLast: () => ipcRenderer.invoke("load-rotation-last"),
  loadRotationAccountRef: () => ipcRenderer.invoke("load-rotation-account-ref"),
  onGenerateLog: (cb) => {
    const handler = (_e, line) => cb(line);
    ipcRenderer.on("generate-log", handler);
    return () => ipcRenderer.removeListener("generate-log", handler);
  },
});
