# Jaaz 项目代码审查报告

**日期**: 2026-04-27
**版本**: v1.0.30
**审查范围**: Electron 主进程 / Python Server / React 前端 / 构建 & 配置

---

## 概要统计

| 严重级别 | 数量 |
|----------|------|
| CRITICAL | 9    |
| HIGH     | 16   |
| MEDIUM   | 26   |
| LOW      | 20   |

---

## CRITICAL 级别问题

### C-1. JavaScript 注入 — `executeJavaScript` 字符串拼接

**位置**: `electron/comfyUIInstaller.js` (L202-294), `electron/ipcHandlers.js` (L75-106, L277-300)

多处使用模板字符串拼接未信任数据注入到 `executeJavaScript` 中：

```javascript
mainWindow.webContents.executeJavaScript(`
  window.dispatchEvent(new CustomEvent('comfyui-install-progress', {
    detail: { percent: ${percent}, status: "${status.replace(/"/g, '\\"')}" }
  }));
`)
```

`.replace(/"/g, '\\"')` 仅处理了双引号，无法防止反引号注入、`${...}` 模板注入、Unicode 转义等攻击。攻击者可控制 worker 输出或 GitHub API 数据即可在渲染进程执行任意 JS。

**建议**: 使用 `mainWindow.webContents.send()` + `ipcRenderer.on()` 替代字符串拼接。

---

### C-2. `webSecurity: false` 在所有窗口启用

**位置**: `electron/main.js` (L135-136, L168-169)

主窗口和子窗口均禁用了同源策略：

```javascript
webSecurity: false,
allowRunningInsecureContent: true,
```

**影响**: 任何加载到这些窗口的 web 内容都可以绕过 CORS、访问本地服务、读取 `file://` 协议文件。子窗口甚至加载外部 URL（L172），外部网页以无同源策略状态运行。

**建议**: 使用自定义协议（`protocol.registerFileProtocol`）或 `webUtils.getPathForFile` 精确控制本地资源访问。

---

### C-3. 路径遍历 — workspace 文件操作

**位置**: `server/routers/workspace.py` (L21, L33, L63, L80)

所有 workspace 端点直接拼接用户提供的路径：

```python
full_path = os.path.join(WORKSPACE_ROOT, path)
```

`path` 值为 `../../etc/passwd` 即可逃逸 workspace 目录。

**更严重**: `delete_file`（L54）直接使用 `os.remove(path)`，**未拼接 WORKSPACE_ROOT**，允许删除系统任意文件。

**建议**: 添加 `os.path.realpath()` 检查确保结果路径在 WORKSPACE_ROOT 内。

---

### C-4. SSRF — ComfyUI 代理端点

**位置**: `server/routers/settings.py` (L276-298)

`comfyui_proxy` 端点接受任意 `url` 和 `path`，拼接后发起服务端请求，无任何 URL 校验或白名单：

```python
full_url = f"{url}{path}"
async with httpx.AsyncClient() as client:
    response = await client.get(full_url)
```

**建议**: 添加 URL 白名单（仅允许 ComfyUI 相关地址），或限制目标为 `localhost`/`127.0.0.1`。

---

### C-5. 任意文件系统访问

**位置**: `server/routers/workspace.py` (L161-242, L291-316, L355-391)

- `browse_filesystem`: 接受任意路径，返回目录列表
- `serve_file`: 接受任意路径，返回文件内容
- `get_file_thumbnail`: 接受任意 `file_path` 查询参数

这些端点无路径限制，允许枚举和读取主机上任何可访问的文件。

---

### C-6. Auth Token 存储在 localStorage

**位置**: `react/src/api/auth.ts` (L94-95, L109, L189-190)

JWT access token 和用户信息存储在 `localStorage`，任何页面 JS（包括 XSS 攻击载荷）均可读取。

**建议**: 使用 httpOnly cookie 存储令牌，或至少使用 `sessionStorage` 降低持久暴露风险。

---

### C-7. Excalidraw 允许嵌入任意 URL

**位置**: `react/src/components/canvas/CanvasExcali.tsx` (L422-426)

```typescript
validateEmbeddable={(url: string) => {
  return true
}}
```

允许在画布中嵌入任意 iframe，可被用于钓鱼/点击劫持攻击。

**建议**: 实现 URL 白名单校验。

---

### C-8. 无 URL 校验的 `open-browser-url`

**位置**: `electron/ipcHandlers.js` (L14)

```javascript
'open-browser-url': async (event, url) => {
    await shell.openExternal(url)
```

渲染进程可传入 `file:///`、自定义协议或内网地址。攻击者可利用此打开 `file:///etc/passwd` 或触发任意协议处理器。

---

### C-9. CI 工作流已从工作树删除

**位置**: `.github/workflows/build.yml` (git status: deleted)

CI/CD 流水线已被删除，推送到远程仓库将导致 CI 完全失效。

---

## HIGH 级别问题

### H-1. 无 IPC 来源校验

**位置**: `electron/main.js` (L306-349), `electron/ipcHandlers.js`

所有 IPC 处理器未校验 `event.senderFrame.origin`。由于子窗口加载外部 URL，恶意网页可调用所有 IPC 处理器。

### H-2. 子窗口加载任意 URL 且无安全隔离

**位置**: `electron/main.js` (L154-184)

`will-navigate` 为每个导航请求创建新 BrowserWindow 并直接加载 URL，同时设置 `webSecurity: false`。

### H-3. API Key 未鉴权暴露

**位置**: `server/routers/config_router.py` (L16)

`GET /api/config` 返回完整配置对象，包含所有 provider 的 `api_key` 字段，无身份认证。

### H-4. 所有 API 端点无身份认证

**位置**: `server/` 所有 routers

虽然绑定 `127.0.0.1` 提供一定保护，但任何本地进程/网页均可调用。

### H-5. API 调用未检查 `response.ok`

**位置**: `react/src/api/canvas.ts`, `api/chat.ts`, `api/config.ts`, `api/upload.ts`

所有 API 函数直接调用 `response.json()`，4xx/5xx 响应被静默当作有效数据返回。

### H-6. `listModels` 错误时返回空数组 — 类型不匹配

**位置**: `react/src/api/model.ts` (L20-28)

函数声明返回 `{ llm: ModelInfo[]; tools: ToolInfo[] }`，但 `.catch()` 返回 `[]`，形状完全不同。

### H-7. 错误边界暴露堆栈信息

**位置**: `react/src/components/common/ErrorBoundary.tsx` (L18-19)

```tsx
<pre className="text-sm">{error?.stack}</pre>
```

生产环境应隐藏堆栈信息。

### H-8. `window.location.pathname` 绕过路由

**位置**: `react/src/components/TopMenu.tsx` (L39, L45, L50)

直接使用 `window.location.pathname` 而非 TanStack Router 的 `useLocation()`，路由变化时不会重新渲染。

### H-9. `window.history.pushState` 绕过路由

**位置**: `react/src/components/chat/Chat.tsx` (L536-540, L573-577)

绕过 TanStack Router 状态管理，可导致路由/状态不同步。

### H-10. 服务器启动轮询无超时

**位置**: `electron/main.js` (L387-401)

`while(true)` 轮询 Python 服务器启动状态，无超时、无最大重试次数。若服务器未启动，应用永远挂起。

### H-11. `uncaughtException` 处理器未退出进程

**位置**: `electron/comfyUIInstaller.js` (L933-946)

违反 Node.js 文档警告 — 未捕获异常后进程处于不一致状态，应退出。

### H-12. Playwright 作为生产依赖

**位置**: `package.json` (L100-102)

`playwright`、`playwright-extra`、`playwright-extra-plugin-stealth` 被列为 `dependencies` 而非 `devDependencies`，显著膨胀生产构建。

### H-13. `start:frontend` 脚本指向不存在的目录

**位置**: `package.json` (L12)

```
"start:frontend": "cd frontend && npm run dev"
```

项目无 `frontend/` 目录，应为 `react/`。

### H-14. 缺少根级 lock 文件

根目录无 `package-lock.json`，`npm install` 不可复现。

### H-15. 测试文件未使用 vitest API

**位置**: `electron/test/comfyuiInstaller/*.test.js`

测试使用 `console.log` 断言和手动模块替换，无法在 CI 中生成通过/失败结果。

### H-16. CI 触发分支与实际分支不匹配

CI 配置触发 `branches: [main]`，但当前分支为 `master`，流水线永远不会触发。

---

## MEDIUM 级别问题

### M-1. 下载文件完整性校验弱

**位置**: `electron/comfyUIInstaller.js` (L793-794)

当 SHA256 不可用时，仅校验文件 > 1MB。恶意/截断文件可通过此检查。

### M-2. `publishPost` 无输入校验

**位置**: `electron/ipcHandlers.js` (L24-37)

渲染进程传入的 `data.video` 路径和字符串直接用于浏览器自动化，可指向敏感系统文件。

### M-3. 同步文件系统操作阻塞事件循环

**位置**: `electron/main.js`, `electron/comfyUIInstaller.js`, `electron/settingsService.js`, `server/routers/workspace.py`

多处 `fs.existsSync`/`fs.readFileSync`/`open()` 在异步路径中使用同步调用。

### M-4. Playwright 浏览器实例未关闭

**位置**: `electron/ipcHandlers.js` (L362-382)

应用退出时未关闭 Playwright 浏览器进程。

### M-5. 命令注入向量

**位置**: `server/routers/workspace.py` (L140-149)

`subprocess.run(["explorer", folder_path])` 中 `folder_path` 来自用户输入，未校验。

### M-6. CORS 通配符

**位置**: `server/services/websocket_state.py` (L6)

`cors_allowed_origins="*"` 允许任意来源的 WebSocket 连接。

### M-7. 未经验证的请求体

**位置**: `server/routers/` 多个端点

大多数 POST 端点使用 `await request.json()` 而非 Pydantic 模型验证。

### M-8. 错误信息泄露内部状态

**位置**: `server/routers/workspace.py` (L27), `settings.py` (L298)

`str(e)` 直接返回到 API 响应中。

### M-9. 裸 `except:` 吞没所有异常

**位置**: `server/services/db_service.py` (L104)

```python
except:
    pass
```

### M-10. 配置初始化异常后仍标记为已初始化

**位置**: `server/services/config_service.py` (L141-145)

`finally` 块设置 `self.initialized = True`，即使配置完全损坏。

### M-11. `get_settings` 声称遮蔽敏感信息但实际未做

**位置**: `server/services/settings_service.py` (L79-161)

`get_settings()` 和 `get_raw_settings()` 返回完全相同的未遮蔽数据。

### M-12. useEffect 无依赖数组

**位置**: `react/src/components/chat/Chat.tsx` (L455-509)

每次渲染都重新订阅 11 个事件总线事件，严重影响性能。

### M-13. Markdown 组件每次渲染重建 components 对象

**位置**: `react/src/components/chat/Markdown.tsx` (L88-297)

`ReactMarkdown` 的 `components` 对象在组件体内创建，每次渲染触发子组件重渲染。

### M-14. 消息使用数组索引作为 React key

**位置**: `react/src/components/chat/Chat.tsx` (L624)

`<div key={`${idx}`}>` 导致不必要的重渲染和状态 bug。

### M-15. 大量 `any` 类型

**位置**: `react/src/` 多个文件

canvas 数据、视频元素、provider 数据、socket 事件等多处使用 `any` 类型。

### M-16. 敏感信息输出到控制台

**位置**: `react/src/api/auth.ts` (L97-101)

认证状态和用户信息被 `console.log` 输出。

### M-17. Token 作为查询参数发送

**位置**: `react/src/api/auth.ts` (L82)

设备码通过 URL 查询参数发送，可能被服务器日志和浏览器历史记录暴露。

### M-18. i18n 不一致 — 大量硬编码中文字符串

**位置**: `react/src/contexts/AuthContext.tsx`, `components/knowledge/Knowledge.tsx`, `components/chat/Chat.tsx`

存在 i18n 系统但使用不一致，多个组件包含硬编码中文。

### M-19. 无数据库连接池

**位置**: `server/services/db_service.py` (L48-197)

每个异步方法创建新的 `aiosqlite.connect()` 连接。

### M-20. 同步 HTTP 调用阻塞事件循环

**位置**: `server/routers/image_router.py` (L22)

`requests.get()` (同步) 在异步端点中调用。

### M-21. HTTP 客户端每次请求新建

**位置**: `server/utils/http_client.py`

每次调用 `HttpClient.create()` 创建新的 `httpx.AsyncClient`，丧失连接池优势。

### M-22. 工具确认使用忙等待轮询

**位置**: `server/services/tool_confirmation_manager.py` (L48-53)

`await asyncio.sleep(0.1)` 循环轮询，应使用 `asyncio.Event`。

### M-23. 三个冗余 HTTP 客户端库

**位置**: `server/requirements.txt`

同时依赖 `httpx`、`aiohttp`、`requests`。

### M-24. React 依赖版本未锁定

**位置**: `server/requirements.txt`

大部分 Python 依赖无版本锁定。

### M-25. ESLint `no-unused-vars` 被禁用

**位置**: `react/eslint.config.js` (L22)

### M-26. `noUnusedLocals`/`noUnusedParameters` 被注释掉

**位置**: `react/tsconfig.app.json` (L21-22)

---

## LOW 级别问题

| # | 位置 | 描述 |
|---|------|------|
| L-1 | `electron/comfyUIInstaller.js` L600, `electron/comfyUIManager.js` L67 | `findComfyUIMainDir` 函数重复定义 |
| L-2 | `electron/gemin_service.ts` | 死代码 — 未使用的 TypeScript 桩 |
| L-3 | `electron/test/` | 测试未使用测试框架 |
| L-4 | `electron/ipcHandlers.js` L375 | 硬编码过时 User-Agent (`Chrome/125.0.0.0`) |
| L-5 | `electron/ipcHandlers.js` L370-405 | 反检测技术引发 ToS 合规风险 |
| L-6 | `electron/main.js` L258 | `require('fs')` 重复引入 |
| L-7 | `electron/comfyUIManager.js` L30-36 | `process.on('exit')` 不支持异步处理器 |
| L-8 | `electron/ipcHandlers.js` L502-533 | `while(true)` 无超时的上传等待循环 |
| L-9 | `electron/main.js` L206 | 魔法数字 `57988` 无常量定义 |
| L-10 | `server/` 全局 | 全部使用 `print()` 而非 `logging` |
| L-11 | `server/routers/image_router.py` L94 | 硬编码 `localhost` URL |
| L-12 | `server/requirements.txt` | `gunicorn`、`mcp`、`piexif`、`pymediainfo` 未使用/未找到引用 |
| L-13 | `react/src/routes/assets.tsx` L8 | 组件命名为 `Home` 而非 `AssetsPage` |
| L-14 | `react/src/components/chat/Chat.tsx` L443 | 错误 toast 持续时间 1 小时 (`3600 * 1000`) |
| L-15 | `react/src/components/chat/Markdown.tsx` L211 | 基于 `includes` 的 dataURL 匹配，脆弱且低效 |
| L-16 | `react/src/components/chat/Chat.tsx` L87 | `mergedToolCallIds` ref 无限增长，无清理 |
| L-17 | `react/src/` 多文件 | 大量注释掉的死代码 |
| L-18 | `react/src/components/` | 多处缺少 ARIA 标签和无障碍支持 |
| L-19 | `.gitignore` | 缺少 `.claude/`、`electron/dist/` 等常见条目 |
| L-20 | 根目录 | 重复中文 README 文件 (`README_zh.md` 和 `README-zh.md`) |

---

## 架构层面观察

### Electron
- JS/TS 混用但无实际 TypeScript 构建流程，`tsconfig.json` 形同虚设
- `ipcHandlers.js` 636 行混合了 ComfyUI 安装和社交媒体发布两个完全无关的关注点
- 全局可变状态管理进程状态（`installationCancelled`、`comfyUIProcess`），不利于测试和推理

### Server
- 大量单例模式 + 可变全局状态，模块导入时即创建实例
- 循环依赖风险：`tools/comfy_dynamic.py` 导入了 `routers/comfyui_execution.py`（工具层导入路由层）
- `print()` + emoji 日志，无结构化日志、无日志级别、无配置能力

### React
- Zustand store 被冗余包裹在 React Context 中，无额外收益
- mitt 事件总线绕过 React 状态模型，组件通过 `useEffect` + `setState` 同步，数据流难以追踪
- 对话框 UI 状态（`showInstallDialog` 等）不必要地存储在全局 store 中
- 严重依赖包重复（`@excalidraw/excalidraw` + `tldraw` + `@xyflow/react`），功能重叠

### 构建 & 测试
- 无根级 lock 文件，构建不可复现
- Electron 和 React 使用不同 TypeScript 版本 (5.8 vs 5.7)
- CI 已删除、无测试步骤、触发分支不匹配
- React 和 Server 端均无测试覆盖

---

## 优先修复建议

1. **安全第一** — 修复所有 CRITICAL 级别问题（C-1 至 C-9），尤其是：
   - `executeJavaScript` 注入 → 替换为 IPC 消息
   - `webSecurity: false` → 使用自定义协议
   - 路径遍历 → 添加 `realpath` 校验
   - SSRF 代理 → 添加 URL 白名单
   - Token 存储 → 迁移至 httpOnly cookie

2. **稳定性** — 修复 HIGH 级别中的关键问题：
   - API 响应状态检查
   - 服务器启动轮询超时
   - IPC 来源校验

3. **质量基建** — 建立最低质量门禁：
   - 恢复 CI 流水线
   - 添加基本测试覆盖
   - 启用 ESLint/TypeScript 严格规则
   - 锁定依赖版本

---

*本报告由代码审查自动生成，暂不包含修复代码。*
