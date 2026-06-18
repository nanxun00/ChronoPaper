import { authHeaders, handleUnauthorized } from './client'

function shouldForceLogin(status, url, detail = '') {
  if (status !== 401 || String(url).includes('/token')) return false
  const text = String(detail)
  if (text.includes('未找到该服务')) return false
  return text.includes('登录') || text.includes('过期') || text.includes('credentials') || text.includes('凭证') || !text
}

/**
 * DeepSeek 流式翻译。onChunk({ content, done, error })
 */
export async function streamTranslate({ text, targetLang = 'zh', signal, onChunk }) {
  const response = await fetch('/api/translate/stream', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ text, target_lang: targetLang }),
    signal,
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const detail = data.detail || data.error || `翻译请求失败 (${response.status})`
    if (shouldForceLogin(response.status, '/api/translate/stream', detail)) {
      handleUnauthorized('登录已过期，请重新登录')
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      const data = JSON.parse(trimmed)
      onChunk?.(data)
      if (data.error) {
        throw new Error(data.error)
      }
      if (data.done) {
        return
      }
    }
  }
}

export function getTranslateConfig() {
  return fetch('/api/translate/config', { headers: authHeaders() }).then((r) => r.json())
}

export function previewCrawlQueryTranslation({ intent_text, keywords }) {
  return apiJson('/api/translate/crawl-query', {
    method: 'POST',
    body: JSON.stringify({ intent_text: intent_text || '', keywords: keywords || '' }),
  })
}
