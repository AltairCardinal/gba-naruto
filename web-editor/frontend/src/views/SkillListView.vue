<template>
  <div class="skill-list">
    <h2>技能配置</h2>
    <div class="actions">
      <button @click="showCreateModal = true" class="btn-primary">新建技能</button>
    </div>

    <table v-if="skills.length > 0" class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>单位ID</th>
          <th>名称</th>
          <th>伤害</th>
          <th>回复</th>
          <th>范围</th>
          <th>消耗</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="skill in skills" :key="skill.id">
          <td>{{ skill.id }}</td>
          <td>{{ skill.unit_id }}</td>
          <td>{{ skill.name }}</td>
          <td>{{ skill.damage }}</td>
          <td>{{ skill.heal }}</td>
          <td>{{ skill.range_min }}-{{ skill.range_max }}</td>
          <td>HP:{{ skill.cost_hp }} CK:{{ skill.cost_chakra }}</td>
          <td>
            <button @click="editSkill(skill)" class="btn-small">编辑</button>
            <button @click="deleteSkill(skill.id)" class="btn-small btn-danger">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">暂无技能</div>

    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ showEditModal ? '编辑技能' : '新建技能' }}</h3>
        <form @submit.prevent="saveSkill">
          <div class="form-row">
            <div class="form-group">
              <label>单位ID</label>
              <input v-model.number="form.unit_id" type="number" required />
            </div>
            <div class="form-group">
              <label>名称</label>
              <input v-model="form.name" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>伤害</label>
              <input v-model.number="form.damage" type="number" />
            </div>
            <div class="form-group">
              <label>回复</label>
              <input v-model.number="form.heal" type="number" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>最小范围</label>
              <input v-model.number="form.range_min" type="number" />
            </div>
            <div class="form-group">
              <label>最大范围</label>
              <input v-model.number="form.range_max" type="number" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>HP消耗</label>
              <input v-model.number="form.cost_hp" type="number" />
            </div>
            <div class="form-group">
              <label>查克拉消耗</label>
              <input v-model.number="form.cost_chakra" type="number" />
            </div>
          </div>
          <div class="form-group">
            <label>效果类型</label>
            <input v-model="form.effect_type" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="form.description" rows="3"></textarea>
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
import { useSkillStore } from '../stores/skillStore'

const store = useSkillStore()

const skills = ref<any[]>([])
const showCreateModal = ref(false)
const showEditModal = ref(false)
const editingId = ref<number | null>(null)

const form = ref({
  unit_id: 0,
  name: '',
  damage: 0,
  heal: 0,
  range_min: 1,
  range_max: 1,
  cost_hp: 0,
  cost_chakra: 0,
  effect_type: '',
  description: ''
})

onMounted(async () => {
  await store.fetchSkills()
  skills.value = store.skills
})

function editSkill(skill: any) {
  editingId.value = skill.id
  form.value = { ...skill }
  showEditModal.value = true
}

async function saveSkill() {
  try {
    if (showEditModal.value && editingId.value) {
      await store.updateSkill(editingId.value, form.value)
    } else {
      await store.createSkill(form.value)
    }
    await store.fetchSkills()
    skills.value = store.skills
    closeModal()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteSkill(id: number) {
  if (!confirm('确认删除?')) return
  try {
    await store.deleteSkill(id)
    await store.fetchSkills()
    skills.value = store.skills
  } catch (e: any) {
    alert(e.message)
  }
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingId.value = null
  form.value = { unit_id: 0, name: '', damage: 0, heal: 0, range_min: 1, range_max: 1, cost_hp: 0, cost_chakra: 0, effect_type: '', description: '' }
}
</script>

<style scoped>
.skill-list { padding: 20px; }
.actions { margin-bottom: 16px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
.data-table th { background: #f5f5f5; }
.empty { padding: 20px; text-align: center; color: #666; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
.modal { background: white; padding: 24px; border-radius: 8px; width: 90%; max-width: 500px; max-height: 80vh; overflow-y: auto; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 500; }
.form-group input, .form-group textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
.form-row { display: flex; gap: 16px; }
.form-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 16px; }
.btn-primary { background: #0066cc; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-secondary { background: #666; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
.btn-small { padding: 4px 8px; margin-right: 4px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer; }
.btn-danger { color: #cc0000; }
</style>
