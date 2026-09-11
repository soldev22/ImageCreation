import type { ProcessingMethod, SegmentationResult } from '../types/images'

const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000/api/v1' : '/api/v1')

export async function processImage(file: File, method: ProcessingMethod, onProgress: (value: number) => void): Promise<SegmentationResult> {
  const form = new FormData()
  form.append('file', file)
  form.append('method', method)
  onProgress(20)
  const token = localStorage.getItem('iris-access-token')
  const response = await fetch(`${API_URL}/isolate`, { method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form })
  onProgress(82)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(data?.detail ?? data?.title ?? 'The image could not be processed.')
  }
  onProgress(96)
  return {
    id: response.headers.get('X-Image-Id') ?? crypto.randomUUID(),
    filename: file.name,
    status: 'completed',
    method,
    confidenceScore: Number(response.headers.get('X-Confidence-Score') ?? 0),
    width: Number(response.headers.get('X-Image-Width') ?? 0),
    height: Number(response.headers.get('X-Image-Height') ?? 0),
    resultUrl: URL.createObjectURL(await response.blob()),
    createdAt: new Date().toISOString(),
  }
}