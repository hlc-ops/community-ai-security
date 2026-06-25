<template>
  <div>
    <div class="page-title">网络摄像头检测（RTSP/IP）</div>
    <div class="page-desc">接入工地网络摄像头（海康/大华等 RTSP 流），后端实时拉流检测，命中高/中危自动抓拍入库并报警。</div>

    <el-card shadow="never" class="ctrl">
      <div class="ctrl-row">
        <el-input
          v-model="url"
          placeholder="rtsp://用户名:密码@摄像头IP:554/Streaming/Channels/101"
          style="flex: 1; min-width: 320px"
          :disabled="running"
        />
        <el-button type="primary" :icon="VideoCamera" :loading="starting" :disabled="running" @click="start">开始</el-button>
        <el-button type="danger" plain :icon="Close" :disabled="!running" @click="stop">停止</el-button>
      </div>
      <div class="ctrl-row" style="margin-top: 12px">
        <span class="lbl">置信度</span>
        <el-slider v-model="conf" :min="0.1" :max="0.9" :step="0.05" style="width: 160px" :disabled="running" :format-tooltip="(v) => v.toFixed(2)" />
        <span class="val">{{ conf.toFixed(2) }}</span>
        <span class="lbl" style="margin-left: 16px">抓拍间隔</span>
        <el-select v-model="snapInterval" style="width: 100px" :disabled="running">
          <el-option label="5 秒" :value="5" />
          <el-option label="10 秒" :value="10" />
          <el-option label="30 秒" :value="30" />
        </el-select>
        <span class="tip">提示：RTSP 地址格式因摄像头品牌而异，海康常见为 /Streaming/Channels/101</span>
      </div>
    </el-card>

    <el-row :gutter="20" style="margin-top: 16px">
      <el-col :span="16">
        <el-card shadow="hover" class="screen-card">
          <div class="screen">
            <div ref="stageEl" class="stage" :style="stageStyle">
              <!-- 后端推过来的原视频（MJPEG，不带框）—— 浏览器自身丝滑播放 -->
              <img
                v-if="running && imgSrc"
                :src="imgSrc"
                class="stage-img"
                alt="实时画面"
                @error="onImgError"
                @load="onImgLoad"
              />
              <!-- AI 框叠层 -->
              <canvas ref="boxCanvas" class="box-overlay"></canvas>
              <!-- 全屏按钮 -->
              <FullscreenButton @toggle="toggleFs" />
              <div v-if="!running || !imgSrc" class="placeholder-overlay">
                <el-icon :size="64"><VideoCamera /></el-icon>
                <div>填写摄像头地址并点击「开始」</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="status-card">
          <div class="box-title">检测状态</div>
          <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
          <template v-else>
            <el-alert v-if="risk === 'high'" title="⚠️ 检测到高危违规！" type="error" :closable="false" show-icon />
            <el-alert v-else-if="risk === 'mid'" title="⚠️ 检测到中危违规！" type="warning" :closable="false" show-icon />
            <el-alert v-else title="✅ 现场安全正常" type="success" :closable="false" show-icon />
          </template>

          <div class="box-title" style="margin-top: 20px">命中类别</div>
          <div v-if="clsList.length" class="cls">
            <el-tag v-for="(c, i) in clsList" :key="i" :type="riskTagType(c)" effect="dark" style="margin: 4px">{{ c }}</el-tag>
          </div>
          <el-empty v-else :image-size="60" description="暂无" />

          <el-divider />
          <div class="meta">
            <div>连接状态：
              <el-tag size="small" :type="running ? (alive ? 'success' : 'warning') : 'info'">
                {{ running ? (alive ? '拉流中' : '连接中…') : '未连接' }}
              </el-tag>
            </div>
            <div>本次抓拍：<b>{{ snapCount }}</b> 张</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 下方会话状态条 -->
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
import { VideoCamera, Close } from '@element-plus/icons-vue'
import { startStream, stopStream, streamStatus, mjpegUrl } from '@/api/stream'
import FullscreenButton from '@/components/FullscreenButton.vue'
import SessionStatusBar from '@/components/SessionStatusBar.vue'
import { fmtTimeShort } from '@/utils/datetime'

const url = ref('')
const conf = ref(0.5)
const snapInterval = ref(10)

const running = ref(false)
const starting = ref(false)
const alive = ref(false)
const error = ref('')
const risk = ref('low')
const clsList = ref([])
const snapCount = ref(0)
const imgSrc = ref('')
const stageAspect = ref('16 / 9')
const viewportH = ref(window.innerHeight)
const boxCanvas = ref(null)
const stageEl = ref(null)

const toggleFs = async () => {
  const el = stageEl.value
  if (!el) return
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await el.requestFullscreen()
  } catch (e) { /* 用户拒绝或浏览器不支持，忽略 */ }
}

// 本次会话统计 / 抓拍 / 类别时间轴
const sessionStart = ref(0)
const sessionSnaps = ref([])
const sessionTimeline = ref([])
const runtime = ref('00:00')
let runtimeTimer = null
const stats = computed(() => [
  { label: '抓拍张数', value: snapCount.value },
  { label: '运行时长', value: runtime.value },
  { label: '连接', value: alive.value ? '在线' : '离线' },
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

let streamId = null
let statusTimer = null
let latestBoxes = []
const onResize = () => { viewportH.value = window.innerHeight }
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

const onImgLoad = (e) => {
  const im = e.target
  if (im.naturalWidth && im.naturalHeight) {
    stageAspect.value = `${im.naturalWidth} / ${im.naturalHeight}`
  }
}

const colorFor = (name) => {
  if (HIGH.includes(name)) return '#f5222d'
  if (MID.includes(name)) return '#faad14'
  return '#52c41a'
}

const _getDisplayRect = (cw, ch, mw, mh) => {
  if (!mw || !mh) return { x: 0, y: 0, w: cw, h: ch }
  const elRatio = cw / ch, mRatio = mw / mh
  if (Math.abs(elRatio - mRatio) < 0.01) return { x: 0, y: 0, w: cw, h: ch }
  if (mRatio > elRatio) { const w = cw, h = cw / mRatio; return { x: 0, y: (ch - h) / 2, w, h } }
  const h = ch, w = ch * mRatio
  return { x: (cw - w) / 2, y: 0, w, h }
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
  // letterbox 修正：MJPEG 是 <img>，取 naturalWidth/Height
  const im = document.querySelector('.stage-img')
  const vr = _getDisplayRect(r.width, r.height, im?.naturalWidth || 0, im?.naturalHeight || 0)
  ctx.lineWidth = 3
  ctx.font = '14px "Microsoft YaHei", sans-serif'
  ctx.textBaseline = 'bottom'
  for (const b of boxes) {
    const x = vr.x + b.x1 * vr.w
    const y = vr.y + b.y1 * vr.h
    const bw = (b.x2 - b.x1) * vr.w
    const bh = (b.y2 - b.y1) * vr.h
    const c = colorFor(b.name)
    ctx.strokeStyle = c
    ctx.strokeRect(x, y, bw, bh)
    const label = `${b.name} ${b.conf.toFixed(2)}`
    const tw = ctx.measureText(label).width + 8
    ctx.fillStyle = c
    ctx.fillRect(x, Math.max(y - 18, 0), tw, 18)
    ctx.fillStyle = '#fff'
    ctx.fillText(label, x + 4, Math.max(y - 2, 14))
  }
}


const HIGH = ['跌倒', '未戴安全帽', '吸烟']
const MID = ['打电话']
const riskTagType = (c) => (HIGH.includes(c) ? 'danger' : MID.includes(c) ? 'warning' : 'success')

const start = async () => {
  if (!url.value.trim()) return ElMessage.warning('请填写摄像头地址')
  starting.value = true
  error.value = ''
  try {
    const res = await startStream({ url: url.value, conf: conf.value, snapInterval: snapInterval.value })
    streamId = res.streamId
    running.value = true
    sessionSnaps.value = []
    sessionTimeline.value = []
    snapCount.value = 0
    sessionStart.value = Date.now()
    updateRuntime()
    if (runtimeTimer) clearInterval(runtimeTimer)
    runtimeTimer = setInterval(updateRuntime, 1000)
    // 加时间戳避免缓存
    imgSrc.value = mjpegUrl(streamId) + '?t=' + Date.now()
    pollStatus()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    starting.value = false
  }
}

const pollStatus = () => {
  // 200ms 拉一次，既能跟上 AI 检测节奏，又不会压垮后端
  statusTimer = setInterval(async () => {
    if (!streamId) return
    try {
      const s = await streamStatus(streamId)
      alive.value = s.alive
      error.value = s.error || ''
      risk.value = s.risk
      clsList.value = s.clsList || []
      // 新抓拍：用截图占位（后端不传 base64 给 status，这里用 mjpeg 当前帧近似）
      if (s.snapCount > snapCount.value) {
        const inc = s.snapCount - snapCount.value
        for (let i = 0; i < inc; i++) {
          sessionSnaps.value.unshift({
            url: mjpegUrl(streamId) + '?t=' + Date.now() + Math.random(),
            risk: s.risk,
            time: fmtTimeShort(new Date().toISOString()),
          })
        }
        if (sessionSnaps.value.length > 30) sessionSnaps.value.length = 30
      }
      snapCount.value = s.snapCount
      pushTimeline(s.clsList)
      latestBoxes = s.boxes || []
      drawBoxes(latestBoxes)        // status 拉来时直接画当前框
      if (s.error) {
        ElMessage.error(s.error)
        stop()
      }
    } catch (e) {
      /* 忽略单次轮询失败 */
    }
  }, 200)
}

const stop = async () => {
  if (statusTimer) { clearInterval(statusTimer); statusTimer = null }
  if (runtimeTimer) { clearInterval(runtimeTimer); runtimeTimer = null }
  const sid = streamId
  streamId = null
  running.value = false
  alive.value = false
  imgSrc.value = ''
  clsList.value = []
  risk.value = 'low'
  latestBoxes = []
  drawBoxes([])
  stageAspect.value = '16 / 9'  // 关闭后回到统一空状态尺寸
  if (sid) {
    try { await stopStream(sid) } catch (e) { /* ignore */ }
  }
}

const onImgError = () => {
  // MJPEG 加载失败（流断开）时不刷屏，由状态轮询兜底
}

onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  stop()
})
</script>

<style scoped>
.ctrl { border-radius: 10px; }
.ctrl-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.lbl { color: #555; font-size: 14px; }
.val { font-weight: bold; color: #0a5a2c; min-width: 42px; }
.tip { color: #aaa; font-size: 12px; }
.screen-card, .status-card { border-radius: 10px; }
.screen {
  background: #111; border-radius: 8px; min-height: 460px;
  display: flex; align-items: center; justify-content: center; overflow: hidden;
}
.stage {
  position: relative;
  width: 100%;
  max-width: 800px;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
}
.stage-img {
  width: 100%;
  height: 100%;
  object-fit: fill;
  display: block;
  background: #000;
}
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
.stage:fullscreen .stage-img {
  object-fit: contain;
}
.box-title { font-weight: 600; font-size: 16px; margin-bottom: 12px; color: #0a5a2c; }
.meta { color: #555; font-size: 14px; display: flex; flex-direction: column; gap: 10px; }
</style>
