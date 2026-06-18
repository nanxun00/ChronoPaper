import { apiJson, authFetch } from './client'

export function listPublicPapers(params = {}) {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.category) qs.set('category', params.category)
  if (params.source) qs.set('source', params.source)
  if (params.min_semantic != null && params.min_semantic !== '') qs.set('min_semantic', String(params.min_semantic))
  if (params.min_quality != null && params.min_quality !== '') qs.set('min_quality', String(params.min_quality))
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiJson(`/api/literature/public${query ? `?${query}` : ''}`)
}

export function listPrivatePapers(params = {}) {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.source) qs.set('source', params.source)
  if (params.min_semantic != null && params.min_semantic !== '') qs.set('min_semantic', String(params.min_semantic))
  if (params.min_quality != null && params.min_quality !== '') qs.set('min_quality', String(params.min_quality))
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiJson(`/api/literature/private${query ? `?${query}` : ''}`)
}

export function getPaperDetail(arxivId) {
  return apiJson(`/api/literature/paper/${encodeURIComponent(arxivId)}`)
}

export function deleteLiteratureEntries({ arxiv_ids, visibility }) {
  return apiJson('/api/literature/delete', {
    method: 'POST',
    body: JSON.stringify({ arxiv_ids, visibility }),
  })
}

export async function uploadLiteraturePdf(file, visibility, title) {
  const form = new FormData()
  form.append('file', file)
  form.append('visibility', visibility)
  if (title) form.append('title', title)
  const response = await authFetch('/api/literature/upload', {
    method: 'POST',
    body: form,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    let errMsg = data.message || `上传失败 (${response.status})`
    if (data.detail) {
      errMsg = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg || String(d)).join('；')
        : String(data.detail)
    }
    throw new Error(errMsg)
  }
  return data
}
