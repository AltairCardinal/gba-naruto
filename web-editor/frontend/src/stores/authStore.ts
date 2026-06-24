import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const TOKEN_KEY = 'gba-naruto-editor-jwt'
const USER_KEY = 'gba-naruto-editor-user'
const PERMS_KEY = 'gba-naruto-editor-perms'
const ROLE_KEY = 'gba-naruto-editor-role'

export interface AuthUser {
  username: string
  role: 'admin' | 'editor'
  permissions: string[]
}

function readToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
function readUsername(): string | null {
  try { return localStorage.getItem(USER_KEY) } catch { return null }
}
function readRole(): string | null {
  try { return localStorage.getItem(ROLE_KEY) } catch { return null }
}
function readPerms(): string[] {
  try {
    const v = localStorage.getItem(PERMS_KEY)
    return v ? JSON.parse(v) : []
  } catch { return [] }
}

export const useAuthStore = defineStore('auth', () => {
  // Token is the only thing that matters for API auth — but we also keep
  // user/role/perms in localStorage so a hard reload still has something to
  // render the navbar with before /me completes.
  const token = ref<string | null>(readToken())
  const username = ref<string | null>(readUsername())
  const role = ref<string | null>(readRole())
  const permissions = ref<string[]>(readPerms())

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  function authHeaders(): Record<string, string> {
    const t = token.value
    return t ? { Authorization: `Bearer ${t}` } : {}
  }

  /** Whether the current user has a specific permission. Admin always does. */
  function has(perm: string): boolean {
    if (role.value === 'admin') return true
    return permissions.value.includes(perm)
  }

  /** Persist the new auth state. Called by login/register/fetchMe. */
  function _persist(t: string, u: string, r: string, p: string[]) {
    token.value = t
    username.value = u
    role.value = r
    permissions.value = p
    try {
      localStorage.setItem(TOKEN_KEY, t)
      localStorage.setItem(USER_KEY, u)
      localStorage.setItem(ROLE_KEY, r)
      localStorage.setItem(PERMS_KEY, JSON.stringify(p))
    } catch {}
  }

  function clear() {
    token.value = null
    username.value = null
    role.value = null
    permissions.value = []
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      localStorage.removeItem(ROLE_KEY)
      localStorage.removeItem(PERMS_KEY)
    } catch {}
  }

  async function login(usernameInput: string, password: string): Promise<void> {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: usernameInput, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Login failed (${res.status})`)
    }
    const data = await res.json()
    // Stash the user/role from login response, then refresh /me to get
    // the full permission list (login doesn't return it).
    _persist(data.access_token, data.username, data.role, [])
    await fetchMe()
  }

  async function register(usernameInput: string, password: string): Promise<void> {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: usernameInput, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(typeof err.detail === 'string' ? err.detail : `Register failed (${res.status})`)
    }
    // Auto-login after register so the user lands on a working session.
    await login(usernameInput, password)
  }

  async function fetchMe(): Promise<AuthUser> {
    const res = await fetch('/api/auth/me', { headers: { ...authHeaders() } })
    if (!res.ok) {
      // Token rejected → clear so router sends user back to /login.
      if (res.status === 401) clear()
      throw new Error(`fetch /me failed (${res.status})`)
    }
    const data = await res.json()
    _persist(token.value || '', data.username, data.role, data.permissions || [])
    return { username: data.username, role: data.role, permissions: data.permissions || [] }
  }

  function logout() {
    clear()
  }

  return {
    token,
    username,
    role,
    permissions,
    isLoggedIn,
    isAdmin,
    authHeaders,
    has,
    login,
    register,
    fetchMe,
    logout,
  }
})
