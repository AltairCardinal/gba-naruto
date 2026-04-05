<template>
  <div class="user-list">
    <h2>用户管理</h2>
    <div class="actions">
      <button @click="showCreateModal = true" class="btn-primary">新建用户</button>
    </div>

    <table v-if="users.length > 0" class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>角色</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.id }}</td>
          <td>{{ user.username }}</td>
          <td>{{ user.role }}</td>
          <td>{{ user.created_at }}</td>
          <td>
            <button @click="editUser(user)" class="btn-small">编辑</button>
            <button @click="deleteUser(user.id)" class="btn-small btn-danger">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无用户</div>

    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ showEditModal ? '编辑用户' : '新建用户' }}</h3>
        <form @submit.prevent="saveUser">
          <div class="form-group">
            <label>用户名</label>
            <input v-model="form.username" required :disabled="showEditModal" />
          </div>
          <div class="form-group">
            <label>密码</label>
            <input v-model="form.password" type="password" :required="!showEditModal" />
          </div>
          <div class="form-group">
            <label>角色</label>
            <select v-model="form.role">
              <option value="admin">管理员</option>
              <option value="editor">编辑</option>
              <option value="viewer">查看者</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="button" @click="closeModal" class="btn-secondary">取消</button>
            <button type="submit" class="btn-primary">保存</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface User {
  id: number
  username: string
  role: string
  created_at: string
}

const users = ref<User[]>([])
const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingId = ref<number | null>(null)

const form = ref({
  username: '',
  password: '',
  role: 'editor'
})

onMounted(async () => {
  await fetchUsers()
})

async function fetchUsers() {
  const res = await fetch('/api/users')
  users.value = await res.json()
}

function editUser(user: User) {
  editingId.value = user.id
  form.value = { username: user.username, password: '', role: user.role }
  showEditModal.value = true
}

async function saveUser() {
  try {
    const method = showEditModal.value ? 'PUT' : 'POST'
    const url = showEditModal.value && editingId.value ? `/api/users/${editingId.value}` : '/api/users'
    
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })
    
    if (!res.ok) throw new Error('Failed to save')
    
    await fetchUsers()
    closeModal()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteUser(id: number) {
  if (!confirm('确认删除?')) return
  await fetch(`/api/users/${id}`, { method: 'DELETE' })
  await fetchUsers()
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingId.value = null
  form.value = { username: '', password: '', role: 'editor' }
}
</script>

<style scoped>
.user-list { padding: 20px; }
.actions { margin-bottom: 16px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
.data-table th { background: #f5f5f5; }
.empty { padding: 20px; text-align: center; color: #666; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal { background: white; padding: 24px; border-radius: 8px; width: 90%; max-width: 400px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 500; }
.form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #0066cc; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary { background: #666; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-small { padding: 4px 8px; margin-right: 4px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer; }
.btn-danger { color: #cc0000; }
</style>
