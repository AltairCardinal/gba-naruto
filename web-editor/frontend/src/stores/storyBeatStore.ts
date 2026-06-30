import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_V1, apiFetch } from '../api/client'
import type { StoryBeatResponse, StoryBeatCreate, StoryBeatUpdate } from '../api/types'

export type StoryBeat = StoryBeatResponse

export const useStoryBeatStore = defineStore('storyBeat', () => {
  const storyBeats = ref<StoryBeat[]>([])
  const currentStoryBeat = ref<StoryBeat | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchStoryBeats(chapterId?: number) {
    loading.value = true
    error.value = null
    try {
      storyBeats.value = await apiFetch<StoryBeat[]>(`${API_V1}/story-beats`, {
        query: { chapter_id: chapterId },
      })
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchStoryBeat(id: number) {
    loading.value = true
    error.value = null
    try {
      currentStoryBeat.value = await apiFetch<StoryBeat>(`${API_V1}/story-beats/${id}`)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createStoryBeat(data: StoryBeatCreate) {
    loading.value = true
    error.value = null
    try {
      return await apiFetch<StoryBeat>(`${API_V1}/story-beats`, {
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

  async function updateStoryBeat(id: number, data: StoryBeatUpdate) {
    loading.value = true
    error.value = null
    try {
      currentStoryBeat.value = await apiFetch<StoryBeat>(`${API_V1}/story-beats/${id}`, {
        method: 'PUT',
        body: data,
      })
      return currentStoryBeat.value
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteStoryBeat(id: number) {
    loading.value = true
    error.value = null
    try {
      await apiFetch<void>(`${API_V1}/story-beats/${id}`, { method: 'DELETE' })
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    storyBeats,
    currentStoryBeat,
    loading,
    error,
    fetchStoryBeats,
    fetchStoryBeat,
    createStoryBeat,
    updateStoryBeat,
    deleteStoryBeat
  }
})