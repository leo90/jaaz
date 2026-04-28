interface ElectronAPI {
  publishPost: (data: {
    channel: string
    title: string
    content: string
    images: string[]
    video: string
  }) => Promise<{ success?: boolean; error?: string }>
  pickImage: () => Promise<string[] | null>
  pickVideo: () => Promise<string | null>
  installComfyUI: () => Promise<{ success: boolean; error?: string }>
  uninstallComfyUI: () => Promise<{ success: boolean; error?: string }>
  cancelComfyUIInstall: () => Promise<{
    success?: boolean
    error?: string
    message?: string
  }>
  checkComfyUIInstalled: () => Promise<boolean>
  // ComfyUI process management methods
  startComfyUIProcess: () => Promise<{ success: boolean; message?: string }>
  stopComfyUIProcess: () => Promise<{ success: boolean; message?: string }>
  getComfyUIProcessStatus: () => Promise<{ running: boolean; pid?: number }>
  // Auto-updater methods
  checkForUpdates: () => Promise<{ message: string }>
  restartAndInstall: () => Promise<void>
  onUpdateDownloaded: (callback: (info: UpdateInfo) => void) => void
  removeUpdateDownloadedListener: () => void
  // Auth methods
  openBrowserUrl: (url: string) => Promise<{ success: boolean; error?: string }>
  // ComfyUI install event listeners (via IPC, replaces unsafe CustomEvent dispatch)
  onComfyuiInstallProgress: (callback: (data: { percent: number; status: string }) => void) => void
  onComfyuiInstallLog: (callback: (data: { message: string }) => void) => void
  onComfyuiInstallError: (callback: (data: { error: string }) => void) => void
  onComfyuiInstallCancelled: (callback: (data: { message: string }) => void) => void
  onComfyuiUninstallProgress: (callback: (data: { percent: number; status: string }) => void) => void
  onComfyuiUninstallLog: (callback: (data: { message: string }) => void) => void
  onComfyuiUninstallError: (callback: (data: { error: string }) => void) => void
  removeComfyuiInstallListeners: () => void
  removeComfyuiUninstallListeners: () => void
}

interface UpdateInfo {
  version: string
  files: unknown[]
  path: string
  sha512: string
  releaseDate: string
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

export {}
