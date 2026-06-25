<template>
  <button
    class="fs-btn"
    :title="isFs ? '退出全屏' : '进入全屏'"
    @click.stop="$emit('toggle')"
  >
    <!-- 进入全屏：四个角向外的箭头 -->
    <svg v-if="!isFs" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
      <path d="M4 4h6v2H6v4H4V4zm10 0h6v6h-2V6h-4V4zM4 14h2v4h4v2H4v-6zm14 0h2v6h-6v-2h4v-4z"/>
    </svg>
    <!-- 退出全屏：四个角向内的箭头 -->
    <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
      <path d="M10 4v6H4V8h4V4h2zm10 4v2h-6V4h2v4h4zM4 14h6v6H8v-4H4v-2zm10 6v-6h6v2h-4v4h-2z"/>
    </svg>
  </button>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

defineEmits(['toggle'])
const isFs = ref(false)
const sync = () => { isFs.value = !!document.fullscreenElement }

onMounted(() => document.addEventListener('fullscreenchange', sync))
onUnmounted(() => document.removeEventListener('fullscreenchange', sync))
</script>

<style scoped>
.fs-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 20;
  transition: background 0.15s, transform 0.15s;
  backdrop-filter: blur(4px);
}
.fs-btn:hover {
  background: rgba(0, 0, 0, 0.8);
  transform: scale(1.05);
}
.fs-btn:active {
  transform: scale(0.95);
}
</style>
