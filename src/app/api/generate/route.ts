import { NextResponse } from 'next/server';
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function GET() {
  return NextResponse.json(
    { message: 'POST to this endpoint with an array of descriptive words.' },
    { status: 405 }
  );
}

export async function POST(req: Request) {
  try {
    const { answers } = await req.json();

    if (!Array.isArray(answers) || !answers.length) {
      return NextResponse.json(
        { error: 'Invalid input. Expected non-empty array.' },
        { status: 400 }
      );
    }

    const cleanedAnswers = answers
      .map((a: string) =>
        a
          .trim()
          .replace(/\s+/g, ' ')
          .replace(/[^\w\s.,!?'"()-]/g, '')
          .slice(0, 100)
      )
      .filter((a: string) => a.length > 3);

    const prompt = `Create an abstract, emotionally expressive image based on: ${cleanedAnswers.join(', ')}.`;

    console.log('🎯 Prompt:', prompt);

    const response = await openai.chat.completions.create({
      model: 'gpt-4-turbo',
      messages: [
        {
          role: 'user',
          content: `Generate a DALL·E 3 image with this prompt: "${prompt}"`,
        },
      ],
      tools: [
        {
          type: 'function',
          function: {
            name: 'generate_image',
            description: 'Generates an image using DALL·E 3',
            parameters: {
              type: 'object',
              properties: {
                prompt: { type: 'string' },
                size: { type: 'string', enum: ['1024x1024'] },
              },
              required: ['prompt', 'size'],
            },
          },
        },
      ],
      tool_choice: {
        type: 'function',
        function: { name: 'generate_image' },
      },
    });

    const toolCall = response.choices?.[0]?.message?.tool_calls?.[0];
    const imageArgs = JSON.parse(toolCall?.function.arguments || '{}');

    const imageResponse = await openai.images.generate({
      model: 'dall-e-3',
      prompt: imageArgs.prompt,
      size: imageArgs.size,
      user: 'user-ai-tester',
    });

    const imageUrl = imageResponse.data?.[0]?.url;
    console.log('🖼️ Image URL:', imageUrl);

    return NextResponse.json({ imageUrl });
  } catch (err: any) {
    console.error('💥 Error in /api/generate:', err);
    return NextResponse.json({ error: 'Image generation failed' }, { status: 500 });
  }
}
