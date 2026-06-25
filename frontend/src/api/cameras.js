import request from './request'

export const fetchCameras = () => request.get('/cameras')
export const createCamera = (data) => request.post('/cameras', data)
export const updateCamera = (id, data) => request.put(`/cameras/${id}`, data)
export const deleteCamera = (id) => request.delete(`/cameras/${id}`)
export const startCamera = (id) => request.post(`/cameras/${id}/start`)
export const stopCamera = (id) => request.post(`/cameras/${id}/stop`)
