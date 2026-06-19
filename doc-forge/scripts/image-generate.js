import OpenAI from 'openai';
import fs from 'fs';
import path from 'path';
import 'dotenv/config';
import { ProxyAgent, fetch as undiciFetch } from 'undici';

const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  ...(proxyUrl && {
    fetch: (url, init) => undiciFetch(url, {
      ...init,
      dispatcher: new ProxyAgent(proxyUrl),
    }),
  }),
});

const MODEL_CONFIGS = {
  'gpt-image-1':      { useB64: true,  defaultSize: '1024x1024', defaultQuality: 'medium' },
  'gpt-image-1-mini': { useB64: true,  defaultSize: '1024x1024', defaultQuality: 'medium' },
  'gpt-image-2':      { useB64: true,  defaultSize: '1024x1024', defaultQuality: 'medium' },
  'dall-e-3':         { useB64: false, defaultSize: '1024x1024', defaultQuality: 'standard' },
  'dall-e-2':         { useB64: false, defaultSize: '512x512',   defaultQuality: null },
};

export async function generateImage(prompt, outputPath, options = {}) {
  const model = options.model || process.env.IMAGE_PROVIDER || 'dall-e-3';
  const config = MODEL_CONFIGS[model];
  if (!config) throw new Error(`Unsupported model: ${model}. Choose from: ${Object.keys(MODEL_CONFIGS).join(', ')}`);

  const params = {
    model,
    prompt,
    n: 1,
    size: options.size || config.defaultSize,
  };
  if (config.defaultQuality) params.quality = options.quality || config.defaultQuality;

  const response = await client.images.generate(params);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  const item = response.data[0];
  if (item.b64_json) {
    fs.writeFileSync(outputPath, Buffer.from(item.b64_json, 'base64'));
  } else {
    const { fetch: undiciFetch, ProxyAgent } = await import('undici');
    const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
    const res = await undiciFetch(item.url, {
      dispatcher: proxyUrl ? new ProxyAgent(proxyUrl) : undefined,
    });
    fs.writeFileSync(outputPath, Buffer.from(await res.arrayBuffer()));
  }
  return outputPath;
}

// CLI 入口：node scripts/image-generate.js --model dall-e-3 --prompt "..." --out output/images/banner.png
if (process.argv[1]?.endsWith('image-generate.js')) {
  const args = Object.fromEntries(
    process.argv.slice(2)
      .filter(a => a.startsWith('--'))
      .map(a => a.slice(2).split('='))
      .map(([k, ...v]) => [k, v.join('=')])
  );
  if (!args.prompt || !args.out) {
    console.error('Usage: node scripts/image-generate.js --prompt "..." --out <path> [--model dall-e-3|gpt-image-1|dall-e-2]');
    process.exit(1);
  }
  generateImage(args.prompt, args.out, { model: args.model })
    .then(p => console.log(`✔ 图像已生成：${p}`))
    .catch(e => { console.error(`✘ 生成失败：${e.message}`); process.exit(1); });
}
