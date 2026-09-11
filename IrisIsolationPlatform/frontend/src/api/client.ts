import type { ProcessingMethod, SegmentationResult } from '../types/images'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'

export async function processImage(file: File, method: ProcessingMethod, onProgress: (value: number) => void): Promise<SegmentationResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('method', method)
  onProgress(20)
  const token = localStorage.getItem('iris-access-token')
  const response = await fetch(`${API_URL}/images`, { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form })
  onProgress(82)
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(data?.detail ?? data?.title ?? 'The image could not be processed.')
  const resultEndpoint = data.resultUrl.startsWith('http') ? data.resultUrl : `${API_URL.replace('/api/v1', '')}${data.resultUrl}`
  const imageResponse = await fetch(resultEndpoint, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!imageResponse.ok) throw new Error('The isolated image could not be retrieved.')
  onProgress(96)
  return { ...data, resultUrl: URL.createObjectURL(await imageResponse.blob()) }
}