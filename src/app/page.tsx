'use client';

import { useEffect, useState } from 'react';
import packageJson from '../../package.json';
import styles from './page.module.css';

const questions = [
  'What place or environment feels most like “home” to you?',
  'If your personality were an animal, what would it be and why?',
  'What color best represents your current mood or inner self?',
  'Describe a dream or fantasy world you’d love to explore.',
  'What kind of weather or natural scene do you feel most connected to?',
  'What symbol or object do you feel spiritually or emotionally drawn to?',
  'If your life had a magical element, what would it be?',
  'What era or style do you identify with most?',
  'If your soul had a visual aesthetic, what would it look like?',
  'What would a statue or monument built in your honor look like?',
];

// 🌟 Pre-filled answers for testing
const defaultAnswers = [
  'A forest cabin in the mountains',
  'An owl, wise and observant',
  'Deep red',
  'A floating island covered in bioluminescent plants',
  'A misty rainforest',
  'A glowing crystal',
  'Time travel',
  'The 1980s with neon lights and synthwave vibes',
  'Floating mountains with glowing waterfalls',
  'A giant tree carved with stories of my life',
];

const waitingMessages = [
  'Curating the light and setting the mood.',
  'Negotiating the finer details with the muse.',
  'Polishing a few beautifully impossible edges.',
  'Your masterpiece is taking the scenic route.',
];

const formatElapsedTime = (seconds: number) => {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  return `${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
};

export default function HomePage() {
  const [formData, setFormData] = useState<string[]>(defaultAnswers);
  const [loading, setLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!loading) {
      return;
    }

    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [loading]);

  const handleChange = (index: number, value: string) => {
    const updated = [...formData];
    updated[index] = value;
    setFormData(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setElapsedSeconds(0);
    setLoading(true);
    setImageUrl('');
    setError('');

    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: formData }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok || typeof data.imageUrl !== 'string' || !data.imageUrl) {
        throw new Error(
          typeof data.error === 'string' ? data.error : 'Image generation failed. Please try again.'
        );
      }

      setImageUrl(data.imageUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Image generation failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!imageUrl) {
      return;
    }

    setDownloadError('');

    try {
      const response = await fetch(imageUrl);
      if (!response.ok) {
        throw new Error('The generated image could not be downloaded.');
      }

      const imageBlob = await response.blob();
      const downloadUrl = URL.createObjectURL(imageBlob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = 'generated-image.png';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch {
      setDownloadError('The generated image could not be downloaded. Please try again.');
    }
  };

  return (
    <main className="container py-5">
      {loading && (
        <div className={styles.waitingOverlay} role="dialog" aria-modal="true" aria-labelledby="waiting-title">
          <div className={styles.waitingModal}>
            <div className={styles.orbit} aria-hidden="true">
              <span className={styles.orbitCore} />
            </div>
            <p className={styles.eyebrow}>Atelier in session</p>
            <h2 id="waiting-title" className={styles.waitingTitle}>Your vision is in the studio</h2>
            <p className={styles.waitingMessage} aria-live="polite">
              {waitingMessages[Math.min(Math.floor(elapsedSeconds / 8), waitingMessages.length - 1)]}
            </p>
            <div className={styles.timer} aria-label={`${elapsedSeconds} seconds elapsed`}>
              <span>Studio time</span>
              <strong>{formatElapsedTime(elapsedSeconds)}</strong>
            </div>
            <div className={styles.progressTrack} aria-hidden="true">
              <span />
            </div>
          </div>
        </div>
      )}

      <div className="text-center mb-5">
        <h1 className="display-4 fw-bold">
          🎨 Test Your AI Image Prompt v{packageJson.version}
        </h1>
        <p className="lead">Auto-filled answers to speed up testing.</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-light p-4 rounded shadow-sm">
        {questions.map((q, i) => (
          <div className="mb-4" key={i}>
            <label className="form-label fw-semibold">
              {i + 1}. {q}
            </label>
            <textarea
              value={formData[i]}
              onChange={(e) => handleChange(i, e.target.value)}
              className="form-control"
              rows={2}
              required
            />
          </div>
        ))}
        <button type="submit" className="btn btn-primary w-100 py-2" disabled={loading}>
          {loading ? 'Generating...' : 'Generate Image'}
        </button>
      </form>

      {error && (
        <div className="alert alert-danger mt-4" role="alert">
          {error}
        </div>
      )}

      {imageUrl && (
        <div className="text-center mt-5">
          <h2 className="h4 mb-3">🖼️ Your Generated Image</h2>
          <img src={imageUrl} alt="Generated Art" className="img-fluid rounded shadow" />
          <div className="mt-4">
            <button type="button" className="btn btn-outline-primary" onClick={handleDownload}>
              Download Image
            </button>
          </div>
          {downloadError && (
            <div className="alert alert-warning mt-3" role="alert">
              {downloadError}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
