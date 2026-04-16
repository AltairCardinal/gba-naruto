<template>
  <div class="loading-spinner" :style="{ width: size, height: size }">
    <div class="spinner" :style="spinnerStyle"></div>
    <span v-if="text" class="loading-text">{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  size?: string
  text?: string
  color?: string
}>(), {
  size: '32px',
  color: '#0066cc'
})

const spinnerStyle = computed(() => ({
  borderTopColor: props.color
}))
</script>

<style scoped>
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.spinner {
  width: 100%;
  height: 100%;
  border: 3px solid #e5e5e5;
  border-top-color: #0066cc;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-text { font-size: 14px; color: #666; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
