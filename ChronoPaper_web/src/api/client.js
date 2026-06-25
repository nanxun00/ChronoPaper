import { message } from 'ant-design-vue'
import { useUserStore } from '@/stores'

let redirecting401 = false
let authVersion = 0

export function notifyAuthSessionChanged() {
  authVersion += 1
  redirecting401 = false
}

export function saveAuthSession(token, roleid) {
  sessionStorage.setItem('token', token)
  if (roleid != null && roleid !== '') {
    sessionStorage.setItem('roleid', String(roleid))
  }
  notifyAuthSessionChanged()
}

export function clearAuthSession() {
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('roleid')
  notifyAuthSessionChanged()
  try {
    useUserStore().logout()
  } catch {
    // Pinia 尚未初始化时忽略
  }
}

/** Token 失效：清登录态并强制回到首页登录 */
export function handleUnauthorized(reason = '登录已过期，请重新登录') {
  if (redirecting401) return
  redirecting401 = true

  clearAuthSession()
  message.warning(reason)

  const loginUrl = new URL('/', window.location.origin)
  loginUrl.searchParams.set('expired', '1')
  if (window.location.pathname !== '/') {
    window.location.replace(loginUrl.toString())
  } else {
    redirecting401 = false
  }
}

export function authHeaders(extra = {}) {
  const token = sessionStorage.getItem('token')
  const headers = { ...extra }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

function shouldForceLogin(status, url, detail = '') {
  if (status !== 401 || String(url).includes('/token')) return false
  const text = String(detail)
  if (text.includes('未找到该服务')) return false
  return (
    text.includes('登录') ||
    text.includes('过期') ||
    text.includes('credentials') ||
    text.includes('凭证') ||
    !text
  )
}

function parseErrorMessage(data, status) {
  let errMsg = data.message || `请求失败 (${status})`
  if (data.detail) {
    errMsg = Array.isArray(data.detail)
      ? data.detail.map((d) => d.msg || String(d)).join('；')
      : String(data.detail)
  }
  return errMsg
}

function handleStaleUnauthorized(versionAtStart) {
  return versionAtStart !== authVersion
}

/** 带鉴权头的 fetch，仅真实鉴权失败时强制回登录页 */
export async function authFetch(url, options = {}) {
  const versionAtStart = authVersion
  const response = await fetch(url, {
    ...options,
    headers: authHeaders(options.headers || {}),
  })
  if (response.status === 401 && !String(url).includes('/token')) {
    const data = await response.clone().json().catch(() => ({}))
    const errMsg = parseErrorMessage(data, response.status)
    if (shouldForceLogin(response.status, url, errMsg)) {
      if (handleStaleUnauthorized(versionAtStart)) {
        throw new Error('登录状态已更新，请重试')
      }
      handleUnauthorized(errMsg.includes('登录') ? errMsg : '登录已过期，请重新登录')
      throw new Error('登录已过期，请重新登录')
    }
  }
  return response
}

export async function apiJson(url, options = {}) {
  const versionAtStart = authVersion
  const response = await fetch(url, {
    ...options,
    headers: authHeaders({
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const errMsg = parseErrorMessage(data, response.status)
    if (shouldForceLogin(response.status, url, errMsg)) {
      if (!handleStaleUnauthorized(versionAtStart)) {
        handleUnauthorized(errMsg.includes('登录') ? errMsg : '登录已过期，请重新登录')
      }
    }
    throw new Error(errMsg)
  }
  return data
}
