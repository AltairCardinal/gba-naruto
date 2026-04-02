<template>
  <div class="dialogue-list">
    <div class="toolbar">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索 key/speaker/text..."
        @keyup.enter="search"
      />
      <button @click="search">搜索</button>
      <button @click="createNew">新建对话</button>
    </div>

    <div v-if="store.loading" class="loading">加载中...</div>
    <div v-else-if="store.error" class="error">{{ store.error }}</div>

    <table v-else>
      <thead>
        <tr>
          <th>Key</th>
          <th>Speaker</th>
          <th>日文</th>
          <th>中文</th>
          <th>字节</th>
          <th>章节</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="d in store.dialogues" :key="d.key">
          <td>{{ d.key }}</td>
          <td>{{ d.speaker || '-' }}</td>
          <td class="text-cell">{{ d.text_ja || '-' }}</td>
          <td class="text-cell">{{ d.text_zh || '-' }}</td>
          <td :class="{ 'over-limit': d.byte_count > d.max_bytes }">
            {{ d.byte_count }}/{{ d.max_bytes }}
          </td>
          <td>{{ d.chapter_id ?? '-' }}</td>
          <td>
            <button @click="edit(d.key)">编辑</button>
            <button @click="remove(d.key)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="showCreateModal" class="modal">
      <div class="modal-content">
        <h3>新建对话</h3>
        <label>Key: <input v-model="newDialogue.key" /></label>
        <label>Speaker: <input v-model="newDialogue.speaker" /></label>
        <label>章节ID: <input v-model.number="newDialogue.chapter_id" type="number" /></label>
        <div class="modal-actions">
          <button @click="submitCreate">创建</button>
          <button @click="showCreateModal = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDialogueStore } from '../stores/dialogueStore'

const router = useRouter()
const store = useDialogueStore()

const searchQuery = ref('')
const showCreateModal = ref(false)
const newDialogue = ref({ key: '', speaker: '', chapter_id: null as number | null })

onMounted(() => {
  store.fetchDialogues()
})

function search() {
  store.fetchDialogues(1, 20, searchQuery.value || undefined)
}

function edit(key: string) {
  router.push(`/dialogues/${key}`)
}

async function remove(key: string) {
  if (confirm(`确认删除 ${key}?`)) {
    await store.deleteDialogue(key)
    store.fetchDialogues()
  }
}

function createNew() {
  newDialogue.value = { key: '', speaker: '', chapter_id: null }
  showCreateModal.value = true
}

async function submitCreate() {
  try {
    await store.createDialogue(newDialogue.value)
    showCreateModal.value = false
    store.fetchDialogues()
  } catch (e: any) {
    alert(e.message)
  }
}
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.toolbar input {
  padding: 8px;
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.toolbar button {
  padding: 8px 16px;
  background: #0066cc;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.text-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.over-limit {
  color: red;
  font-weight: bold;
}

.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  width: 400px;
}

.modal-content label {
  display: block;
  margin-bottom: 10px;
}

.modal-content input {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.modal-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.modal-actions button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.loading, .error {
  padding: 20px;
  text-align: center;
}

.error {
  color: red;
}
</style>