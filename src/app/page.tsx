'use client';

import { useState } from 'react';

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



export default function HomePage() {
  const [formData, setFormData] = useState<string[]>(defaultAnswers);
  const [loading, setLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState('');

  const handleChange = (index: number, value: string) => {
    const updated = [...formData];
    updated[index] = value;
    setFormData(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setImageUrl('');

    const response = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: formData }),
    });

    const data = await response.json();
    setImageUrl(data.imageUrl);
    setLoading(false);
  };

  return (
    <main className="container py-5">
      <div className="text-center mb-5">
        <h1 className="display-4 fw-bold">🎨 Test Your AI Image Prompt</h1>
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

      {imageUrl && (
        <div className="text-center mt-5">
          <h2 className="h4 mb-3">🖼️ Your Generated Image</h2>
          <img src={imageUrl} alt="Generated Art" className="img-fluid rounded shadow" />
        </div>
      )}
    </main>
  );
}
