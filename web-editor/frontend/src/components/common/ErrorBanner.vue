<template>
  <div v-if="message" class="error-banner" @click="dismiss">
    {{ message }}
    <button class="dismiss-btn" @click.stop="dismiss">×</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ message: string; duration?: number }>()
const emit = defineEmits<{ (e: 'dismiss'): void }>()

const message = ref(props.message)

if (props.duration) {
  setTimeout(() => dismiss(), props.duration)
}

function dismiss() {
  message.value = ''
  emit('dismiss')
}
</script>

<style scoped>
.error-banner {
  background: #fee2e2;
  border: 1px solid #ef4444;
  color: #991b1b;
  padding: 10px 16px;
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
}
.dismiss-btn { background: none; border: none; font-size: 18px; cursor: pointer; color: #991b1b; }
</style>
