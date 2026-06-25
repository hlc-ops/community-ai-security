<template>
  <div class="cockpit">
    <!-- 顶部 -->
    <div class="header">
      <div class="title">🏗️ 工地安防 · AI 指挥中心</div>
      <div class="clock">{{ clock }}</div>
      <el-button class="exit-btn" plain @click="exit">退出大屏</el-button>
    </div>

    <!-- KPI -->
    <div class="kpi-row">
      <div class="kpi score-kpi" :style="{ borderColor: scoreColor + '80' }">
        <div class="num" :style="{ color: scoreColor }">{{ score.score }}<span class="num-of">/100</span></div>
        <div class="lab">工地安全指数 · <span :style="{ color: scoreColor }">{{ score.grade }}</span></div>
      </div>
      <div class="kpi"><div class="num">{{ stats.total }}</div><div class="lab">累计告警</div></div>
      <div class="kpi danger"><div class="num">{{ stats.byRisk?.high || 0 }}</div><div class="lab">高危事件</div></div>
      <div class="kpi warn"><div class="num">{{ stats.pending }}</div><div class="lab">待处理</div></div>
      <div class="kpi ok"><div class="num">{{ onlineCams }}/{{ totalCams }}</div><div class="lab">在线摄像头</div></div>
    </div>

    <div class="main-grid">
      <!-- 左：实时告警流 -->
      <div class="panel">
        <div class="panel-title">⚠️ 实时告警流</div>
        <div class="alert-stream">
          <div v-if="!alerts.length" class="empty">暂无告警</div>
          <transition-group name="slide" tag="div">
            <div
              v-for="a in alerts" :key="a.key"
              class="alert-item"
              :class="a.risk"
            >
              <div class="alert-time">{{ a.timeShort }}</div>
              <div class="alert-body">
                <span class="risk-tag">{{ a.riskZh }}</span>
                <span class="alert-cls">{{ a.cls }}</span>
                <span class="alert-source">来源：{{ a.typeZh }}</span>
              </div>
            </div>
          </transition-group>
        </div>
      </div>

      <!-- 中：趋势图 -->
      <div class="panel">
        <div class="panel-title">📈 近 7 天告警趋势</div>
        <BaseChart v-if="stats.trend?.length" :option="trendOption" />
      </div>

      <!-- 右：违规类别 -->
      <div class="panel">
        <div class="panel-title">🎯 违规类别分布</div>
        <BaseChart v-if="classCount" :option="classOption" />
        <div v-else class="empty">暂无数据</div>
      </div>
    </div>

    <!-- 底部 -->
    <div class="bottom-grid">
      <div class="panel">
        <div class="panel-title">📹 摄像头状态</div>
        <div class="cam-list">
          <div v-for="c in cams" :key="c.id" class="cam-item" :class="{ on: c.online }">
            <span class="cam-dot"></span>
            <span class="cam-name">{{ c.name }}</span>
            <span class="cam-loc">{{ c.location || '—' }}</span>
            <span class="cam-state">{{ c.online ? '在线' : (c.error ? '异常' : '离线') }}</span>
          </div>
          <div v-if="!cams.length" class="empty">尚未登记摄像头</div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title">🏆 高频违规 TOP 5</div>
        <div class="rank-list">
          <div v-for="(c, i) in topClasses" :key="c.name" class="rank-item">
            <span class="rank-no">{{ i + 1 }}</span>
            <span class="rank-name">{{ c.name }}</span>
            <div class="rank-bar"><div class="rank-fill" :style="{ width: c.pct + '%' }"></div></div>
            <span class="rank-cnt">{{ c.count }}</span>
          </div>
          <div v-if="!topClasses.length" class="empty">暂无数据</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import BaseChart from '@/components/BaseChart.vue'
import { fetchStats } from '@/api/records'
import { fetchSafetyScore } from '@/api/reports'
import { fetchCameras } from '@/api/cameras'
import { useAuthStore } from '@/store/auth'
import { fmtTimeShort } from '@/utils/datetime'

const router = useRouter()
const auth = useAuthStore()

const stats = reactive({ total: 0, pending: 0, byRisk: {}, byType: {}, byClass: {}, trend: [] })
const score = reactive({ score: 100, grade: '优秀', gradeColor: 'success', components: {} })
const cams = ref([])
const alerts = ref([])
const clock = ref('')

const classCount = computed(() => Object.keys(stats.byClass || {}).length)
const onlineCams = computed(() => cams.value.filter((c) => c.online).length)
const totalCams = computed(() => cams.value.length)
const topClasses = computed(() => {
  const arr = Object.entries(stats.byClass || {}).map(([name, count]) => ({ name, count }))
  arr.sort((a, b) => b.count - a.count)
  const max = arr[0]?.count || 1
  return arr.slice(0, 5).map((c) => ({ ...c, pct: Math.round((c.count / max) * 100) }))
})

const trendOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis' },
  legend: { data: ['总数', '高危'], textStyle: { color: '#a5dcff' } },
  grid: { left: 36, right: 16, top: 32, bottom: 26 },
  xAxis: {
    type: 'category', data: (stats.trend || []).map((t) => t.date),
    axisLine: { lineStyle: { color: '#2a4a66' } }, axisLabel: { color: '#a5dcff' },
  },
  yAxis: {
    type: 'value', minInterval: 1,
    axisLine: { lineStyle: { color: '#2a4a66' } }, axisLabel: { color: '#a5dcff' },
    splitLine: { lineStyle: { color: 'rgba(80,120,160,0.2)' } },
  },
  series: [
    { name: '总数', type: 'line', smooth: true, data: (stats.trend || []).map((t) => t.total),
      itemStyle: { color: '#00ffd1' }, areaStyle: { color: 'rgba(0,255,209,0.18)' } },
    { name: '高危', type: 'line', smooth: true, data: (stats.trend || []).map((t) => t.high),
      itemStyle: { color: '#ff4d6d' } },
  ],
}))

const classOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, textStyle: { color: '#a5dcff' } },
  series: [{
    type: 'pie', radius: ['40%', '65%'], center: ['50%', '45%'],
    data: Object.entries(stats.byClass || {}).map(([name, value]) => ({ name, value })),
    label: { color: '#dff5ff', formatter: '{b}:{c}' },
    itemStyle: { borderColor: '#0a1929', borderWidth: 2 },
  }],
}))

const RISK_ZH = { high: '高危', mid: '中危', low: '低危' }
const TYPE_ZH = { img: '图片', video: '视频', camera: '实时/摄像头' }

const formatAlert = (r) => ({
  key: r.id + ':' + Date.now() + Math.random(),
  risk: r.risk,
  riskZh: RISK_ZH[r.risk] || r.risk,
  cls: (r.clsList || []).join('、') || '违规',
  typeZh: TYPE_ZH[r.type] || r.type,
  timeShort: fmtTimeShort(r.createdAt),
})

const pushAlert = (a) => {
  alerts.value.unshift(a)
  if (alerts.value.length > 12) alerts.value.length = 12
}

const load = async () => {
  try { Object.assign(stats, await fetchStats()) } catch (e) {}
  try { Object.assign(score, await fetchSafetyScore('day')) } catch (e) {}
  try { cams.value = (await fetchCameras()).items } catch (e) {}
}
const scoreColor = computed(() => {
  if (score.score >= 95) return '#00ffd1'
  if (score.score >= 85) return '#5cff8a'
  if (score.score >= 70) return '#ffb84d'
  return '#ff4d6d'
})

let es = null
let timer = null
let clockTimer = null

const updateClock = () => {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  clock.value = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const exit = () => router.push({ name: 'dashboard' })

onMounted(() => {
  load()
  timer = setInterval(load, 10000)
  updateClock(); clockTimer = setInterval(updateClock, 1000)
  if (auth.token) {
    es = new EventSource(`/api/events/stream?token=${encodeURIComponent(auth.token)}`)
    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data)
        if (evt.type === 'alert') {
          pushAlert(formatAlert(evt.data))
          // 大屏上即时刷新一次 KPI
          load()
        }
      } catch (err) { /* ignore */ }
    }
  }
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (clockTimer) clearInterval(clockTimer)
  if (es) es.close()
})
</script>

<style scoped>
.cockpit {
  position: fixed; inset: 0;
  background: radial-gradient(ellipse at top, #0e2d52 0%, #061121 100%);
  color: #dff5ff;
  font-family: 'Microsoft YaHei', system-ui, sans-serif;
  padding: 16px 24px;
  display: flex; flex-direction: column; gap: 14px;
  overflow: auto;
}
.header {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(120, 200, 255, 0.15);
}
.title { font-size: 28px; font-weight: bold; color: #00ffd1; letter-spacing: 2px; }
.clock { font-size: 22px; font-family: Consolas, monospace; color: #a5dcff; }
.exit-btn { color: #dff5ff; border-color: rgba(120,200,255,0.4); background: transparent; }
.kpi-row { display: grid; grid-template-columns: 1.3fr 1fr 1fr 1fr 1fr; gap: 14px; }
.kpi.score-kpi {
  background: linear-gradient(180deg, rgba(0,255,209,0.12), rgba(0,255,209,0.02));
  border-width: 2px;
}
.kpi .num-of { font-size: 18px; color: #677; margin-left: 2px; }
.kpi {
  background: linear-gradient(180deg, rgba(0,255,209,0.08), rgba(0,255,209,0.02));
  border: 1px solid rgba(0,255,209,0.25);
  border-radius: 10px;
  padding: 18px 22px;
  display: flex; flex-direction: column; align-items: center;
}
.kpi.danger { border-color: rgba(255,77,109,0.5); background: linear-gradient(180deg, rgba(255,77,109,0.1), rgba(255,77,109,0.02)); }
.kpi.warn { border-color: rgba(255,184,77,0.5); background: linear-gradient(180deg, rgba(255,184,77,0.1), rgba(255,184,77,0.02)); }
.kpi.ok { border-color: rgba(92,255,138,0.4); background: linear-gradient(180deg, rgba(92,255,138,0.08), rgba(92,255,138,0.02)); }
.kpi .num { font-size: 42px; font-weight: bold; color: #00ffd1; font-family: Consolas, monospace; }
.kpi.danger .num { color: #ff7088; }
.kpi.warn .num { color: #ffb84d; }
.kpi.ok .num { color: #5cff8a; }
.kpi .lab { margin-top: 6px; color: #a5dcff; font-size: 14px; letter-spacing: 1px; }

.main-grid {
  display: grid; grid-template-columns: 1.2fr 1.4fr 1.2fr; gap: 14px; flex: 1; min-height: 320px;
}
.bottom-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 14px; min-height: 220px; }
.panel {
  background: rgba(10, 35, 65, 0.55);
  border: 1px solid rgba(120,200,255,0.18);
  border-radius: 10px;
  padding: 14px 18px;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.panel-title { color: #00ffd1; font-size: 16px; margin-bottom: 10px; letter-spacing: 1px; }

.alert-stream { flex: 1; overflow-y: auto; }
.alert-item {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 10px; margin-bottom: 6px;
  border-radius: 6px;
  background: rgba(255,77,109,0.08);
  border-left: 3px solid #ff4d6d;
}
.alert-item.mid { background: rgba(255,184,77,0.08); border-left-color: #ffb84d; }
.alert-item.low { background: rgba(92,255,138,0.06); border-left-color: #5cff8a; }
.alert-time { font-family: Consolas, monospace; color: #a5dcff; font-size: 13px; min-width: 70px; }
.alert-body { display: flex; gap: 8px; align-items: center; font-size: 14px; flex: 1; flex-wrap: wrap; }
.risk-tag {
  background: #ff4d6d; color: white; font-size: 12px; padding: 2px 8px; border-radius: 3px;
}
.alert-item.mid .risk-tag { background: #ffb84d; color: #2a1a00; }
.alert-item.low .risk-tag { background: #5cff8a; color: #003322; }
.alert-cls { color: #fff; font-weight: 600; }
.alert-source { color: #a5dcff; font-size: 12px; margin-left: auto; }
.slide-enter-active { transition: all .35s ease; }
.slide-enter-from { opacity: 0; transform: translateX(-30px); }

.cam-list { flex: 1; overflow-y: auto; }
.cam-item {
  display: grid; grid-template-columns: 16px 1fr 1fr auto; align-items: center; gap: 10px;
  padding: 8px 4px; border-bottom: 1px dashed rgba(120,200,255,0.12); font-size: 14px;
}
.cam-dot { width: 10px; height: 10px; border-radius: 50%; background: #555; }
.cam-item.on .cam-dot { background: #5cff8a; box-shadow: 0 0 8px #5cff8a; }
.cam-name { color: #fff; }
.cam-loc { color: #a5dcff; font-size: 13px; }
.cam-state { color: #888; font-size: 13px; }
.cam-item.on .cam-state { color: #5cff8a; }

.rank-list { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.rank-item { display: grid; grid-template-columns: 24px 80px 1fr 50px; align-items: center; gap: 8px; }
.rank-no {
  font-weight: bold; text-align: center;
  background: linear-gradient(180deg, #00ffd1, #00aa88); color: #002b22;
  border-radius: 4px; padding: 1px 0;
}
.rank-name { color: #fff; font-size: 14px; }
.rank-bar { background: rgba(120,200,255,0.1); height: 12px; border-radius: 6px; overflow: hidden; }
.rank-fill { height: 100%; background: linear-gradient(90deg, #00ffd1, #00aaff); }
.rank-cnt { text-align: right; font-family: Consolas, monospace; color: #00ffd1; }

.empty { color: #678; text-align: center; padding: 20px; }
</style>
