import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiFetch } from '../api/client'
import type { RomStructure, RomStructureListResponse } from '../api/types'

export const useRomExplorerStore = defineStore('romExplorer', () => {
  const structures = ref<RomStructure[]>([])
  const currentStructure = ref<string | null>(null)
  const rows = ref<Array<Record<string, number | string | null>>>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadStructures() {
    loading.value = true
    error.value = null
    try {
      structures.value = await apiFetch<RomStructure[]>('/api/rom/structures')
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function loadStructure(name: string, limit = 100, offset = 0) {
    loading.value = true
    error.value = null
    try {
      const r = await apiFetch<RomStructureListResponse>(
        `/api/rom/structures/${name}`,
        { query: { limit, offset } },
      )
      currentStructure.value = name
      rows.value = r.rows
      total.value = r.total
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return {
    structures,
    currentStructure,
    rows,
    total,
    loading,
    error,
    loadStructures,
    loadStructure,
  }
})