import request from './request'

// 图片检测：multipart 上传，字段 image + conf
export const detectImage = (file, conf) => {
  const fd = new FormData()
  fd.append('image', file)
  fd.append('conf', conf)
  return request.post('/detect/image', fd)
}

// 视频/摄像头单帧检测：base64 dataURL，可选检测区域 zone
export const detectFrame = (image, conf, zone = null) =>
  request.post('/detect/frame', { image, conf, zone })
export const detectVideoFrame = (image, conf, zone = null) =>
  request.post('/detect/video_frame', { image, conf, zone })

// 新增检测记录
export const createRecord = (data) => request.post('/records', data)
