import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useAuthStore } from '@/store/auth'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截：自动带上 JWT
request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截：统一错误处理，401 跳登录
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const msg = error.response?.data?.msg || error.message || '请求失败'
    if (status === 401) {
      const auth = useAuthStore()
      auth.logout()
      if (router.currentRoute.value.name !== 'login') {
        ElMessage.error('登录已过期，请重新登录')
        router.push({ name: 'login' })
      }
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  },
)

export default request
