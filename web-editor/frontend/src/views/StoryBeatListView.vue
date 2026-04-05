<template>
  <div class="story-beat-list">
    <h2>剧情节拍</h2>
    <div class="actions">
      <button @click="showCreateModal = true" class="btn-primary">新建节拍</button>
    </div>

    <table v-if="beats.length > 0" class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>章节</th>
          <th>索引</th>
          <th>类型</th>
          <th>标题</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="beat in beats" :key="beat.id">
          <td>{{ beat.id }}</td>
          <td>{{ beat.chapter_id }}</td>
          <td>{{ beat.beat_index }}</td>
          <td>{{ beat.beat_type }}</td>
          <td>{{ beat.title }}</td>
          <td>
            <button @click="editBeat(beat)" class="btn-small">编辑</button>
            <button @click="deleteBeat(beat.id)" class="btn-small btn-danger">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无剧情节拍</div>

    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ showEditModal ? '编辑节拍' : '新建节拍' }}</h3>
        <form @submit.prevent="saveBeat">
          <div class="form-row">
            <div class="form-group">
              <label>章节ID</label>
              <input v-model.number="form.chapter_id" type="number" required />
            </div>
            <div class="form-group">
              <label>节拍索引</label>
              <input v-model.number="form.beat_index" type="number" required />
            </div>
          </div>
          <div class="form-group">
            <label>类型</label>
            <select v-model="form.beat_type">
              <option value="dialogue">对话</option>
              <option value="battle">战斗</option>
              <option value="cutscene">过场</option>
              <option value="choice">选择</option>
            </select>
          </div>
          <div class="form-group">
            <label>标题</label>
            <input v-model="form.title" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="form.description" rows="3"></textarea>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>触发类型</label>
              <input v-model="form.trigger_type" />
            </div>
            <div class="form-group">
              <label>触发参数</label>
              <input v-model="form.trigger_param" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>对话Key</label>
              <input v-model="form.dialogue_key" />
            </div>
            <div class="form-group">
              <label>战斗配置ID</label>
              <input v-model.number="form.battle_config_id" type="number" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>地图ID</label>
              <input v-model="form.map_id" />
            </div>
            <div class="form-group">
              <label>X</label>
              <input v-model.number="form.position_x" type="number" />
            </div>
            <div class="form-group">
              <label>Y</label>
              <input v-model.number="form.position_y" type="number" />
            </div>
          </div>
          <div class="form-group">
            <label>下一节拍ID</label>
            <input v-model.number="form.next_beat_id" type="number" />
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
import { useStoryBeatStore } from '../stores/storyBeatStore'

const store = useStoryBeatStore()

const beats = ref<any[]>([])
const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingId = ref<number | null>(null)

const form = ref({
  chapter_id: 1,
  beat_index: 0,
  beat_type: 'dialogue',
  title: '',
  description: '',
  trigger_type: '',
  trigger_param: '',
  dialogue_key: '',
  battle_config_id: null as number | null,
  map_id: '',
  position_x: null as number | null,
  position_y: null as number | null,
  next_beat_id: null as number | null
})

onMounted(async () => {
  await store.fetchStoryBeats()
  beats.value = store.storyBeats
})

function editBeat(beat: any) {
  editingId.value = beat.id
  form.value = { ...beat }
  showEditModal.value = true
}

async function saveBeat() {
  try {
    if (showEditModal.value && editingId.value) {
      await store.updateStoryBeat(editingId.value, form.value)
    } else {
      await store.createStoryBeat(form.value)
    }
    await store.fetchStoryBeats()
    beats.value = store.storyBeats
    closeModal()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteBeat(id: number) {
  if (!confirm('确认删除?')) return
  try {
    await store.deleteStoryBeat(id)
    await store.fetchStoryBeats()
    beats.value = store.storyBeats
  } catch (e: any) {
    alert(e.message)
  }
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingId.value = null
  form.value = {
    chapter_id: 1,
    beat_index: 0,
    beat_type: 'dialogue',
    title: '',
    description: '',
    trigger_type: '',
    trigger_param: '',
    dialogue_key: '',
    battle_config_id: null,
    map_id: '',
    position_x: null,
    position_y: null,
    next_beat_id: null
  }
}
</script>

<style scoped>
.story-beat-list { padding: 20px; }
.actions { margin-bottom: 16px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
.data-table th { background: #f5f5f5; }
.empty { padding: 20px; text-align: center; color: #666; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal { background: white; padding: 24px; border-radius: 8px; width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 500; }
.form-group input, .form-group textarea, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
.form-row { display: flex; gap: 16px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #0066cc; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary { background: #666; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-small { padding: 4px 8px; margin-right: 4px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer; }
.btn-danger { color: #cc0000; }
</style>
