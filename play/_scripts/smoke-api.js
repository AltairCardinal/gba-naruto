#!/usr/bin/env node
/**
 * L3 e2e smoke test: verify all CRUD store URL endpoints return 200/expected.
 *
 * Why this exists:
 *   6/30/2026 — 5 stores called /api/{dialogues,skills,story-beats,
 *   battle-configs,units} but the real prefix is /api/v1/*. Bug shipped
 *   because no automated check caught the prefix drift. This script
 *   hits the 5 endpoints via fetch and fails if any returns 404.
 *
 * Usage:
 *   node play/_scripts/smoke-api.js [BASE_URL]
 *
 * Default BASE_URL: https://sh.kibox.com.cn
 * Exit 0 if all 5 endpoints return 200, 1 otherwise.
 */

const BASE_URL = process.argv[2] || 'https://sh.kibox.com.cn'

const ENDPOINTS = [
  { name: 'dialogues',       path: '/web-editor/api/v1/dialogues' },
  { name: 'skills',          path: '/web-editor/api/v1/skills' },
  { name: 'units',           path: '/web-editor/api/v1/units' },
  { name: 'story-beats',     path: '/web-editor/api/v1/story-beats' },
  { name: 'battle-configs',  path: '/web-editor/api/v1/battle-configs' },
]

async function login() {
  const res = await fetch(`${BASE_URL}/web-editor/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'kibox', password: 'Ztl159632' }),
  })
  if (!res.ok) throw new Error(`login failed: ${res.status}`)
  const data = await res.json()
  if (!data.access_token) throw new Error('login: no access_token in response')
  return data.access_token
}

async function check(name, path, token) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return { name, path, status: res.status, ok: res.ok }
}

async function main() {
  console.log(`[smoke] BASE_URL=${BASE_URL}`)
  let token
  try {
    token = await login()
    console.log(`[smoke] login OK (token len=${token.length})`)
  } catch (e) {
    console.error(`[smoke] FATAL: ${e.message}`)
    process.exit(2)
  }

  let failed = 0
  for (const ep of ENDPOINTS) {
    try {
      const r = await check(ep.name, ep.path, token)
      const tag = r.ok ? '✅' : '❌'
      console.log(`[smoke] ${tag} ${r.name.padEnd(18)} ${r.path} → ${r.status}`)
      if (!r.ok) failed++
    } catch (e) {
      console.error(`[smoke] ❌ ${ep.name.padEnd(18)} ${ep.path} → ${e.message}`)
      failed++
    }
  }

  console.log(`[smoke] ${failed === 0 ? 'PASS' : 'FAIL'}: ${ENDPOINTS.length - failed}/${ENDPOINTS.length} OK`)
  process.exit(failed === 0 ? 0 : 1)
}

main().catch(err => {
  console.error('[smoke] unhandled:', err)
  process.exit(2)
})