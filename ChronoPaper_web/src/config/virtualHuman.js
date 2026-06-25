const DEFAULT_AVATAR_ID = '201353001'
const DEFAULT_VCN = 'x4_chaoge'
const DEFAULT_SCENE_ID = '327375606956298240'
const DEFAULT_SERVER_URL = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact'

const normalizeAvatarId = (value) => {
  const id = String(value || DEFAULT_AVATAR_ID)
  return id === '201355001' ? DEFAULT_AVATAR_ID : id
}

const normalizeVcn = (value) => {
  const vcn = String(value || DEFAULT_VCN)
  return vcn === 'x4_mingge' ? DEFAULT_VCN : vcn
}

const parseAvatarOptions = () => {
  const raw = import.meta.env.VITE_VH_AVATAR_OPTIONS
  if (!raw) {
    return [{ id: DEFAULT_AVATAR_ID, label: DEFAULT_VCN, vcn: DEFAULT_VCN }]
  }

  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length > 0) {
      return parsed
        .filter((item) => item && item.id)
        .map((item) => ({
          id: normalizeAvatarId(item.id),
          label: item.label === 'x4_mingge' ? DEFAULT_VCN : (item.label || normalizeAvatarId(item.id)),
          vcn: normalizeVcn(item.vcn),
        }))
    }
  } catch (err) {
    console.warn('[virtualHuman] invalid VITE_VH_AVATAR_OPTIONS', err)
  }

  return [{ id: DEFAULT_AVATAR_ID, label: DEFAULT_VCN, vcn: DEFAULT_VCN }]
}

export const virtualHumanApiConfig = {
  appId: import.meta.env.VITE_VH_APP_ID || '',
  apiKey: import.meta.env.VITE_VH_API_KEY || '',
  apiSecret: import.meta.env.VITE_VH_API_SECRET || '',
  sceneId: import.meta.env.VITE_VH_SCENE_ID || DEFAULT_SCENE_ID,
  serverUrl: import.meta.env.VITE_VH_SERVER_URL || DEFAULT_SERVER_URL,
}

export const virtualHumanDefaults = {
  defaultAvatarId: normalizeAvatarId(import.meta.env.VITE_VH_DEFAULT_AVATAR_ID),
  defaultVcn: normalizeVcn(import.meta.env.VITE_VH_DEFAULT_VCN),
}

export const virtualHumanAvatarOptions = parseAvatarOptions()

const XRTC_PROXY_PATH = String(import.meta.env.VITE_VH_XRTC_PROXY_PATH || '').trim()
const XRTC_ORIGIN_HOST = String(import.meta.env.VITE_VH_XRTC_ORIGIN_HOST || '').trim()
const XRTC_TARGET_HOST = String(import.meta.env.VITE_VH_XRTC_TARGET_HOST || '').trim()

function resolveStreamOriginHost() {
  if (XRTC_ORIGIN_HOST) return XRTC_ORIGIN_HOST
  if (!XRTC_PROXY_PATH || typeof window === 'undefined') return ''
  const { hostname, port } = window.location
  return port ? `${hostname}:${port}` : hostname
}

/** 开发环境经 Vite 代理 XRTC 时的本地 originHost */
export const virtualHumanStreamProxy = {
  get originHost() {
    return resolveStreamOriginHost()
  },
  proxyPath: XRTC_PROXY_PATH,
}

/** 讯飞 XRTC 真实目标域名，仅在配置了代理时使用 */
export function getXrtcProxyTargetHost() {
  return XRTC_TARGET_HOST
}
