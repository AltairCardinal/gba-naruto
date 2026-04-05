<template>
  <div class="battle-config-editor">
    <h2>战斗配置编辑器</h2>
    
    <div class="actions">
      <button @click="showCreateModal = true" class="btn-primary">新建配置</button>
    </div>

    <table v-if="configs.length > 0" class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>名称</th>
          <th>章节</th>
          <th>场景</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="config in configs" :key="config.id">
          <td>{{ config.id }}</td>
          <td>{{ config.name }}</td>
          <td>{{ config.chapter_id }}</td>
          <td>{{ config.scenario_id }}</td>
          <td>
            <button @click="editConfig(config)" class="btn-small">编辑</button>
            <button @click="deleteConfig(config.id)" class="btn-small btn-danger">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无战斗配置</div>

    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ showEditModal ? '编辑配置' : '新建配置' }}</h3>
        <form @submit.prevent="saveConfig">
          <div class="form-group">
            <label>名称</label>
            <input v-model="form.name" required />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>章节ID</label>
              <input v-model.number="form.chapter_id" type="number" />
            </div>
            <div class="form-group">
              <label>场景ID</label>
              <input v-model.number="form.scenario_id" type="number" />
            </div>
          </div>
          <div class="form-group">
            <label>回合限制</label>
            <input v-model.number="form.turn_limit" type="number" />
          </div>
          <div class="form-group">
            <label>胜利条件</label>
            <input v-model="form.win_condition" />
          </div>
          <div class="form-group">
            <label>失败条件</label>
            <input v-model="form.lose_condition" />
          </div>
          <div class="form-group">
            <label>我方单位 (JSON)</label>
            <textarea v-model="playerUnitsJson" rows="4"></textarea>
          </div>
          <div class="form-group">
            <label>敌方单位 (JSON)</label>
            <textarea v-model="enemyUnitsJson" rows="4"></textarea>
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
import { useBattleConfigStore } from '../stores/battleConfigStore'

const store = useBattleConfigStore()

const configs = ref<any[]>([])
const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingId = ref<number | null>(null)

const form = ref({
  name: '',
  chapter_id: null as number | null,
  scenario_id: null as number | null,
  turn_limit: null as number | null,
  win_condition: '',
  lose_condition: ''
})

const playerUnitsJson = ref('[]')
const enemyUnitsJson = ref('[]')

onMounted(async () => {
  await store.fetchConfigs()
  configs.value = store.configs
})

function editConfig(config: any) {
  editingId.value = config.id
  form.value = {
    name: config.name,
    chapter_id: config.chapter_id,
    scenario_id: config.scenario_id,
    turn_limit: config.turn_limit,
    win_condition: config.win_condition || '',
    lose_condition: config.lose_condition || ''
  }
  playerUnitsJson.value = JSON.stringify(config.player_units || [], null, 2)
  enemyUnitsJson.value = JSON.stringify(config.enemy_units || [], null, 2)
  showEditModal.value = true
}

async function saveConfig() {
  try {
    const data: any = { ...form.value }
    data.player_units = JSON.parse(playerUnitsJson.value || '[]')
    data.enemy_units = JSON.parse(enemyUnitsJson.value || '[]')
    
    if (showEditModal.value && editingId.value) {
      await store.updateConfig(editingId.value, data)
    } else {
      await store.createConfig(data)
    }
    await store.fetchConfigs()
    configs.value = store.configs
    closeModal()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteConfig(id: number) {
  if (!confirm('确认删除?')) return
  try {
    await store.deleteConfig(id)
    await store.fetchConfigs()
    configs.value = store.configs
  } catch (e: any) {
    alert(e.message)
  }
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingId.value = null
  form.value = {
    name: '',
    chapter_id: null,
    scenario_id: null,
    turn_limit: null,
    win_condition: '',
    lose_condition: ''
  }
  playerUnitsJson.value = '[]'
  enemyUnitsJson.value = '[]'
}
</script>

<style scoped>
.battle-config-editor {
  padding: 20px;
}

.actions {
  margin-bottom: 16px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th, .data-table td {
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
}

.data-table th {
  background: #f5f5f5;
}

.empty {
  padding: 20px;
  text-align: center;
  color: #666;
}

.modal-overlay {
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

.modal {
  background: white;
  padding: 24px;
  border-radius: 8px;
  width: 90%;
  max-width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-weight: 500;
}

.form-group input, .form-group textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row .form-group {
  flex: 1;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 16px;
}

.btn-primary {
  background: #0066cc;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
}

.btn-secondary {
  background: #666;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
}

.btn-small {
  padding: 4px 8px;
  margin-right: 4px;
  border: 1px solid #ddd;
  background: #f5f5f5;
  border-radius: 4px;
  cursor: pointer;
}

.btn-danger {
  color: #cc0000;
}
</style>
