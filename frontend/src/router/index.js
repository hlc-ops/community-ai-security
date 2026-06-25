import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import AppLayout from '@/components/AppLayout.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/cockpit',
    name: 'cockpit',
    component: () => import('@/views/Cockpit.vue'),
    meta: { requiresAuth: true },
  },
  // 居民端 H5(扫码即用,无需登录)
  {
    path: '/h5',
    name: 'h5',
    component: () => import('@/views/H5Community.vue'),
    meta: { isPublic: true },
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'image',
        name: 'image',
        component: () => import('@/views/ImageDetect.vue'),
        meta: { title: '图片检测' },
      },
      {
        path: 'video',
        name: 'video',
        component: () => import('@/views/VideoDetect.vue'),
        meta: { title: '视频检测' },
      },
      {
        path: 'camera',
        name: 'camera',
        component: () => import('@/views/CameraDetect.vue'),
        meta: { title: '实时检测' },
      },
      {
        path: 'rtsp',
        name: 'rtsp',
        component: () => import('@/views/RtspDetect.vue'),
        meta: { title: '网络摄像头' },
      },
      {
        path: 'cameras',
        name: 'cameras',
        component: () => import('@/views/Cameras.vue'),
        meta: { title: '设备管理' },
      },
      {
        path: 'records',
        name: 'records',
        component: () => import('@/views/RecordList.vue'),
        meta: { title: '检测记录' },
      },
      {
        path: 'replay',
        name: 'replay',
        component: () => import('@/views/VideoReplay.vue'),
        meta: { title: '视频回放' },
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('@/views/Reports.vue'),
        meta: { title: '报表导出' },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/UserManage.vue'),
        meta: { title: '用户管理', adminOnly: true },
      },
      {
        path: 'audit',
        name: 'audit',
        component: () => import('@/views/AuditLog.vue'),
        meta: { title: '审计日志', adminOnly: true },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：未登录访问受保护页 → 登录页；已登录访问登录页 → 首页
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.matched.some((r) => r.meta.requiresAuth) && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isLoggedIn) {
    return { name: 'dashboard' }
  }
  // 管理员专属页面拦截非管理员
  if (to.matched.some((r) => r.meta.adminOnly) && !auth.isAdmin) {
    return { name: 'dashboard' }
  }
  return true
})

export default router
