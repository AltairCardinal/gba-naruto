<template>
  <div class="build-view">
    <div class="build-header">
      <h2>构建流水线</h2>
      <div class="status-badge" :class="store.buildStatus.status">
        {{ statusText }}
      </div>
    </div>
    
    <div class="build-controls">
      <button 
        @click="triggerBuild" 
        :disabled="store.buildStatus.status === 'running'"
      >
        触发构建
      </button>
      <button 
        @click="store.downloadRom" 
        :disabled="store.buildStatus.status !== 'done'"
      >
        下载 ROM
      </button>
      <button @click="store.clearLogs">清除日志</button>
    </div>
    
    <div class="terminal" ref="terminalRef">
      <div v-if="store.buildStatus.logs.length === 0" class="terminal-empty">
        等待构建...
      </div>
      <div v-else v-for="(log, index) in store.buildStatus.logs" :key="index" class="log-line">
        {{ log }}
      </div>
    </div>
    
    <div v-if="store.buildStatus.progress > 0" class="progress-bar">
      <div class="progress-fill" :style="{ width: store.buildStatus.progress + '%' }"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, nextTick } from 'vue'
import { useBuildStore } from '../stores/buildStore'

const store = useBuildStore()
const terminalRef = ref<HTMLElement | null>(null)

const statusText = computed(() => {
  const statusMap: Record<string, string> = {
    idle: '空闲',
    running: '构建中',
    done: '完成',
    error: '错误'
  }
  return statusMap[store.buildStatus.status] || '未知'
})

async function triggerBuild() {
  try {
    await store.triggerBuild()
  } catch (e: any) {
    alert(e.message)
  }
}

function scrollToBottom() {
  if (terminalRef.value) {
    terminalRef.value.scrollTop = terminalRef.value.scrollHeight
  }
}

onMounted(() => {
  store.connectBuildWs()
  store.fetchBuildStatus()
})

onUnmounted(() => {
  if (store.wsConnection) {
    store.wsConnection.close()
  }
})
</script>

<style scoped>
.build-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.build-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.build-header h2 {
  font-size: 20px;
  color: #333;
}

.status-badge {
  padding: 6px 16px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
}

.status-badge.idle {
  background: #e0e0e0;
  color: #666;
}

.status-badge.running {
  background: #fff3cd;
  color: #856404;
}

.status-badge.done {
  background: #d4edda;
  color: #155724;
}

.status-badge.error {
  background: #f8d7da;
  color: #721c24;
}

.build-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.build-controls button {
  padding: 10px 20px;
  background: #0066cc;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.build-controls button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.build-controls button:hover:not(:disabled) {
  background: #0052a3;
}

.terminal {
  background: #1a1a1a;
  color: #00ff00;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  padding: 15px;
  border-radius: 4px;
  height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.terminal-empty {
  color: #666;
}

.log-line {
  line-height: 1.6;
}

.progress-bar {
  margin-top: 15px;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #0066cc;
  transition: width 0.3s ease;
}
</style>