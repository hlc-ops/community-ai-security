import request from './request'

export const startStream = (data) => request.post('/stream/start', data)
export const stopStream = (streamId) => request.post('/stream/stop', { streamId })
export const streamStatus = (sid) => request.get(`/stream/status/${sid}`)
export const mjpegUrl = (sid) => `/api/stream/mjpeg/${sid}`
