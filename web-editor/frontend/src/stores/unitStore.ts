import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Unit {
  id: number
  char_id: number
  name: string
  name_ja: string | null
  name_zh: string | null
  hp: number
  attack: number
  defense: number
  speed: number
  chapter_id: number | null
  map_id: string | null
  position_x: number | null
  position_y: number | null
  team: number
  created_at: string
  updated_at: string
}

export const useUnitStore = defineStore('unit', () => {
  const units = ref<Unit[]>([])
  const currentUnit = ref<Unit | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchUnits(chapterId?: number, team?: number, mapId?: string) {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (chapterId !== undefined) params.append('chapter_id', String(chapterId))
      if (team !== undefined) params.append('team', String(team))
      if (mapId) params.append('map_id', mapId)
      
      const res = await fetch(`/api/units?${params}`)
      if (!res.ok) throw new Error('Failed to fetch units')
      units.value = await res.json()
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
      const res = await fetch(`/api/units/${id}`)
      if (!res.ok) throw new Error('Unit not found')
      currentUnit.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createUnit(data: Partial<Unit>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/units', {
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

  async function updateUnit(id: number, data: Partial<Unit>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/units/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!res.ok) throw new Error('Failed to update')
      currentUnit.value = await res.json()
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
      const res = await fetch(`/api/units/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete')
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
