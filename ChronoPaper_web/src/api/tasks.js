import { apiJson } from './client'

export function listTasks() {
  return apiJson('/api/tasks')
}

export function createCrawlTask(payload) {
  return apiJson('/api/tasks/crawl', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getTask(taskId) {
  return apiJson(`/api/tasks/${taskId}`)
}

export function runTask(taskId) {
  return apiJson(`/api/tasks/${taskId}/run`, { method: 'POST' })
}

export function cancelTask(taskId) {
  return apiJson(`/api/tasks/${taskId}/cancel`, { method: 'POST' })
}
