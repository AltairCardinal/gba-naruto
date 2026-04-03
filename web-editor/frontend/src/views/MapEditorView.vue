<template>
  <div class="map-editor">
    <div class="editor-header">
      <h2>地图编辑器</h2>
      <select v-model="selectedMapId" @change="loadMap" class="map-select">
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
          @mousemove="handleMouseMove"
        ></canvas>
        <div class="status-bar">
          坐标: ({{ hoverPos.x }}, {{ hoverPos.y }}) | 
          Tile ID: {{ currentTile?.tile_id ?? '-' }} |
          HFlip: {{ currentTile?.hflip ? '是' : '否' }} |
          VFlip: {{ currentTile?.vflip ? '是' : '否' }} |
          Palette: {{ currentTile?.palette_bank ?? 0 }}
        </div>
      </div>
      
      <div class="palette-panel">
        <h3>瓦片面板</h3>
        <div class="palette-grid">
          <div 
            v-for="id in 312" 
            :key="id-1"
            class="tile-cell"
            :class="{ selected: selectedTileId === id-1 }"
            @click="selectTile(id-1)"
          >
            {{ id-1 }}
          </div>
        </div>
        <div class="palette-info">
          <p>选中瓦片 ID: {{ selectedTileId }}</p>
        </div>
      </div>
    </div>
    
    <div class="editor-actions">
      <button @click="saveMap" :disabled="!hasChanges" class="save-btn">
        保存修改
      </button>
      <button @click="reloadMap" class="reload-btn">
        重新加载
      </button>
      <span v-if="saveStatus" class="save-status">{{ saveStatus }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'

interface TileData {
  tile_id: number
  hflip: boolean
  vflip: boolean
  palette_bank: number
}

interface MapInfo {
  id: string
  name: string
  address: string
  dimensions: string
  tile_grid?: TileData[][]
}

const TILE_SIZE = 16

const maps = ref<MapInfo[]>([])
const selectedMapId = ref('map_1')
const currentMap = ref<TileData[][]>([])
const originalMap = ref<TileData[][]>([])
const canvasRef = ref<HTMLCanvasElement | null>(null)
const selectedTileId = ref(0)
const hoverPos = ref({ x: -1, y: -1 })
const saveStatus = ref('')

const hasChanges = computed(() => {
  if (!currentMap.value.length) return false
  return JSON.stringify(currentMap.value) !== JSON.stringify(originalMap.value)
})

const currentTile = computed(() => {
  const { x, y } = hoverPos.value
  if (x < 0 || y < 0 || y >= 32 || x >= 32) return null
  return currentMap.value[y]?.[x]
})

async function fetchMaps() {
  const res = await fetch('/api/maps')
  maps.value = await res.json()
}

async function loadMap() {
  const res = await fetch(`/api/maps/${selectedMapId.value}`)
  const data = await res.json()
  currentMap.value = data.tile_grid as TileData[][]
  originalMap.value = JSON.parse(JSON.stringify(currentMap.value))
  renderCanvas()
  saveStatus.value = ''
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
      const tile = currentMap.value[y]?.[x]
      if (tile) {
        const hue = (tile.tile_id * 15) % 360
        const sat = 60
        const light = tile.hflip || tile.vflip ? 70 : 50
        ctx.fillStyle = `hsl(${hue}, ${sat}%, ${light}%)`
        ctx.fillRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE - 1, TILE_SIZE - 1)
        
        ctx.fillStyle = '#000'
        ctx.font = '8px sans-serif'
        ctx.fillText(String(tile.tile_id), x * TILE_SIZE + 2, y * TILE_SIZE + 10)
      }
    }
  }
  
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
  
  if (x >= 0 && x < 32 && y >= 0 && y < 32) {
    currentMap.value[y][x] = {
      tile_id: selectedTileId.value,
      hflip: false,
      vflip: false,
      palette_bank: 0
    }
    renderCanvas()
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

function selectTile(id: number) {
  selectedTileId.value = id
}

async function saveMap() {
  try {
    const res = await fetch(`/api/maps/${selectedMapId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tile_grid: currentMap.value })
    })
    const result = await res.json()
    if (result.success) {
      originalMap.value = JSON.parse(JSON.stringify(currentMap.value))
      saveStatus.value = '保存成功！'
      setTimeout(() => saveStatus.value = '', 3000)
    }
  } catch (e) {
    saveStatus.value = '保存失败'
  }
}

function reloadMap() {
  loadMap()
}

onMounted(async () => {
  await fetchMaps()
  await loadMap()
})
</script>

<style scoped>
.map-editor {
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

.palette-panel {
  width: 280px;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 8px;
}

.palette-panel h3 {
  font-size: 16px;
  margin-bottom: 15px;
  color: #333;
}

.palette-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.tile-cell {
  aspect-ratio: 1;
  background: #ddd;
  border: 1px solid #ccc;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.tile-cell:hover {
  background: #ccc;
}

.tile-cell.selected {
  border: 2px solid #0066cc;
  background: #e6f0ff;
}

.palette-info {
  margin-top: 15px;
  padding: 10px;
  background: #fff;
  border-radius: 4px;
}

.palette-info p {
  font-size: 14px;
  color: #333;
}

.editor-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  align-items: center;
}

.save-btn {
  padding: 10px 24px;
  background: #28a745;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.save-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.save-btn:hover:not(:disabled) {
  background: #218838;
}

.reload-btn {
  padding: 10px 24px;
  background: #6c757d;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.reload-btn:hover {
  background: #5a6268;
}

.save-status {
  color: #28a745;
  font-size: 14px;
}
</style>