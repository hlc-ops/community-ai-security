import request from './request'
import { useAuthStore } from '@/store/auth'

export const fetchReportSummary = (start, end) =>
  request.get('/reports/summary', { params: { start, end } })

export const fetchSafetyScore = (period = 'day') =>
  request.get('/reports/safety_score', { params: { period } })

export const fetchHeatmap = (type = 'hour', days = 30) =>
  request.get('/reports/heatmap', { params: { type, days } })

export const generateAiSummary = (period = 'day') =>
  request.post('/reports/ai_summary', { period })

// PDF 下载：带上 token，拿 blob 触发浏览器下载
export const downloadReportPdf = async (start, end) => {
  const auth = useAuthStore()
  const res = await fetch(`/api/reports/pdf?start=${start}&end=${end}`, {
    headers: { Authorization: `Bearer ${auth.token}` },
  })
  if (!res.ok) throw new Error('下载失败')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `工地安防报表_${start}_${end}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}
