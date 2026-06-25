<template>
  <div>
    <div class="page-title">用户管理</div>
    <div class="page-desc">管理系统账号：新增操作员、分配角色、重置密码、启用/停用。</div>

    <el-card shadow="never">
      <div class="bar">
        <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table :data="users" v-loading="loading" style="margin-top: 12px">
        <el-table-column label="账号" prop="username" min-width="120" />
        <el-table-column label="姓名" min-width="120">
          <template #default="{ row }">{{ row.realName || '—' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? '管理员' : '操作员' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="160">
          <template #default="{ row }">{{ fmt(row.lastLogin) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="warning" @click="openReset(row)">重置密码</el-button>
            <el-button
              link
              :type="row.enabled ? 'info' : 'success'"
              :disabled="row.id === myId"
              @click="toggleStatus(row)"
            >
              {{ row.enabled ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" :disabled="row.id === myId" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '新增用户'" width="460px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="账号">
          <el-input v-model="form.username" :disabled="editing" placeholder="至少 3 个字符" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.realName" placeholder="选填" />
        </el-form-item>
        <el-form-item v-if="!editing" label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 个字符" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role">
            <el-radio-button value="operator">操作员</el-radio-button>
            <el-radio-button value="admin">管理员</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetVisible" title="重置密码" width="400px">
      <el-form label-width="80px">
        <el-form-item label="新密码">
          <el-input v-model="newPwd" type="password" show-password placeholder="至少 6 个字符" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitReset">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import {
  fetchUsers, createUser, updateUser, resetPassword, setUserStatus, deleteUser,
} from '@/api/users'

const auth = useAuthStore()
const myId = auth.user?.id

const users = ref([])
const loading = ref(false)
const saving = ref(false)

const dialogVisible = ref(false)
const editing = ref(false)
const form = reactive({ id: null, username: '', realName: '', password: '', role: 'operator' })

const resetVisible = ref(false)
const resetId = ref(null)
const newPwd = ref('')

const fmt = (iso) => (iso ? iso.replace('T', ' ').slice(0, 19) : '从未登录')

const load = async () => {
  loading.value = true
  try {
    const res = await fetchUsers()
    users.value = res.items
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editing.value = false
  Object.assign(form, { id: null, username: '', realName: '', password: '', role: 'operator' })
  dialogVisible.value = true
}
const openEdit = (row) => {
  editing.value = true
  Object.assign(form, { id: row.id, username: row.username, realName: row.realName, password: '', role: row.role })
  dialogVisible.value = true
}

const submit = async () => {
  saving.value = true
  try {
    if (editing.value) {
      await updateUser(form.id, { realName: form.realName, role: form.role })
      ElMessage.success('已更新')
    } else {
      await createUser({ username: form.username, password: form.password, realName: form.realName, role: form.role })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

const openReset = (row) => {
  resetId.value = row.id
  newPwd.value = ''
  resetVisible.value = true
}
const submitReset = async () => {
  saving.value = true
  try {
    await resetPassword(resetId.value, newPwd.value)
    ElMessage.success('密码已重置')
    resetVisible.value = false
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

const toggleStatus = async (row) => {
  await setUserStatus(row.id, !row.enabled)
  ElMessage.success(row.enabled ? '已停用' : '已启用')
  load()
}

const remove = async (row) => {
  await ElMessageBox.confirm(`确认删除用户「${row.username}」？`, '提示', { type: 'warning' })
  await deleteUser(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.bar {
  display: flex;
  gap: 10px;
}
</style>
