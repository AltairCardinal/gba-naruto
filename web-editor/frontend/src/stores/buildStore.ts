import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface BuildStatus {
  status: 'idle' | 'running' | 'done' | 'error'
  logs: string[]
  progress: number
  rom_path: string | null
}

export const useBuildStore = defineStore('build', () => {
  const buildStatus = ref<BuildStatus>({
    status: 'idle',
    logs: [],
    progress: 0,
    rom_path: null
  })
  
  const wsConnection = ref<WebSocket | null>(null)
  const wsConnected = ref(false)

  function connectBuildWs() {
    if (wsConnection.value) return
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/build`
    
    const ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      wsConnected.value = true
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      buildStatus.value = {
        status: data.status,
        logs: data.logs,
        progress: data.progress,
        rom_path: data.rom_path
      }
    }
    
    ws.onclose = () => {
      wsConnected.value = false
      wsConnection.value = null
    }
    
    ws.onerror = () => {
      wsConnected.value = false
    }
    
    wsConnection.value = ws
  }

  async function triggerBuild() {
    const res = await fetch('/api/build/trigger', { method: 'POST' })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Failed to trigger build')
    }
    return await res.json()
  }

  async function fetchBuildStatus() {
    const res = await fetch('/api/build/status')
    if (!res.ok) throw new Error('Failed to fetch build status')
    buildStatus.value = await res.json()
  }

  async function downloadRom() {
    const link = document.createElement('a')
    link.href = '/api/build/download'
    link.download = 'naruto-sequel-dev.gba'
    link.click()
  }

  function clearLogs() {
    buildStatus.value.logs = []
  }

  return {
    buildStatus,
    wsConnection,
    wsConnected,
    connectBuildWs,
    triggerBuild,
    fetchBuildStatus,
    downloadRom,
    clearLogs
  }
})