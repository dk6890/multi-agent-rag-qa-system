import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000
})

function unwrapResponse(response) {
  const result = response.data
  if (!result || typeof result.code === 'undefined') {
    throw new Error('接口返回格式不正确')
  }

  if (result.code !== 200) {
    throw new Error(result.msg || '请求失败')
  }

  return result.data
}

export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await request.post('/files/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })

  return unwrapResponse(response)
}

export async function listFiles() {
  const response = await request.get('/files/list')
  return unwrapResponse(response)
}

export async function askQuestion(payload) {
  const response = await request.post('/chat/ask', payload)
  return unwrapResponse(response)
}

export default request
