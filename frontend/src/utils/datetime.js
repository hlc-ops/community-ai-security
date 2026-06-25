/**
 * 后端时间戳格式化（UTC → 本地时区，浏览器自动按用户时区显示）。
 * 后端 ISO 字符串带 'Z' 后缀（如 "2026-06-13T08:00:00Z"），Date 会按 UTC 解析。
 */
const pad = (n) => String(n).padStart(2, '0')

export const fmtTime = (iso) => {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return iso
  }
}

export const fmtTimeShort = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return ''
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return ''
  }
}
