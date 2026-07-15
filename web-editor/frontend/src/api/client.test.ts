// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { apiFetch } from './client'

describe('apiFetch authentication', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('gba-naruto-editor-jwt', 'editor-token')
    setActivePinia(createPinia())
  })

  it('uses the token persisted by authStore', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch<{ ok: boolean }>('/api/v1/dialogues')

    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer editor-token')
  })
})
