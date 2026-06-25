<template>
  <el-card shadow="never" class="status-bar">
    <el-row :gutter="16">
      <!-- 左：抓拍墙（占主要视觉空间） -->
      <el-col :span="14">
        <div class="bar-title">
          <span><el-icon><Picture /></el-icon> 本次会话抓拍</span>
          <el-tag size="small" type="info">{{ snapshots.length }} 张</el-tag>
        </div>
        <div v-if="!snapshots.length" class="empty-state">
          <el-icon :size="36" class="empty-icon"><PictureFilled /></el-icon>
          <div class="empty-title">暂无抓拍</div>
          <div class="empty-desc">命中高/中危违规时按设定间隔自动抓拍</div>
        </div>
        <div v-else class="snap-strip">
          <div v-for="(s, i) in displaySnaps" :key="i" class="snap-card">
            <el-image
              :src="s.url"
              fit="cover"
              class="snap-img"
              :preview-src-list="allUrls"
              :initial-index="i"
              :preview-teleported="true"
            />
            <div class="snap-meta">
              <el-tag :type="riskColor(s.risk)" size="small" effect="dark">{{ riskZh(s.risk) }}</el-tag>
              <span class="snap-time">{{ s.time }}</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 中：4 项统计（2×2 紧凑卡片） -->
      <el-col :span="6">
        <div class="bar-title">
          <span><el-icon><DataAnalysis /></el-icon> 本次统计</span>
        </div>
        <div class="stat-grid">
          <div v-for="(s, i) in stats" :key="i" class="stat-item">
            <div class="stat-num">{{ s.value }}<span v-if="s.suffix" class="stat-suffix">{{ s.suffix }}</span></div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </div>
      </el-col>

      <!-- 右：类别时间轴（窄列） -->
      <el-col :span="4">
        <div class="bar-title">
          <span><el-icon><Clock /></el-icon> 近 60 秒类别</span>
        </div>
        <div v-if="!timeline.length" class="empty-state mini">
          <el-icon :size="24" class="empty-icon"><Clock /></el-icon>
          <div class="empty-desc">尚未检测到目标</div>
        </div>
        <div v-else class="timeline">
          <div v-for="(t, i) in recentTimeline" :key="i" class="tl-row">
            <span class="tl-time">{{ t.time }}</span>
            <div class="tl-tags">
              <el-tag
                v-for="(c, j) in t.classes"
                :key="j"
                :type="classColor(c)"
                size="small"
                effect="plain"
                style="margin: 1px"
              >{{ c }}</el-tag>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { Picture, PictureFilled, DataAnalysis, Clock } from '@element-plus/icons-vue'

const props = defineProps({
  snapshots: { type: Array, default: () => [] },
  stats:     { type: Array, default: () => [] },
  timeline:  { type: Array, default: () => [] },
})

const MAX_SNAPS = 8
const MAX_TIMELINE = 8

const displaySnaps = computed(() => props.snapshots.slice(0, MAX_SNAPS))
const allUrls = computed(() => props.snapshots.map((s) => s.url))
const recentTimeline = computed(() => props.timeline.slice(0, MAX_TIMELINE))

const HIGH = ['跌倒', '未戴安全帽', '吸烟']
const MID = ['打电话']
const classColor = (c) => (HIGH.includes(c) ? 'danger' : MID.includes(c) ? 'warning' : 'success')
const riskZh = (r) => ({ high: '高危', mid: '中危', low: '低危' }[r] || r)
const riskColor = (r) => ({ high: 'danger', mid: 'warning', low: 'success' }[r] || 'info')
</script>

<style scoped>
.status-bar { border-radius: 10px; }
.bar-title {
  font-weight: 600;
  color: #0a5a2c;
  font-size: 14px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 6px;
  border-bottom: 1px dashed #e8eef0;
}
.bar-title :deep(.el-icon) { margin-right: 4px; vertical-align: middle; }

/* ==== 抓拍墙 ==== */
.snap-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  min-height: 180px;
}
.snap-card {
  border: 1px solid #eee;
  border-radius: 6px;
  overflow: hidden;
  background: #fafafa;
  display: flex;
  flex-direction: column;
}
.snap-img { width: 100%; height: 90px; cursor: zoom-in; display: block; }
.snap-meta {
  padding: 4px 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #888;
}
.snap-time { font-family: Consolas, monospace; }

/* ==== 统计 2×2 ==== */
.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 8px;
  min-height: 180px;
}
.stat-item {
  background: linear-gradient(135deg, #f6fbf7 0%, #fafbfc 100%);
  border: 1px solid #e8eef0;
  border-radius: 6px;
  padding: 8px 10px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.stat-num {
  font-size: 20px;
  font-weight: bold;
  color: #0a5a2c;
  font-family: Consolas, monospace;
  line-height: 1.1;
}
.stat-suffix {
  font-size: 11px;
  color: #888;
  margin-left: 2px;
  font-weight: normal;
}
.stat-label {
  font-size: 11px;
  color: #888;
  margin-top: 4px;
}

/* ==== 时间轴 ==== */
.timeline {
  max-height: 180px;
  overflow-y: auto;
  font-size: 12px;
  padding-right: 4px;
}
.tl-row {
  padding: 4px 0;
  border-bottom: 1px dashed #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.tl-time { color: #888; font-family: Consolas, monospace; font-size: 11px; }
.tl-tags { display: flex; flex-wrap: wrap; gap: 2px; }

/* ==== 空状态 ==== */
.empty-state {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #fafbfc;
  border: 1px dashed #e8eef0;
  border-radius: 8px;
  color: #aaa;
  text-align: center;
}
.empty-state.mini {
  min-height: 180px;
  gap: 4px;
}
.empty-icon { color: #d0d6df; }
.empty-title { font-size: 14px; color: #888; }
.empty-desc { font-size: 12px; color: #b0b6bc; padding: 0 8px; }
</style>
