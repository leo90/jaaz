// electron/main.js
// npx electron electron/main.js

const fs = require('fs')
const path = require('path')
const os = require('os')
// to import a ts module, we need to import like below
// const gemini = require('./dist/gemin_service')
const logPath = path.join(os.homedir(), 'jaaz-log.txt')
// Check if the log file exists and delete it
if (fs.existsSync(logPath)) {
  fs.unlinkSync(logPath)
}

const logStream = fs.createWriteStream(logPath, { flags: 'a' })

// Redirect all stdout and stderr to the log file
process.stdout.write = process.stderr.write = logStream.write.bind(logStream)

// Optional: Add timestamps to log output
const origLog = console.log
console.log = (...args) => {
  const time = new Date().toISOString()
  origLog(`[${time}]`, ...args)
}

console.error = (...args) => {
  const time = new Date().toISOString()
  origLog(`[${time}][ERROR]`, ...args)
}

// Initial log entry
console.log('🟢 Jaaz Electron app starting...')

const { app, BrowserWindow, ipcMain, dialog, session, protocol } = require('electron')
const { spawn } = require('child_process')

const { autoUpdater } = require('electron-updater')

const net = require('net')

// Initialize settings service
const settingsService = require('./settingsService')

function findAvailablePort(startPort, maxAttempts = 100) {
  return new Promise((resolve, reject) => {
    let attempts = 0

    const tryPort = (port) => {
      attempts++
      if (attempts > maxAttempts) {
        reject(new Error(`Could not find available port after ${maxAttempts} attempts`))
        return
      }

      const server = net.createServer()

      server.on('error', (err) => {
        if (err.code === 'EADDRINUSE') {
          console.log(`Port ${port} is in use, trying next port...`)
          server.close()
          tryPort(port + 1)
        } else {
          reject(err)
        }
      })

      // 明确指定 host 为 127.0.0.1，确保检测到端口占用
      server.listen(port, '127.0.0.1', () => {
        server.close(() => {
          console.log(`Found available port: ${port}`)
          resolve(port)
        })
      })
    }

    tryPort(startPort)
  })
}

let mainWindow
let pyProc = null
let pyPort = null
let childWindows = [] // Track all child windows

// check for updates after the app is ready
// Auto-updater event handlers
autoUpdater.on('checking-for-update', () => {
  console.log('Checking for update...')
})

autoUpdater.on('update-available', (info) => {
  console.log('Update available.')
  console.log('Version:', info.version)
  console.log('Release date:', info.releaseDate)
  // Automatically download the update when available
  autoUpdater.downloadUpdate()
})

autoUpdater.on('update-not-available', (info) => {
  console.log('Update not available:', info)
})

autoUpdater.on('error', (err) => {
  console.log('Error in auto-updater. ' + err)
})

autoUpdater.on('download-progress', (progressObj) => {
  let log_message = 'Download speed: ' + progressObj.bytesPerSecond
  log_message = log_message + ' - Downloaded ' + progressObj.percent + '%'
  log_message = log_message + ' (' + progressObj.transferred + '/' + progressObj.total + ')'
  console.log(log_message)
})

autoUpdater.on('update-downloaded', (info) => {
  console.log('new Jaaz version downloaded:', info.version)

  // send message to renderer process
  if (mainWindow) {
    mainWindow.webContents.send('update-downloaded', info)
  }
})

const createWindow = (pyPort) => {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    icon: path.join(__dirname, '../assets/icons/jaaz.png'), // ✅ Use .png for dev
    autoHideMenuBar: true, // Hide menu bar (can be toggled with Alt key)
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  // Handle window closed event
  mainWindow.on('closed', () => {
    // Close all child windows
    childWindows.forEach((window) => {
      if (!window.isDestroyed()) {
        window.close()
      }
    })
    childWindows = []
    mainWindow = null
  })

  // Handle all navigation requests (intercept all link clicks)
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    console.log('Navigation requested:', navigationUrl)
    event.preventDefault()

    // Only allow http/https URLs in child windows
    try {
      const parsed = new URL(navigationUrl)
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        console.error('Blocked navigation to non-http(s) URL:', navigationUrl)
        return
      }
    } catch {
      console.error('Invalid URL in navigation request:', navigationUrl)
      return
    }

    // Create new window for external links with sandbox for isolation
    const newWindow = new BrowserWindow({
      width: 800,
      height: 600,
      title: 'Jaaz Preview',
      icon: path.join(__dirname, '../assets/icons/jaaz.png'),
      autoHideMenuBar: true,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
      },
    })
    newWindow.loadURL(navigationUrl)

    // Add to child windows array
    childWindows.push(newWindow)

    // Handle new window closed event
    newWindow.on('closed', () => {
      // Remove from child windows array
      const index = childWindows.indexOf(newWindow)
      if (index > -1) {
        childWindows.splice(index, 1)
      }
    })
  })

  // In development, use Vite dev server
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5174', {
      extraHeaders: 'pragma: no-cache\n',
    })
    mainWindow.webContents.openDevTools()
  } else {
    // In production, load built files
    mainWindow.loadURL(`http://127.0.0.1:${pyPort}`, {
      extraHeaders: 'pragma: no-cache\n',
    })
  }
}

// 获取 app.asar 内部的根路径
const appRoot = app.getAppPath()

const startPythonApi = async () => {
  // Find an available port
  pyPort = await findAvailablePort(57988)
  console.log('available pyPort:', pyPort)

  // 在某些开发情况，我们希望 python server 独立运行，那么就不通过 electron 启动
  if (process.env.NODE_ENV === 'development') {
    try {
      const response = await fetch(`http://127.0.0.1:${pyPort}`)
      if (response.ok) {
        console.log('Python service already running on port:', pyPort)
        return pyPort
      }
    } catch (error) {
      console.log('Starting Python service on port:', pyPort)
    }
  } else {
    console.log('Starting Python service on port:', pyPort)
  }

  // 确定UI dist目录
  const env = {
    ...process.env,
  }
  env.PYTHONIOENCODING = 'utf-8'
  env.DEFAULT_PORT = pyPort // 添加端口到环境变量
  if (app.isPackaged) {
    env.UI_DIST_DIR = path.join(process.resourcesPath, 'react', 'dist')
    env.USER_DATA_DIR = app.getPath('userData')
    env.IS_PACKAGED = '1'
  }

  // Set BASE_API_URL based on environment
  env.BASE_API_URL =
    process.env.NODE_ENV === 'development' ? 'http://localhost:3000' : 'https://jaaz.app'
  console.log('BASE_API_URL:', env.BASE_API_URL)

  // Apply proxy settings and get environment variables
  try {
    const proxyEnvVars = await settingsService.getProxyEnvironmentVariables()

    // Merge proxy environment variables into env
    Object.assign(env, proxyEnvVars)
  } catch (error) {
    console.error('Failed to get proxy environment variables:', error)
  }

  // Determine the Python executable path (considering packaged app)
  const isWindows = process.platform === 'win32'
  const pythonExecutable = app.isPackaged
    ? path.join(process.resourcesPath, 'server', 'dist', 'main', isWindows ? 'main.exe' : 'main')
    : 'python'
  console.log('Resolved Python executable:', pythonExecutable)

  const fs = require('fs')

  console.log('Exists?', fs.existsSync(pythonExecutable))

  // fs.chmodSync(pythonExecutable, "755");

  console.log('Python executable path:', pythonExecutable)
  console.log('Python executable exists?', fs.existsSync(pythonExecutable))
  console.log('env:', env)
  const scriptPath = path.join(__dirname, '../server/main.py')

  // Start the FastAPI process
  pyProc = spawn(
    pythonExecutable,
    app.isPackaged ? [`--port`, pyPort] : [scriptPath, `--port`, pyPort],
    { env: env }
  )

  // Log output to logStream (shared with console.log)
  pyProc.stdout.on('data', (data) => {
    const log = `[${new Date().toISOString()}][PYTHON stdout] ${data}`
    logStream.write(log)
    process.stdout.write(log) // optional: echo to terminal if running from CLI
  })

  pyProc.stderr.on('data', (data) => {
    const log = `[${new Date().toISOString()}][PYTHON stderr] ${data}`
    logStream.write(log)
    process.stderr.write(log) // optional: echo to terminal if running from CLI
  })

  // Optional: log if spawn fails
  pyProc.on('error', (err) => {
    const log = `[${new Date().toISOString()}][PYTHON spawn error] ${err.toString()}\n`
    logStream.write(log)
    process.stderr.write(log)
  })

  // Optional: log process exit
  pyProc.on('exit', (code, signal) => {
    const log = `[${new Date().toISOString()}][PYTHON exited] code=${code}, signal=${signal}\n`
    logStream.write(log)
  })

  return pyPort
}

// Validate IPC origin helper — SECURITY CRITICAL
function validateIpcOrigin(event) {
  const origin = event.senderFrame.origin
  const isAllowed = Array.from(ALLOWED_IPC_ORIGINS).some(allowed => {
    // Exact match first
    if (origin === allowed) return true
    // Prefix match with trailing slash protection — prevents localhost.attacker.com bypass
    if (origin.startsWith(allowed + '/')) return true
    // Handle file:// protocol specially — must be exactly 'file://'
    if (allowed === 'file://' && origin === 'file://') return true
    return false
  })
  if (!isAllowed) {
    console.error(`IPC call from unauthorized origin: ${origin}`)
    throw new Error(`IPC call from unauthorized origin: ${origin}`)
  }
}

// Add these handlers before app.whenReady()
ipcMain.handle('pick-image', async (event) => {
  validateIpcOrigin(event)
  const result = await dialog.showOpenDialog({
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'gif', 'webp'] }],
  })

  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths
  }
  return null
})

ipcMain.handle('pick-video', async (event) => {
  validateIpcOrigin(event)
  const result = await dialog.showOpenDialog({
    properties: ['openFile'],
    filters: [{ name: 'Videos', extensions: ['mp4', 'webm', 'mov', 'avi'] }],
  })

  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0]
  }
  return null
})

// Add IPC handlers for manual update check
ipcMain.handle('check-for-updates', (event) => {
  validateIpcOrigin(event)
  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify()
    return { message: 'Checking for updates...' }
  } else {
    return { message: 'Auto-updater is disabled in development mode' }
  }
})

// restart and install the new version
ipcMain.handle('restart-and-install', (event) => {
  validateIpcOrigin(event)
  autoUpdater.quitAndInstall()
})

const ipcHandlers = require('./ipcHandlers')

// Allowed origins for IPC calls (prevent malicious child windows from calling handlers)
const ALLOWED_IPC_ORIGINS = new Set([
  'http://localhost:5174',    // Vite dev server
  'http://127.0.0.1',        // Production Python server
  'file://',                  // Local file protocol
])

for (const [channel, handler] of Object.entries(ipcHandlers)) {
  ipcMain.handle(channel, (event, ...args) => {
    // Validate IPC origin — reject calls from unauthorized frames
    validateIpcOrigin(event)
    return handler(event, ...args)
  })
}

// Make this app a single instance app
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  // Another instance is already running, quit this one
  app.quit()
} else {
  // This is the first instance, set up second-instance handler
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    // Someone tried to run a second instance, focus our window instead
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })

  app.whenReady().then(async () => {
    // Register custom protocol for local file access (replaces webSecurity:false)
    protocol.handle('local-file', (request) => {
      const { net: electronNet } = require('electron')
      try {
        // SECURITY: Remove protocol and normalize path to prevent traversal attacks
        let filePath = decodeURIComponent(request.url.replace(/^local-file:\/*/, ''))

        // Block Windows UNC paths (\\server\share or //server/share)
        if (filePath.match(/^[\\/]{2}[^\\/]/)) {
          console.error('Blocked UNC path in local-file protocol:', filePath)
          return new Response(null, { status: 403, statusText: 'Forbidden' })
        }

        // SECURITY: Normalize path to resolve '..' and prevent traversal
        filePath = path.normalize(filePath)

        // On Windows, block attempts to access other drives (e.g., D:\)
        // For app files, they should be within the app's own directories
        if (process.platform === 'win32') {
          // Convert to absolute if relative (shouldn't happen but defense in depth)
          if (!path.isAbsolute(filePath)) {
            filePath = path.resolve('/', filePath)
          }
          // Validate it's a local path - no UNC, no drive jumping
          const pathRoot = path.parse(filePath).root
          if (pathRoot.match(/^[\\/]{2}/)) {
            console.error('Blocked UNC path:', filePath)
            return new Response(null, { status: 403, statusText: 'Forbidden' })
          }
        }

        return electronNet.fetch(`file://${filePath}`)
      } catch (error) {
        console.error('Error in local-file protocol:', error)
        return new Response(null, { status: 500, statusText: 'Internal Server Error' })
      }
    })

    // Initialize proxy settings for Electron sessions
    try {
      await settingsService.applyProxySettings()
      console.log('Proxy settings applied for Electron sessions')
    } catch (error) {
      console.error('Failed to apply proxy settings for Electron sessions:', error)
    }

    // Check for updates in production every time app starts
    if (process.env.NODE_ENV !== 'development' && app.isPackaged) {
      // Wait a bit for the app to fully load before checking updates
      setTimeout(() => {
        autoUpdater.checkForUpdatesAndNotify()
      }, 3000)
    }

    // Start Python API in both development and production
    const pyPort = await startPythonApi()

    // Wait for Python server to start, with timeout (max 60 seconds)
    const SERVER_START_TIMEOUT = 60_000
    const POLL_INTERVAL = 1000
    const startTime = Date.now()

    while (true) {
      if (Date.now() - startTime > SERVER_START_TIMEOUT) {
        console.error(`Python server failed to start within ${SERVER_START_TIMEOUT / 1000}s`)
        dialog.showErrorBox(
          'Server Start Failed',
          'The Python server failed to start within the expected time. Please try restarting the application.'
        )
        app.quit()
        return
      }

      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL))
      let status = await fetch(`http://127.0.0.1:${pyPort}`)
        .then((res) => {
          return res.ok
        })
        .catch((err) => {
          console.error(err)
          return false
        })
      if (status) {
        break
      }
    }

    createWindow(pyPort)
  })
}

// Quit the app and clean up the Python process
app.on('will-quit', async (event) => {
  event.preventDefault()

  try {
    // clear cache
    await session.defaultSession.clearCache()
    console.log('Cache cleared on app exit')
  } catch (error) {
    console.error('Failed to clear cache:', error)
  }

  // kill python process
  if (pyProc) {
    pyProc.kill()
    pyProc = null
  }

  app.exit()
})

app.on('window-all-closed', () => {
  app.quit()
})

// ipcMain.handle("reveal-in-explorer", async (event, filePath) => {
//   try {
//     // Convert relative path to absolute path
//     const fullPath = path.join(app.getPath("userData"), "workspace", filePath);

//     // Use shell.openPath which is the recommended way in Electron
//     await shell.showItemInFolder(fullPath);
//     return { success: true };
//   } catch (error) {
//     console.error("Error revealing file:", error);
//     return { error: error.message };
//   }
// });
