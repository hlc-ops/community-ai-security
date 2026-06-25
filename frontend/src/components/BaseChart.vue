<template>
  <div ref="el" class="chart"></div>
</template>

<script setup>
import { ref, shallowRef, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
})

const el = ref(null)
const chart = shallowRef(null)

const render = () => {
  if (!chart.value && el.value) {
    chart.value = echarts.init(el.value)
  }
  if (chart.value) chart.value.setOption(props.option, true)
}

const onResize = () => chart.value && chart.value.resize()

onMounted(async () => {
  await nextTick()
  render()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart.value && chart.value.dispose()
})

watch(() => props.option, render, { deep: true })
</script>

<style scoped>
.chart {
  width: 100%;
  height: 320px;
}
</style>
