<template>
  <div class="audio-view">
    <h2>音频管理</h2>
    <div class="actions">
      <button @click="showCreateModal = true" class="btn-primary">新建音频</button>
    </div>

    <table v-if="audioFiles.length > 0" class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>类型</th>
          <th>ROM偏移</th>
          <th>大小</th>
          <th>时长(秒)</th>
          <th>格式</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="audio in audioFiles" :key="audio.id">
          <td>{{ audio.id }}</td>
          <td>{{ audio.name }}</td>
          <td>{{ audio.type }}</td>
          <td>{{ audio.rom_offset ? '0x' + audio.rom_offset.toString(16).toUpperCase() : '-' }}</td>
          <td>{{ audio.size }}</td>
          <td>{{ audio.duration_seconds }}</td>
          <td>{{ audio.format }}</td>
          <td>
            <button v-if="audio.rom_offset" @click="previewAudio(audio.id)" class="btn-small">预览</button>
            <button @click="editAudio(audio)" class="btn-small">编辑</button>
            <button @click="deleteAudio(audio.id)" class="btn-small btn-danger">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无音频文件</div>

    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ showEditModal ? '编辑音频' : '新建音频' }}</h3>
        <form @submit.prevent="saveAudio">
          <div class="form-group">
            <label>名称</label>
            <input v-model="form.name" required />
          </div>
          <div class="form-group">
            <label>类型</label>
            <select v-model="form.type" required>
              <option value="bgm">背景音乐</option>
              <option value="se">音效</option>
              <option value="voice">语音</option>
              <option value="ambient">环境音</option>
            </select>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>ROM偏移 (十进制)</label>
              <input v-model.number="form.rom_offset" type="number" />
            </div>
            <div class="form-group">
              <label>大小 (字节)</label>
              <input v-model.number="form.size" type="number" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>时长 (秒)</label>
              <input v-model.number="form.duration_seconds" type="number" step="0.1" />
            </div>
            <div class="form-group">
              <label>格式</label>
              <select v-model="form.format">
                <option value="pcm8">PCM 8-bit</option>
                <option value="pcm16">PCM 16-bit</option>
              </select>
            </div>
          </div>
          <div class="form-actions">
            <button type="button" @click="closeModal" class="btn-secondary">取消</button>
            <button type="submit" class="btn-primary">保存</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showPreview" class="modal-overlay" @click.self="showPreview = false">
      <div class="modal">
        <h3>音频预览</h3>
        <audio ref="audioPlayer" controls style="width: 100%;"></audio>
        <div class="form-actions">
          <button @click="showPreview = false" class="btn-secondary">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { getErrorMessage } from '../utils/error'

interface AudioFile {
  id: number
  name: string
  type: string
  rom_offset: number | null
  size: number | null
  duration_seconds: number | null
  format: string | null
}

const audioFiles = ref<AudioFile[]>([])
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showPreview = ref(false)
const editingId = ref<number | null>(null)
const audioPlayer = ref<HTMLAudioElement | null>(null)

const form = ref({
  name: '',
  type: 'bgm',
  rom_offset: null as number | null,
  size: null as number | null,
  duration_seconds: null as number | null,
  format: 'pcm8'
})

onMounted(async () => {
  await fetchAudioFiles()
})

async function fetchAudioFiles() {
  const res = await fetch('/api/audio')
  audioFiles.value = await res.json()
}

function editAudio(audio: AudioFile) {
  editingId.value = audio.id
  form.value = {
    name: audio.name,
    type: audio.type,
    rom_offset: audio.rom_offset,
    size: audio.size,
    duration_seconds: audio.duration_seconds,
    format: audio.format || 'pcm8'
  }
  showEditModal.value = true
}

async function saveAudio() {
  try {
    const method = showEditModal.value ? 'PUT' : 'POST'
    const url = showEditModal.value && editingId.value ? `/api/audio/${editingId.value}` : '/api/audio'
    
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })
    
    if (!res.ok) throw new Error('Failed to save')
    
    await fetchAudioFiles()
    closeModal()
  } catch (e) {
    alert(getErrorMessage(e))
  }
}

async function deleteAudio(id: number) {
  if (!confirm('确认删除?')) return
  await fetch(`/api/audio/${id}`, { method: 'DELETE' })
  await fetchAudioFiles()
}

async function previewAudio(id: number) {
  try {
    const res = await fetch(`/api/audio/preview/${id}`)
    if (!res.ok) throw new Error('Failed to load audio')
    
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    
    showPreview.value = true
    await nextTick()
    
    if (audioPlayer.value) {
      audioPlayer.value.src = url
      audioPlayer.value.play()
    }
  } catch (e) {
    alert(getErrorMessage(e))
  }
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingId.value = null
  form.value = { name: '', type: 'bgm', rom_offset: null, size: null, duration_seconds: null, format: 'pcm8' }
}
</script>

<style scoped>
.audio-view { padding: 20px; }
.actions { margin-bottom: 16px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
.data-table th { background: #f5f5f5; }
.empty { padding: 20px; text-align: center; color: #666; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal { background: white; padding: 24px; border-radius: 8px; width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 500; }
.form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
.form-row { display: flex; gap: 16px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #0066cc; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary { background: #666; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-small { padding: 4px 8px; margin-right: 4px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer; }
.btn-danger { color: #cc0000; }
</style>
