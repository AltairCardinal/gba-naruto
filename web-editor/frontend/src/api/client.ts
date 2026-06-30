/**
 * Centralized API client.
 *
 * Why this file exists:
 * 6/30/2026 — 5 stores each called `/api/{dialogues,skills,story-beats,
 * battle-configs,units}` but the real router prefix is `/api/v1/*`. We
 * fixed it with sed once, but the only way to keep it from happening
 * again is to centralize the base URLs here and to type-check fetch
 * calls against the backend's OpenAPI schema. See types.ts.
 *
 * Rules for adding a new endpoint:
 *   1. Pick a base: API_V1 or API_PLAIN
 *   2. Use apiFetch<T>() — never raw fetch() in stores
 *   3. If the type doesn't exist yet, add it to types.ts
 */

export const API_V1 = '/api/v1'
export const API_PLAIN = '/api'

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API ${status}`)
    this.status = status
    this.body = body
  }
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined | null>
  signal?: AbortSignal
}

/**
 * Typed fetch wrapper. Throws ApiError on non-2xx.
 *
 * Usage:
 *   const list = await apiFetch<DialogueResponse[]>(`${API_V1}/dialogues`)
 *   const one  = await apiFetch<DialogueResponse>(`${API_V1}/dialogues/${key}`)
 */
export async function apiFetch<T>(path: string, opts: ApiFetchOptions = {}): Promise<T> {
  const { method = 'GET', body, query, signal } = opts
  let url = path
  if (query) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) qs.set(k, String(v))
    }
    const s = qs.toString()
    if (s) url += (path.includes('?') ? '&' : '?') + s
  }
  const res = await fetch(url, {
    method,
    signal,
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...authHeaders(),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let errBody: unknown
    try {
      errBody = await res.json()
    } catch {
      errBody = await res.text().catch(() => null)
    }
    throw new ApiError(res.status, errBody)
  }
  // 204 No Content → return undefined cast
  if (res.status === 204) return undefined as T
  // Some endpoints return empty body on success (e.g. delete).
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}