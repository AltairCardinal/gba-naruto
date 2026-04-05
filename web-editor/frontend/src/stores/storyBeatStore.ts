import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface StoryBeat {
  id: number
  chapter_id: number
  beat_index: number
  beat_type: string
  title: string | null
  title_ja: string | null
  title_zh: string | null
  description: string | null
  description_ja: string | null
  description_zh: string | null
  trigger_type: string | null
  trigger_param: string | null
  dialogue_key: string | null
  battle_config_id: number | null
  map_id: string | null
  position_x: number | null
  position_y: number | null
  next_beat_id: number | null
  created_at: string
  updated_at: string
}

export const useStoryBeatStore = defineStore('storyBeat', () => {
  const storyBeats = ref<StoryBeat[]>([])
  const currentStoryBeat = ref<StoryBeat | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchStoryBeats(chapterId?: number) {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (chapterId !== undefined) params.append('chapter_id', String(chapterId))
      
      const res = await fetch(`/api/story-beats?${params}`)
      if (!res.ok) throw new Error('Failed to fetch story beats')
      storyBeats.value = await res.json()
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
      const res = await fetch(`/api/story-beats/${id}`)
      if (!res.ok) throw new Error('Story beat not found')
      currentStoryBeat.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createStoryBeat(data: Partial<StoryBeat>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/story-beats', {
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

  async function updateStoryBeat(id: number, data: Partial<StoryBeat>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/story-beats/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!res.ok) throw new Error('Failed to update')
      currentStoryBeat.value = await res.json()
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
      const res = await fetch(`/api/story-beats/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete')
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
