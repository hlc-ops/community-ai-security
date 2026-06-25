import request from './request'

export const fetchAuditLogs = (params) => request.get('/audit/logs', { params })
