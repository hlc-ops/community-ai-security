<template>
  <div class="polygon-editor">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select v-model="currentType" size="small" style="width: 160px">
          <el-option
            v-for="opt in POLYGON_TYPES"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          >
            <span style="display:flex; align-items:center; gap:8px;">
              <span class="type-dot" :style="{ background: opt.color }"></span>
              {{ opt.label }}
            </span>
          </el-option>
        </el-select>
        <el-input
          v-model="currentName"
          size="small"
          placeholder="区域名称(如 A-01 车位)"
          style="width: 200px"
        />
        <el-input-number
          v-model="currentDwell"
          size="small"
          :min="0" :max="3600"
          controls-position="right"
          style="width: 130px"
        />
        <span class="hint-mono">秒停留</span>
      </div>
      <div class="toolbar-right">
        <el-button size="small" :disabled="!drawing" @click="cancelDrawing">取消</el-button>
        <el-button
          size="small"
          type="primary"
          :icon="Plus"
          :disabled="drawing"
          @click="startDrawing"
        >
          画区域
        </el-button>
      </div>
    </div>

    <!-- 画布 -->
    <div class="canvas-wrap" :class="{ 'is-drawing': drawing }">
      <!-- 背景图 -->
      <img v-if="bgUrl" :src="bgUrl" class="bg-img" :style="{ width: w + 'px', height: h + 'px' }" />
      <div v-else class="bg-placeholder" :style="{ width: w + 'px', height: h + 'px' }">
        <el-icon><Picture /></el-icon>
        <span>请先取一张摄像头画面作为背景</span>
      </div>

      <!-- SVG 叠层 -->
      <svg
        class="svg-overlay"
        :width="w"
        :height="h"
        :viewBox="`0 0 ${w} ${h}`"
        @click="onCanvasClick"
        @mousemove="onMouseMove"
      >
        <!-- 已保存的多边形 -->
        <g v-for="p in polygons" :key="p.id">
          <polygon
            :points="toSvgPoints(p.points)"
            :fill="`${typeColor(p.type)}33`"
            :stroke="typeColor(p.type)"
            stroke-width="2"
          />
          <text
            v-if="p.points.length"
            :x="centroid(p.points).x"
            :y="centroid(p.points).y"
            :fill="typeColor(p.type)"
            font-size="13"
            font-weight="600"
            text-anchor="middle"
          >
            {{ p.name }}
          </text>
        </g>

        <!-- 当前正在画的多边形 -->
        <g v-if="drawing && drawingPoints.length">
          <polyline
            :points="toSvgPoints([...drawingPoints, mousePos].filter(Boolean))"
            :stroke="currentColor"
            stroke-width="2"
            fill="none"
            stroke-dasharray="6 4"
          />
          <circle
            v-for="(pt, i) in drawingPoints"
            :key="i"
            :cx="pt[0] * w"
            :cy="pt[1] * h"
            r="4"
            :fill="currentColor"
            stroke="#0a1628"
            stroke-width="2"
          />
          <!-- 闭合提示:第一个点画大圆 -->
          <circle
            v-if="drawingPoints.length >= 3"
            :cx="drawingPoints[0][0] * w"
            :cy="drawingPoints[0][1] * h"
            r="8"
            fill="none"
            :stroke="currentColor"
            stroke-width="2"
            stroke-dasharray="3 3"
          />
        </g>
      </svg>

      <!-- 操作提示 -->
      <div v-if="drawing" class="overlay-tip">
        点击画面添加顶点 · 至少 3 个点 · 点击第一个点(虚线圈)闭合
      </div>
    </div>

    <!-- 已配置区域列表 -->
    <div class="poly-list">
      <div class="list-title">已配置区域 ({{ polygons.length }})</div>
      <div v-if="!polygons.length" class="list-empty">还没有配置任何区域,点上方"画区域"开始</div>
      <div v-for="p in polygons" :key="p.id" class="list-item">
        <div class="item-left">
          <span class="type-dot" :style="{ background: typeColor(p.type) }"></span>
          <span class="item-name">{{ p.name || '未命名' }}</span>
          <el-tag size="small">{{ p.typeZh }}</el-tag>
        </div>
        <div class="item-right">
          <span class="item-meta">{{ p.points.length }} 顶点 · {{ p.dwellThreshold }}s</span>
          <el-button text :icon="Delete" type="danger" @click="removePolygon(p)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Plus, Delete, Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  bgUrl: { type: String, default: '' },
  modelValue: { type: Array, default: () => [] },  // 已有 polygons
  width: { type: Number, default: 800 },
  height: { type: Number, default: 450 },
})
const emit = defineEmits(['update:modelValue', 'save'])

const POLYGON_TYPES = [
  { value: 'no_parking',    label: '禁停区',     color: '#ff5470' },
  { value: 'fire_lane',     label: '消防通道',   color: '#ff5470' },
  { value: 'parking_slot',  label: '合法车位',   color: '#4ecdc4' },
  { value: 'charging_slot', label: '充电车位',   color: '#ffb74d' },
  { value: 'lawn',          label: '绿地草坪',   color: '#a78bfa' },
  { value: 'elevator_zone', label: '电梯轿厢',   color: '#ff5470' },
  { value: 'passage',       label: '通道(忽略)', color: '#5b9bff' },
]

const w = computed(() => props.width)
const h = computed(() => props.height)

const polygons = ref([...props.modelValue])
const currentType = ref('no_parking')
const currentName = ref('')
const currentDwell = ref(0)
const drawing = ref(false)
const drawingPoints = ref([])  // [[normX, normY], ...]
const mousePos = ref(null)

const currentColor = computed(() => typeColor(currentType.value))

const typeColor = (t) => POLYGON_TYPES.find(o => o.value === t)?.color || '#5b9bff'
const typeLabel = (t) => POLYGON_TYPES.find(o => o.value === t)?.label || t

const toSvgPoints = (pts) => {
  return pts
    .filter(Boolean)
    .map(p => `${(Array.isArray(p) ? p[0] : p.x) * w.value},${(Array.isArray(p) ? p[1] : p.y) * h.value}`)
    .join(' ')
}

const centroid = (pts) => {
  let x = 0, y = 0
  for (const p of pts) { x += p[0]; y += p[1] }
  return { x: (x / pts.length) * w.value, y: (y / pts.length) * h.value }
}

const startDrawing = () => {
  if (!currentName.value.trim()) {
    return ElMessage.warning('请先填写区域名称')
  }
  drawing.value = true
  drawingPoints.value = []
  mousePos.value = null
}
const cancelDrawing = () => {
  drawing.value = false
  drawingPoints.value = []
  mousePos.value = null
}

const onCanvasClick = (e) => {
  if (!drawing.value) return
  const rect = e.currentTarget.getBoundingClientRect()
  const x = (e.clientX - rect.left) / rect.width
  const y = (e.clientY - rect.top) / rect.height

  // 检查是否点击第一个点闭合
  if (drawingPoints.value.length >= 3) {
    const first = drawingPoints.value[0]
    const dist = Math.hypot((first[0] - x) * w.value, (first[1] - y) * h.value)
    if (dist < 12) {
      finishPolygon()
      return
    }
  }
  drawingPoints.value.push([Math.round(x * 10000) / 10000, Math.round(y * 10000) / 10000])
}

const onMouseMove = (e) => {
  if (!drawing.value) return
  const rect = e.currentTarget.getBoundingClientRect()
  mousePos.value = [
    (e.clientX - rect.left) / rect.width,
    (e.clientY - rect.top) / rect.height,
  ]
}

const finishPolygon = () => {
  if (drawingPoints.value.length < 3) {
    return ElMessage.warning('至少需要 3 个顶点')
  }
  const newPoly = {
    id: 'tmp_' + Date.now(),
    name: currentName.value,
    type: currentType.value,
    typeZh: typeLabel(currentType.value),
    points: [...drawingPoints.value],
    dwellThreshold: currentDwell.value,
    enabled: true,
  }
  polygons.value.push(newPoly)
  emit('update:modelValue', polygons.value)
  emit('save', newPoly)
  cancelDrawing()
  currentName.value = ''
  ElMessage.success(`区域「${newPoly.name}」已添加`)
}

const removePolygon = (p) => {
  polygons.value = polygons.value.filter(x => x !== p)
  emit('update:modelValue', polygons.value)
}
</script>

<style scoped>
.polygon-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3);
  background: var(--bg-overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.hint-mono {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-3);
  margin-left: -4px;
}
.type-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

/* 画布 */
.canvas-wrap {
  position: relative;
  margin: 0 auto;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border);
  background: #0a1628;
}
.canvas-wrap.is-drawing { cursor: crosshair; }
.canvas-wrap.is-drawing .svg-overlay { cursor: crosshair; }

.bg-img {
  display: block;
  object-fit: cover;
}
.bg-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  background: var(--bg-elevated);
  color: var(--text-3);
  font-size: 14px;
}
.bg-placeholder .el-icon { font-size: 40px; }

.svg-overlay {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: all;
}

.overlay-tip {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(10, 22, 40, 0.9);
  backdrop-filter: blur(20px);
  color: var(--text);
  padding: 8px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-brand);
  font-size: 12px;
  font-weight: 500;
  z-index: 10;
}

/* 已配置列表 */
.poly-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.list-title {
  font-size: 11px;
  color: var(--text-3);
  font-weight: 600;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  font-family: var(--font-mono);
}
.list-empty {
  text-align: center;
  color: var(--text-3);
  padding: var(--space-6);
  background: var(--bg-overlay);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color var(--duration-base) var(--ease-out);
}
.list-item:hover { border-color: var(--border-brand); }
.item-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.item-name {
  color: var(--text);
  font-weight: 500;
  font-size: 14px;
}
.item-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.item-meta {
  font-family: var(--font-mono);
  color: var(--text-3);
  font-size: 11px;
}
</style>
