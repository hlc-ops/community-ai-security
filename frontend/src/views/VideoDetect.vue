<template>
  <div>
    <div class="page-title">视频检测</div>
    <div class="page-desc">上传视频文件，逐帧识别违规行为，命中高/中危时按设定间隔自动抓拍入库。</div>

    <!-- 控制栏 -->
    <el-card shadow="never" class="ctrl">
      <div class="ctrl-row">
        <el-button type="primary" :icon="Upload" @click="pickFile">选择视频</el-button>
        <el-button :icon="VideoPause" :disabled="!running" @click="togglePause">
          {{ paused ? '继续' : '暂停' }}
        </el-button>
        <el-button type="success" plain :icon="Camera" :disabled="!running" @click="capture">截图</el-button>
        <el-button type="danger" plain :icon="Close" :disabled="!running" @click="close">关闭视频</el-button>
        <input ref="fileEl" type="file" accept="video/*" style="display: none" @change="onFile" />

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
      <el-col :span="16">
        <el-card shadow="hover" class="screen-card">
          <div class="screen">
            <div ref="stageEl" class="stage" :style="stageStyle">
              <!-- 原视频自己 30fps 丝滑播放（舞台按视频实际比例自适应，避免拉伸） -->
              <video
                ref="videoEl"
                playsinline muted
                class="stage-video"
                :class="{ off: !running }"
                @loadedmetadata="onMeta"
              ></video>
              <!-- AI 检测框叠层 -->
              <canvas ref="boxCanvas" class="box-overlay"></canvas>
              <!-- 全屏按钮 -->
              <FullscreenButton @toggle="toggleFs" />
              <div v-if="!running" class="placeholder-overlay">
                <el-icon :size="64"><VideoCamera /></el-icon>
                <div>点击「选择视频」开始逐帧检测</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

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
            <div>播放状态：<el-tag size="small" :type="running ? (paused ? 'warning' : 'success') : 'info'">{{ running ? (paused ? '已暂停' : '检测中') : '未开始' }}</el-tag></div>
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
import { Upload, VideoPause, Camera, Close, VideoCamera } from '@element-plus/icons-vue'
import { detectVideoFrame, createRecord } from '@/api/detect'
import FullscreenButton from '@/components/FullscreenButton.vue'
import SessionStatusBar from '@/components/SessionStatusBar.vue'
import { fmtTimeShort } from '@/utils/datetime'

const fileEl = ref(null)
const videoEl = ref(null)
const boxCanvas = ref(null)
const stageEl = ref(null)
const conf = ref(0.5)
const snapInterval = ref(10)

const running = ref(false)
const paused = ref(false)
const risk = ref('low')
const clsList = ref([])
const snapCount = ref(0)
const stageAspect = ref('16 / 9')   // 视频加载后按真实比例自适应
const viewportH = ref(window.innerHeight)
let latestBoxes = []
let latestResultImg = ''
const onResize = () => { viewportH.value = window.innerHeight }

// 本次会话统计
const sessionFrames = ref(0)
const sessionStart = ref(0)
const sessionSnaps = ref([])
const sessionTimeline = ref([])
const runtime = ref('00:00')
let runtimeTimer = null
const stats = computed(() => [
  { label: '已处理帧', value: sessionFrames.value },
  { label: '抓拍张数', value: snapCount.value },
  { label: '播放时长', value: runtime.value },
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

let objectUrl = null
let processing = false
let loopTimer = null
let lastSnap = 0

const HIGH = ['跌倒', '未戴安全帽', '吸烟']
const MID = ['打电话']
const riskTagType = (c) => (HIGH.includes(c) ? 'danger' : MID.includes(c) ? 'warning' : 'success')

const pickFile = () => fileEl.value.click()

const onFile = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = '' // 允许重复选同一文件
  await startVideo(file)
}

const startVideo = async (file) => {
  close()
  const v = videoEl.value
  objectUrl = URL.createObjectURL(file)
  v.src = objectUrl
  v.loop = false
  await new Promise((r) => v.addEventListener('canplay', r, { once: true }))
  await v.play()
  running.value = true
  paused.value = false
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
}

const loop = async () => {
  if (!running.value || processing) return
  const v = videoEl.value
  if (!v || v.paused || v.ended) {
    if (v && v.ended) close()
    return
  }
  processing = true
  try {
    if (v.videoWidth) {
      const canvas = document.createElement('canvas')
      canvas.width = v.videoWidth
      canvas.height = v.videoHeight
      canvas.getContext('2d').drawImage(v, 0, 0)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.6)
      const res = await detectVideoFrame(dataUrl, conf.value)
      latestBoxes = res.boxes || []
      latestResultImg = res.img || ''
      drawBoxes(latestBoxes)        // AI 返回时直接画当前框
      risk.value = res.risk
      clsList.value = res.cls_list || []
      sessionFrames.value++
      pushTimeline(res.cls_list)
      maybeSnap(res)
    }
  } catch (e) {
    /* 单帧失败忽略 */
  } finally {
    processing = false
    if (running.value) loopTimer = setTimeout(loop, 120)
  }
}

// ---- AI 框叠层绘制（与 CameraDetect 同一套配色，与后端一致） ----
const colorFor = (name) => {
  if (HIGH.includes(name)) return '#f5222d'
  if (MID.includes(name)) return '#faad14'
  return '#52c41a'
}

// 算出媒体的实际显示矩形（考虑 object-fit: contain 在全屏下产生的黑边）
const _getDisplayRect = (cw, ch, mw, mh) => {
  if (!mw || !mh) return { x: 0, y: 0, w: cw, h: ch }
  const elRatio = cw / ch
  const mRatio = mw / mh
  if (Math.abs(elRatio - mRatio) < 0.01) return { x: 0, y: 0, w: cw, h: ch }
  if (mRatio > elRatio) {       // 媒体更宽：上下留黑边
    const w = cw, h = cw / mRatio
    return { x: 0, y: (ch - h) / 2, w, h }
  } else {                       // 媒体更高：左右留黑边
    const h = ch, w = ch * mRatio
    return { x: (cw - w) / 2, y: 0, w, h }
  }
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
  // 全屏 letterbox 修正：把框约束在视频实际显示区内
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
      type: 'video',
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

const togglePause = () => {
  const v = videoEl.value
  if (!v) return
  if (paused.value) {
    v.play()
    paused.value = false
    loop()
  } else {
    v.pause()
    paused.value = true
  }
}

const close = () => {
  if (loopTimer) { clearTimeout(loopTimer); loopTimer = null }
  if (runtimeTimer) { clearInterval(runtimeTimer); runtimeTimer = null }
  const v = videoEl.value
  if (v) { v.pause(); v.src = '' }
  if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null }
  running.value = false
  paused.value = false
  latestResultImg = ''
  latestBoxes = []
  drawBoxes([])
  risk.value = 'low'
  clsList.value = []
  // 关闭后舞台回到统一的电脑尺寸（16:9），避免上次手机视频的"细长框"残留
  stageAspect.value = '16 / 9'
}

const capture = () => {
  const v = videoEl.value
  if (!v || !v.videoWidth) return ElMessage.warning('暂无画面')
  const c = document.createElement('canvas')
  c.width = v.videoWidth
  c.height = v.videoHeight
  const ctx = c.getContext('2d')
  ctx.drawImage(v, 0, 0)
  if (latestBoxes.length) {
    _drawBoxesOnCtx(ctx, latestBoxes, c.width, c.height, 4, Math.round(c.height / 25), 0, 0)
  }
  const a = document.createElement('a')
  a.href = c.toDataURL('image/jpeg', 0.9)
  a.download = 'video_' + new Date().toISOString().slice(0, 19).replace(/:/g, '-') + '.jpg'
  a.click()
}

onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  close()
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
  /* aspect-ratio 由 :style 动态绑定（按视频真实比例） */
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
/* 全屏模式：舞台占满屏幕 */
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
.legacy-placeholder {
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
