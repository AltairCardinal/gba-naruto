import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Dialogue {
  id: number
  key: string
  speaker: string | null
  text_ja: string | null
  text_zh: string | null
  chapter_id: number | null
  byte_count: number
  max_bytes: number
  created_at: string
  updated_at: string
}

export const useDialogueStore = defineStore('dialogue', () => {
  const dialogues = ref<Dialogue[]>([])
  const currentDialogue = ref<Dialogue | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchDialogues(page = 1, limit = 20, search?: string, chapterId?: number) {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams({ page: String(page), limit: String(limit) })
      if (search) params.append('search', search)
      if (chapterId !== undefined) params.append('chapter_id', String(chapterId))
      
      const res = await fetch(`/api/dialogues?${params}`)
      if (!res.ok) throw new Error('Failed to fetch dialogues')
      dialogues.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchDialogue(key: string) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/dialogues/${key}`)
      if (!res.ok) throw new Error('Dialogue not found')
      currentDialogue.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createDialogue(data: Partial<Dialogue>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/dialogues', {
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

  async function updateDialogue(key: string, data: Partial<Dialogue>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/dialogues/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!res.ok) throw new Error('Failed to update')
      currentDialogue.value = await res.json()
      return currentDialogue.value
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteDialogue(key: string) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/dialogues/${key}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete')
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function getByteCount(key: string) {
    const res = await fetch(`/api/dialogues/${key}/byte-count`)
    if (!res.ok) throw new Error('Failed to get byte count')
    return await res.json()
  }

  return {
    dialogues,
    currentDialogue,
    loading,
    error,
    fetchDialogues,
    fetchDialogue,
    createDialogue,
    updateDialogue,
    deleteDialogue,
    getByteCount
  }
})