import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_V1, apiFetch } from '../api/client'
import type { DialogueResponse, DialogueCreate, DialogueUpdate } from '../api/types'

export type Dialogue = DialogueResponse

export const useDialogueStore = defineStore('dialogue', () => {
  const dialogues = ref<Dialogue[]>([])
  const currentDialogue = ref<Dialogue | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchDialogues(page = 1, limit = 20, search?: string, chapterId?: number) {
    loading.value = true
    error.value = null
    try {
      dialogues.value = await apiFetch<Dialogue[]>(`${API_V1}/dialogues`, {
        query: { page, limit, search, chapter_id: chapterId },
      })
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
      currentDialogue.value = await apiFetch<Dialogue>(`${API_V1}/dialogues/${key}`)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createDialogue(data: DialogueCreate) {
    loading.value = true
    error.value = null
    try {
      return await apiFetch<Dialogue>(`${API_V1}/dialogues`, {
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

  async function updateDialogue(key: string, data: DialogueUpdate) {
    loading.value = true
    error.value = null
    try {
      currentDialogue.value = await apiFetch<Dialogue>(`${API_V1}/dialogues/${key}`, {
        method: 'PUT',
        body: data,
      })
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
      await apiFetch<void>(`${API_V1}/dialogues/${key}`, { method: 'DELETE' })
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function getByteCount(key: string) {
    return apiFetch<{ count: number }>(`${API_V1}/dialogues/${key}/byte-count`)
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