import request from './request'

export const llmStatus = () => request.get('/llm/status')
export const reviewRecord = (recordId) => request.post('/llm/review', { recordId })
export const generateWorkOrder = (recordId) => request.post('/llm/work_order', { recordId })
