'use client';

import { useState } from 'react';

export default function HomePage() {
  const [input, setInput] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const generateImage = async () => {
    setError('');
    setImageUrl('');
    setLoading(true);

    const baseUrl =
      process.env.NODE_ENV === 'development'
        ? 'http://localhost:3000'
        : '';

    try {
      const res = await fetch(`${baseUrl}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: input.split(',').map(str => str.trim()) }),
      });

      const data = await res.json();

      if (res.ok) {
        setImageUrl(data.imageUrl);
      } else {
        setError(data.error || 'Unexpected error');
      }
    } catch (e: any) {
      console.error('🔥 fetch() failed:', e);
      setError('Failed to reach server.');
    }

    setLoading(false);
  };

  return (
    <main style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>AI Image Generator</h1>
      <p>Enter comma-separated descriptive words:</p>
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        rows={3}
        style={{ width: '100%', marginBottom: '1rem' }}
        placeholder="e.g. abstract, ethereal, forest, golden light"
      />
      <br />
      <button onClick={generateImage} disabled={loading}>
        {loading ? 'Generating...' : 'Generate'}
      </button>

      {error && <p style={{ color: 'red' }}>⚠️ {error}</p>}

      {imageUrl && (
        <div style={{ marginTop: '2rem' }}>
          <h3>Result:</h3>
          <img src={imageUrl} alt="Generated" style={{ maxWidth: '100%' }} />
        </div>
      )}
    </main>
  );
}
