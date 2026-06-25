const LOGIN_PATHS = new Set(['/', '/login'])

/** 登录成功后应跳转的路径（过滤 `/`、空串与登录页，避免原地停留） */
export function resolvePostLoginRedirect(raw) {
  const fallback = '/chat'
  if (typeof raw !== 'string') return fallback

  const path = raw.trim()
  if (!path || path === '/') return fallback
  if (!path.startsWith('/') || path.startsWith('//')) return fallback

  const pathname = path.split('?')[0].split('#')[0]
  if (LOGIN_PATHS.has(pathname)) return fallback

  return path
}

/** Token and login state helpers */
export function getToken() {
  return sessionStorage.getItem('token')
}

export function getRoleId() {
  return sessionStorage.getItem('roleid')
}

export function isLoggedIn() {
  return Boolean(getToken())
}

export function clearAuth() {
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('roleid')
}
