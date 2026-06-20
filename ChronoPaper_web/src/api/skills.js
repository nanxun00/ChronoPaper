import { apiJson } from './client'

export function listSkills() {
  return apiJson('/api/skills/')
}

export function reloadSkills() {
  return apiJson('/api/skills/reload', { method: 'POST' })
}

export function patchSkill(skillId, enabled) {
  return apiJson(`/api/skills/${encodeURIComponent(skillId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled }),
  })
}

export function approveSkillCodegen(body) {
  return apiJson('/api/skills/codegen/approve', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function uploadSkillZip(file) {
  const form = new FormData()
  form.append('file', file)
  const token = sessionStorage.getItem('token')
  const response = await fetch('/api/skills/upload', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.detail || `上传失败 (${response.status})`)
  }
  return data
}
