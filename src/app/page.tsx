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
    <main style={styles.container}>
      <h1 style={styles.heading}>AI Image Generator</h1>
      <p style={styles.subheading}>Enter comma-separated descriptive words:</p>

      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        rows={3}
        placeholder="e.g. surreal, twilight, forest, radiant"
      />

      <button onClick={generateImage} disabled={loading} style={styles.button}>
        {loading ? 'Generating...' : 'Generate'}
      </button>

      {error && <p style={styles.error}>⚠️ {error}</p>}

      {imageUrl && (
        <div style={styles.imageContainer}>
          <h3 style={styles.subheading}>Result:</h3>
          <img src={imageUrl} alt="Generated" style={styles.image} />
        </div>
      )}
    </main>
  );
}

const styles = {
  container: {
    padding: '2rem',
    maxWidth: '600px',
    margin: 'auto',
    fontFamily: 'Arial, sans-serif',
  },
  heading: {
    fontSize: '2rem',
    marginBottom: '1rem',
  },
  subheading: {
    fontSize: '1rem',
    marginBottom: '0.5rem',
  },
  textarea: {
    width: '100%',
    padding: '0.75rem',
    fontSize: '1rem',
    marginBottom: '1rem',
    border: '1px solid #ccc',
    borderRadius: '5px',
    resize: 'vertical',
  },
  button: {
    padding: '0.5rem 1.5rem',
    fontSize: '1rem',
    cursor: 'pointer',
    backgroundColor: '#111',
    color: '#fff',
    border: 'none',
    borderRadius: '5px',
  },
  error: {
    color: 'crimson',
    marginTop: '1rem',
  },
  imageContainer: {
    marginTop: '2rem',
  },
  image: {
    maxWidth: '100%',
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
  },
};
