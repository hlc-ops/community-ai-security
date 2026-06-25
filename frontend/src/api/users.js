import request from './request'

export const fetchUsers = () => request.get('/users')
export const createUser = (data) => request.post('/users', data)
export const updateUser = (id, data) => request.put(`/users/${id}`, data)
export const resetPassword = (id, password) => request.put(`/users/${id}/password`, { password })
export const setUserStatus = (id, enabled) => request.put(`/users/${id}/status`, { enabled })
export const deleteUser = (id) => request.delete(`/users/${id}`)
