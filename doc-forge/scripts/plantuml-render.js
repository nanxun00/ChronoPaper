import plantumlEncoder from 'plantuml-encoder';
import fs from 'fs';
import path from 'path';
import https from 'https';

export function getPlantUMLUrl(umlCode, format = 'png') {
  const encoded = plantumlEncoder.encode(umlCode);
  return `https://www.plantuml.com/plantuml/${format}/${encoded}`;
}

function httpsRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const opts = {
      hostname: urlObj.hostname,
      port: 443,
      path: urlObj.pathname + urlObj.search,
      method: options.method || 'GET',
      headers: options.headers || {},
    };
    const req = https.request(opts, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        const redirects = (options.redirects || 0) + 1;
        if (redirects > 5) return reject(new Error('重定向次数过多'));
        resolve(httpsRequest(res.headers.location, { ...options, redirects }));
      } else {
        resolve(res);
      }
    });
    req.on('error', reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

async function downloadBuffer(url) {
  const res = await httpsRequest(url);
  return new Promise((resolve, reject) => {
    if (res.statusCode !== 200) {
      res.resume();
      return reject(new Error(`PlantUML 服务器返回 ${res.statusCode}`));
    }
    const chunks = [];
    res.on('data', chunk => chunks.push(chunk));
    res.on('end', () => resolve(Buffer.concat(chunks)));
    res.on('error', reject);
  });
}

async function pngToPdf(pngBuffer, outputPath) {
  const sharp = (await import('sharp')).default;
  const PDFDocument = (await import('pdfkit')).default;
  const meta = await sharp(pngBuffer).metadata();
  const width = meta.width || 800;
  const height = meta.height || 600;

  const doc = new PDFDocument({ size: [width, height], margin: 0 });
  const stream = fs.createWriteStream(outputPath);
  doc.pipe(stream);
  doc.image(pngBuffer, 0, 0, { width, height });
  doc.end();

  return new Promise((resolve, reject) => {
    stream.on('finish', () => resolve(outputPath));
    stream.on('error', reject);
  });
}

export async function downloadDiagram(umlCode, outputPath, format = 'png') {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });

  if (format === 'pdf') {
    // PDF：先下载 PNG 再转换为 PDF（PlantUML 公共服务器不支持直接 PDF 渲染）
    const pngUrl = getPlantUMLUrl(umlCode, 'png');
    const pngBuffer = await downloadBuffer(pngUrl);
    if (pngBuffer.toString('utf-8', 0, 5) === '<html') {
      throw new Error('PlantUML 服务器返回了 HTML 错误页面，渲染失败');
    }
    return pngToPdf(pngBuffer, outputPath);
  }

  const url = getPlantUMLUrl(umlCode, format);
  const buffer = await downloadBuffer(url);

  if (buffer.toString('utf-8', 0, 5) === '<html') {
    throw new Error('PlantUML 服务器返回了 HTML 错误页面，渲染失败');
  }
  fs.writeFileSync(outputPath, buffer);
  return outputPath;
}
