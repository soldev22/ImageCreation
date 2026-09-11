import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Download, Eye, ImagePlus, Moon, ScanEye, Sun, Upload, X } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider'
import { processImage } from './api/client'
import type { ProcessingMethod, SegmentationResult } from './types/images'
import './App.css'

const MAX_FILE_BYTES = 4 * 1024 * 1024

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => localStorage.getItem('iris-theme') === 'dark' ? 'dark' : 'light')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [result, setResult] = useState<SegmentationResult | null>(null)
  const [method, setMethod] = useState<ProcessingMethod>('opencv')
  const [progress, setProgress] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('iris-theme', theme)
  }, [theme])

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])
  useEffect(() => () => { if (result?.resultUrl.startsWith('blob:')) URL.revokeObjectURL(result.resultUrl) }, [result])

  const selectFile = (nextFile: File) => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    if (result?.resultUrl.startsWith('blob:')) URL.revokeObjectURL(result.resultUrl)
    setFile(nextFile)
    setPreviewUrl(URL.createObjectURL(nextFile))
    setResult(null)
    setError('')
    setProgress(0)
  }

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    accept: { 'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'], 'image/webp': ['.webp'] },
    maxFiles: 1,
    maxSize: MAX_FILE_BYTES,
    noClick: Boolean(file),
    onDrop: (acceptedFiles, rejectedFiles) => {
      if (rejectedFiles.length) {
        const oversized = rejectedFiles[0].errors.some(({ code }) => code === 'file-too-large')
        setError(oversized ? 'Image must be 4 MB or smaller.' : 'Choose a JPEG, PNG, or WebP image.')
      } else if (acceptedFiles[0]) selectFile(acceptedFiles[0])
    },
  })

  const runIsolation = async () => {
    if (!file) return
    setError('')
    setIsProcessing(true)
    setProgress(8)
    try {
      setResult(await processImage(file, method, setProgress))
      setProgress(100)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Iris isolation failed.')
    } finally {
      setIsProcessing(false)
    }
  }

  const clearFile = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    if (result?.resultUrl.startsWith('blob:')) URL.revokeObjectURL(result.resultUrl)
    setFile(null); setPreviewUrl(''); setResult(null); setError(''); setProgress(0)
  }

  const confidenceLabel = useMemo(() => {
    if (!result) return ''
    return result.confidenceScore >= 0.85 ? 'Excellent boundary match' : result.confidenceScore >= 0.65 ? 'Good boundary match' : 'Review recommended'
  }, [result])

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Iris Isolation Platform home"><span className="brand-mark"><Eye size={21} /></span><span>Iris <b>Isolation</b></span></a>
        <div className="topbar-actions"><span className="system-status"><i /> Vision systems online</span><button className="icon-button" type="button" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} aria-label={`Use ${theme === 'light' ? 'dark' : 'light'} theme`}>{theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}</button></div>
      </header>

      <main id="top">
        <section className="intro-band">
          <div><p className="kicker">Precision ocular imaging</p><h1>Reveal the iris.<br /><em>Nothing else.</em></h1></div>
          <p className="intro-copy">Clinical-grade boundary detection meets a quiet, focused workflow. Upload an eye photograph and receive a transparent iris extraction in seconds.</p>
        </section>

        <section className="workspace" aria-label="Iris processing workspace">
          <aside className="control-rail">
            <div className="step-heading"><span>01</span><div><h2>Source image</h2><p>One eye, clearly photographed</p></div></div>
            <div {...getRootProps({ className: `dropzone ${isDragActive ? 'is-active' : ''} ${file ? 'has-file' : ''}` })}>
              <input {...getInputProps()} />
              {file && previewUrl ? <div className="file-preview"><img src={previewUrl} alt="Selected eye" /><div><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(2)} MB</span></div><button type="button" onClick={(event) => { event.stopPropagation(); clearFile() }} aria-label="Remove selected image"><X size={17} /></button></div> : <><ImagePlus size={28} /><strong>{isDragActive ? 'Release to examine' : 'Drop an eye photograph'}</strong><span>or click to browse</span><small>JPEG, PNG or WebP · max 4 MB</small></>}
            </div>
            {file && <button className="text-action" type="button" onClick={open}><Upload size={15} /> Choose another image</button>}
            <div className="divider" />
            <div className="step-heading compact"><span>02</span><div><h2>Detection method</h2><p>Select the analysis engine</p></div></div>
            <div className="method-switch" role="radiogroup" aria-label="Detection method">
              {(['opencv', 'unet'] as const).map((value) => <button key={value} type="button" className={method === value ? 'selected' : ''} onClick={() => setMethod(value)} role="radio" aria-checked={method === value}><b>{value === 'opencv' ? 'OpenCV' : 'U-Net'}</b><span>{value === 'opencv' ? 'Fast · deterministic' : 'Deep segmentation'}</span></button>)}
            </div>
            {error && <div className="error-message" role="alert">{error}</div>}
            <button className="process-button" type="button" disabled={!file || isProcessing} onClick={runIsolation}><ScanEye size={19} /> {isProcessing ? 'Isolating iris…' : 'Isolate iris'}</button>
            {isProcessing && <div className="progress" aria-label={`Processing ${progress}%`}><span style={{ width: `${progress}%` }} /></div>}
          </aside>

          <div className="result-stage">
            {result && previewUrl ? <div className="result-content">
              <div className="result-toolbar"><div><span className="result-index">03</span><div><h2>Isolation result</h2><p>Drag the marker to compare</p></div></div><span className="complete-badge">Complete</span></div>
              <div className="comparison-frame"><ReactCompareSlider itemOne={<ReactCompareSliderImage src={previewUrl} alt="Original eye photograph" />} itemTwo={<ReactCompareSliderImage src={result.resultUrl} alt="Isolated transparent iris" />} /><span className="comparison-label before">Original</span><span className="comparison-label after">Isolated</span></div>
              <div className="result-footer"><div className="confidence"><div className="confidence-ring" style={{ '--score': `${result.confidenceScore * 360}deg` } as CSSProperties}><strong>{Math.round(result.confidenceScore * 100)}%</strong></div><div><span>Segmentation confidence</span><b>{confidenceLabel}</b></div></div><a className="download-button" href={result.resultUrl} download={`iris-${result.id}.png`}><Download size={18} /> Download PNG</a></div>
            </div> : <div className="empty-result"><div className="iris-placeholder"><span /><i /></div><p className="kicker">Awaiting source</p><h2>Your isolated iris will appear here</h2><p>Upload a well-lit, in-focus photograph to begin. The full eye should be visible without heavy glare.</p></div>}
          </div>
        </section>
      </main>
      <footer><span>© 2026 Iris Isolation Platform</span><span>Images are processed securely and never used for model training.</span></footer>
    </div>
  )
}