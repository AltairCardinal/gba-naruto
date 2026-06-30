import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_V1, apiFetch } from '../api/client'
import type { BattleConfigResponse, BattleConfigCreate, BattleConfigUpdate } from '../api/types'

/**
 * Backend returns only (id, chapter_id, scenario_id, config_json, created_at, updated_at).
 * Anything else (player_units, win_condition, etc.) lives inside `config_json`
 * — views should JSON.parse it rather than expecting top-level fields.
 */
export type BattleConfig = BattleConfigResponse

export const useBattleConfigStore = defineStore('battleConfig', () => {
  const configs = ref<BattleConfig[]>([])
  const currentConfig = ref<BattleConfig | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchConfigs(chapterId?: number, scenarioId?: number) {
    loading.value = true
    error.value = null
    try {
      configs.value = await apiFetch<BattleConfig[]>(`${API_V1}/battle-configs`, {
        query: { chapter_id: chapterId, scenario_id: scenarioId },
      })
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
      currentConfig.value = await apiFetch<BattleConfig>(`${API_V1}/battle-configs/${id}`)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createConfig(data: BattleConfigCreate) {
    loading.value = true
    error.value = null
    try {
      return await apiFetch<BattleConfig>(`${API_V1}/battle-configs`, {
        method: 'POST',
        body: data,
      })
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateConfig(id: number, data: BattleConfigUpdate) {
    loading.value = true
    error.value = null
    try {
      currentConfig.value = await apiFetch<BattleConfig>(`${API_V1}/battle-configs/${id}`, {
        method: 'PUT',
        body: data,
      })
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
      await apiFetch<void>(`${API_V1}/battle-configs/${id}`, { method: 'DELETE' })
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