<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">设备 · 围栏管理</div>
        <div class="page-desc">登记摄像头档案 + 配置电子围栏,业务规则由摄像头位置类型 + Polygon 类型联合决定。</div>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增摄像头</el-button>
      </div>
    </div>

    <PremiumCard :hoverable="false">
      <el-table :data="cams" v-loading="loading">
        <el-table-column label="名称" prop="name" min-width="160">
          <template #default="{ row }">
            <div class="cam-name">
              <StatusBeacon :status="beaconStatus(row)" />
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="位置类型" min-width="120">
          <template #default="{ row }">
            <el-tag :type="locationTagType(row.locationType)" size="small">
              {{ row.locationTypeZh || '露天监控' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="安装位置" min-width="120">
          <template #default="{ row }">
            <span class="loc-text">{{ row.location || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="RTSP 地址" min-width="280">
          <template #default="{ row }">
            <code class="url">{{ row.url }}</code>
          </template>
        </el-table-column>
        <el-table-column label="健康状态" width="160">
          <template #default="{ row }">
            <el-tag v-if="row.healthState === 'online'" type="success" size="small">在线</el-tag>
            <el-tag v-else-if="row.healthState === 'error'" type="danger" size="small">异常</el-tag>
            <el-tag v-else-if="row.healthState === 'recent'" type="warning" size="small">心跳停 {{ formatGap(row.offlineFor) }}</el-tag>
            <el-tag v-else-if="row.healthState === 'offline'" type="danger" size="small">离线 {{ formatGap(row.offlineFor) }}</el-tag>
            <el-tag v-else type="info" size="small">未启动</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.online" link type="success"
              :disabled="!row.enabled" @click="start(row)"
            >开启</el-button>
            <el-button v-else link type="warning" @click="stop(row)">停止</el-button>
            <el-button link type="primary" @click="openPolygons(row)">围栏</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </PremiumCard>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑摄像头' : '新增摄像头'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如:1 号楼 3 单元电梯" />
        </el-form-item>
        <el-form-item label="位置类型">
          <el-select v-model="form.locationType" style="width: 100%">
            <el-option
              v-for="opt in LOCATION_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            >
              <span style="display:flex; justify-content: space-between; align-items: center;">
                <span>{{ opt.label }}</span>
                <span style="color: var(--text-3); font-size: 11px;">{{ opt.hint }}</span>
              </span>
            </el-option>
          </el-select>
          <div class="tip">决定业务规则。如选"电梯轿厢",检测到电瓶车立即告警</div>
        </el-form-item>
        <el-form-item label="安装位置">
          <el-input v-model="form.location" placeholder="选填,如:1 号楼东南角" />
        </el-form-item>
        <el-form-item label="RTSP 地址">
          <el-input
            v-model="form.url"
            type="textarea"
            :rows="2"
            placeholder="rtsp://用户名:密码@IP:554/Streaming/Channels/101"
          />
        </el-form-item>
        <el-form-item label="置信度">
          <el-slider v-model="form.conf" :min="0.1" :max="0.9" :step="0.05" style="width: 220px" :format-tooltip="(v) => v.toFixed(2)" />
          <span class="conf-val">{{ form.conf.toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="抓拍间隔">
          <el-select v-model="form.snapInterval" style="width: 140px">
            <el-option label="5 秒" :value="5" />
            <el-option label="10 秒" :value="10" />
            <el-option label="30 秒" :value="30" />
            <el-option label="60 秒" :value="60" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-divider style="margin: 8px 0" />
        <el-form-item label="开启时段">
          <el-switch v-model="form.scheduleEnabled" />
          <span class="tip">仅在该时段做 AI 识别,外则只拉流不检测</span>
        </el-form-item>
        <el-form-item v-if="form.scheduleEnabled" label="作业时间">
          <el-time-picker
            v-model="form.scheduleStart"
            placeholder="开始" format="HH:mm" value-format="HH:mm"
            style="width: 130px"
          />
          <span style="margin: 0 8px">至</span>
          <el-time-picker
            v-model="form.scheduleEnd"
            placeholder="结束" format="HH:mm" value-format="HH:mm"
            style="width: 130px"
          />
          <span class="tip">支持跨夜(如 22:00 至 06:00)</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 围栏编辑 -->
    <el-dialog
      v-model="polyDialogVisible"
      :title="`电子围栏 · ${currentCam?.name || ''}`"
      width="640px"
    >
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
        前端 polygon 编辑器开发中。可在管理 API 临时配置,或等待 PolygonEditor 组件上线。
      </el-alert>
      <div class="poly-list">
        <div v-if="!polygons.length" class="poly-empty">该摄像头还没有配置任何围栏区域</div>
        <div v-for="p in polygons" :key="p.id" class="poly-item">
          <div class="poly-info">
            <el-tag :type="polyTagType(p.type)" size="small">{{ p.typeZh }}</el-tag>
            <span class="poly-name">{{ p.name || '未命名' }}</span>
            <span class="poly-dwell">停留阈值 {{ p.dwellThreshold }} 秒</span>
          </div>
          <el-switch v-model="p.enabled" disabled />
        </div>
      </div>
      <template #footer>
        <el-button @click="polyDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import {
  fetchCameras, createCamera, updateCamera, deleteCamera,
  startCamera, stopCamera,
} from '@/api/cameras'
import PremiumCard from '@/components/PremiumCard.vue'
import StatusBeacon from '@/components/StatusBeacon.vue'

const LOCATION_OPTIONS = [
  { value: 'outdoor',           label: '露天监控',  hint: '默认场景' },
  { value: 'elevator',          label: '电梯轿厢',  hint: '电瓶车进入即告警' },
  { value: 'building_entrance', label: '单元门口',  hint: '电瓶车进楼道告警' },
  { value: 'parking_lot',       label: '停车场',    hint: '违停 + 车位统计' },
  { value: 'charging_station',  label: '充电桩区',  hint: '占用充电位检测' },
  { value: 'lawn_area',         label: '绿地周边',  hint: '宠物/人闯入草坪' },
  { value: 'fire_lane',         label: '消防通道',  hint: '车辆占用即告警' },
  { value: 'garage',            label: '地下车库',  hint: '综合场景' },
]

const LOC_TAG_TYPE = {
  outdoor: '',
  elevator: 'danger',
  building_entrance: 'warning',
  parking_lot: '',
  charging_station: 'warning',
  lawn_area: 'success',
  fire_lane: 'danger',
  garage: '',
}

const POLY_TAG_TYPE = {
  fire_lane: 'danger',
  no_parking: 'warning',
  charging_slot: 'warning',
  lawn: 'success',
  parking_slot: '',
  elevator_zone: 'danger',
  passage: 'info',
}

const cams = ref([])
const loading = ref(false)
const saving = ref(false)

const dialogVisible = ref(false)
const editing = ref(false)
const form = reactive({
  id: null, name: '', location: '', locationType: 'outdoor', url: '',
  conf: 0.5, snapInterval: 10, enabled: true,
  scheduleEnabled: false, scheduleStart: '07:00', scheduleEnd: '19:00',
})

const polyDialogVisible = ref(false)
const currentCam = ref(null)
const polygons = ref([])

let pollTimer = null

const load = async () => {
  loading.value = true
  try {
    const res = await fetchCameras()
    cams.value = res.items
  } catch (e) { /* 拦截器已提示 */ }
  finally { loading.value = false }
}

const openCreate = () => {
  editing.value = false
  Object.assign(form, {
    id: null, name: '', location: '', locationType: 'outdoor', url: '',
    conf: 0.5, snapInterval: 10, enabled: true,
    scheduleEnabled: false, scheduleStart: '07:00', scheduleEnd: '19:00',
  })
  dialogVisible.value = true
}

const openEdit = (row) => {
  editing.value = true
  Object.assign(form, {
    id: row.id, name: row.name, location: row.location || '',
    locationType: row.locationType || 'outdoor',
    url: row.url, conf: row.conf, snapInterval: row.snapInterval, enabled: row.enabled,
    scheduleEnabled: row.scheduleEnabled, scheduleStart: row.scheduleStart, scheduleEnd: row.scheduleEnd,
  })
  dialogVisible.value = true
}

const submit = async () => {
  if (!form.name.trim() || !form.url.trim()) return ElMessage.warning('名称与地址不能为空')
  saving.value = true
  try {
    if (editing.value) {
      await updateCamera(form.id, { ...form })
      ElMessage.success('已更新')
    } else {
      await createCamera({ ...form })
      ElMessage.success('已新增')
    }
    dialogVisible.value = false
    load()
  } catch (e) { /* 拦截器已提示 */ }
  finally { saving.value = false }
}

const start = async (row) => {
  try {
    await startCamera(row.id)
    ElMessage.success('已发起拉流,5 秒内可见状态')
    load()
  } catch (e) { /* 拦截器已提示 */ }
}
const stop = async (row) => {
  await stopCamera(row.id)
  ElMessage.success('已停止')
  load()
}
const remove = async (row) => {
  await ElMessageBox.confirm(`确认删除「${row.name}」?正在拉流的会先被停止`, '提示', { type: 'warning' })
  await deleteCamera(row.id)
  ElMessage.success('已删除')
  load()
}

const openPolygons = async (row) => {
  currentCam.value = row
  polygons.value = []
  polyDialogVisible.value = true
  // TODO: 后续接 GET /api/cameras/:id/polygons
}

const formatGap = (sec) => {
  if (!sec || sec < 60) return `${sec || 0}s`
  if (sec < 3600) return `${Math.floor(sec / 60)} 分`
  if (sec < 86400) return `${Math.floor(sec / 3600)} 小时`
  return `${Math.floor(sec / 86400)} 天`
}

const beaconStatus = (row) => {
  if (row.healthState === 'online') return 'online'
  if (row.healthState === 'offline' || row.healthState === 'error') return 'offline'
  if (row.healthState === 'recent') return 'warning'
  return 'standby'
}
const locationTagType = (t) => LOC_TAG_TYPE[t] || ''
const polyTagType = (t) => POLY_TAG_TYPE[t] || ''

onMounted(() => {
  load()
  pollTimer = setInterval(load, 5000)
})
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}
.header-actions {
  display: flex;
  gap: var(--space-2);
}
.cam-name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text);
  font-weight: 500;
}
.loc-text { color: var(--text-2); font-size: 13px; }
.url {
  color: var(--text-2);
  font-size: 12px;
  background: var(--bg-overlay);
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  word-break: break-all;
  font-family: var(--font-mono);
  border: 1px solid var(--border);
}
.conf-val {
  font-weight: 600;
  color: var(--brand);
  margin-left: 8px;
  font-family: var(--font-mono);
}
.tip {
  color: var(--text-3);
  font-size: 12px;
  margin-left: 10px;
  display: block;
  margin-top: 4px;
}

/* Polygon 列表 */
.poly-list { display: flex; flex-direction: column; gap: var(--space-2); }
.poly-empty {
  text-align: center;
  color: var(--text-3);
  padding: var(--space-8) var(--space-4);
  background: var(--bg-overlay);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
}
.poly-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.poly-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.poly-name { color: var(--text); font-weight: 500; font-size: 14px; }
.poly-dwell {
  font-family: var(--font-mono);
  color: var(--text-3);
  font-size: 11px;
}
</style>
