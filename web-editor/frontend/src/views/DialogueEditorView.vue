<template>
  <div class="dialogue-editor">
    <div class="header">
      <button @click="goBack">← 返回</button>
      <h2>编辑: {{ key }}</h2>
    </div>

    <div v-if="store.loading" class="loading">加载中...</div>
    <div v-else-if="store.error" class="error">{{ store.error }}</div>

    <div v-else-if="dialogue" class="editor-form">
      <div class="field">
        <label>Key:</label>
        <input v-model="dialogue.key" disabled />
      </div>

      <div class="field">
        <label>Speaker:</label>
        <input v-model="dialogue.speaker" @input="markDirty" />
      </div>

      <div class="field">
        <label>Chapter ID:</label>
        <input v-model.number="dialogue.chapter_id" type="number" @input="markDirty" />
      </div>

      <div class="field">
        <label>Max Bytes:</label>
        <input v-model.number="dialogue.max_bytes" type="number" @input="markDirty" />
      </div>

      <div class="text-columns">
        <div class="text-col">
          <label>日文 (Japanese):</label>
          <textarea
            v-model="dialogue.text_ja"
            @input="updateBytes"
            rows="10"
          ></textarea>
          <div class="byte-count" :class="{ over: byteCount.ja > (dialogue.max_bytes || 255) }">
            字节: {{ byteCount.ja }} / {{ dialogue.max_bytes || 255 }}
          </div>
        </div>

        <div class="text-col">
          <label>中文 (Chinese):</label>
          <textarea
            v-model="dialogue.text_zh"
            @input="updateBytes"
            rows="10"
          ></textarea>
          <div class="byte-count" :class="{ over: byteCount.zh > (dialogue.max_bytes || 255) }">
            字节: {{ byteCount.zh }} / {{ dialogue.max_bytes || 255 }}
          </div>
        </div>
      </div>

      <div class="total-bytes">
        总计: {{ byteCount.total }} / {{ dialogue.max_bytes || 255 }}
        <span v-if="byteCount.total > (dialogue.max_bytes || 255)" class="warn">
          超出 {{ byteCount.total - (dialogue.max_bytes || 255) }} 字节
        </span>
      </div>

      <div class="actions">
        <button @click="save" :disabled="!dirty">保存</button>
        <button @click="goBack">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialogueStore } from '../stores/dialogueStore'

const route = useRoute()
const router = useRouter()
const store = useDialogueStore()

const key = computed(() => route.params.key as string)
const dialogue = ref<any>(null)
const dirty = ref(false)
const byteCount = ref({ ja: 0, zh: 0, total: 0 })

onMounted(async () => {
  await store.fetchDialogue(key.value)
  dialogue.value = { ...store.currentDialogue }
  updateBytes()
})

function calcBytes(str: string | null) {
  return str ? new TextEncoder().encode(str).length : 0
}

function updateBytes() {
  if (!dialogue.value) return
  byteCount.value.ja = calcBytes(dialogue.value.text_ja)
  byteCount.value.zh = calcBytes(dialogue.value.text_zh)
  byteCount.value.total = byteCount.value.ja + byteCount.value.zh
}

function markDirty() {
  dirty.value = true
}

async function save() {
  try {
    await store.updateDialogue(key.value, {
      speaker: dialogue.value.speaker,
      text_ja: dialogue.value.text_ja,
      text_zh: dialogue.value.text_zh,
      chapter_id: dialogue.value.chapter_id,
      max_bytes: dialogue.value.max_bytes
    })
    dirty.value = false
    alert('保存成功!')
  } catch (e: any) {
    alert(e.message)
  }
}

function goBack() {
  router.push('/dialogues')
}
</script>

<style scoped>
.dialogue-editor {
  padding: 20px;
}

.header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}

.header button {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 4px;
  cursor: pointer;
}

.editor-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.field {
  display: flex;
  align-items: center;
  gap: 10px;
}

.field label {
  width: 100px;
  font-weight: bold;
}

.field input {
  flex: 1;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.text-columns {
  display: flex;
  gap: 20px;
}

.text-col {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.text-col label {
  font-weight: bold;
  margin-bottom: 8px;
}

.text-col textarea {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  resize: vertical;
}

.byte-count {
  margin-top: 8px;
  font-size: 14px;
  color: #666;
}

.byte-count.over {
  color: red;
  font-weight: bold;
}

.total-bytes {
  padding: 15px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 16px;
}

.total-bytes .warn {
  color: red;
  font-weight: bold;
  margin-left: 10px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.actions button {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.actions button:first-child {
  background: #0066cc;
  color: #fff;
}

.actions button:first-child:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.loading, .error {
  padding: 20px;
  text-align: center;
}

.error {
  color: red;
}
</style>