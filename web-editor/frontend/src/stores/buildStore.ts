import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './authStore'

export interface BuildStatus {
  build_id?: string | null
  status: 'idle' | 'running' | 'done' | 'error'
  logs: string[]
  progress: number
  rom_path: string | null
  error?: string | null
}

function authHeaders(): Record<string, string> {
  // Delegate to the auth store so we have a single source of truth for
  // the JWT. (We don't import the store at module level because pinia
  // may not be installed yet when this module is first evaluated.)
  try {
    const auth = useAuthStore()
    return auth.authHeaders()
  } catch {
    return {}
  }
}

export const useBuildStore = defineStore('build', () => {
  const buildStatus = ref<BuildStatus>({
    build_id: null,
    status: 'idle',
    logs: [],
    progress: 0,
    rom_path: null,
    error: null,
  })

  const wsConnection = ref<WebSocket | null>(null)
  const wsConnected = ref(false)
  const currentBuildId = ref<string | null>(null)
  const isDownloading = ref(false)

  function connectBuildWs(buildId?: string | null) {
    if (wsConnection.value) {
      wsConnection.value.close()
      wsConnection.value = null
    }

    const auth = useAuthStore()
    if (!buildId) {
      buildStatus.value.error = '缺少 build_id，无法连接构建日志'
      return false
    }
    if (!auth.token) {
      buildStatus.value.error = '登录已过期，请重新登录'
      return false
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/build`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', token: auth.token, build_id: buildId }))
      wsConnected.value = true
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.build_id) currentBuildId.value = data.build_id
        buildStatus.value = {
          build_id: data.build_id ?? currentBuildId.value,
          status: data.status,
          logs: data.logs ?? [],
          progress: data.progress ?? 0,
          rom_path: data.rom_path ?? null,
          error: data.error ?? null,
        }
        if (data.status === 'done' || data.status === 'error') {
          // Server stops streaming after terminal status; let the WS hang up
          // gracefully so the next trigger_build can re-open it.
          setTimeout(() => {
            if (wsConnection.value === ws) {
              ws.close()
            }
          }, 1500)
        }
      } catch (e) {
        console.warn('[buildStore] ws parse error', e)
      }
    }

    ws.onclose = (event) => {
      wsConnected.value = false
      if (wsConnection.value === ws) wsConnection.value = null
      if (event.code === 4401) {
        auth.logout()
        buildStatus.value.error = '登录已过期，请重新登录'
      } else if (event.code === 4403) {
        buildStatus.value.error = '无权查看该构建'
      } else if (event.code === 4404) {
        buildStatus.value.error = '构建记录不存在或已失效'
      }
    }

    ws.onerror = () => {
      wsConnected.value = false
    }

    wsConnection.value = ws
    return true
  }

  /**
   * Login is now handled by the authStore. We keep these methods as thin
   * delegating wrappers so any other code still calling store.login() etc.
   * (e.g. the legacy BuildView inline form, scripts) keeps working.
   */
  async function login(username: string, password: string): Promise<string> {
    const auth = useAuthStore()
    await auth.login(username, password)
    return auth.token || ''
  }

  function logout() {
    const auth = useAuthStore()
    auth.logout()
  }

  function getStoredUser(): string | null {
    try {
      const auth = useAuthStore()
      return auth.username
    } catch {
      return null
    }
  }

  async function triggerBuild() {
    const res = await fetch('/api/build/trigger', {
      method: 'POST',
      headers: { ...authHeaders() },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to trigger build (${res.status})`)
    }
    const data = await res.json()
    currentBuildId.value = data.build_id
    buildStatus.value = {
      build_id: data.build_id,
      status: 'running',
      logs: ['[BUILD] Triggered...'],
      progress: 0,
      rom_path: null,
      error: null,
    }
    // Open a per-build WS so logs stream live
    connectBuildWs(data.build_id)
    return data
  }

  async function fetchBuildStatus(buildId?: string | null) {
    const qs = buildId ? `?build_id=${encodeURIComponent(buildId)}` : ''
    const res = await fetch(`/api/build/status${qs}`, {
      headers: { ...authHeaders() },
    })
    if (!res.ok) throw new Error(`Failed to fetch build status (${res.status})`)
    const data = await res.json()
    if (data.build_id) currentBuildId.value = data.build_id
    buildStatus.value = {
      build_id: data.build_id ?? currentBuildId.value,
      status: data.status,
      logs: data.logs ?? [],
      progress: data.progress ?? 0,
      rom_path: data.rom_path ?? null,
      error: data.error ?? null,
    }
    return data
  }

  async function downloadRom(buildId?: string | null) {
    const qs = buildId ? `?build_id=${encodeURIComponent(buildId)}` : ''
    const auth = useAuthStore()
    isDownloading.value = true
    buildStatus.value.error = null
    let objectUrl: string | null = null
    try {
      const res = await fetch(`/api/build/download${qs}`, {
        headers: { ...auth.authHeaders() },
      })
      if (!res.ok) {
        if (res.status === 401) auth.logout()
        const payload = await res.json().catch(() => ({}))
        throw new Error(payload.detail || `ROM 下载失败（${res.status}）`)
      }
      objectUrl = URL.createObjectURL(await res.blob())
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = 'naruto-sequel-dev.gba'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (error) {
      buildStatus.value.error = error instanceof Error ? error.message : 'ROM 下载失败'
      throw error
    } finally {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
      isDownloading.value = false
    }
  }

  /**
   * Open the emulator with the current build's ROM. Uses the *public* ROM
   * endpoint so the editor → emulator link works without juggling JWTs in
   * the URL. The build_id is a 122-bit UUID acting as the access token.
   */
  function openInEmulator(): boolean {
    const id = currentBuildId.value
    if (!id) {
      console.warn('[buildStore] openInEmulator: no current build_id')
      return false
    }
    if (buildStatus.value.status !== 'done') {
      console.warn('[buildStore] openInEmulator: build not done')
      return false
    }
    // /gba-naruto is the public prefix; the API path then reaches the
    // backend through nginx without exposing the JWT to the emulator tab.
    const emulatorBase = `${window.location.protocol}//${window.location.host}/gba-naruto/play/`
    const romPath = `/gba-naruto/api/public/rom/${encodeURIComponent(id)}`
    const url = `${emulatorBase}?rom=${encodeURIComponent(romPath)}`
    window.open(url, '_blank', 'noopener')
    return true
  }

  function clearLogs() {
    buildStatus.value.logs = []
  }

  return {
    buildStatus,
    wsConnection,
    wsConnected,
    currentBuildId,
    isDownloading,
    connectBuildWs,
    login,
    logout,
    getStoredUser,
    triggerBuild,
    fetchBuildStatus,
    downloadRom,
    openInEmulator,
    clearLogs,
  }
})
