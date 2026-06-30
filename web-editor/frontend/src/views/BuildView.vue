<template>
  <div class="build-view">
    <div class="build-header">
      <h2>构建流水线</h2>
      <div class="status-badge" :class="store.buildStatus.status">
        {{ statusText }}
      </div>
    </div>

    <div v-if="!auth.isLoggedIn" class="login-prompt">
      <p>请先<a href="#" @click.prevent="goLogin">登录</a>再使用构建功能。</p>
    </div>

    <div class="build-controls">
      <button
        v-if="auth.has('trigger_build')"
        @click="triggerBuild"
        :disabled="store.buildStatus.status === 'running'"
      >
        触发构建
      </button>
      <span v-else class="no-perm-hint">🔒 无构建权限，请联系管理员</span>
      <button
        @click="() => store.downloadRom()"
        :disabled="store.buildStatus.status !== 'done'"
      >
        下载 ROM
      </button>
      <button
        @click="store.openInEmulator"
        :disabled="!canOpenInEmulator"
        title="在模拟器中打开（多用户隔离：使用本 build 的 ROM）"
      >
        在模拟器中打开
      </button>
      <button @click="store.clearLogs">清除日志</button>
    </div>

    <div v-if="store.currentBuildId" class="build-id-line">
      build_id: <code>{{ store.currentBuildId }}</code>
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
import { useRouter } from 'vue-router'
import { useBuildStore } from '../stores/buildStore'
import { useAuthStore } from '../stores/authStore'

const store = useBuildStore()
const auth = useAuthStore()
const router = useRouter()

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

const canOpenInEmulator = computed(() => {
  return store.buildStatus.status === 'done' && !!store.currentBuildId
})

function goLogin() {
  router.push({ path: '/login', query: { redirect: '/build' } })
}

async function triggerBuild() {
  try {
    await store.triggerBuild()
    nextTick(scrollToBottom)
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
  // Only attempt to reconnect WS if we have a token. If /me fails the
  // route guard will already have bounced us to /login, but be defensive.
  if (auth.isLoggedIn) {
    store.connectBuildWs()
    store.fetchBuildStatus().catch(() => {})
  }
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
  margin-bottom: 12px;
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

.status-badge.idle { background: #e0e0e0; color: #666; }
.status-badge.running { background: #fff3cd; color: #856404; }
.status-badge.done { background: #d4edda; color: #155724; }
.status-badge.error { background: #f8d7da; color: #721c24; }

.login-prompt {
  background: #fff8e1;
  border: 1px solid #ffe0a3;
  padding: 10px 14px;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #6d4c00;
}
.login-prompt a { color: #0066cc; font-weight: 500; }

.no-perm-hint {
  display: inline-block;
  align-self: center;
  color: #b08500;
  font-size: 13px;
  padding: 6px 10px;
  background: #fff8e1;
  border-radius: 3px;
}

.build-controls {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
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

.build-id-line {
  font-size: 12px;
  color: #555;
  margin-bottom: 8px;
  word-break: break-all;
}

.build-id-line code {
  background: #eef;
  padding: 1px 6px;
  border-radius: 3px;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}

.terminal {
  background: #1a1a1a;
  color: #00ff00;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  padding: 15px;
  border-radius: 4px;
  height: 380px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.terminal-empty { color: #666; }
.log-line { line-height: 1.6; }

.progress-bar {
  margin-top: 12px;
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
