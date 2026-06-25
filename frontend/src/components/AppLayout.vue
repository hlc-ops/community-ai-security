<template>
  <el-container class="layout">
    <!-- 侧边栏 -->
    <el-aside width="232px" class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">
          <img v-if="brand.logoUrl" :src="brand.logoUrl" class="brand-img" alt="logo" />
          <svg v-else viewBox="0 0 24 24" fill="none" class="brand-svg">
            <path d="M3 21V9l9-7 9 7v12h-6v-7H9v7H3z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="brand-text">
          <div class="brand-name">{{ brand.name || '智慧物业' }}</div>
          <div class="brand-tag">SMART COMMUNITY</div>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="side-menu"
        background-color="transparent"
        text-color="var(--side-text)"
        active-text-color="#ffffff"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon><span>物业指挥中心</span>
        </el-menu-item>

        <div class="menu-group">实时监控</div>
        <el-menu-item index="/image">
          <el-icon><Picture /></el-icon><span>图像识别</span>
        </el-menu-item>
        <el-menu-item index="/video">
          <el-icon><VideoCamera /></el-icon><span>视频分析</span>
        </el-menu-item>
        <el-menu-item index="/camera">
          <el-icon><Monitor /></el-icon><span>本机摄像头</span>
        </el-menu-item>
        <el-menu-item index="/rtsp">
          <el-icon><Connection /></el-icon><span>网络摄像头</span>
        </el-menu-item>
        <el-menu-item index="/cameras">
          <el-icon><VideoCameraFilled /></el-icon><span>设备 · 围栏</span>
        </el-menu-item>

        <div class="menu-group">事件中心</div>
        <el-menu-item index="/records">
          <el-icon><Document /></el-icon><span>告警事件</span>
        </el-menu-item>
        <el-menu-item index="/replay">
          <el-icon><VideoPlay /></el-icon><span>事件回放</span>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><DataLine /></el-icon><span>统计报表</span>
        </el-menu-item>

        <div class="menu-group">系统管理</div>
        <el-menu-item v-if="auth.isAdmin" index="/users">
          <el-icon><UserFilled /></el-icon><span>账户管理</span>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/audit">
          <el-icon><Tickets /></el-icon><span>操作审计</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon><span>偏好设置</span>
        </el-menu-item>
      </el-menu>

      <div class="side-foot">
        <button class="cockpit-btn" @click="$router.push('/cockpit')">
          <span class="cockpit-dot"></span>
          可视化大屏
        </button>
        <div class="copyright">© 2026 Smart Community</div>
      </div>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="header-left">
          <span class="crumb-prefix">{{ crumb.prefix }}</span>
          <span class="crumb-sep">·</span>
          <span class="crumb-current">{{ crumb.current }}</span>
        </div>
        <div class="header-right">
          <el-tooltip :content="muted ? '点击恢复告警声音' : '点击静音'" placement="bottom">
            <button class="icon-btn" @click="toggleMute">
              <el-icon><component :is="muted ? Mute : Bell" /></el-icon>
            </button>
          </el-tooltip>
          <el-dropdown @command="onCommand">
            <button class="user-btn">
              <div class="user-avatar">{{ (auth.user?.realName || auth.user?.username || '?').slice(0, 1) }}</div>
              <div class="user-info">
                <span class="user-name">{{ auth.user?.realName || auth.user?.username }}</span>
                <span class="user-role">{{ auth.isAdmin ? '管理员' : '操作员' }}</span>
              </div>
              <el-icon class="user-arrow"><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区（子路由） -->
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Bell, Mute } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import { useBrandStore } from '@/store/brand'
import { startRealtimeAlerts, stopRealtimeAlerts, setMuted, isMuted, setCustomSound } from '@/utils/realtimeAlerts'
import request from '@/api/request'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const brand = useBrandStore()

const activeMenu = computed(() => route.path)
const crumb = computed(() => ({
  prefix: '智慧物业',
  current: route.meta.title || '指挥中心',
}))

const muted = ref(isMuted())
const toggleMute = () => { muted.value = !muted.value; setMuted(muted.value) }

const onCommand = async (cmd) => {
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
    stopRealtimeAlerts()
    auth.logout()
    ElMessage.success('已退出')
    router.push({ name: 'login' })
  }
}

const loadAlertSound = async () => {
  try {
    const r = await request.get('/settings/alert_sound')
    setCustomSound(r.url || '')
  } catch (e) { /* ignore */ }
}

onMounted(() => {
  if (auth.token) {
    startRealtimeAlerts(auth.token, router)
    loadAlertSound()
  }
})
onUnmounted(() => stopRealtimeAlerts())
watch(() => auth.token, (t) => {
  if (t) { startRealtimeAlerts(t, router); loadAlertSound() }
  else stopRealtimeAlerts()
})
</script>

<style scoped>
.layout { height: 100vh; }

/* ============================================================
   侧栏（深色商务感）
   ============================================================ */
.sidebar {
  background: var(--side-bg);
  background: linear-gradient(180deg, var(--side-bg) 0%, var(--side-bg-2) 100%);
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.03);
}

/* 品牌区 */
.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 22px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  position: relative;
}
.brand-block::after {
  content: '';
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: -1px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--brand), transparent);
  opacity: 0.4;
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-gradient);
  color: #0a1628;
  flex-shrink: 0;
  box-shadow: 0 4px 16px rgba(78, 205, 196, 0.3);
  position: relative;
  overflow: hidden;
}
.brand-mark::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.2), transparent);
  opacity: 0.6;
}
.brand-svg {
  width: 20px;
  height: 20px;
  position: relative;
  z-index: 1;
}
.brand-img {
  max-width: 30px;
  max-height: 30px;
  object-fit: contain;
}
.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.brand-name {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.2px;
  line-height: 1.2;
}
.brand-tag {
  color: var(--brand);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 1.5px;
  font-family: var(--font-mono);
}

/* 菜单分组 */
.menu-group {
  color: var(--side-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  padding: 18px 22px 8px;
}

/* 菜单（覆盖 el-menu） */
.side-menu {
  border: none;
  flex: 1;
  padding: 4px 10px;
  overflow-y: auto;
}
.side-menu :deep(.el-menu-item) {
  height: 38px;
  line-height: 38px;
  border-radius: 6px;
  margin: 2px 0;
  padding: 0 12px !important;
  font-size: 13.5px;
  color: var(--side-text) !important;
  transition: background 0.15s ease;
}
.side-menu :deep(.el-menu-item .el-icon) {
  margin-right: 10px;
  font-size: 16px;
  color: var(--side-muted);
}
.side-menu :deep(.el-menu-item:hover) {
  background: var(--side-hover) !important;
  color: #fff !important;
}
.side-menu :deep(.el-menu-item:hover .el-icon) { color: #fff; }
.side-menu :deep(.el-menu-item.is-active) {
  background: var(--side-active) !important;
  color: #fff !important;
  font-weight: 500;
  position: relative;
}
.side-menu :deep(.el-menu-item.is-active .el-icon) { color: var(--side-active-line); }
.side-menu :deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: -10px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--side-active-line);
}

/* 底部入口 */
.side-foot {
  padding: 14px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}
.cockpit-btn {
  width: 100%;
  height: 38px;
  border-radius: 6px;
  background: rgba(26, 191, 128, 0.08);
  border: 1px solid rgba(26, 191, 128, 0.3);
  color: #cdebd9;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
}
.cockpit-btn:hover {
  background: rgba(26, 191, 128, 0.16);
  color: #fff;
  transform: translateY(-1px);
}
.cockpit-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #1abf80;
  box-shadow: 0 0 8px #1abf80;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.copyright {
  margin-top: 10px;
  font-size: 11px;
  text-align: center;
  color: var(--side-muted);
}

/* ============================================================
   顶栏(亮色 + 玻璃质感)
   ============================================================ */
.header {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.crumb-prefix {
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
}
.crumb-sep {
  color: var(--text-3);
  opacity: 0.4;
}
.crumb-current {
  color: var(--text);
  font-weight: 500;
  font-size: 15px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.icon-btn {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-2);
  transition: all var(--duration-base) var(--ease-out);
}
.icon-btn:hover {
  border-color: var(--border-brand);
  color: var(--brand);
  background: var(--brand-soft);
  transform: translateY(-1px);
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 12px 4px 4px;
  height: 38px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}
.user-btn:hover {
  border-color: var(--border-brand);
  transform: translateY(-1px);
}
.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: var(--brand-gradient);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  box-shadow: 0 2px 8px rgba(22, 179, 168, 0.25);
}
.user-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.2;
}
.user-name { color: var(--text); font-size: 13px; font-weight: 500; }
.user-role {
  color: var(--text-3);
  font-size: 10px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-family: var(--font-mono);
}
.user-arrow { color: var(--text-3); font-size: 12px; }

/* 主内容 */
.main {
  background: transparent;
  padding: 28px 32px;
  min-height: calc(100vh - 60px);
}
</style>
