<template>
  <div>
    <div class="page-title">检测记录</div>
    <div class="page-desc">图片 / 视频 / 实时检测产生的违规事件统一记录，可筛选、处理与导出。</div>

    <!-- 工具栏 -->
    <el-card shadow="never" class="toolbar">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="来源">
          <el-select v-model="filters.type" placeholder="全部" clearable style="width: 120px" @change="reload">
            <el-option label="图片检测" value="img" />
            <el-option label="视频检测" value="video" />
            <el-option label="实时检测" value="camera" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险">
          <el-select v-model="filters.risk" placeholder="全部" clearable style="width: 110px" @change="reload">
            <el-option label="高危" value="high" />
            <el-option label="中危" value="mid" />
            <el-option label="低危" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 130px" @change="reload">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已处理" value="processed" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="带视频">
          <el-switch v-model="filters.hasClip" @change="reload" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="filters.keyword" placeholder="搜索处理意见" clearable style="width: 160px" @keyup.enter="reload" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="reload">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <div class="batch-bar">
        <el-button type="success" plain :disabled="!selected.length" @click="batchProcess">
          批量标记已处理（{{ selected.length }}）
        </el-button>
        <el-button type="danger" plain :disabled="!selected.length" @click="batchDelete">
          批量删除（{{ selected.length }}）
        </el-button>
        <el-button @click="exportCsv">导出 CSV</el-button>
        <el-button type="warning" plain @click="doEscalate">扫描超时升级</el-button>
      </div>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" style="margin-top: 16px">
      <el-table
        :data="rows"
        v-loading="loading"
        @selection-change="(v) => (selected = v)"
        empty-text="暂无记录"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column label="截图" width="100">
          <template #default="{ row }">
            <el-image
              v-if="row.imgUrl"
              :src="row.imgUrl"
              fit="cover"
              class="thumb"
              :preview-src-list="[row.imgUrl]"
              :preview-teleported="true"
            />
            <span v-else class="muted">无</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="160">
          <template #default="{ row }">{{ fmt(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="来源" width="100">
          <template #default="{ row }">{{ row.typeZh }}</template>
        </el-table-column>
        <el-table-column label="风险 / AI 紧急度" width="150">
          <template #default="{ row }">
            <el-tag :type="riskTag(row.risk)" effect="dark" size="small">{{ row.riskZh }}</el-tag>
            <el-tag
              v-if="row.urgency"
              :type="urgencyTag(row.urgency)"
              effect="plain"
              size="small"
              style="margin-left: 4px"
            >
              {{ row.urgencyZh }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="违规业务" min-width="130">
          <template #default="{ row }">
            <el-tag v-if="row.violationZh" :type="violationTagType(row.violationType)" size="small">
              {{ row.violationZh }}
            </el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="检测对象" min-width="140">
          <template #default="{ row }">
            <el-tag v-for="(c, i) in row.clsList" :key="i" size="small" effect="plain" style="margin: 2px">{{ c }}</el-tag>
            <span v-if="!row.clsList?.length" class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="视频" width="70" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="row.clipUrl" content="点击查看告警视频片段">
              <el-button text type="primary" :icon="VideoPlay" @click="openDetail(row)" />
            </el-tooltip>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ row.statusZh }}</el-tag>
            <el-tag v-if="row.escalated" type="danger" effect="dark" size="small" style="margin-left: 4px">升级</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处理人" width="100">
          <template #default="{ row }">
            <span v-if="row.assigneeId">{{ assigneeName(row.assigneeId) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === 'pending'" link type="success" @click="quickProcess(row)">处理</el-button>
            <el-button link type="danger" @click="removeOne(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pager"
        layout="total, prev, pager, next, sizes"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        @current-change="(p) => (page = p) && load()"
        @size-change="(s) => { pageSize = s; page = 1; load() }"
      />
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="检测记录详情" width="720px">
      <template v-if="current">
        <!-- 告警视频片段（有则优先显示，截图作为缩略图）-->
        <video
          v-if="current.clipUrl"
          :src="current.clipUrl"
          controls
          preload="metadata"
          :poster="current.imgUrl"
          class="detail-clip"
        ></video>
        <el-image
          v-else-if="current.imgUrl"
          :src="current.imgUrl"
          fit="contain"
          class="detail-img"
          :preview-src-list="[current.imgUrl]"
          :preview-teleported="true"
        />
        <el-descriptions :column="2" border style="margin-top: 16px">
          <el-descriptions-item label="来源">{{ current.typeZh }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="riskTag(current.risk)" effect="dark" size="small">{{ current.riskZh }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="current.urgency" label="AI 紧急度">
            <el-tag :type="urgencyTag(current.urgency)" effect="plain" size="small">{{ current.urgencyZh }}</el-tag>
            <span class="muted" style="margin-left: 6px">{{ current.urgencyReason }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="检测时间">{{ fmt(current.createdAt) }}</el-descriptions-item>
          <el-descriptions-item label="持续时间">{{ current.duration }}</el-descriptions-item>
          <el-descriptions-item label="违规类别" :span="2">
            <el-tag v-for="(c, i) in current.clsList" :key="i" size="small" style="margin: 2px">{{ c }}</el-tag>
            <span v-if="!current.clsList?.length" class="muted">未识别到目标</span>
          </el-descriptions-item>
          <el-descriptions-item label="状态" :span="2">
            <el-tag :type="current.status === 'processed' ? 'success' : 'info'" size="small">{{ current.statusZh }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 大模型二次复核 -->
        <div class="llm-area">
          <div class="llm-head">
            <span class="process-title" style="margin: 0">
              <el-icon><MagicStick /></el-icon> AI 大模型复核
            </span>
            <el-button
              type="primary"
              size="small"
              :loading="reviewing"
              @click="doReview"
            >
              {{ current.llmReviewed ? '重新复核' : '开始复核' }}
            </el-button>
          </div>

          <el-empty
            v-if="!current.llmReviewed"
            :image-size="50"
            description="尚未复核，点击「开始复核」让视觉大模型二次研判并给出整改建议"
          />
          <div v-else class="llm-result">
            <div class="llm-row">
              <span class="llm-label">研判结论：</span>
              <el-tag :type="current.llmConfirmed ? 'danger' : 'success'" effect="dark" size="small">
                {{ current.llmConfirmed ? '确认存在安全隐患' : '未发现明显隐患（疑似误报）' }}
              </el-tag>
            </div>
            <div class="llm-row">
              <span class="llm-label">画面描述：</span>
              <span>{{ current.llmDescription || '—' }}</span>
            </div>
            <div class="llm-row">
              <span class="llm-label">整改建议：</span>
              <span>{{ current.llmAdvice || '—' }}</span>
            </div>
          </div>
        </div>

        <!-- AI 物业工单(社区版独有)-->
        <div class="llm-area work-order-area">
          <div class="llm-head">
            <span class="process-title" style="margin: 0">
              <el-icon><Document /></el-icon> AI 物业工单
            </span>
            <el-button
              type="primary"
              size="small"
              :loading="generatingOrder"
              @click="doGenerateOrder"
            >
              {{ current.workOrder ? '重新生成' : '生成工单' }}
            </el-button>
          </div>

          <el-empty
            v-if="!current.workOrder"
            :image-size="50"
            description="点击「生成工单」让 AI 自动分配执行人、写明步骤和时限"
          />
          <div v-else class="work-order">
            <div class="wo-header">
              <div class="wo-title">{{ current.workOrder.title }}</div>
              <div class="wo-tags">
                <el-tag :type="priorityTag(current.workOrder.priority)" effect="dark" size="small">
                  {{ priorityZh(current.workOrder.priority) }}
                </el-tag>
                <el-tag size="small">{{ current.workOrder.assigneeRole }}</el-tag>
                <el-tag size="small" type="info">⏱ {{ current.workOrder.timeframe }}</el-tag>
                <el-tag v-if="current.workOrder.notifyOwner" type="warning" size="small">
                  📢 通知业主
                </el-tag>
              </div>
            </div>

            <div class="wo-section">
              <div class="wo-label">情况说明</div>
              <div class="wo-summary">{{ current.workOrder.summary }}</div>
            </div>

            <div class="wo-section">
              <div class="wo-label">执行步骤</div>
              <ol class="wo-actions">
                <li v-for="(a, i) in current.workOrder.actions" :key="i">{{ a }}</li>
              </ol>
            </div>

            <div class="wo-section expected">
              <div class="wo-label">期望结果</div>
              <div class="wo-summary">{{ current.workOrder.expected }}</div>
            </div>
          </div>
        </div>

        <div class="process-area">
          <div class="process-title">处理意见</div>
          <el-input
            v-model="remark"
            type="textarea"
            :rows="3"
            placeholder="请输入处理意见…"
            :disabled="current.status === 'processed'"
          />
        </div>
      </template>
      <template #footer>
        <div class="dialog-footer">
          <div class="assign-area" v-if="current && auth.isAdmin">
            <span class="assign-label">指派处理人：</span>
            <el-select v-model="assignTo" placeholder="选择处理人" clearable style="width: 160px">
              <el-option v-for="u in users" :key="u.id" :label="u.realName || u.username" :value="u.id" />
            </el-select>
            <el-button size="small" @click="doAssign">保存指派</el-button>
          </div>
          <div class="state-actions" v-if="current">
            <el-button @click="detailVisible = false">关闭弹窗</el-button>
            <el-button
              v-if="current.status === 'pending'"
              type="warning"
              @click="transitionTo('processing')"
            >开始处理</el-button>
            <el-button
              v-if="current.status === 'pending' || current.status === 'processing'"
              type="success"
              @click="transitionTo('processed')"
            >完成处理</el-button>
            <el-button
              v-if="current.status === 'processed'"
              @click="transitionTo('closed')"
            >关闭工单</el-button>
            <el-button
              v-if="current.status === 'closed'"
              type="info"
              plain
              @click="transitionTo('pending')"
            >重新打开</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import {
  fetchRecords, updateRecord, deleteRecord, batchRecords,
  assignRecord, escalateOverdue,
} from '@/api/records'
import { fetchUsers } from '@/api/users'
import { reviewRecord, generateWorkOrder } from '@/api/llm'
import { useAuthStore } from '@/store/auth'
import { fmtTime } from '@/utils/datetime'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const selected = ref([])
const filters = reactive({ type: '', risk: '', status: '', keyword: '', hasClip: false })

const detailVisible = ref(false)
const current = ref(null)
const remark = ref('')
const reviewing = ref(false)
const generatingOrder = ref(false)

const priorityZh = (p) => ({
  immediate: '立即处置',
  high: '紧急',
  normal: '一般',
  low: '可缓',
}[p] || p)
const priorityTag = (p) => ({
  immediate: 'danger',
  high: 'warning',
  normal: 'info',
  low: '',
}[p] || 'info')

const doGenerateOrder = async () => {
  if (!current.value) return
  generatingOrder.value = true
  try {
    const res = await generateWorkOrder(current.value.id)
    current.value = res.record
    ElMessage.success('AI 工单已生成')
  } catch (e) { /* 拦截器已提示 */ }
  finally { generatingOrder.value = false }
}
const assignTo = ref(null)
const users = ref([])
const auth = useAuthStore()
const userMap = computed(() => Object.fromEntries(users.value.map((u) => [u.id, u.realName || u.username])))
const assigneeName = (id) => userMap.value[id] || `#${id}`

const riskTag = (r) => (r === 'high' ? 'danger' : r === 'mid' ? 'warning' : 'success')

const VIOLATION_TAG_TYPE = {
  fire_alert: 'danger',
  fire_lane_blocked: 'danger',
  ebike_in_elevator: 'danger',
  ebike_in_entrance: 'danger',
  illegal_parking: 'warning',
  ebike_illegal_park: 'warning',
  charging_slot_misuse: 'warning',
  litter: 'warning',
  pet_intrusion: 'info',
  human_intrusion: 'info',
}
const violationTagType = (v) => VIOLATION_TAG_TYPE[v] || ''
const statusTag = (s) => ({ pending: 'info', processing: 'warning', processed: 'success', closed: '' }[s] || 'info')
const urgencyTag = (u) => ({ immediate: 'danger', high: 'warning', normal: 'info', low: '' }[u] || 'info')
const fmt = fmtTime

const load = async () => {
  loading.value = true
  try {
    const res = await fetchRecords({
      type: filters.type || undefined,
      risk: filters.risk || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined,
      hasClip: filters.hasClip ? '1' : undefined,
      page: page.value,
      pageSize: pageSize.value,
    })
    rows.value = res.items
    total.value = res.total
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const reload = () => {
  page.value = 1
  load()
}
const resetFilters = () => {
  filters.type = filters.risk = filters.status = filters.keyword = ''
  reload()
}

const openDetail = (row) => {
  current.value = row
  remark.value = row.remark || ''
  assignTo.value = row.assigneeId || null
  detailVisible.value = true
}

const loadUsers = async () => {
  if (!auth.isAdmin) return
  try {
    const res = await fetchUsers()
    users.value = res.items
  } catch (e) { /* 非管理员会 403，忽略 */ }
}

const doAssign = async () => {
  if (!current.value) return
  await assignRecord(current.value.id, assignTo.value)
  ElMessage.success('已分配')
  load()
}

const transitionTo = async (status) => {
  if (!current.value) return
  if (status === 'processed' && !remark.value.trim()) {
    return ElMessage.warning('请输入处理意见')
  }
  const data = { status }
  if (status === 'processed') data.remark = remark.value.trim()
  await updateRecord(current.value.id, data)
  ElMessage.success('已更新')
  detailVisible.value = false
  load()
}

const doEscalate = async () => {
  const res = await escalateOverdue(30)
  ElMessage.success(`扫描完成，标记 ${res.escalated} 条超时升级`)
  load()
}

const submitProcess = async () => {
  if (!remark.value.trim()) return ElMessage.warning('请输入处理意见')
  await updateRecord(current.value.id, { status: 'processed', remark: remark.value.trim() })
  ElMessage.success('已处理')
  detailVisible.value = false
  load()
}

const doReview = async () => {
  reviewing.value = true
  try {
    const res = await reviewRecord(current.value.id)
    // 用后端返回的最新记录刷新弹窗内容
    current.value = res.record
    // 同步列表里的该行
    const i = rows.value.findIndex((r) => r.id === res.record.id)
    if (i !== -1) rows.value[i] = res.record
    ElMessage.success('大模型复核完成')
  } catch (e) {
    /* 拦截器已提示（含未配置 Key 的提示）*/
  } finally {
    reviewing.value = false
  }
}

const quickProcess = async (row) => {
  const { value } = await ElMessageBox.prompt('请输入处理意见', '处理记录', {
    inputPlaceholder: '如：已通知现场负责人整改',
    inputValidator: (v) => (v && v.trim() ? true : '处理意见不能为空'),
  }).catch(() => ({}))
  if (value === undefined) return
  await updateRecord(row.id, { status: 'processed', remark: value.trim() })
  ElMessage.success('已处理')
  load()
}

const removeOne = async (row) => {
  await ElMessageBox.confirm('确认删除这条记录？', '提示', { type: 'warning' })
  await deleteRecord(row.id)
  ElMessage.success('已删除')
  load()
}

const batchProcess = async () => {
  await batchRecords({ action: 'process', ids: selected.value.map((r) => r.id) })
  ElMessage.success('已批量处理')
  load()
}
const batchDelete = async () => {
  await ElMessageBox.confirm(`确认删除选中的 ${selected.value.length} 条记录？`, '提示', { type: 'warning' })
  await batchRecords({ action: 'delete', ids: selected.value.map((r) => r.id) })
  ElMessage.success('已批量删除')
  load()
}

const exportCsv = () => {
  if (!rows.value.length) return ElMessage.warning('当前无数据可导出')
  let csv = '﻿时间,来源,风险,违规类别,状态,处理意见\n'
  rows.value.forEach((r) => {
    csv += `${fmt(r.createdAt)},${r.typeZh},${r.riskZh},"${(r.clsList || []).join('、')}",${r.statusZh},"${r.remark || ''}"\n`
  })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  a.download = `检测记录_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
}

onMounted(() => { load(); loadUsers() })
</script>

<style scoped>
.toolbar {
  border-radius: 10px;
}
.batch-bar {
  display: flex;
  gap: 10px;
}
.thumb {
  width: 64px;
  height: 42px;
  border-radius: 4px;
  border: 1px solid #eee;
  cursor: zoom-in;
}
.muted {
  color: #bbb;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.detail-img {
  display: block;
  width: 100%;
  height: 320px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #eee;
  cursor: zoom-in;
}
.detail-clip {
  display: block;
  width: 100%;
  max-height: 400px;
  background: #000;
  border-radius: 6px;
}
.process-area {
  margin-top: 18px;
}
.process-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: #0a5a2c;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.llm-area {
  margin-top: 18px;
  background: var(--brand-soft);
  border: 1px solid var(--border-brand);
  border-radius: var(--radius-lg);
  padding: 16px 18px;
}
.work-order-area {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}
.work-order-area::before {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 50%; height: 50%;
  background: radial-gradient(ellipse at top right, rgba(22, 179, 168, 0.08), transparent 60%);
  pointer-events: none;
}
.work-order {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.wo-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--border);
}
.wo-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.2px;
}
.wo-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.wo-section { padding: 0; }
.wo-section.expected {
  padding: 12px;
  background: var(--success-bg);
  border: 1px dashed rgba(22, 179, 168, 0.3);
  border-radius: var(--radius-md);
}
.wo-label {
  font-size: 11px;
  color: var(--text-3);
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  font-family: var(--font-mono);
  margin-bottom: 6px;
}
.wo-summary {
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
}
.wo-actions {
  margin: 0;
  padding-left: 20px;
  color: var(--text);
  font-size: 14px;
  line-height: 1.8;
}
.wo-actions li {
  padding-left: 4px;
  color: var(--text);
}
.wo-actions li::marker {
  color: var(--brand);
  font-weight: 600;
}
.llm-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.llm-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  color: #444;
}
.llm-row {
  line-height: 1.6;
}
.llm-label {
  color: #888;
  margin-right: 4px;
}
.dialog-footer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.assign-area {
  display: flex;
  align-items: center;
  gap: 8px;
}
.assign-label {
  color: #555;
  font-size: 14px;
}
.state-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
