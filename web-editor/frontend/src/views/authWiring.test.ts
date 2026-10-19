import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

describe('authenticated view wiring', () => {
  it('MapEditor uses the shared auth store token instead of a legacy key', () => {
    const source = readFileSync(new URL('./MapEditorView.vue', import.meta.url), 'utf8')
    expect(source).not.toContain("localStorage.getItem('access_token')")
    expect(source).toContain('auth.authHeaders()')
    expect(source).toContain("headers: { 'Content-Type': 'application/json', ...auth.authHeaders() }")
  })
})
