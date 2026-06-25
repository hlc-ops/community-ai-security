<template>
  <div>
    <div class="page-title">告警视频回放</div>
    <div class="page-desc">所有触发了视频片段录像的告警事件——前 5 秒+后 5 秒画面，作为取证/复盘依据。</div>

    <!-- 筛选 -->
    <el-card shadow="never" class="bar-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="风险">
          <el-select v-model="filters.risk" placeholder="全部" clearable style="width: 110px" @change="reload">
            <el-option label="高危" value="high" />
            <el-option label="中危" value="mid" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.type" placeholder="全部" clearable style="width: 130px" @change="reload">
            <el-option label="实时检测" value="camera" />
            <el-option label="视频检测" value="video" />
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
        <el-form-item>
          <el-button type="primary" @click="reload">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-empty v-if="!loading && !rows.length" description="暂无视频片段。开启网络摄像头监测后，触发高/中危事件时会自动录制 ~10 秒片段" />

    <!-- 网格 -->
    <div class="grid" v-loading="loading">
      <div v-for="row in rows" :key="row.id" class="clip-card">
        <video
          :src="row.clipUrl"
          :poster="row.imgUrl"
          preload="metadata"
          controls
          class="clip-video"
        ></video>
        <div class="clip-meta">
          <div class="meta-row">
            <el-tag :type="riskTag(row.risk)" effect="dark" size="small">{{ row.riskZh }}</el-tag>
            <el-tag size="small">{{ row.typeZh }}</el-tag>
            <el-tag :type="statusTag(row.status)" size="small">{{ row.statusZh }}</el-tag>
          </div>
          <div class="meta-row">
            <el-tag v-for="(c, i) in row.clsList" :key="i" size="small" effect="plain">{{ c }}</el-tag>
          </div>
          <div class="meta-row time">
            <el-icon><Clock /></el-icon> {{ fmt(row.createdAt) }}
          </div>
        </div>
      </div>
    </div>

    <el-pagination
      v-if="total > pageSize"
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      @current-change="(p) => (page = p) && load()"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Clock } from '@element-plus/icons-vue'
import { fetchRecords } from '@/api/records'
import { fmtTime } from '@/utils/datetime'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(12)
const loading = ref(false)
const filters = reactive({ risk: '', type: '', status: '' })

const fmt = fmtTime
const riskTag = (r) => (r === 'high' ? 'danger' : r === 'mid' ? 'warning' : 'success')
const statusTag = (s) => ({ pending: 'info', processing: 'warning', processed: 'success', closed: '' }[s] || 'info')

const load = async () => {
  loading.value = true
  try {
    const res = await fetchRecords({
      hasClip: '1',
      type: filters.type || undefined,
      risk: filters.risk || undefined,
      status: filters.status || undefined,
      page: page.value,
      pageSize: pageSize.value,
    })
    rows.value = res.items
    total.value = res.total
  } catch (e) { /* 拦截器已提示 */ } finally { loading.value = false }
}
const reload = () => { page.value = 1; load() }
const resetFilters = () => { filters.risk = ''; filters.type = ''; filters.status = ''; reload() }

onMounted(load)
</script>

<style scoped>
.bar-card { border-radius: 10px; margin-bottom: 16px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  min-height: 200px;
}
.clip-card {
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
}
.clip-video {
  width: 100%;
  height: 200px;
  object-fit: cover;
  background: #000;
}
.clip-meta {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.meta-row {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  align-items: center;
}
.meta-row.time {
  color: #888;
  font-size: 12px;
}
.pager { margin-top: 16px; justify-content: center; }
</style>
