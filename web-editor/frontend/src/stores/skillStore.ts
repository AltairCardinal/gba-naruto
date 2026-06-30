import { defineStore } from 'pinia'
import { ref } from 'vue'
import { API_V1, apiFetch } from '../api/client'
import type { SkillResponse, SkillCreate, SkillUpdate } from '../api/types'

export type Skill = SkillResponse

export const useSkillStore = defineStore('skill', () => {
  const skills = ref<Skill[]>([])
  const currentSkill = ref<Skill | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchSkills(unitId?: number) {
    loading.value = true
    error.value = null
    try {
      skills.value = await apiFetch<Skill[]>(`${API_V1}/skills`, {
        query: { unit_id: unitId },
      })
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
      currentSkill.value = await apiFetch<Skill>(`${API_V1}/skills/${id}`)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createSkill(data: SkillCreate) {
    loading.value = true
    error.value = null
    try {
      return await apiFetch<Skill>(`${API_V1}/skills`, {
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

  async function updateSkill(id: number, data: SkillUpdate) {
    loading.value = true
    error.value = null
    try {
      currentSkill.value = await apiFetch<Skill>(`${API_V1}/skills/${id}`, {
        method: 'PUT',
        body: data,
      })
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
      await apiFetch<void>(`${API_V1}/skills/${id}`, { method: 'DELETE' })
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