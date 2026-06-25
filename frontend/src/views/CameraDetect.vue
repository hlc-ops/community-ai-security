<template>
  <div>
    <div class="page-title">实时检测（摄像头）</div>
    <div class="page-desc">调用摄像头实时识别违规行为，命中高/中危时按设定间隔自动抓拍入库。</div>

    <!-- 控制栏 -->
    <el-card shadow="never" class="ctrl">
      <div class="ctrl-row">
        <el-button type="primary" :icon="VideoCamera" @click="toggle">
          {{ running ? '关闭摄像头' : '开启摄像头' }}
        </el-button>
        <el-button :icon="RefreshRight" :disabled="!running" @click="switchCam">切换前后置</el-button>
        <el-button type="success" plain :icon="Camera" :disabled="!running" @click="capture">截图</el-button>
        <el-button :type="drawing ? 'warning' : 'default'" :icon="Crop" :disabled="!running" @click="toggleDraw">
          {{ drawing ? '完成划定' : '划定区域' }}
        </el-button>
        <el-button v-if="zone" :icon="Delete" :disabled="!running" @click="clearZone">清除区域</el-button>

        <div class="spacer"></div>

        <span class="lbl">置信度</span>
        <el-slider v-model="conf" :min="0.1" :max="0.9" :step="0.05" style="width: 160px" :format-tooltip="(v) => v.toFixed(2)" />
        <span class="val">{{ conf.toFixed(2) }}</span>

        <span class="lbl" style="margin-left: 16px">抓拍间隔</span>
        <el-select v-model="snapInterval" style="width: 100px">
          <el-option label="2 秒" :value="2" />
          <el-option label="5 秒" :value="5" />
          <el-option label="10 秒" :value="10" />
          <el-option label="30 秒" :value="30" />
        </el-select>
      </div>
    </el-card>

    <el-row :gutter="20" style="margin-top: 16px">
      <!-- 画面 -->
      <el-col :span="16">
        <el-card shadow="hover" class="screen-card">
          <div class="screen">
            <div ref="stageEl" class="stage" :style="stageStyle">
              <!-- 原视频 30fps 丝滑播放（舞台按摄像头实际比例自适应，避免拉伸） -->
              <video
                ref="videoEl"
                autoplay playsinline muted
                class="stage-video"
                :class="{ off: !running }"
                @loadedmetadata="onMeta"
              ></video>
              <!-- AI 检测框叠层 -->
              <canvas ref="boxCanvas" class="box-overlay"></canvas>
              <!-- 电子围栏圈选叠层 -->
              <canvas
                ref="zoneCanvas"
                class="zone-canvas"
                :class="{ drawing }"
                @mousedown="onDown"
                @mousemove="onMove"
                @mouseup="onUp"
                @mouseleave="onUp"
              ></canvas>
              <div v-if="drawing" class="draw-tip">在画面上按住拖拽，框选只需检测的危险区域</div>
              <!-- 全屏按钮 -->
              <FullscreenButton @toggle="toggleFs" />
              <div v-if="!running" class="placeholder-overlay">
                <el-icon :size="64"><VideoCamera /></el-icon>
                <div>点击「开启摄像头」开始实时检测</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 状态 -->
      <el-col :span="8">
        <el-card shadow="hover" class="status-card">
          <div class="box-title">检测状态</div>
          <el-alert v-if="risk === 'high'" title="⚠️ 检测到高危违规！" type="error" :closable="false" show-icon />
          <el-alert v-else-if="risk === 'mid'" title="⚠️ 检测到中危违规！" type="warning" :closable="false" show-icon />
          <el-alert v-else title="✅ 现场安全正常" type="success" :closable="false" show-icon />

          <div class="box-title" style="margin-top: 20px">命中类别</div>
          <div v-if="clsList.length" class="cls">
            <el-tag v-for="(c, i) in clsList" :key="i" :type="riskTagType(c)" effect="dark" style="margin: 4px">{{ c }}</el-tag>
          </div>
          <el-empty v-else :image-size="60" description="暂无" />

          <el-divider />
          <div class="meta">
            <div>运行状态：<el-tag size="small" :type="running ? 'success' : 'info'">{{ running ? '检测中' : '已停止' }}</el-tag></div>
            <div>本次抓拍：<b>{{ snapCount }}</b> 张</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 下方会话状态条：抓拍墙 / 统计 / 类别时间轴 -->
    <SessionStatusBar
      :snapshots="sessionSnaps"
      :stats="stats"
      :timeline="sessionTimeline"
      style="margin-top: 20px"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoCamera, RefreshRight, Camera, Crop, Delete } from '@element-plus/icons-vue'
import { detectFrame, createRecord } from '@/api/detect'
import FullscreenButton from '@/components/FullscreenButton.vue'
import SessionStatusBar from '@/components/SessionStatusBar.vue'
import { fmtTimeShort } from '@/utils/datetime'

const videoEl = ref(null)
const zoneCanvas = ref(null)
const boxCanvas = ref(null)
const stageEl = ref(null)
const conf = ref(0.5)
const snapInterval = ref(10)

const running = ref(false)
const risk = ref('low')
const clsList = ref([])
const snapCount = ref(0)
const stageAspect = ref('4 / 3')   // 视频元数据就绪后按真实比例自适应
const viewportH = ref(window.innerHeight)
let latestBoxes = []        // 最近一次检测的归一化框（截图时复用）
let latestResultImg = ''    // 后端返回的标注图（仅入库/抓拍用，不显示）
const onResize = () => { viewportH.value = window.innerHeight }

// 本次会话统计 / 抓拍 / 类别时间轴
const sessionFrames = ref(0)
const sessionStart = ref(0)
const sessionSnaps = ref([])     // [{url, risk, time}]
const sessionTimeline = ref([])  // [{time, classes:[]}]
const runtime = ref('00:00')
let runtimeTimer = null
const stats = computed(() => [
  { label: '已处理帧', value: sessionFrames.value },
  { label: '抓拍张数', value: snapCount.value },
  { label: '运行时长', value: runtime.value },
  { label: '当前风险', value: risk.value === 'high' ? '高' : risk.value === 'mid' ? '中' : '低' },
])
const updateRuntime = () => {
  if (!sessionStart.value) { runtime.value = '00:00'; return }
  const sec = Math.floor((Date.now() - sessionStart.value) / 1000)
  const m = String(Math.floor(sec / 60)).padStart(2, '0')
  const s = String(sec % 60).padStart(2, '0')
  runtime.value = `${m}:${s}`
}
const pushTimeline = (clsList) => {
  if (!clsList?.length) return
  const t = fmtTimeShort(new Date().toISOString())
  const last = sessionTimeline.value[0]
  if (last && last.time === t) {
    last.classes = Array.from(new Set([...last.classes, ...clsList]))
  } else {
    sessionTimeline.value.unshift({ time: t, classes: [...clsList] })
    if (sessionTimeline.value.length > 30) sessionTimeline.value.length = 30
  }
}
const stageStyle = computed(() => {
  const parts = stageAspect.value.split('/').map((s) => Number(s.trim()))
  if (parts.length !== 2 || !parts[0] || !parts[1]) return {}
  const aw = parts[0], ah = parts[1]
  const maxH = viewportH.value * 0.7
  const maxW = 800
  let w = maxW, h = w * ah / aw
  if (h > maxH) { h = maxH; w = h * aw / ah }
  return { width: w + 'px', height: h + 'px' }
})

const onMeta = () => {
  const v = videoEl.value
  if (v && v.videoWidth && v.videoHeight) {
    stageAspect.value = `${v.videoWidth} / ${v.videoHeight}`
  }
}

const toggleFs = async () => {
  const el = stageEl.value
  if (!el) return
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await el.requestFullscreen()
  } catch (e) { /* 用户拒绝或浏览器不支持，忽略 */ }
}

// 检测区域（电子围栏）：归一化矩形 {x1,y1,x2,y2}，null 表示全画面
const drawing = ref(false)
const zone = ref(null)
let drag = null

let stream = null
let useFront = false
let processing = false
let loopTimer = null
let lastSnap = 0

const HIGH = ['跌倒', '未戴安全帽', '吸烟']
const MID = ['打电话']
const riskTagType = (c) => (HIGH.includes(c) ? 'danger' : MID.includes(c) ? 'warning' : 'success')

const start = async () => {
  try {
    if (stream) stopStream()
    const facing = useFront ? 'user' : 'environment'
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facing } },
      })
    } catch (e1) {
      stream = await navigator.mediaDevices.getUserMedia({ video: true })
    }
    videoEl.value.srcObject = stream
    await videoEl.value.play()
    running.value = true
    lastSnap = 0
    snapCount.value = 0
    sessionFrames.value = 0
    sessionSnaps.value = []
    sessionTimeline.value = []
    sessionStart.value = Date.now()
    updateRuntime()
    if (runtimeTimer) clearInterval(runtimeTimer)
    runtimeTimer = setInterval(updateRuntime, 1000)
    loop()
  } catch (e) {
    ElMessage.error('无法访问摄像头：' + e.message)
  }
}

const loop = async () => {
  if (!running.value || processing) return
  processing = true
  try {
    const v = videoEl.value
    if (v && v.videoWidth) {
      const canvas = document.createElement('canvas')
      canvas.width = 640
      canvas.height = 480
      canvas.getContext('2d').drawImage(v, 0, 0, 640, 480)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.6)
      const res = await detectFrame(dataUrl, conf.value, zone.value)
      latestBoxes = res.boxes || []
      latestResultImg = res.img || ''
      drawBoxes(latestBoxes)         // AI 返回时直接画当前框
      risk.value = res.risk
      clsList.value = res.cls_list || []
      sessionFrames.value++
      pushTimeline(res.cls_list)
      maybeSnap(res)
    }
  } catch (e) {
    /* 单帧失败忽略，继续下一帧 */
  } finally {
    processing = false
    if (running.value) loopTimer = setTimeout(loop, 120)
  }
}

// ---- AI 框叠层绘制（按风险配色，与后端一致）----
const colorFor = (name) => {
  if (HIGH.includes(name)) return '#f5222d'  // 高危：红
  if (MID.includes(name)) return '#faad14'   // 中危：黄
  return '#52c41a'                            // 合规（安全帽/反光衣等）：绿
}

const _getDisplayRect = (cw, ch, mw, mh) => {
  if (!mw || !mh) return { x: 0, y: 0, w: cw, h: ch }
  const elRatio = cw / ch, mRatio = mw / mh
  if (Math.abs(elRatio - mRatio) < 0.01) return { x: 0, y: 0, w: cw, h: ch }
  if (mRatio > elRatio) { const w = cw, h = cw / mRatio; return { x: 0, y: (ch - h) / 2, w, h } }
  const h = ch, w = ch * mRatio
  return { x: (cw - w) / 2, y: 0, w, h }
}

const _drawBoxesOnCtx = (ctx, boxes, w, h, lineWidth = 3, fontSize = 14, ox = 0, oy = 0) => {
  ctx.lineWidth = lineWidth
  ctx.font = `${fontSize}px "Microsoft YaHei", sans-serif`
  ctx.textBaseline = 'bottom'
  for (const b of boxes) {
    const x = ox + b.x1 * w
    const y = oy + b.y1 * h
    const bw = (b.x2 - b.x1) * w
    const bh = (b.y2 - b.y1) * h
    const c = colorFor(b.name)
    ctx.strokeStyle = c
    ctx.strokeRect(x, y, bw, bh)
    const label = `${b.name} ${b.conf.toFixed(2)}`
    const tw = ctx.measureText(label).width + 8
    ctx.fillStyle = c
    ctx.fillRect(x, Math.max(y - fontSize - 4, 0), tw, fontSize + 4)
    ctx.fillStyle = '#fff'
    ctx.fillText(label, x + 4, Math.max(y - 2, fontSize))
  }
}

const drawBoxes = (boxes) => {
  const canvas = boxCanvas.value
  if (!canvas) return
  const r = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  if (canvas.width !== r.width * dpr || canvas.height !== r.height * dpr) {
    canvas.width = r.width * dpr
    canvas.height = r.height * dpr
  }
  const ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, r.width, r.height)
  if (!boxes || !boxes.length) return
  const v = videoEl.value
  const vr = _getDisplayRect(r.width, r.height, v?.videoWidth || 0, v?.videoHeight || 0)
  _drawBoxesOnCtx(ctx, boxes, vr.w, vr.h, 3, 14, vr.x, vr.y)
}


const maybeSnap = async (res) => {
  if (res.risk !== 'high' && res.risk !== 'mid') return
  const now = Date.now()
  if (now - lastSnap < snapInterval.value * 1000) return
  lastSnap = now
  try {
    await createRecord({
      type: 'camera',
      risk: res.risk,
      clsList: res.cls_list || [],
      image: res.img,
      durationSeconds: 0,
      startedAt: new Date().toISOString(),
    })
    snapCount.value++
    sessionSnaps.value.unshift({
      url: res.img,
      risk: res.risk,
      time: fmtTimeShort(new Date().toISOString()),
    })
    if (sessionSnaps.value.length > 30) sessionSnaps.value.length = 30
  } catch (e) {
    /* 拦截器已提示 */
  }
}

const stopStream = () => {
  if (loopTimer) { clearTimeout(loopTimer); loopTimer = null }
  if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null }
  if (videoEl.value) videoEl.value.srcObject = null
}

const stop = () => {
  running.value = false
  stopStream()
  if (runtimeTimer) { clearInterval(runtimeTimer); runtimeTimer = null }
  latestResultImg = ''
  latestBoxes = []
  drawBoxes([])  // 清空框
  risk.value = 'low'
  clsList.value = []
  stageAspect.value = '16 / 9'  // 关闭后回到统一空状态尺寸
}

const toggle = () => (running.value ? stop() : start())

const switchCam = async () => {
  if (!running.value) return
  useFront = !useFront
  await start()
}

const capture = () => {
  const v = videoEl.value
  if (!v || !v.videoWidth) return ElMessage.warning('暂无画面')
  // 把当前视频帧 + 最近一次的框合成一张图
  const c = document.createElement('canvas')
  c.width = v.videoWidth
  c.height = v.videoHeight
  const ctx = c.getContext('2d')
  ctx.drawImage(v, 0, 0)
  if (latestBoxes.length) {
    // 截图时画面是原视频帧，无 letterbox，可直接用全画布尺寸
    _drawBoxesOnCtx(ctx, latestBoxes, c.width, c.height, 4, Math.round(c.height / 25), 0, 0)
  }
  const a = document.createElement('a')
  a.href = c.toDataURL('image/jpeg', 0.9)
  a.download = 'camera_' + new Date().toISOString().slice(0, 19).replace(/:/g, '-') + '.jpg'
  a.click()
}

// ---- 检测区域圈选 ----
const toggleDraw = () => {
  drawing.value = !drawing.value
  if (drawing.value) ElMessage.info('在画面上按住拖拽，框选危险区域')
}

const _rel = (e) => {
  const c = zoneCanvas.value
  const r = c.getBoundingClientRect()
  return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height, r }
}

const onDown = (e) => {
  if (!drawing.value) return
  const p = _rel(e)
  drag = { x1: p.x, y1: p.y, x2: p.x, y2: p.y }
}

const onMove = (e) => {
  if (!drawing.value || !drag) return
  const p = _rel(e)
  drag.x2 = p.x
  drag.y2 = p.y
  // 画橡皮筋矩形反馈
  const c = zoneCanvas.value
  c.width = p.r.width
  c.height = p.r.height
  const ctx = c.getContext('2d')
  ctx.clearRect(0, 0, c.width, c.height)
  ctx.strokeStyle = '#ffd700'
  ctx.lineWidth = 2
  ctx.strokeRect(
    drag.x1 * c.width, drag.y1 * c.height,
    (drag.x2 - drag.x1) * c.width, (drag.y2 - drag.y1) * c.height,
  )
}

const onUp = () => {
  if (!drawing.value || !drag) return
  const x1 = Math.min(drag.x1, drag.x2)
  const y1 = Math.min(drag.y1, drag.y2)
  const x2 = Math.max(drag.x1, drag.x2)
  const y2 = Math.max(drag.y1, drag.y2)
  drag = null
  if (x2 - x1 < 0.03 || y2 - y1 < 0.03) {
    ElMessage.warning('区域太小，请重新框选')
    return
  }
  zone.value = { x1, y1, x2, y2 }
  drawing.value = false
  // 清掉前端橡皮筋，区域框由后端在返回帧里画
  const c = zoneCanvas.value
  if (c) c.getContext('2d').clearRect(0, 0, c.width, c.height)
  ElMessage.success('检测区域已设定，仅检测区域内目标')
}

const clearZone = () => {
  zone.value = null
  const c = zoneCanvas.value
  if (c) c.getContext('2d').clearRect(0, 0, c.width, c.height)
  ElMessage.success('已清除区域，恢复全画面检测')
}

onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  stop()
})
</script>

<style scoped>
.ctrl {
  border-radius: 10px;
}
.ctrl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.spacer {
  flex: 1;
}
.lbl {
  color: #555;
  font-size: 14px;
}
.val {
  font-weight: bold;
  color: #0a5a2c;
  min-width: 42px;
}
.screen-card,
.status-card {
  border-radius: 10px;
}
.screen {
  background: #111;
  border-radius: 8px;
  min-height: 460px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.stage {
  position: relative;
  width: 100%;
  max-width: 800px;
  /* aspect-ratio 由 :style 动态绑定（按视频/摄像头真实比例） */
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}
.stage-video {
  width: 100%;
  height: 100%;
  object-fit: fill;
  display: block;
  background: #000;
}
.stage-video.off { visibility: hidden; }
.box-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.placeholder-overlay {
  position: absolute;
  inset: 0;
  color: rgba(255, 255, 255, 0.4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  pointer-events: none;
}
.stage:fullscreen {
  width: 100vw !important;
  height: 100vh !important;
  max-width: none !important;
  max-height: none !important;
  border-radius: 0;
}
.stage:fullscreen .stage-video {
  object-fit: contain;
}
.zone-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.zone-canvas.drawing {
  pointer-events: auto;
  cursor: crosshair;
  background: rgba(0, 0, 0, 0.08);
}
.draw-tip {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.6);
  color: #ffd700;
  font-size: 13px;
  padding: 4px 12px;
  border-radius: 4px;
}
.screen-placeholder {
  color: rgba(255, 255, 255, 0.4);
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.box-title {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 12px;
  color: #0a5a2c;
}
.meta {
  color: #555;
  font-size: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
