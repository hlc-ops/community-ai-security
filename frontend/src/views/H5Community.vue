<template>
  <div class="h5">
    <!-- 顶部 Hero -->
    <div class="hero">
      <div class="hero-bg"></div>
      <div class="hero-content">
        <div class="hero-eyebrow">SMART COMMUNITY</div>
        <div class="hero-title">{{ overview.communityName || '智慧社区' }}</div>
        <div class="hero-score">
          <div class="score-circle" :style="{ borderColor: overview.gradeColor }">
            <div class="score-num" :style="{ color: overview.gradeColor }">
              <CountUp :value="overview.score || 0" />
            </div>
            <div class="score-of">/100</div>
          </div>
          <div class="score-meta">
            <div class="score-label">社区安全指数</div>
            <div class="score-grade" :style="{ color: overview.gradeColor }">
              · {{ overview.grade || '良好' }}
            </div>
            <div class="score-time">{{ relativeTime(overview.updatedAt) }} · 实时更新</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 4 卡数据 -->
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-icon green">
          <el-icon><Van /></el-icon>
        </div>
        <div class="metric-body">
          <div class="metric-label">剩余车位</div>
          <div class="metric-num">
            <CountUp :value="overview.parking?.available || 0" />
            <span class="metric-of">/ {{ overview.parking?.total || 0 }}</span>
          </div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon blue">
          <el-icon><Bell /></el-icon>
        </div>
        <div class="metric-body">
          <div class="metric-label">今日事件</div>
          <div class="metric-num">
            <CountUp :value="overview.today?.total || 0" />
          </div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon gold">
          <el-icon><Monitor /></el-icon>
        </div>
        <div class="metric-body">
          <div class="metric-label">在线摄像头</div>
          <div class="metric-num">
            <CountUp :value="overview.cameras?.online || 0" />
            <span class="metric-of">/ {{ overview.cameras?.total || 0 }}</span>
          </div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon purple">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="metric-body">
          <div class="metric-label">已处理</div>
          <div class="metric-num">
            <CountUp :value="overview.today?.processed || 0" />
          </div>
        </div>
      </div>
    </div>

    <!-- 车位余量进度条 -->
    <div class="section">
      <div class="section-title">
        <el-icon><Van /></el-icon>
        <span>车位余量</span>
        <span class="section-tag">实时</span>
      </div>
      <div class="parking-bar">
        <div class="parking-text">
          <span class="big-num">{{ overview.parking?.available || 0 }}</span>
          <span class="big-sub">个车位空闲</span>
        </div>
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{
              width: parkingUsageWidth + '%',
              background: parkingUsageColor,
            }"
          ></div>
        </div>
        <div class="progress-meta">
          <span>占用率 {{ parkingUsage.toFixed(1) }}%</span>
          <span>{{ overview.parking?.total || 0 }} 个总车位</span>
        </div>
      </div>
    </div>

    <!-- 事件列表 -->
    <div class="section">
      <div class="section-title">
        <el-icon><List /></el-icon>
        <span>近期事件</span>
        <span class="section-tag">{{ events.length }} 条</span>
      </div>
      <div v-if="!events.length" class="empty">暂无事件</div>
      <div v-else class="event-list">
        <div
          v-for="ev in events"
          :key="ev.id"
          class="event-item"
          :class="`risk-${ev.risk}`"
        >
          <div class="event-icon">
            <el-icon v-if="ev.risk === 'high'"><Warning /></el-icon>
            <el-icon v-else><Bell /></el-icon>
          </div>
          <div class="event-body">
            <div class="event-head">
              <span class="event-type">{{ ev.typeZh }}</span>
              <span class="event-time">{{ relativeTime(ev.createdAt) }}</span>
            </div>
            <div class="event-meta">
              <span class="risk-tag" :class="`risk-${ev.risk}`">{{ ev.riskZh }}</span>
              <span class="status-tag" :class="`status-${ev.status}`">{{ ev.statusZh }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 反馈入口 -->
    <div class="section feedback-card" @click="openFeedback">
      <el-icon class="fb-icon"><ChatLineRound /></el-icon>
      <div class="fb-body">
        <div class="fb-title">报修 · 投诉 · 建议</div>
        <div class="fb-desc">物业 30 分钟内响应</div>
      </div>
      <el-icon class="fb-arrow"><ArrowRight /></el-icon>
    </div>

    <!-- 底部 -->
    <div class="footer">
      <div>© 2026 {{ overview.communityName || '智慧社区' }}</div>
      <div class="powered">Powered by YOLO + LLM</div>
    </div>

    <!-- 反馈对话框 -->
    <el-dialog
      v-model="feedbackVisible"
      title="提交反馈"
      width="92%"
      class="h5-dialog"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-position="top">
        <el-form-item label="您的姓名(选填)">
          <el-input v-model="form.name" placeholder="例如:张先生" maxlength="32" />
        </el-form-item>
        <el-form-item label="联系方式(选填)">
          <el-input v-model="form.contact" placeholder="手机号或微信" maxlength="64" />
        </el-form-item>
        <el-form-item label="问题描述" required>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="5"
            placeholder="例如:3 号楼电梯按钮坏了..."
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feedbackVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitFeedback">
          提交
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import {
  Van, Bell, Monitor, CircleCheck, Warning, List,
  ChatLineRound, ArrowRight,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import CountUp from '@/components/CountUp.vue'
import request from '@/api/request'

const overview = ref({})
const events = ref([])
const feedbackVisible = ref(false)
const submitting = ref(false)
const form = reactive({ name: '', contact: '', content: '' })

const parkingUsage = computed(() => {
  const p = overview.value?.parking
  if (!p || !p.total) return 0
  return (p.occupied / p.total) * 100
})
const parkingUsageWidth = computed(() => Math.max(2, parkingUsage.value))
const parkingUsageColor = computed(() => {
  const u = parkingUsage.value
  if (u < 60) return 'linear-gradient(90deg, #16b3a8, #138c84)'
  if (u < 85) return 'linear-gradient(90deg, #f59e0b, #ea580c)'
  return 'linear-gradient(90deg, #ef4444, #dc2626)'
})

const loadOverview = async () => {
  try {
    const res = await request.get('/public/overview')
    overview.value = res.data
  } catch (e) { /* ignore */ }
}
const loadEvents = async () => {
  try {
    const res = await request.get('/public/events', { params: { limit: 8 } })
    events.value = res.data
  } catch (e) { /* ignore */ }
}

const openFeedback = () => {
  Object.assign(form, { name: '', contact: '', content: '' })
  feedbackVisible.value = true
}

const submitFeedback = async () => {
  if (!form.content.trim()) {
    return ElMessage.warning('请填写问题描述')
  }
  submitting.value = true
  try {
    const res = await request.post('/public/feedback', { ...form })
    ElMessage.success(res.msg || '提交成功')
    feedbackVisible.value = false
  } catch (e) { /* ignore */ }
  finally { submitting.value = false }
}

const relativeTime = (iso) => {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  const sec = Math.max(0, (Date.now() - t) / 1000)
  if (sec < 60) return '刚刚'
  if (sec < 3600) return `${Math.floor(sec / 60)} 分钟前`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时前`
  return `${Math.floor(sec / 86400)} 天前`
}

let timer = null
onMounted(() => {
  loadOverview()
  loadEvents()
  // 30 秒自动刷新
  timer = setInterval(() => {
    loadOverview()
    loadEvents()
  }, 30000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.h5 {
  min-height: 100vh;
  background: #fafbfc;
  color: #0f172a;
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  padding-bottom: 80px;
  /* 屏蔽外部布局影响 */
  margin: -28px -32px -100px -32px;
}

/* === Hero === */
.hero {
  position: relative;
  padding: 32px 20px 28px;
  overflow: hidden;
}
.hero-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, #16b3a8 0%, #0e7a73 100%);
  border-radius: 0 0 28px 28px;
}
.hero-bg::after {
  content: '';
  position: absolute;
  top: -40px; right: -40px;
  width: 220px; height: 220px;
  background: radial-gradient(circle, rgba(255,255,255,0.25), transparent 70%);
  border-radius: 50%;
}
.hero-content {
  position: relative;
  z-index: 1;
  color: white;
}
.hero-eyebrow {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2px;
  opacity: 0.85;
  font-family: "JetBrains Mono", monospace;
}
.hero-title {
  font-size: 22px;
  font-weight: 600;
  margin-top: 6px;
  letter-spacing: -0.3px;
}
.hero-score {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 20px;
  background: rgba(255,255,255,0.15);
  backdrop-filter: blur(12px);
  border-radius: 16px;
  padding: 14px 16px;
  border: 1px solid rgba(255,255,255,0.2);
}
.score-circle {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  border: 3px solid #fff;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.score-num {
  font-family: "JetBrains Mono", monospace;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -1px;
  line-height: 1;
}
.score-of {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}
.score-meta {
  flex: 1;
}
.score-label {
  font-size: 13px;
  opacity: 0.9;
}
.score-grade {
  font-size: 18px;
  font-weight: 600;
  margin-top: 2px;
}
.score-time {
  font-size: 11px;
  opacity: 0.8;
  margin-top: 4px;
}

/* === 4 卡 === */
.metric-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 0 16px;
  margin-top: -12px;
  position: relative;
  z-index: 2;
}
.metric-card {
  background: #fff;
  border-radius: 14px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
  border: 1px solid #f1f5f9;
}
.metric-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.metric-icon.green { background: rgba(22, 179, 168, 0.12); color: #16b3a8; }
.metric-icon.blue { background: rgba(59, 130, 246, 0.12); color: #3b82f6; }
.metric-icon.gold { background: rgba(245, 158, 11, 0.12); color: #f59e0b; }
.metric-icon.purple { background: rgba(139, 92, 246, 0.12); color: #8b5cf6; }
.metric-label {
  font-size: 12px;
  color: #94a3b8;
}
.metric-num {
  font-family: "JetBrains Mono", monospace;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.5px;
  margin-top: 2px;
}
.metric-of {
  font-size: 12px;
  color: #94a3b8;
  margin-left: 4px;
  font-weight: 400;
}

/* === Section === */
.section {
  margin: 24px 16px 0;
  background: #fff;
  border-radius: 14px;
  padding: 16px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.03);
}
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 14px;
}
.section-title .el-icon { color: #16b3a8; }
.section-tag {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 400;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

/* === Parking === */
.parking-text {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 12px;
}
.big-num {
  font-family: "JetBrains Mono", monospace;
  font-size: 38px;
  font-weight: 700;
  color: #16b3a8;
  letter-spacing: -1px;
}
.big-sub {
  color: #475569;
  font-size: 14px;
}
.progress-bar {
  height: 10px;
  background: #f1f5f9;
  border-radius: 5px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 5px;
  transition: width 600ms cubic-bezier(0.16, 1, 0.3, 1);
}
.progress-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11px;
  color: #94a3b8;
  font-family: "JetBrains Mono", monospace;
}

/* === 事件列表 === */
.empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px 0;
  font-size: 13px;
}
.event-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.event-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: #fafbfc;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
}
.event-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  font-size: 16px;
}
.event-item.risk-high .event-icon {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.event-item.risk-mid .event-icon {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}
.event-body { flex: 1; min-width: 0; }
.event-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.event-type {
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
}
.event-time {
  font-size: 11px;
  color: #94a3b8;
  font-family: "JetBrains Mono", monospace;
}
.event-meta {
  display: flex;
  gap: 6px;
}
.risk-tag, .status-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
}
.risk-tag.risk-high { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.risk-tag.risk-mid { background: rgba(245, 158, 11, 0.1); color: #f59e0b; }
.risk-tag.risk-low { background: rgba(22, 179, 168, 0.1); color: #16b3a8; }
.status-tag.status-pending { background: #f1f5f9; color: #64748b; }
.status-tag.status-processed { background: rgba(22, 179, 168, 0.1); color: #16b3a8; }
.status-tag.status-processing { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }

/* === 反馈卡 === */
.feedback-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(135deg, #16b3a8, #138c84);
  color: white;
  cursor: pointer;
  transition: transform 0.2s ease;
}
.feedback-card:active { transform: scale(0.98); }
.fb-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  background: rgba(255,255,255,0.2);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px;
}
.fb-body { flex: 1; }
.fb-title { font-size: 15px; font-weight: 600; }
.fb-desc { font-size: 12px; opacity: 0.85; margin-top: 2px; }
.fb-arrow { font-size: 16px; opacity: 0.7; }

/* === 底部 === */
.footer {
  text-align: center;
  color: #94a3b8;
  font-size: 11px;
  margin-top: 28px;
  line-height: 1.8;
}
.powered {
  font-family: "JetBrains Mono", monospace;
  letter-spacing: 0.5px;
  opacity: 0.7;
}
</style>
