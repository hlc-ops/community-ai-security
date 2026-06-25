<template>
  <div>
    <div class="page-title">报表导出</div>
    <div class="page-desc">按时间段汇总检测数据，预览后可一键导出 PDF 安全日报 / 周报。</div>

    <el-card shadow="never" class="bar-card">
      <div class="bar">
        <span class="lbl">统计周期</span>
        <el-date-picker
          v-model="range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          :shortcuts="shortcuts"
          @change="load"
        />
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
        <el-button type="success" :icon="Download" :loading="downloading" @click="download">导出 PDF</el-button>
      </div>
    </el-card>

    <div v-loading="loading">
      <el-row :gutter="20" style="margin-top: 16px">
        <el-col :span="6"><el-card shadow="hover" class="stat"><div class="num">{{ s.total }}</div><div class="lab">检测总数</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat"><div class="num danger">{{ s.byRisk?.['高危'] || 0 }}</div><div class="lab">高危事件</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat"><div class="num warn">{{ s.pending }}</div><div class="lab">未处理</div></el-card></el-col>
        <el-col :span="6"><el-card shadow="hover" class="stat"><div class="num">{{ s.processed }}</div><div class="lab">已处理</div></el-card></el-col>
      </el-row>

      <!-- AI 智能日报 -->
      <el-card shadow="never" class="ai-card" style="margin-top: 16px">
        <template #header>
          <div class="card-head">
            <div class="head-left">
              <span class="ai-badge">AI</span>
              <span>智能日报</span>
            </div>
            <div class="head-right">
              <el-radio-group v-model="aiPeriod" size="small">
                <el-radio-button value="day">今日</el-radio-button>
                <el-radio-button value="week">近 7 天</el-radio-button>
              </el-radio-group>
              <el-button type="primary" plain size="small" :loading="aiLoading" @click="genAi">
                {{ aiReport ? '重新生成' : '生成报告' }}
              </el-button>
            </div>
          </div>
        </template>

        <div v-if="!aiReport" class="ai-empty">
          <div class="ai-empty-icon">✨</div>
          <div>点击右上方"生成报告"，让 AI 替你写一份可读、可执行的工地安全报告</div>
          <div class="ai-empty-hint">无需手工总结，30 秒搞定</div>
        </div>

        <div v-else class="ai-body">
          <div class="ai-section">
            <div class="ai-section-title">总览</div>
            <p class="ai-summary">{{ aiReport.summary }}</p>
          </div>

          <div class="ai-section" v-if="aiReport.highlights?.length">
            <div class="ai-section-title">关键发现</div>
            <ul class="ai-list">
              <li v-for="(h, i) in aiReport.highlights" :key="i">{{ h }}</li>
            </ul>
          </div>

          <div class="ai-section" v-if="aiReport.recommendations?.length">
            <div class="ai-section-title">执行建议</div>
            <ul class="ai-list recs">
              <li v-for="(r, i) in aiReport.recommendations" :key="i">{{ r }}</li>
            </ul>
          </div>

          <div class="ai-section" v-if="aiReport.outlook">
            <div class="ai-section-title">下阶段重点</div>
            <p class="ai-outlook">{{ aiReport.outlook }}</p>
          </div>
        </div>
      </el-card>

      <el-row :gutter="20" style="margin-top: 16px">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>违规类别统计</template>
            <el-table :data="classRows" empty-text="该时段无数据">
              <el-table-column label="违规类别" prop="name" />
              <el-table-column label="出现次数" prop="count" width="120" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>检测来源分布</template>
            <el-table :data="typeRows" empty-text="该时段无数据">
              <el-table-column label="来源" prop="name" />
              <el-table-column label="数量" prop="count" width="120" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Download } from '@element-plus/icons-vue'
import { fetchReportSummary, downloadReportPdf, generateAiSummary } from '@/api/reports'

const today = new Date().toISOString().slice(0, 10)
const weekAgo = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
const range = ref([weekAgo, today])
const loading = ref(false)
const downloading = ref(false)
const s = reactive({ total: 0, processed: 0, pending: 0, byRisk: {}, byType: {}, byClass: {} })

// AI 智能日报
const aiPeriod = ref('day')
const aiLoading = ref(false)
const aiReport = ref(null)
const genAi = async () => {
  aiLoading.value = true
  try {
    const r = await generateAiSummary(aiPeriod.value)
    aiReport.value = r.data
    if (!r.generated) ElMessage.info('该时段无违规数据，已使用默认提示')
    else ElMessage.success('AI 报告已生成')
  } catch (e) { /* 拦截器已提示 */ } finally { aiLoading.value = false }
}

const classRows = computed(() => Object.entries(s.byClass || {}).map(([name, count]) => ({ name, count })))
const typeRows = computed(() => Object.entries(s.byType || {}).map(([name, count]) => ({ name, count })))

const shortcuts = [
  { text: '近 7 天', value: () => [new Date(Date.now() - 6 * 86400000), new Date()] },
  { text: '近 30 天', value: () => [new Date(Date.now() - 29 * 86400000), new Date()] },
  { text: '今天', value: () => [new Date(), new Date()] },
]

const load = async () => {
  if (!range.value?.length) return
  loading.value = true
  try {
    const res = await fetchReportSummary(range.value[0], range.value[1])
    Object.assign(s, res.summary)
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const download = async () => {
  if (!range.value?.length) return ElMessage.warning('请先选择时间段')
  downloading.value = true
  try {
    await downloadReportPdf(range.value[0], range.value[1])
    ElMessage.success('PDF 已开始下载')
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    downloading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.bar-card { border-radius: 10px; }
.bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.lbl { color: #555; font-size: 14px; }
.stat { text-align: center; }
.num { font-size: 30px; font-weight: bold; color: #0a5a2c; }
.num.warn { color: #faad14; }
.num.danger { color: #f5222d; }
.lab { margin-top: 6px; color: #888; font-size: 14px; }

/* ===== AI 智能日报 ===== */
.ai-card {
  background: linear-gradient(180deg, #f7faf8 0%, var(--surface) 80%);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: var(--text);
}
.head-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ai-badge {
  background: linear-gradient(135deg, var(--brand), #1abf80);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  letter-spacing: 0.6px;
}
.ai-empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-2);
  font-size: 14px;
}
.ai-empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}
.ai-empty-hint {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 6px;
}
.ai-body {
  padding: 4px;
}
.ai-section {
  margin-bottom: 18px;
}
.ai-section:last-child {
  margin-bottom: 0;
}
.ai-section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-3);
  letter-spacing: 0.8px;
  text-transform: uppercase;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px dashed var(--divider);
}
.ai-summary, .ai-outlook {
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
  margin: 0;
}
.ai-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.ai-list li {
  color: var(--text);
  font-size: 14px;
  line-height: 1.7;
  padding-left: 18px;
  position: relative;
  padding-top: 4px;
  padding-bottom: 4px;
}
.ai-list li::before {
  content: '·';
  position: absolute;
  left: 6px;
  top: 4px;
  color: var(--text-3);
  font-weight: bold;
}
.ai-list.recs li::before {
  content: '→';
  color: var(--brand);
}
</style>
