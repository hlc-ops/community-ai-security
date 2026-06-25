<template>
  <div class="dashboard">
    <!-- 顶部欢迎 + 状态条 -->
    <div class="welcome-bar">
      <div>
        <div class="welcome-eyebrow">PROPERTY INSIGHT</div>
        <h1 class="welcome-title">
          {{ greeting }}
          <span class="welcome-name">{{ auth.user?.realName || auth.user?.username }}</span>
        </h1>
        <p class="welcome-sub">{{ todayStr }} · 社区运行状态实时监控</p>
      </div>
      <div class="status-summary">
        <StatusBeacon status="online" :label="`${activeStreams} 路在线`" />
      </div>
    </div>

    <!-- 安全指数主卡 -->
    <PremiumCard class="score-card" :hoverable="false">
      <div class="score-grid">
        <div class="score-block">
          <div class="block-eyebrow">SAFETY INDEX</div>
          <div class="score-num" :style="{ color: scoreColor }">
            <CountUp :value="score.score" :duration="1200" />
            <span class="score-of">/100</span>
          </div>
          <div class="score-grade">
            <span class="score-dot" :style="{ background: scoreColor, boxShadow: `0 0 12px ${scoreColor}` }"></span>
            <span class="score-grade-text">{{ score.grade }}</span>
          </div>
        </div>
        <div class="score-trend">
          <div class="block-eyebrow">7-DAY TREND</div>
          <BaseChart v-if="score.trend?.length" :option="scoreTrendOption" style="height:110px" />
        </div>
        <div class="score-components">
          <div class="comp-item">
            <span class="comp-k">高危事件</span>
            <b class="comp-v danger">
              <CountUp :value="score.components?.high || 0" />
            </b>
          </div>
          <div class="comp-item">
            <span class="comp-k">中危事件</span>
            <b class="comp-v warn">
              <CountUp :value="score.components?.mid || 0" />
            </b>
          </div>
          <div class="comp-item">
            <span class="comp-k">已处理</span>
            <b class="comp-v ok">
              <CountUp :value="score.components?.processed || 0" />
            </b>
          </div>
          <div class="comp-item">
            <span class="comp-k">待办</span>
            <b class="comp-v">
              <CountUp :value="score.components?.pending || 0" />
            </b>
          </div>
        </div>
      </div>
    </PremiumCard>

    <!-- 4 个数据卡 -->
    <div class="stat-row">
      <PremiumCard class="stat-card" glow-color="rgba(78, 205, 196, 0.15)">
        <div class="stat-icon">
          <el-icon><Document /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">累计事件</div>
          <div class="stat-num">
            <CountUp :value="stats.total" />
          </div>
          <div class="stat-foot">全部已归档</div>
        </div>
      </PremiumCard>

      <PremiumCard class="stat-card" glow-color="rgba(255, 183, 77, 0.15)">
        <div class="stat-icon warn">
          <el-icon><Clock /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">待处理</div>
          <div class="stat-num warn">
            <CountUp :value="stats.pending" />
          </div>
          <div class="stat-foot">需要物业关注</div>
        </div>
      </PremiumCard>

      <PremiumCard class="stat-card" glow-color="rgba(255, 84, 112, 0.15)">
        <div class="stat-icon danger">
          <el-icon><Warning /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">高危事件</div>
          <div class="stat-num danger">
            <CountUp :value="stats.byRisk?.high || 0" />
          </div>
          <div class="stat-foot">重点跟进</div>
        </div>
      </PremiumCard>

      <PremiumCard class="stat-card" glow-color="rgba(91, 155, 255, 0.15)">
        <div class="stat-icon info">
          <el-icon><Histogram /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">违规类型</div>
          <div class="stat-num">
            <CountUp :value="classCount" />
          </div>
          <div class="stat-foot">覆盖 {{ classCount }} 类场景</div>
        </div>
      </PremiumCard>
    </div>

    <!-- 图表区 1:趋势 + 类别 -->
    <div class="chart-row">
      <PremiumCard title="近 7 天事件趋势" class="trend-card">
        <template #extra>
          <el-button text type="primary" @click="loadStats" :icon="Refresh">刷新</el-button>
        </template>
        <BaseChart v-if="hasData" :option="trendOption" style="height: 280px" />
        <el-empty v-else description="暂无数据" :image-size="80" />
      </PremiumCard>

      <PremiumCard title="违规类别分布">
        <BaseChart v-if="classCount" :option="classOption" style="height: 280px" />
        <el-empty v-else description="暂无数据" :image-size="80" />
      </PremiumCard>
    </div>

    <!-- 图表区 2:来源(大) + 风险(小) -->
    <div class="chart-row">
      <PremiumCard title="检测来源分布" class="trend-card">
        <BaseChart v-if="hasData" :option="typeOption" style="height: 260px" />
        <el-empty v-else description="暂无数据" :image-size="80" />
      </PremiumCard>

      <PremiumCard title="风险等级占比">
        <BaseChart v-if="hasData" :option="riskOption" style="height: 260px" />
        <el-empty v-else description="暂无数据" :image-size="80" />
      </PremiumCard>
    </div>

    <!-- 热力图 -->
    <PremiumCard title="事件热力图" subtitle="近 30 天 · 时段 × 类别(越深说明该时段该类违规越集中)">
      <BaseChart v-if="heatData.data.length" :option="heatmapOption" style="height: 400px" />
      <el-empty v-else description="暂无足够数据生成热力图" :image-size="80" />
    </PremiumCard>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Document, Clock, Warning, Histogram, Refresh } from '@element-plus/icons-vue'
import { fetchStats } from '@/api/records'
import { fetchSafetyScore, fetchHeatmap } from '@/api/reports'
import BaseChart from '@/components/BaseChart.vue'
import PremiumCard from '@/components/PremiumCard.vue'
import CountUp from '@/components/CountUp.vue'
import StatusBeacon from '@/components/StatusBeacon.vue'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

const stats = reactive({ total: 0, pending: 0, byRisk: {}, byType: {}, byClass: {}, trend: [] })
const score = reactive({ score: 100, grade: '优秀', gradeColor: 'success', components: {}, trend: [] })
const heatData = ref({ xLabels: [], yLabels: [], data: [], max: 1 })
const activeStreams = ref(0)
const classCount = computed(() => Object.keys(stats.byClass || {}).length)
const hasData = computed(() => stats.total > 0)

const todayStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好,'
  if (h < 12) return '早上好,'
  if (h < 14) return '中午好,'
  if (h < 18) return '下午好,'
  return '晚上好,'
})

const scoreColor = computed(() => {
  if (score.score >= 95) return '#16b3a8'
  if (score.score >= 85) return '#3b82f6'
  if (score.score >= 70) return '#f59e0b'
  return '#ef4444'
})

const loadStats = async () => {
  try { Object.assign(stats, await fetchStats()) } catch (e) {}
  try { Object.assign(score, await fetchSafetyScore('day')) } catch (e) {}
  try {
    const h = await fetchHeatmap('hour', 30)
    let max = 1
    for (const [, , v] of h.data) if (v > max) max = v
    heatData.value = { ...h, max }
  } catch (e) {}
}

// ECharts 亮色主题统一配置
const chartTheme = {
  textColor: '#475569',
  axisColor: '#e5e7eb',
  splitColor: '#f1f5f9',
}
const TOOLTIP_BASE = {
  backgroundColor: 'rgba(255, 255, 255, 0.98)',
  borderColor: '#e5e7eb',
  textStyle: { color: '#0f172a' },
  extraCssText: 'box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08); border-radius: 8px;',
}

const baseGrid = { left: 50, right: 24, top: 30, bottom: 36 }
const baseAxisStyle = {
  axisLine: { lineStyle: { color: chartTheme.axisColor } },
  axisLabel: { color: chartTheme.textColor, fontSize: 11 },
  splitLine: { lineStyle: { color: chartTheme.splitColor } },
}

// 近 7 天趋势
const trendOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    ...TOOLTIP_BASE,
  },
  legend: { data: ['事件总数', '高危'], bottom: 0, textStyle: { color: chartTheme.textColor } },
  grid: { ...baseGrid, bottom: 50 },
  xAxis: { type: 'category', data: (stats.trend || []).map((t) => t.date), ...baseAxisStyle },
  yAxis: { type: 'value', minInterval: 1, ...baseAxisStyle },
  series: [
    {
      name: '事件总数', type: 'line', smooth: true,
      data: (stats.trend || []).map((t) => t.total),
      lineStyle: { color: '#16b3a8', width: 2 },
      itemStyle: { color: '#16b3a8' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(22,179,168,0.25)' }, { offset: 1, color: 'rgba(22,179,168,0)' }],
        },
      },
      symbol: 'circle', symbolSize: 6,
    },
    {
      name: '高危', type: 'line', smooth: true,
      data: (stats.trend || []).map((t) => t.high),
      lineStyle: { color: '#ef4444', width: 2 },
      itemStyle: { color: '#ef4444' },
      symbol: 'circle', symbolSize: 6,
    },
  ],
}))

const classOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    ...TOOLTIP_BASE,
  },
  legend: { bottom: 0, textStyle: { color: chartTheme.textColor }, itemWidth: 10, itemHeight: 10 },
  series: [{
    type: 'pie', radius: ['50%', '72%'], center: ['50%', '45%'],
    data: Object.entries(stats.byClass || {}).map(([name, value]) => ({ name, value })),
    label: { color: chartTheme.textColor, fontSize: 11 },
    itemStyle: { borderColor: '#ffffff', borderWidth: 2 },
    color: ['#16b3a8', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#10b981', '#ec4899'],
  }],
}))

const RISK_ZH = { high: '高危', mid: '中危', low: '低危' }
const RISK_COLOR = { high: '#ef4444', mid: '#f59e0b', low: '#16b3a8' }
const riskOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    ...TOOLTIP_BASE,
  },
  legend: { bottom: 0, textStyle: { color: chartTheme.textColor }, itemWidth: 10, itemHeight: 10 },
  series: [{
    type: 'pie', radius: '65%', center: ['50%', '45%'],
    data: Object.entries(stats.byRisk || {}).map(([k, v]) => ({
      name: RISK_ZH[k] || k, value: v,
      itemStyle: { color: RISK_COLOR[k] },
    })),
    label: { color: chartTheme.textColor, fontSize: 11 },
    itemStyle: { borderColor: '#ffffff', borderWidth: 2 },
  }],
}))

const scoreTrendOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    ...TOOLTIP_BASE,
  },
  grid: { left: 36, right: 16, top: 12, bottom: 20 },
  xAxis: { type: 'category', data: (score.trend || []).map((t) => t.date), ...baseAxisStyle, axisLabel: { color: chartTheme.textColor, fontSize: 10 } },
  yAxis: { type: 'value', min: 0, max: 100, ...baseAxisStyle, axisLabel: { color: chartTheme.textColor, fontSize: 10 } },
  series: [{
    type: 'line', smooth: true,
    data: (score.trend || []).map((t) => t.score),
    lineStyle: { color: scoreColor.value, width: 2 },
    itemStyle: { color: scoreColor.value },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: `${scoreColor.value}40` },
          { offset: 1, color: `${scoreColor.value}00` },
        ],
      },
    },
    symbol: 'circle', symbolSize: 5,
  }],
}))

const heatmapOption = computed(() => ({
  tooltip: {
    position: 'top',
    ...TOOLTIP_BASE,
    formatter: (p) => `${heatData.value.yLabels[p.data[1]]} · ${heatData.value.xLabels[p.data[0]]}: ${p.data[2]} 次`,
  },
  grid: { left: 70, right: 24, top: 12, bottom: 40 },
  xAxis: { type: 'category', data: heatData.value.xLabels, ...baseAxisStyle, splitArea: { show: false } },
  yAxis: { type: 'category', data: heatData.value.yLabels, ...baseAxisStyle, splitArea: { show: false } },
  visualMap: {
    min: 0, max: heatData.value.max,
    calculable: true, orient: 'horizontal',
    left: 'center', bottom: 0,
    textStyle: { color: chartTheme.textColor, fontSize: 11 },
    inRange: { color: ['#f0fdfa', '#16b3a8', '#f59e0b', '#ef4444'] },
  },
  series: [{
    type: 'heatmap', data: heatData.value.data,
    itemStyle: { borderColor: '#ffffff', borderWidth: 1 },
  }],
}))

const TYPE_ZH = { img: '图像识别', video: '视频分析', camera: '实时监控' }
const typeOption = computed(() => {
  const entries = Object.entries(stats.byType || {})
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 32, 58, 0.95)',
      borderColor: 'rgba(78,205,196,0.3)',
      textStyle: { color: '#f1f5f9' },
    },
    grid: { ...baseGrid, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: entries.map(([k]) => TYPE_ZH[k] || k), ...baseAxisStyle },
    yAxis: { type: 'value', minInterval: 1, ...baseAxisStyle },
    series: [{
      type: 'bar', barWidth: '45%',
      data: entries.map(([, v]) => v),
      itemStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: '#16b3a8' }, { offset: 1, color: 'rgba(22,179,168,0.2)' }],
        },
        borderRadius: [6, 6, 0, 0],
      },
    }],
  }
})

onMounted(loadStats)
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  animation: fade-in-up 0.5s var(--ease-out) both;
}

/* ===== 欢迎条 ===== */
.welcome-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--divider);
}
.welcome-eyebrow {
  color: var(--brand);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 2px;
  font-family: var(--font-mono);
  margin-bottom: 8px;
}
.welcome-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.5px;
  line-height: 1.2;
}
.welcome-name {
  background: var(--brand-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.welcome-sub {
  color: var(--text-2);
  font-size: 14px;
  margin-top: 6px;
}

/* ===== 安全指数卡 ===== */
.score-card {
  padding: var(--space-2) 0;
}
.score-grid {
  display: grid;
  grid-template-columns: 1.1fr 1.4fr 1fr;
  gap: var(--space-6);
  padding: var(--space-2) var(--space-2);
}
.block-eyebrow {
  font-size: 10px;
  color: var(--text-3);
  font-weight: 600;
  letter-spacing: 1.5px;
  font-family: var(--font-mono);
  margin-bottom: 12px;
}
.score-num {
  font-size: 64px;
  font-weight: 600;
  font-family: var(--font-mono);
  line-height: 1;
  letter-spacing: -3px;
}
.score-of {
  font-size: 18px;
  color: var(--text-3);
  margin-left: 4px;
  font-weight: 400;
  letter-spacing: 0;
}
.score-grade {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.score-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
}
.score-grade-text {
  font-size: 13px;
  color: var(--text-2);
  font-weight: 500;
}
.score-trend {
  border-left: 1px solid var(--divider);
  padding-left: var(--space-5);
}
.score-components {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  padding-left: var(--space-5);
  border-left: 1px solid var(--divider);
  align-content: center;
}
.comp-item {
  background: var(--bg-overlay);
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}
.comp-k {
  display: block;
  font-size: 11px;
  color: var(--text-3);
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-bottom: 6px;
  font-weight: 500;
}
.comp-v {
  font-family: var(--font-mono);
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
}
.comp-v.danger { color: var(--danger); }
.comp-v.warn { color: var(--warning); }
.comp-v.ok { color: var(--success); }

/* ===== 数据卡片 ===== */
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.stat-card :deep(.card-body) {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-5);
}
.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 20px;
  flex-shrink: 0;
}
.stat-icon.warn { background: var(--warning-bg); color: var(--warning); }
.stat-icon.danger { background: var(--danger-bg); color: var(--danger); }
.stat-icon.info { background: var(--info-bg); color: var(--info); }

.stat-content { flex: 1; }
.stat-label {
  font-size: 12px;
  color: var(--text-3);
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 500;
  margin-bottom: 6px;
}
.stat-num {
  font-size: 32px;
  font-weight: 600;
  color: var(--text);
  font-family: var(--font-mono);
  letter-spacing: -1px;
  line-height: 1.1;
}
.stat-num.warn { color: var(--warning); }
.stat-num.danger { color: var(--danger); }
.stat-foot {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 6px;
}

/* ===== 图表行 ===== */
.chart-row {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: var(--space-4);
}
.chart-row .trend-card { grid-column: 1; }

@media (max-width: 1280px) {
  .stat-row { grid-template-columns: repeat(2, 1fr); }
  .score-grid { grid-template-columns: 1fr; }
  .score-trend, .score-components {
    border-left: none;
    padding-left: 0;
    border-top: 1px solid var(--divider);
    padding-top: var(--space-4);
  }
  .chart-row { grid-template-columns: 1fr; }
}
</style>
