// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useBuildStore } from './buildStore'

describe('build ROM download', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('gba-naruto-editor-jwt', 'download-token')
    setActivePinia(createPinia())
  })

  it('downloads the selected build through authenticated fetch', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob([new Uint8Array([1, 2, 3])]), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const createObjectURL = vi.fn().mockReturnValue('blob:rom')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    const store = useBuildStore()
    await store.downloadRom('owned-build')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/build/download?build_id=owned-build',
      expect.objectContaining({
        headers: { Authorization: 'Bearer download-token' },
      }),
    )
    expect(createObjectURL).toHaveBeenCalled()
    expect(click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:rom')
  })

  it('authenticates the websocket first frame for an explicit build', () => {
    class FakeWebSocket {
      static instances: FakeWebSocket[] = []
      url: string
      sent: string[] = []
      onopen: (() => void) | null = null
      onmessage = null
      onclose = null
      onerror = null
      constructor(url: string) {
        this.url = url
        FakeWebSocket.instances.push(this)
      }
      send(value: string) { this.sent.push(value) }
      close() {}
    }
    vi.stubGlobal('WebSocket', FakeWebSocket)

    const store = useBuildStore()
    store.connectBuildWs('owned-build')
    const websocket = FakeWebSocket.instances[0]
    websocket.onopen?.()

    expect(websocket.url).toMatch(/\/ws\/build$/)
    expect(JSON.parse(websocket.sent[0])).toEqual({
      type: 'auth', token: 'download-token', build_id: 'owned-build',
    })
  })
})
