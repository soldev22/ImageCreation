export type ProcessingMethod = 'opencv' | 'unet'

export interface SegmentationResult {
  id: string
  filename: string
  status: 'completed'
  method: ProcessingMethod
  confidenceScore: number
  width: number
  height: number
  resultUrl: string
  createdAt: string
}