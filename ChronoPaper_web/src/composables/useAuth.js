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
