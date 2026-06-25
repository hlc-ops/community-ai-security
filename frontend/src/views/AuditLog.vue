<template>
  <div>
    <div class="page-title">审计日志</div>
    <div class="page-desc">登录、用户/摄像头/记录/配置等关键操作的完整留痕。</div>

    <el-card shadow="never" class="bar-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="filters.username" placeholder="按账号过滤" clearable style="width: 150px" @keyup.enter="reload" />
        </el-form-item>
        <el-form-item label="操作">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 160px" @change="reload">
            <el-option label="登录" value="login" />
            <el-option label="用户操作" value="user" />
            <el-option label="摄像头操作" value="camera" />
            <el-option label="记录操作" value="record" />
            <el-option label="配置变更" value="setting" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            @change="reload"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="reload">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <el-table :data="rows" v-loading="loading" empty-text="暂无日志">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ fmt(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="账号" prop="username" width="120">
          <template #default="{ row }">{{ row.username || '—' }}</template>
        </el-table-column>
        <el-table-column label="IP" prop="ip" width="140" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-tag size="small" :type="tagType(row.action)">{{ row.actionZh }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象">
          <template #default="{ row }">
            <span class="muted">{{ row.targetType || '—' }}</span>
            <span v-if="row.targetId" style="margin-left: 4px">#{{ row.targetId }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" prop="detail" min-width="200">
          <template #default="{ row }">{{ row.detail || '—' }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, prev, pager, next, sizes"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        @current-change="(p) => (page = p) && load()"
        @size-change="(s) => { pageSize = s; page = 1; load() }"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { fetchAuditLogs } from '@/api/audit'
import { fmtTime } from '@/utils/datetime'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filters = reactive({ username: '', action: '' })
const range = ref([])

const fmt = fmtTime
const tagType = (a) => {
  if (a.startsWith('login.fail')) return 'danger'
  if (a.startsWith('login')) return 'success'
  if (a.includes('delete')) return 'danger'
  if (a.includes('setting')) return 'warning'
  return 'info'
}

const load = async () => {
  loading.value = true
  try {
    const params = {
      username: filters.username || undefined,
      action: filters.action || undefined,
      start: range.value?.[0],
      end: range.value?.[1],
      page: page.value,
      pageSize: pageSize.value,
    }
    const res = await fetchAuditLogs(params)
    rows.value = res.items
    total.value = res.total
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
const reload = () => { page.value = 1; load() }
const resetFilters = () => { filters.username = ''; filters.action = ''; range.value = []; reload() }

onMounted(load)
</script>

<style scoped>
.bar-card { border-radius: 10px; }
.muted { color: #aaa; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
