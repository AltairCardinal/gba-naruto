<template>
  <div class="user-mgmt">
    <h2>用户管理</h2>
    <p class="hint">在此为普通用户授予 / 撤销 4 种权限。admin 始终拥有所有权限。</p>

    <div v-if="loading" class="loading">加载中…</div>

    <table v-else-if="users.length > 0" class="data-table">
      <thead>
        <tr>
          <th>用户名</th>
          <th>角色</th>
          <th v-for="p in PERMS" :key="p">{{ PERM_LABELS[p] }}</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id" :class="{ 'is-self': user.username === auth.username }">
          <td>
            <strong>{{ user.username }}</strong>
            <span v-if="user.username === auth.username" class="self-tag">（你）</span>
          </td>
          <td>
            <span class="role-badge" :class="user.role">{{ user.role }}</span>
          </td>
          <td v-for="p in PERMS" :key="p" class="perm-cell">
            <input
              type="checkbox"
              :checked="user.permissions.includes(p)"
              :disabled="user.role === 'admin' || saving === user.username"
              @change="togglePerm(user, p, ($event.target as HTMLInputElement).checked)"
            />
          </td>
          <td>
            <button
              class="btn-danger-small"
              :disabled="user.username === auth.username || deleting === user.username"
              :title="user.username === auth.username ? '不能删除自己' : '删除此用户'"
              @click="deleteUser(user.username)"
            >
              {{ deleting === user.username ? '删除中…' : '删除' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else class="empty">暂无用户</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/authStore'

const auth = useAuthStore()

const PERMS = ['create_file', 'modify_file', 'delete_file', 'trigger_build']
const PERM_LABELS: Record<string, string> = {
  create_file: '新增',
  modify_file: '编辑',
  delete_file: '删除',
  trigger_build: '构建',
}

interface User {
  id: number
  username: string
  role: string
  created_at?: string
  permissions: string[]
}

const users = ref<User[]>([])
const loading = ref(false)
const saving = ref<string | null>(null)  // username currently saving
const deleting = ref<string | null>(null)

async function fetchUsers() {
  loading.value = true
  try {
    const res = await fetch('/api/users', { headers: { ...auth.authHeaders() } })
    if (!res.ok) throw new Error(`加载失败 (${res.status})`)
    users.value = await res.json()
  } catch (e: any) {
    alert(e?.message || '加载用户失败')
  } finally {
    loading.value = false
  }
}

/**
 * Toggle a single permission. We don't PUT a delta — the API expects a
 * complete permissions list — so we recompute the full set client-side
 * from the current row + the toggled perm, then PUT it.
 */
async function togglePerm(user: User, perm: string, granted: boolean) {
  const next = new Set(user.permissions)
  if (granted) next.add(perm)
  else next.delete(perm)
  await savePermissions(user, Array.from(next))
}

async function savePermissions(user: User, perms: string[]) {
  saving.value = user.username
  try {
    const res = await fetch(`/api/users/${encodeURIComponent(user.username)}/permissions`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...auth.authHeaders() },
      body: JSON.stringify({ permissions: perms }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `保存失败 (${res.status})`)
    }
    // Refresh the row from server to stay in sync (server may reorder).
    const updated: User = await res.json()
    const idx = users.value.findIndex((u) => u.id === user.id)
    if (idx >= 0) users.value[idx] = updated
  } catch (e: any) {
    alert(e?.message || '保存失败')
    // Reload to revert optimistic UI
    await fetchUsers()
  } finally {
    saving.value = null
  }
}

async function deleteUser(username: string) {
  if (username === auth.username) return  // belt-and-suspenders with backend
  if (!confirm(`确认删除用户 "${username}"？此操作不可撤销。`)) return
  deleting.value = username
  try {
    const res = await fetch(`/api/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers: { ...auth.authHeaders() },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `删除失败 (${res.status})`)
    }
    await fetchUsers()
  } catch (e: any) {
    alert(e?.message || '删除失败')
  } finally {
    deleting.value = null
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.user-mgmt { padding: 8px 0; }
h2 { color: #333; margin-bottom: 6px; }
.hint { color: #666; font-size: 13px; margin-bottom: 18px; }

.loading, .empty {
  padding: 40px 0;
  text-align: center;
  color: #888;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table th, .data-table td {
  border: 1px solid #e0e0e0;
  padding: 9px 12px;
  text-align: left;
}

.data-table th {
  background: #f5f7fa;
  font-weight: 600;
  color: #444;
}

.data-table tr.is-self {
  background: #fff8e1;
}

.perm-cell { text-align: center; }
.perm-cell input[type="checkbox"] { cursor: pointer; }
.perm-cell input[type="checkbox"]:disabled { cursor: not-allowed; opacity: 0.5; }

.self-tag {
  margin-left: 4px;
  font-size: 11px;
  color: #b08500;
  font-weight: 500;
}

.role-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}
.role-badge.admin { background: #ffe0b2; color: #b08500; }
.role-badge.editor { background: #e3f2fd; color: #0066cc; }

.btn-danger-small {
  background: #fff;
  color: #c62828;
  border: 1px solid #f5b6c0;
  padding: 4px 10px;
  border-radius: 3px;
  font-size: 12px;
  cursor: pointer;
}
.btn-danger-small:hover:not(:disabled) {
  background: #fde7ea;
}
.btn-danger-small:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
