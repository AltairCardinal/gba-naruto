<template>
  <div class="unit-placement-editor">
    <div class="editor-header">
      <h2>角色放置编辑器</h2>
      <select v-model="selectedMapId" @change="loadMapAndUnits" class="map-select">
        <option v-for="map in maps" :key="map.id" :value="map.id">{{ map.name }} ({{ map.dimensions }})</option>
      </select>
    </div>
    
    <div class="editor-main">
      <div class="canvas-container">
        <canvas 
          ref="canvasRef" 
          :width="32 * TILE_SIZE" 
          :height="32 * TILE_SIZE"
          @click="handleCanvasClick"
          @contextmenu.prevent="handleRightClick"
        ></canvas>
        <div class="status-bar">
          坐标: ({{ hoverPos.x }}, {{ hoverPos.y }}) |
          模式: {{ dragMode ? '拖拽放置' : '点击放置' }}
        </div>
      </div>
      
      <div class="units-panel">
        <h3>单位列表</h3>
        <div class="unit-tabs">
          <button 
            :class="{ active: showTeam === 0 }" 
            @click="showTeam = 0"
          >我方单位</button>
          <button 
            :class="{ active: showTeam === 1 }" 
            @click="showTeam = 1"
          >敌方单位</button>
        </div>
        
        <div class="unit-list">
          <div 
            v-for="unit in filteredUnits" 
            :key="unit.id"
            class="unit-item"
            :class="{ selected: selectedUnit?.id === unit.id, [`team-${unit.team}`]: true }"
            @click="selectUnit(unit)"
          >
            <span class="unit-name">{{ unit.name }}</span>
            <span class="unit-pos">({{ unit.position_x }}, {{ unit.position_y }})</span>
          </div>
        </div>
        
        <div class="unit-form" v-if="selectedUnit">
          <h4>编辑单位</h4>
          <div class="form-group">
            <label>名称</label>
            <input v-model="editingUnit.name" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>X</label>
              <input v-model.number="editingUnit.position_x" type="number" min="0" max="31" />
            </div>
            <div class="form-group">
              <label>Y</label>
              <input v-model.number="editingUnit.position_y" type="number" min="0" max="31" />
            </div>
          </div>
          <div class="form-actions">
            <button @click="saveUnit" class="btn-primary">保存</button>
            <button @click="deleteUnit" class="btn-danger">删除</button>
          </div>
        </div>
        
        <div class="create-form">
          <h4>新建单位</h4>
          <div class="form-group">
            <label>名称</label>
            <input v-model="newUnit.name" placeholder="单位名称" />
          </div>
          <div class="form-group">
            <label>选择队伍</label>
            <select v-model.number="newUnit.team">
              <option :value="0">我方</option>
              <option :value="1">敌方</option>
            </select>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>X</label>
              <input v-model.number="newUnit.position_x" type="number" min="0" max="31" />
            </div>
            <div class="form-group">
              <label>Y</label>
              <input v-model.number="newUnit.position_y" type="number" min="0" max="31" />
            </div>
          </div>
          <button @click="createUnit" class="btn-primary">添加单位</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'

interface TileData {
  tile_id: number
  hflip: boolean
  vflip: boolean
  palette_bank: number
}

interface Unit {
  id: number
  char_id: number
  name: string
  name_ja?: string
  name_zh?: string
  hp: number
  attack: number
  defense: number
  speed: number
  chapter_id?: number
  map_id?: string
  position_x: number
  position_y: number
  team: number
}

interface MapInfo {
  id: string
  name: string
  address: string
  dimensions: string
}

const TILE_SIZE = 16

const maps = ref<MapInfo[]>([])
const selectedMapId = ref('map_1')
const units = ref<Unit[]>([])
const showTeam = ref(0)
const selectedUnit = ref<Unit | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const hoverPos = ref({ x: -1, y: -1 })
const dragMode = ref(false)

const newUnit = ref({
  name: '',
  team: 0,
  position_x: 0,
  position_y: 0
})

const editingUnit = ref({
  name: '',
  position_x: 0,
  position_y: 0
})

const filteredUnits = computed(() => {
  return units.value.filter(u => u.team === showTeam.value)
})

async function fetchMaps() {
  const res = await fetch('/api/maps')
  maps.value = await res.json()
}

async function fetchUnits() {
  const res = await fetch(`/api/units?map_id=${selectedMapId.value}`)
  units.value = await res.json()
}

async function loadMapAndUnits() {
  await fetchUnits()
  renderCanvas()
}

function renderCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  
  ctx.fillStyle = '#222'
  ctx.fillRect(0, 0, 32 * TILE_SIZE, 32 * TILE_SIZE)
  
  for (let y = 0; y < 32; y++) {
    for (let x = 0; x < 32; x++) {
      ctx.fillStyle = '#334'
      ctx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE - 1, TILE_SIZE - 1)
    }
  }
  
  units.value.forEach(unit => {
    const color = unit.team === 0 ? '#4a9' : '#d44'
    ctx.fillStyle = color
    ctx.fillRect(unit.position_x * TILE_SIZE, unit.position_y * TILE_SIZE, TILE_SIZE - 1, TILE_SIZE - 1)
    
    ctx.fillStyle = '#fff'
    ctx.font = '8px sans-serif'
    ctx.fillText(String(unit.name.charAt(0)), unit.position_x * TILE_SIZE + 4, unit.position_y * TILE_SIZE + 11)
  })
  
  if (hoverPos.value.x >= 0 && hoverPos.value.y >= 0) {
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.strokeRect(hoverPos.value.x * TILE_SIZE, hoverPos.value.y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
  }
}

function handleCanvasClick(e: MouseEvent) {
  const canvas = canvasRef.value
  if (!canvas) return
  
  const rect = canvas.getBoundingClientRect()
  const x = Math.floor((e.clientX - rect.left) / TILE_SIZE)
  const y = Math.floor((e.clientY - rect.top) / TILE_SIZE)
  
  if (x < 0 || x >= 32 || y < 0 || y >= 32) return
  
  if (selectedUnit.value) {
    selectedUnit.value.position_x = x
    selectedUnit.value.position_y = y
    editingUnit.value.position_x = x
    editingUnit.value.position_y = y
    renderCanvas()
  }
}

function handleRightClick(e: MouseEvent) {
  const canvas = canvasRef.value
  if (!canvas) return
  
  const rect = canvas.getBoundingClientRect()
  const x = Math.floor((e.clientX - rect.left) / TILE_SIZE)
  const y = Math.floor((e.clientY - rect.top) / TILE_SIZE)
  
  if (x < 0 || x >= 32 || y < 0 || y >= 32) return
  
  const unit = units.value.find(u => u.position_x === x && u.position_y === y)
  if (unit) {
    selectUnit(unit)
  }
}

function handleMouseMove(e: MouseEvent) {
  const canvas = canvasRef.value
  if (!canvas) return
  
  const rect = canvas.getBoundingClientRect()
  const x = Math.floor((e.clientX - rect.left) / TILE_SIZE)
  const y = Math.floor((e.clientY - rect.top) / TILE_SIZE)
  
  if (x >= 0 && x < 32 && y >= 0 && y < 32) {
    hoverPos.value = { x, y }
  } else {
    hoverPos.value = { x: -1, y: -1 }
  }
  renderCanvas()
}

function selectUnit(unit: Unit) {
  selectedUnit.value = unit
  editingUnit.value = {
    name: unit.name,
    position_x: unit.position_x,
    position_y: unit.position_y
  }
}

async function saveUnit() {
  if (!selectedUnit.value) return
  
  await fetch(`/api/units/${selectedUnit.value.id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: editingUnit.value.name,
      position_x: editingUnit.value.position_x,
      position_y: editingUnit.value.position_y
    })
  })
  
  selectedUnit.value.name = editingUnit.value.name
  selectedUnit.value.position_x = editingUnit.value.position_x
  selectedUnit.value.position_y = editingUnit.value.position_y
  
  renderCanvas()
}

async function deleteUnit() {
  if (!selectedUnit.value) return
  if (!confirm('确认删除?')) return
  
  await fetch(`/api/units/${selectedUnit.value.id}`, {
    method: 'DELETE'
  })
  
  selectedUnit.value = null
  await fetchUnits()
  renderCanvas()
}

async function createUnit() {
  if (!newUnit.value.name) {
    alert('请输入单位名称')
    return
  }
  
  await fetch('/api/units', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: newUnit.value.name,
      char_id: Math.floor(Math.random() * 100),
      team: newUnit.value.team,
      map_id: selectedMapId.value,
      position_x: newUnit.value.position_x,
      position_y: newUnit.value.position_y,
      hp: 100,
      attack: 10,
      defense: 5,
      speed: 5
    })
  })
  
  newUnit.value.name = ''
  await fetchUnits()
  renderCanvas()
}

onMounted(async () => {
  await fetchMaps()
  await loadMapAndUnits()
  
  if (canvasRef.value) {
    canvasRef.value.addEventListener('mousemove', handleMouseMove)
  }
})
</script>

<style scoped>
.unit-placement-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.editor-header h2 {
  font-size: 20px;
  color: #333;
}

.map-select {
  padding: 8px 12px;
  font-size: 14px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.editor-main {
  display: flex;
  gap: 20px;
  flex: 1;
}

.canvas-container {
  display: flex;
  flex-direction: column;
}

canvas {
  border: 2px solid #333;
  cursor: crosshair;
}

.status-bar {
  margin-top: 10px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 13px;
  color: #666;
}

.units-panel {
  width: 320px;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 8px;
}

.units-panel h3 {
  font-size: 16px;
  margin-bottom: 15px;
  color: #333;
}

.unit-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.unit-tabs button {
  flex: 1;
  padding: 8px;
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
}

.unit-tabs button.active {
  background: #0066cc;
  color: #fff;
  border-color: #0066cc;
}

.unit-list {
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: 15px;
}

.unit-item {
  padding: 8px 12px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-bottom: 4px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
}

.unit-item:hover {
  background: #f0f0f0;
}

.unit-item.selected {
  border-color: #0066cc;
  background: #e6f0ff;
}

.unit-item.team-0 {
  border-left: 3px solid #4a9;
}

.unit-item.team-1 {
  border-left: 3px solid #d44;
}

.unit-name {
  font-weight: 500;
}

.unit-pos {
  font-size: 12px;
  color: #666;
}

.unit-form, .create-form {
  padding: 12px;
  background: #fff;
  border-radius: 4px;
  margin-bottom: 12px;
}

.unit-form h4, .create-form h4 {
  font-size: 14px;
  margin-bottom: 10px;
  color: #333;
}

.form-group {
  margin-bottom: 10px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: #666;
}

.form-group input, .form-group select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
}

.form-row {
  display: flex;
  gap: 10px;
}

.form-row .form-group {
  flex: 1;
}

.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.btn-primary {
  padding: 8px 16px;
  background: #0066cc;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-danger {
  padding: 8px 16px;
  background: #cc0000;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
</style>
