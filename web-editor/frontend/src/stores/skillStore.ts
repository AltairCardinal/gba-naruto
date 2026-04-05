import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Skill {
  id: number
  unit_id: number
  name: string
  name_ja: string | null
  name_zh: string | null
  description: string | null
  description_ja: string | null
  description_zh: string | null
  damage: number
  heal: number
  range_min: number
  range_max: number
  cost_hp: number
  cost_chakra: number
  effect_type: string | null
  created_at: string
  updated_at: string
}

export const useSkillStore = defineStore('skill', () => {
  const skills = ref<Skill[]>([])
  const currentSkill = ref<Skill | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSkills(unitId?: number) {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (unitId !== undefined) params.append('unit_id', String(unitId))
      
      const res = await fetch(`/api/skills?${params}`)
      if (!res.ok) throw new Error('Failed to fetch skills')
      skills.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchSkill(id: number) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/skills/${id}`)
      if (!res.ok) throw new Error('Skill not found')
      currentSkill.value = await res.json()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createSkill(data: Partial<Skill>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/skills', {
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

  async function updateSkill(id: number, data: Partial<Skill>) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/skills/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })
      if (!res.ok) throw new Error('Failed to update')
      currentSkill.value = await res.json()
      return currentSkill.value
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteSkill(id: number) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/skills/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete')
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    skills,
    currentSkill,
    loading,
    error,
    fetchSkills,
    fetchSkill,
    createSkill,
    updateSkill,
    deleteSkill
  }
})
