import request from './request'

export const getAlertConfig = () => request.get('/settings/alert')
export const saveAlertConfig = (data) => request.put('/settings/alert', data)
export const testAlert = (data) => request.post('/settings/alert/test', data)

export const getBrand = () => request.get('/settings/brand')
export const saveBrand = (data) => request.put('/settings/brand', data)
export const uploadBrandLogo = (file) => {
  const fd = new FormData()
  fd.append('logo', file)
  return request.post('/settings/brand/logo', fd)
}

export const getAlertSound = () => request.get('/settings/alert_sound')
export const uploadAlertSound = (file) => {
  const fd = new FormData()
  fd.append('audio', file)
  return request.post('/settings/alert_sound', fd)
}
export const clearAlertSound = () => request.delete('/settings/alert_sound')

export const getClassConfs = () => request.get('/settings/class_confs')
export const saveClassConfs = (config) => request.put('/settings/class_confs', { config })

export const getRetention = () => request.get('/settings/retention')
export const saveRetention = (config) => request.put('/settings/retention', { config })
export const runCleanup = () => request.post('/settings/retention/run')
export const getHealthDetail = () => request.get('/settings/health')

export const getTriageEnabled = () => request.get('/settings/triage')
export const saveTriageEnabled = (enabled) => request.put('/settings/triage', { enabled })

// ====== LLM 多服务商配置 ======
export const listLLMProviders = () => request.get('/settings/llm_providers')
export const createLLMProvider = (data) => request.post('/settings/llm_providers', data)
export const updateLLMProvider = (id, data) => request.put(`/settings/llm_providers/${id}`, data)
export const deleteLLMProvider = (id) => request.delete(`/settings/llm_providers/${id}`)
export const setLLMPreferred = (id) => request.put('/settings/llm_preferred', { id })
export const testLLMProvider = (id) => request.post(`/settings/llm_providers/${id}/test`)
