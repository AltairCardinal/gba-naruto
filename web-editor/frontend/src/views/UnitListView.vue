<template>
  <div class="unit-list">
    <h2>单位配置</h2>
    <div class="actions">
      <button @click="showCreateModal = true" class="btn-primary">新建单位</button>
    </div>

    <table v-if="units.length > 0" class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Char ID</th>
          <th>名称</th>
          <th>HP</th>
          <th>攻击</th>
          <th>防御</th>
          <th>速度</th>
          <th>队伍</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="unit in units" :key="unit.id">
          <td>{{ unit.id }}</td>
          <td>{{ unit.char_id }}</td>
          <td>{{ unit.name }}</td>
          <td>{{ unit.hp }}</td>
          <td>{{ unit.attack }}</td>
          <td>{{ unit.defense }}</td>
          <td>{{ unit.speed }}</td>
          <td>{{ unit.team }}</td>
          <td>
            <button @click="editUnit(unit)" class="btn-small">编辑</button>
            <button @click="deleteUnit(unit.id)" class="btn-small btn-danger">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无单位</div>

    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ showEditModal ? '编辑单位' : '新建单位' }}</h3>
        <form @submit.prevent="saveUnit">
          <div class="form-row">
            <div class="form-group">
              <label>Char ID</label>
              <input v-model.number="form.char_id" type="number" required />
            </div>
            <div class="form-group">
              <label>名称</label>
              <input v-model="form.name" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>HP</label>
              <input v-model.number="form.hp" type="number" />
            </div>
            <div class="form-group">
              <label>攻击</label>
              <input v-model.number="form.attack" type="number" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>防御</label>
              <input v-model.number="form.defense" type="number" />
            </div>
            <div class="form-group">
              <label>速度</label>
              <input v-model.number="form.speed" type="number" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>队伍 (0=我方, 1=敌方)</label>
              <input v-model.number="form.team" type="number" />
            </div>
            <div class="form-group">
              <label>章节ID</label>
              <input v-model.number="form.chapter_id" type="number" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>地图ID</label>
              <input v-model="form.map_id" />
            </div>
            <div class="form-group">
              <label>X 坐标</label>
              <input v-model.number="form.position_x" type="number" />
            </div>
            <div class="form-group">
              <label>Y 坐标</label>
              <input v-model.number="form.position_y" type="number" />
            </div>
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
import { useUnitStore } from '../stores/unitStore'

const store = useUnitStore()

const units = ref<any[]>([])
const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingId = ref<number | null>(null)

const form = ref({
  char_id: 0,
  name: '',
  hp: 100,
  attack: 10,
  defense: 5,
  speed: 5,
  team: 0,
  chapter_id: null as number | null,
  map_id: '',
  position_x: null as number | null,
  position_y: null as number | null
})

onMounted(async () => {
  await store.fetchUnits()
  units.value = store.units
})

function editUnit(unit: any) {
  editingId.value = unit.id
  form.value = {
    char_id: unit.char_id,
    name: unit.name,
    hp: unit.hp,
    attack: unit.attack,
    defense: unit.defense,
    speed: unit.speed,
    team: unit.team,
    chapter_id: unit.chapter_id,
    map_id: unit.map_id || '',
    position_x: unit.position_x,
    position_y: unit.position_y
  }
  showEditModal.value = true
}

async function saveUnit() {
  try {
    if (showEditModal.value && editingId.value) {
      await store.updateUnit(editingId.value, form.value)
    } else {
      await store.createUnit(form.value)
    }
    await store.fetchUnits()
    units.value = store.units
    closeModal()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteUnit(id: number) {
  if (!confirm('确认删除?')) return
  try {
    await store.deleteUnit(id)
    await store.fetchUnits()
    units.value = store.units
  } catch (e: any) {
    alert(e.message)
  }
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingId.value = null
  form.value = {
    char_id: 0,
    name: '',
    hp: 100,
    attack: 10,
    defense: 5,
    speed: 5,
    team: 0,
    chapter_id: null,
    map_id: '',
    position_x: null,
    position_y: null
  }
}
</script>

<style scoped>
.unit-list { padding: 20px; }
.actions { margin-bottom: 16px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
.data-table th { background: #f5f5f5; }
.empty { padding: 20px; text-align: center; color: #666; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal { background: white; padding: 24px; border-radius: 8px; width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto; }
.form-group { margin-bottom: 16px; flex: 1; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 500; }
.form-group input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
.form-row { display: flex; gap: 16px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #0066cc; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary { background: #666; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-small { padding: 4px 8px; margin-right: 4px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer; }
.btn-danger { color: #cc0000; }
</style>
