import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface BattleConfig {
  id: number
  name: string
  chapter_id: number | null
  scenario_id: number | null
  player_units: any[] | null
  enemy_units: any[] | null
  terrain_mod: any | null
  turn_limit: number | null
  win_condition: string | null
  lose_condition: string | null
  created_at: string
  updated_at: string
}

export const useBattleConfigStore = defineStore('battleConfig', () => {
  const configs = ref<BattleConfig[]>([])
  const currentConfig = ref<BattleConfig | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchConfigs(chapterId?: number, scenarioId?: number) {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (chapterId !== undefined) params.append('chapter_id', String(chapterId))
      if (scenarioId !== undefined) params.append('scenario_id', String(scenarioId))
      
      const res = await fetch(`/api/battle-configs?${params}`)
      if (!res.ok) throw new Error('Failed to fetch battle configs')
      configs.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchConfig(id: number) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/battle-configs/${id}`)
      if (!res.ok) throw new Error('Config not found')
      currentConfig.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createConfig(data: Partial<BattleConfig>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/battle-configs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to create')
      }
      return await res.json()
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(id: number, data: Partial<BattleConfig>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/battle-configs/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!res.ok) throw new Error('Failed to update')
      currentConfig.value = await res.json()
      return currentConfig.value
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteConfig(id: number) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/battle-configs/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete')
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    configs,
    currentConfig,
    loading,
    error,
    fetchConfigs,
    fetchConfig,
    createConfig,
    updateConfig,
    deleteConfig
  }
})
