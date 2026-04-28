const { contextBridge, ipcRenderer } = require('electron')

// const ipcHandlers = require("./ipcHandlers");

// console.log("Available IPC handlers:", Object.keys(ipcHandlers));

// // Dynamically build API based on handler function names
// const exposedAPI = {};
// for (const name of Object.keys(ipcHandlers)) {
//   exposedAPI[name] = (...args) => {
//     console.log(`Calling IPC handler: ${name} with args:`, args);
//     return ipcRenderer.invoke(name, ...args);
//   };
// }

// console.log("Exposing API with methods:", Object.keys(exposedAPI));

contextBridge.exposeInMainWorld('electronAPI', {
  openBrowserUrl: (url) => ipcRenderer.invoke('open-browser-url', url),

  publishPost: (...args) => {
    return ipcRenderer.invoke('publishPost', ...args)
  },
  // Add new file picker methods
  pickImage: () => ipcRenderer.invoke('pick-image'),
  pickVideo: () => ipcRenderer.invoke('pick-video'),
  // Add ComfyUI installation methods
  installComfyUI: () => ipcRenderer.invoke('install-comfyui'),
  uninstallComfyUI: () => ipcRenderer.invoke('uninstall-comfyui'),
  cancelComfyUIInstall: () => ipcRenderer.invoke('cancel-comfyui-install'),
  checkComfyUIInstalled: () => ipcRenderer.invoke('check-comfyui-installed'),
  // Add ComfyUI process management methods
  startComfyUIProcess: () => ipcRenderer.invoke('start-comfyui-process'),
  stopComfyUIProcess: () => ipcRenderer.invoke('stop-comfyui-process'),
  getComfyUIProcessStatus: () =>
    ipcRenderer.invoke('get-comfyui-process-status'),
  // Add auto-updater methods
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  restartAndInstall: () => ipcRenderer.invoke('restart-and-install'),
  // Listen for update events
  onUpdateDownloaded: (callback) => {
    ipcRenderer.on('update-downloaded', (event, info) => callback(info))
  },
  removeUpdateDownloadedListener: () => {
    ipcRenderer.removeAllListeners('update-downloaded')
  },
  // Listen for ComfyUI install/uninstall events (replaces CustomEvent dispatch)
  onComfyuiInstallProgress: (callback) => {
    ipcRenderer.on('comfyui-install-progress', (event, data) => callback(data))
  },
  onComfyuiInstallLog: (callback) => {
    ipcRenderer.on('comfyui-install-log', (event, data) => callback(data))
  },
  onComfyuiInstallError: (callback) => {
    ipcRenderer.on('comfyui-install-error', (event, data) => callback(data))
  },
  onComfyuiInstallCancelled: (callback) => {
    ipcRenderer.on('comfyui-install-cancelled', (event, data) => callback(data))
  },
  onComfyuiUninstallProgress: (callback) => {
    ipcRenderer.on('comfyui-uninstall-progress', (event, data) => callback(data))
  },
  onComfyuiUninstallLog: (callback) => {
    ipcRenderer.on('comfyui-uninstall-log', (event, data) => callback(data))
  },
  onComfyuiUninstallError: (callback) => {
    ipcRenderer.on('comfyui-uninstall-error', (event, data) => callback(data))
  },
  removeComfyuiInstallListeners: () => {
    ipcRenderer.removeAllListeners('comfyui-install-progress')
    ipcRenderer.removeAllListeners('comfyui-install-log')
    ipcRenderer.removeAllListeners('comfyui-install-error')
    ipcRenderer.removeAllListeners('comfyui-install-cancelled')
  },
  removeComfyuiUninstallListeners: () => {
    ipcRenderer.removeAllListeners('comfyui-uninstall-progress')
    ipcRenderer.removeAllListeners('comfyui-uninstall-log')
    ipcRenderer.removeAllListeners('comfyui-uninstall-error')
  },
})
