import { apiJson, authFetch } from './client'

export function listPublicPapers(params = {}) {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.category) qs.set('category', params.category)
  if (params.source) qs.set('source', params.source)
  if (params.min_semantic != null && params.min_semantic !== '') qs.set('min_semantic', String(params.min_semantic))
  if (params.min_quality != null && params.min_quality !== '') qs.set('min_quality', String(params.min_quality))
  if (params.review_status) qs.set('review_status', params.review_status)
  if (params.page) qs.set('page', String(params.page))
  if (params.page_size) qs.set('page_size', String(params.page_size))
  const query = qs.toString()
  return apiJson(`/api/literature/public${query ? `?${query}` : ''}`)
}

export function listPrivatePapers(params = {}) {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.source) qs.set('source', params.source)
  if (params.library_id) qs.set('library_id', params.library_id)
  if (params.min_semantic != null && params.min_semantic !== '') qs.set('min_semantic', String(params.min_semantic))
  if (params.min_quality != null && params.min_quality !== '') qs.set('min_quality', String(params.min_quality))
  if (params.review_status) qs.set('review_status', params.review_status)
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

export function approveLiteratureEntries({ arxiv_ids, visibility }) {
  return apiJson('/api/literature/approve', {
    method: 'POST',
    body: JSON.stringify({ arxiv_ids, visibility }),
  })
}

export function rejectLiteratureEntries({ arxiv_ids, visibility }) {
  return apiJson('/api/literature/reject', {
    method: 'POST',
    body: JSON.stringify({ arxiv_ids, visibility }),
  })
}

export function parseLiteratureEntries({ arxiv_ids, visibility }) {
  return apiJson('/api/literature/parse', {
    method: 'POST',
    body: JSON.stringify({ arxiv_ids, visibility }),
  })
}

export function indexLiteratureEntries({ arxiv_ids, visibility }) {
  return apiJson('/api/literature/index', {
    method: 'POST',
    body: JSON.stringify({ arxiv_ids, visibility }),
  })
}

export function graphIndexLiteratureEntries({ arxiv_ids, visibility }) {
  return apiJson('/api/literature/graph-index', {
    method: 'POST',
    body: JSON.stringify({ arxiv_ids, visibility }),
  })
}

export function fetchLiteraturePdf({ arxiv_ids, visibility }) {
  return apiJson('/api/literature/fetch-pdf', {
    method: 'POST',
    body: JSON.stringify({ arxiv_ids, visibility }),
  })
}

export async function uploadLiteraturePdf(file, visibility, title, libraryId) {
  const form = new FormData()
  form.append('file', file)
  form.append('visibility', visibility)
  if (title) form.append('title', title)
  if (libraryId) form.append('library_id', libraryId)
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

export function listLiteratureLibraries() {
  return apiJson('/api/literature/libraries')
}

export function createLiteratureLibrary(body) {
  return apiJson('/api/literature/libraries', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function deleteLiteratureLibrary(libraryId) {
  return apiJson(`/api/literature/libraries/${encodeURIComponent(libraryId)}`, {
    method: 'DELETE',
  })
}
