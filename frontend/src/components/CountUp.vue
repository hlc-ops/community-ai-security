<template>
  <span class="count-up" :class="{ 'is-running': running }">{{ display }}</span>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'

const props = defineProps({
  value: { type: Number, required: true },
  duration: { type: Number, default: 1200 },
  decimals: { type: Number, default: 0 },
  prefix: { type: String, default: '' },
  suffix: { type: String, default: '' },
  separator: { type: String, default: ',' },
})

const display = ref(format(0))
const running = ref(false)

function format(num) {
  let n = Number(num).toFixed(props.decimals)
  const [intPart, decPart] = n.split('.')
  const withSep = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, props.separator)
  return props.prefix + (decPart ? `${withSep}.${decPart}` : withSep) + props.suffix
}

// 缓动函数(ease-out cubic)
function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3)
}

function animate(from, to) {
  running.value = true
  const start = performance.now()
  function tick(now) {
    const elapsed = now - start
    const t = Math.min(1, elapsed / props.duration)
    const eased = easeOutCubic(t)
    const current = from + (to - from) * eased
    display.value = format(current)
    if (t < 1) {
      requestAnimationFrame(tick)
    } else {
      display.value = format(to)
      running.value = false
    }
  }
  requestAnimationFrame(tick)
}

watch(() => props.value, (val, oldVal) => {
  animate(oldVal || 0, val)
})

onMounted(() => {
  animate(0, props.value)
})
</script>

<style scoped>
.count-up {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: var(--letter-tight);
  display: inline-block;
}
.count-up.is-running {
  color: var(--brand);
}
</style>
