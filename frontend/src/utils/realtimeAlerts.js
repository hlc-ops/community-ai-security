/**
 * 实时告警订阅：登录态下打开 SSE，新告警弹通知 + 蜂鸣声。
 *
 * EventSource 不支持自定义请求头，所以 token 走 query。
 * Web Audio 的浏览器策略：要求用户先有交互；登录本身是一次交互，所以登录后可发声。
 */
import { ElNotification } from 'element-plus'
import { fmtTime } from './datetime'

let es = null
let muted = false
let customSoundUrl = ''
let customAudio = null

export const setCustomSound = (url) => {
  customSoundUrl = url || ''
  customAudio = null  // 下次播放时按新 URL 创建
}

const playCustom = () => {
  if (muted || !customSoundUrl) return false
  try {
    if (!customAudio) customAudio = new Audio(customSoundUrl)
    customAudio.currentTime = 0
    customAudio.play().catch(() => {})
    return true
  } catch (e) {
    return false
  }
}

const beep = (freq = 880, durMs = 250) => {
  if (muted) return
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.value = freq
    gain.gain.setValueAtTime(0.001, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durMs / 1000)
    osc.start()
    osc.stop(ctx.currentTime + durMs / 1000)
    setTimeout(() => ctx.close().catch(() => {}), durMs + 100)
  } catch (e) {
    /* 静默：声音不是关键路径 */
  }
}

const handleEvent = (router, evt) => {
  // 摄像头离线/恢复通知
  if (evt.type === 'camera_offline') {
    const d = evt.data || {}
    ElNotification({
      title: '📡 摄像头离线',
      message: `${d.name || '摄像头'}${d.location ? '（' + d.location + '）' : ''} · 失去连接`,
      type: 'error',
      position: 'top-right',
      duration: 10000,
      onClick: () => router && router.push({ name: 'cameras' }),
    })
    if (!playCustom()) { beep(620, 250); setTimeout(() => beep(520, 250), 280); setTimeout(() => beep(620, 250), 560) }
    return
  }
  if (evt.type === 'camera_online') {
    const d = evt.data || {}
    ElNotification({
      title: '✅ 摄像头恢复',
      message: `${d.name || '摄像头'} 已重新上线`,
      type: 'success',
      position: 'top-right',
      duration: 4000,
    })
    return
  }
  if (evt.type !== 'alert') return
  const rec = evt.data || {}
  const isHigh = rec.risk === 'high'
  const cls = (rec.clsList || []).join('、') || '违规'
  ElNotification({
    title: isHigh ? '⚠️ 高危违规告警' : '⚠️ 违规告警',
    message: `${rec.typeZh || ''} · ${cls} · ${fmtTime(rec.createdAt)}`,
    type: isHigh ? 'error' : 'warning',
    position: 'top-right',
    duration: 8000,
    onClick: () => router && router.push({ name: 'records' }),
  })
  // 优先播自定义音；未配置则用内置蜂鸣（高危 2 声，中危 1 声）
  if (!playCustom()) {
    beep(isHigh ? 920 : 760, 250)
    if (isHigh) setTimeout(() => beep(720, 250), 300)
  }
}

export const startRealtimeAlerts = (token, router) => {
  stopRealtimeAlerts()
  if (!token) return
  try {
    es = new EventSource(`/api/events/stream?token=${encodeURIComponent(token)}`)
    es.onmessage = (e) => {
      try {
        handleEvent(router, JSON.parse(e.data))
      } catch (err) { /* ignore */ }
    }
    es.onerror = () => { /* 浏览器自动重连，无需处理 */ }
  } catch (e) {
    /* 不可用环境，静默 */
  }
}

export const stopRealtimeAlerts = () => {
  if (es) {
    try { es.close() } catch (e) { /* ignore */ }
    es = null
  }
}

export const setMuted = (v) => { muted = !!v }
export const isMuted = () => muted
