import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_V1, apiFetch } from '../api/client'
import type { UnitResponse, UnitCreate, UnitUpdate } from '../api/types'

export type Unit = UnitResponse

export const useUnitStore = defineStore('unit', () => {
  const units = ref<Unit[]>([])
  const currentUnit = ref<Unit | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchUnits(chapterId?: number, team?: number, mapId?: string) {
    loading.value = true
    error.value = null
    try {
      units.value = await apiFetch<Unit[]>(`${API_V1}/units`, {
        query: { chapter_id: chapterId, team, map_id: mapId },
      })
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchUnit(id: number) {
    loading.value = true
    error.value = null
    try {
      currentUnit.value = await apiFetch<Unit>(`${API_V1}/units/${id}`)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createUnit(data: UnitCreate) {
    loading.value = true
    error.value = null
    try {
      return await apiFetch<Unit>(`${API_V1}/units`, {
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

  async function updateUnit(id: number, data: UnitUpdate) {
    loading.value = true
    error.value = null
    try {
      currentUnit.value = await apiFetch<Unit>(`${API_V1}/units/${id}`, {
        method: 'PUT',
        body: data,
      })
      return currentUnit.value
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteUnit(id: number) {
    loading.value = true
    error.value = null
    try {
      await apiFetch<void>(`${API_V1}/units/${id}`, { method: 'DELETE' })
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    units,
    currentUnit,
    loading,
    error,
    fetchUnits,
    fetchUnit,
    createUnit,
    updateUnit,
    deleteUnit
  }
})