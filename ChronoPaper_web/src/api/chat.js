import { apiJson, authFetch } from './client'

export function listConversations() {
  return apiJson('/api/chat/conversations')
}

export function createConversation(body = {}) {
  return apiJson('/api/chat/conversations', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getConversation(convId) {
  return apiJson(`/api/chat/conversations/${encodeURIComponent(convId)}`)
}

export function updateConversation(convId, body) {
  return apiJson(`/api/chat/conversations/${encodeURIComponent(convId)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function deleteConversation(convId) {
  return apiJson(`/api/chat/conversations/${encodeURIComponent(convId)}`, {
    method: 'DELETE',
  })
}

export function deleteMessageTurn(convId, assistantMsgId) {
  return apiJson(
    `/api/chat/conversations/${encodeURIComponent(convId)}/turns/${encodeURIComponent(assistantMsgId)}`,
    { method: 'DELETE' },
  )
}

export async function postChat(body) {
  const response = await authFetch('/api/chat/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return response
}

export async function fetchChatRefs(curResId) {
  const response = await authFetch(`/api/chat/refs?cur_res_id=${encodeURIComponent(curResId)}`)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.detail || `请求失败 (${response.status})`)
  }
  return data
}

export async function callChat(query, meta = null) {
  return apiJson('/api/chat/call', {
    method: 'POST',
    body: JSON.stringify({ query, meta }),
  })
}
