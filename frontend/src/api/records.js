import request from './request'

export const fetchStats = () => request.get('/records/stats')
export const fetchRecords = (params) => request.get('/records', { params })
export const fetchRecord = (id) => request.get(`/records?id=${id}`)
export const updateRecord = (id, data) => request.patch(`/records/${id}`, data)
export const deleteRecord = (id) => request.delete(`/records/${id}`)
export const batchRecords = (data) => request.post('/records/batch', data)
export const assignRecord = (id, assigneeId) =>
  request.post(`/records/${id}/assign`, { assigneeId })
export const escalateOverdue = (minutes = 30) =>
  request.post('/records/escalate_overdue', { minutes })
