<template>
  <aside
    v-show="state.visible"
    ref="panelRef"
    class="virtual-human-panel"
    :class="{ 'is-collapsed': state.collapsed, 'is-dragging': dragState.dragging }"
    :style="panelStyle"
  >
    <div v-if="state.collapsed" class="vh-mini" @pointerdown="startDrag">
      <button
        type="button"
        class="vh-mini-avatar"
        title="展开数字虚拟人"
        aria-label="展开数字虚拟人"
        @click.stop="toggleCollapsed"
      >
        <span class="vh-mini-avatar__figure">
          <RobotOutlined />
        </span>
        <span class="vh-mini-avatar__label">AI客服小飞</span>
      </button>
      <div class="vh-mini-card">
        <button
          type="button"
          class="vh-mini-action"
          title="在线咨询"
          aria-label="在线咨询"
          @click.stop="openQuestionConsult"
        >
          <CustomerServiceOutlined />
          <span>在线<br>咨询</span>
        </button>
        <button
          type="button"
          class="vh-mini-action"
          title="语音咨询"
          aria-label="语音咨询"
          @click.stop="openVoiceConsult"
        >
          <PhoneOutlined />
          <span>语音<br>咨询</span>
        </button>
        <button
          type="button"
          class="vh-mini-close"
          title="关闭"
          aria-label="关闭数字虚拟人"
          @click.stop="hidePanel"
        >
          <CloseOutlined />
        </button>
      </div>
    </div>

    <header v-else class="vh-header" @pointerdown="startDrag">
      <div class="vh-brand">
        <RobotOutlined class="vh-brand__icon" />
        <div class="vh-brand__text">
          <div class="vh-brand__title">Virtual Human</div>
          <div class="vh-brand__status">{{ statusText }}</div>
        </div>
      </div>

      <div class="vh-toolbar">
        <button
          type="button"
          class="vh-icon-btn"
          :title="state.muted ? 'Unmute' : 'Mute'"
          :aria-label="state.muted ? 'Unmute virtual human' : 'Mute virtual human'"
          @click="toggleMuted"
        >
          <component :is="state.muted ? AudioMutedOutlined : AudioOutlined" />
        </button>
        <button
          type="button"
          class="vh-icon-btn"
          :title="state.collapsed ? 'Expand' : 'Collapse'"
          :aria-label="state.collapsed ? 'Expand virtual human panel' : 'Collapse virtual human panel'"
          @click="toggleCollapsed"
        >
          <component :is="state.collapsed ? ExpandOutlined : CompressOutlined" />
        </button>
        <button
          type="button"
          class="vh-icon-btn"
          title="Hide"
          aria-label="Hide virtual human panel"
          @click="hidePanel"
        >
          <CloseOutlined />
        </button>
      </div>
    </header>

    <div v-show="!state.collapsed" class="vh-body">
      <section class="vh-stage" @click="focusQuestionInput">
        <div ref="stageRef" class="vh-stage__mount"></div>
        <div v-if="showPlaceholder" class="vh-placeholder">
          <LoadingOutlined v-if="state.loading || state.resourceLoading" spin />
          <RobotOutlined v-else />
          <span>{{ placeholderText }}</span>
        </div>
        <form
          v-if="state.questionInputVisible || state.listening || state.voiceProcessing"
          class="vh-conversation"
          @submit.prevent="submitQuestion"
          @click.stop
        >
          <button
            type="button"
            class="vh-round-btn"
            :class="{ active: state.listening }"
            :title="state.listening ? '停止语音输入' : '语音输入'"
            :aria-label="state.listening ? '停止语音输入' : '语音输入'"
            :disabled="state.voiceProcessing"
            @click="toggleVoiceInput"
          >
            <LoadingOutlined v-if="state.voiceProcessing" spin />
            <AudioOutlined v-else />
          </button>
          <div class="vh-question-box" :class="{ 'is-listening': state.listening || state.voiceProcessing }">
            <span v-if="state.listening || state.voiceProcessing" class="vh-voice-text">
              {{ voiceStatusText }}
            </span>
            <input
              v-else
              ref="questionInputRef"
              v-model="state.questionText"
              class="vh-question-input"
              type="text"
              placeholder="请输入你的问题"
              autocomplete="off"
              @keydown.stop
              @keyup.esc.stop.prevent="hideQuestionInput"
            >
            <button
              type="submit"
              class="vh-send-btn"
              title="发送"
              aria-label="发送问题"
              :disabled="!state.questionText.trim() || state.voiceProcessing"
            >
              <SendOutlined />
            </button>
          </div>
        </form>
        <div v-if="state.voiceError" class="vh-voice-error">{{ state.voiceError }}</div>
      </section>

      <section class="vh-meta">
        <div class="vh-meta__row">
          <span class="vh-meta__label">Avatar</span>
          <span class="vh-meta__value">{{ currentAvatarLabel }}</span>
        </div>
        <div class="vh-avatar-list" aria-label="Avatar switcher">
          <button
            v-for="item in normalizedAvatarOptions"
            :key="item.id"
            type="button"
            class="vh-avatar-chip"
            :class="{ active: item.id === state.currentAvatarId }"
            :disabled="state.loading || item.id === state.currentAvatarId"
            @click="switchAvatar(item.id)"
          >
            <SwapOutlined v-if="item.id !== state.currentAvatarId" />
            <RobotOutlined v-else />
            <span>{{ item.label }}</span>
          </button>
        </div>
      </section>
    </div>
  </aside>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import {
  AudioMutedOutlined,
  AudioOutlined,
  CustomerServiceOutlined,
  CloseOutlined,
  CompressOutlined,
  ExpandOutlined,
  LoadingOutlined,
  RobotOutlined,
  PhoneOutlined,
  SendOutlined,
  SwapOutlined,
} from '@ant-design/icons-vue'
import AvatarPlatform from '@/vendor/avatar-sdk-web_3.2.3.1002/esm/index.js'
import { audioBlobToWav16k } from '@/utils/audioPcm'

const DEFAULT_AVATAR_ID = '201353001'
const DEFAULT_VCN = 'x4_chaoge'
const DEFAULT_SERVER_URL = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact'
const MAX_SPEECH_CHUNK_LENGTH = 160
const PANEL_POSITION_KEY = 'virtual-human-panel-position'
const PANEL_MARGIN = 8
const NO_VOICE_TIMEOUT_MS = 10000
const VOICE_ACTIVITY_THRESHOLD = 0.018

const props = defineProps({
  apiConfig: {
    type: Object,
    default: () => ({}),
  },
  avatarOptions: {
    type: Array,
    default: () => [],
  },
  defaultAvatarId: {
    type: [String, Number],
    default: DEFAULT_AVATAR_ID,
  },
  defaultVcn: {
    type: String,
    default: DEFAULT_VCN,
  },
})
const emit = defineEmits(['request-close', 'speech-end', 'submit-question'])

const state = reactive({
  visible: true,
  collapsed: false,
  muted: false,
  sdkHidden: false,
  loading: false,
  ready: false,
  speaking: false,
  status: 'idle',
  errorMessage: '',
  currentAvatarId: String(props.defaultAvatarId || DEFAULT_AVATAR_ID),
  resourceLoading: false,
  questionText: '',
  questionInputVisible: false,
  listening: false,
  voiceProcessing: false,
  voiceError: '',
  panelX: null,
  panelY: null,
})

const panelRef = ref(null)
const stageRef = ref(null)
const questionInputRef = ref(null)
const platform = shallowRef(null)
const initPromise = shallowRef(null)
const manualStop = ref(false)
const temporaryPlayerMuted = ref(false)
const mediaRecorder = shallowRef(null)
let manualStopTimer = null
let speechRunSeq = 0
let chunkPlaybackActive = false
let pendingFrameStopResolve = null
let pendingFrameStopTimer = null
let pendingFrameStopReadyAt = 0
let voiceChunks = []
let voiceRecordingTimer = null
let resourceLoadingTimer = null
let voiceAudioContext = null
let voiceAnalyser = null
let voiceLevelBuffer = null
let voiceActivityTimer = null
let voiceActivityDetected = false

const dragState = reactive({
  dragging: false,
  pointerId: null,
  offsetX: 0,
  offsetY: 0,
})

const panelStyle = computed(() => {
  if (state.panelX === null || state.panelY === null) {
    return {
      top: '72px',
      right: '24px',
      left: 'auto',
      bottom: 'auto',
    }
  }

  return {
    left: `${state.panelX}px`,
    top: `${state.panelY}px`,
    right: 'auto',
    bottom: 'auto',
  }
})

const holdManualStop = (duration = 3000) => {
  manualStop.value = true
  if (manualStopTimer) {
    clearTimeout(manualStopTimer)
  }
  manualStopTimer = setTimeout(() => {
    manualStop.value = false
    manualStopTimer = null
  }, duration)
}

const releaseManualStop = () => {
  if (manualStopTimer) {
    clearTimeout(manualStopTimer)
    manualStopTimer = null
  }
  manualStop.value = false
}

const isCurrentPlatform = (instance) => platform.value === instance

const stopResourceLoading = () => {
  if (resourceLoadingTimer) {
    clearTimeout(resourceLoadingTimer)
    resourceLoadingTimer = null
  }
  state.resourceLoading = false
}

const startResourceLoading = (duration = 3200) => {
  state.resourceLoading = true
  if (resourceLoadingTimer) {
    clearTimeout(resourceLoadingTimer)
  }
  resourceLoadingTimer = setTimeout(() => {
    resourceLoadingTimer = null
    state.resourceLoading = false
  }, duration)
}

const getPanelSize = () => {
  const el = panelRef.value
  return {
    width: el?.offsetWidth || (state.collapsed ? 64 : 320),
    height: el?.offsetHeight || (state.collapsed ? 180 : 680),
  }
}

const clampPanelPosition = (x, y) => {
  if (typeof window === 'undefined') return { x, y }
  const { width, height } = getPanelSize()
  const maxX = Math.max(PANEL_MARGIN, window.innerWidth - width - PANEL_MARGIN)
  const maxY = Math.max(PANEL_MARGIN, window.innerHeight - height - PANEL_MARGIN)
  return {
    x: Math.min(Math.max(PANEL_MARGIN, x), maxX),
    y: Math.min(Math.max(PANEL_MARGIN, y), maxY),
  }
}

const persistPanelPosition = () => {
  if (typeof window === 'undefined' || state.panelX === null || state.panelY === null) return
  try {
    window.localStorage.setItem(PANEL_POSITION_KEY, JSON.stringify({
      x: state.panelX,
      y: state.panelY,
    }))
  } catch (err) {
    console.warn('[virtualHuman] save panel position failed', err)
  }
}

const applyPanelPosition = (x, y, { persist = true } = {}) => {
  const next = clampPanelPosition(x, y)
  state.panelX = next.x
  state.panelY = next.y
  if (persist) {
    persistPanelPosition()
  }
}

const ensurePanelPosition = () => {
  if (typeof window === 'undefined') return
  if (state.panelX !== null && state.panelY !== null) {
    applyPanelPosition(state.panelX, state.panelY, { persist: false })
    return
  }

  try {
    const raw = window.localStorage.getItem(PANEL_POSITION_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Number.isFinite(parsed?.x) && Number.isFinite(parsed?.y)) {
        applyPanelPosition(parsed.x, parsed.y, { persist: false })
        return
      }
    }
  } catch (err) {
    console.warn('[virtualHuman] load panel position failed', err)
  }

  const { width } = getPanelSize()
  applyPanelPosition(window.innerWidth - width - 24, 72, { persist: false })
}

const resolvePendingFrameStop = (completed = false) => {
  if (pendingFrameStopTimer) {
    clearTimeout(pendingFrameStopTimer)
    pendingFrameStopTimer = null
  }
  if (pendingFrameStopResolve) {
    const resolve = pendingFrameStopResolve
    pendingFrameStopResolve = null
    resolve(completed)
  }
}

const estimateChunkDuration = (chunk) => {
  return Math.min(45000, Math.max(9000, String(chunk || '').length * 360))
}

const waitForFrameStop = (runId, chunk) => new Promise((resolve) => {
  resolvePendingFrameStop(false)
  pendingFrameStopReadyAt = Date.now() + 700
  pendingFrameStopResolve = (completed) => {
    resolve(Boolean(completed) && runId === speechRunSeq)
  }
  pendingFrameStopTimer = setTimeout(() => {
    resolvePendingFrameStop(runId === speechRunSeq)
  }, estimateChunkDuration(chunk))
})

const resolvedApiConfig = computed(() => ({
  appId: props.apiConfig?.appId || '',
  apiKey: props.apiConfig?.apiKey || '',
  apiSecret: props.apiConfig?.apiSecret || '',
  sceneId: props.apiConfig?.sceneId || '',
  serverUrl: props.apiConfig?.serverUrl || DEFAULT_SERVER_URL,
}))

const normalizedAvatarOptions = computed(() => {
  const fallback = {
    id: String(props.defaultAvatarId || DEFAULT_AVATAR_ID),
    label: 'Default Avatar',
    vcn: props.defaultVcn || DEFAULT_VCN,
  }
  const source = Array.isArray(props.avatarOptions) ? props.avatarOptions : []
  const normalized = source
    .filter((item) => item && item.id)
    .map((item) => ({
      id: String(item.id),
      label: item.label || String(item.id),
      vcn: item.vcn ? String(item.vcn) : undefined,
    }))

  if (normalized.length === 0) {
    return [fallback]
  }

  if (!normalized.some((item) => item.id === state.currentAvatarId)) {
    return [...normalized, { ...fallback, id: state.currentAvatarId, label: state.currentAvatarId }]
  }

  return normalized
})

const currentAvatar = computed(() => (
  normalizedAvatarOptions.value.find((item) => item.id === state.currentAvatarId)
  || normalizedAvatarOptions.value[0]
))

const currentAvatarLabel = computed(() => currentAvatar.value?.label || state.currentAvatarId)
const currentVcn = computed(() => currentAvatar.value?.vcn || props.defaultVcn || DEFAULT_VCN)

const statusText = computed(() => {
  if (state.resourceLoading) return '资源加载中'
  if (state.sdkHidden) return 'SDK unavailable'
  if (state.loading) return 'Initializing'
  if (state.speaking) return state.muted ? 'Speaking muted' : 'Speaking'
  if (state.ready) return state.muted ? 'Ready muted' : 'Ready'
  if (state.errorMessage) return 'Unavailable'
  return 'Idle'
})

const placeholderText = computed(() => {
  if (state.resourceLoading) return '资源加载中.....'
  if (state.sdkHidden) return 'SDK unavailable'
  if (state.loading) return 'Initializing SDK'
  if (state.errorMessage) return state.errorMessage
  return 'Waiting for SDK'
})

const showPlaceholder = computed(() => (
  state.loading || state.resourceLoading || state.sdkHidden || !state.ready
))

const voiceStatusText = computed(() => {
  if (state.voiceProcessing) return '正在识别语音...'
  if (state.listening) return '正在聆听中...'
  return ''
})

const formatError = (err) => {
  if (!err) return 'Virtual human SDK error'
  return err.message || err.msg || String(err)
}

const isConfigError = (err) => formatError(err).startsWith('Missing virtual human config')

const validateApiConfig = () => {
  const api = resolvedApiConfig.value
  const missing = ['appId', 'apiKey', 'apiSecret', 'sceneId', 'serverUrl'].filter((key) => !api[key])
  if (missing.length > 0) {
    throw new Error(`Missing virtual human config: ${missing.join(', ')}`)
  }
}

const buildGlobalParams = (avatarId = state.currentAvatarId) => ({
  stream: {
    protocol: 'xrtc',
    fps: 25,
    bitrate: 1000000,
    alpha: 1,
  },
  avatar: {
    avatar_id: String(avatarId),
    width: 1080,
    height: 1920,
    mask_region: '[0,0,1080,1920]',
    scale: 1,
    move_h: 0,
    move_v: 0,
    audio_format: 1,
  },
  tts: {
    vcn: currentVcn.value,
    speed: 50,
    pitch: 50,
    volume: 100,
  },
  avatar_dispatch: {
    interactive_mode: 0,
    enable_action_status: 1,
    content_analysis: 1,
  },
  air: {
    air: 1,
    add_nonsemantic: 1,
  },
  subtitle: {
    subtitle: 0,
    font_color: '#FFFFFF',
  },
})

const buildPlayExtend = () => ({
  nlp: false,
  tts: {
    vcn: currentVcn.value,
    speed: 50,
    pitch: 50,
    volume: 100,
    audio: {
      sample_rate: 16000,
    },
  },
  avatar_dispatch: {
    interactive_mode: 0,
    enable_action_status: 1,
    content_analysis: 1,
  },
  air: {
    air: 1,
    add_nonsemantic: 1,
  },
})

const stripMarkdownForSpeech = (text) => {
  return String(text ?? '')
    .replace(/\r\n?/g, '\n')
    .replace(/```[\s\S]*?```/g, ' 这里有一段代码内容，已略过。 ')
    .replace(/\$\$[\s\S]*?\$\$/g, ' 这里有一个公式，已略过。 ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\(([^)]*)\)/g, '$1')
    .replace(/https?:\/\/[^\s)]+/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '和')
    .replace(/&lt;/gi, '小于')
    .replace(/&gt;/gi, '大于')
    .replace(/&quot;/gi, '"')
    .replace(/^\s*\|?[\s:-]{3,}\|[\s|:-]*$/gm, ' ')
    .replace(/^\s{0,3}#{1,6}\s*/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+[.)]\s+/gm, '')
    .replace(/\[\[(?:cmd|action|txt|src|img|video|link|h5_url|options)=[\s\S]*?\]\]/gi, ' ')
    .replace(/\[[\s\S]*?\]/g, (match) => match.length <= 40 ? match.replace(/\[/g, '（').replace(/\]/g, '）') : ' ')
    .replace(/[|*_~]/g, ' ')
    .replace(/[{}<>]/g, ' ')
    .replace(/[\u0000-\u001f\u007f]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

const splitLongSentence = (sentence) => {
  const chunks = []
  let cursor = 0
  while (cursor < sentence.length) {
    chunks.push(sentence.slice(cursor, cursor + MAX_SPEECH_CHUNK_LENGTH))
    cursor += MAX_SPEECH_CHUNK_LENGTH
  }
  return chunks
}

const buildSpeechChunks = (text) => {
  const cleaned = stripMarkdownForSpeech(text)
  if (!cleaned) return []

  const sentences = cleaned.match(/[^。！？!?；;\n]+[。！？!?；;]?/g) || [cleaned]
  const chunks = []
  let current = ''

  for (const rawSentence of sentences) {
    const sentence = rawSentence.trim()
    if (!sentence) continue

    if (sentence.length > MAX_SPEECH_CHUNK_LENGTH) {
      if (current) {
        chunks.push(current)
        current = ''
      }
      chunks.push(...splitLongSentence(sentence))
      continue
    }

    const next = current ? `${current} ${sentence}` : sentence
    if (next.length > MAX_SPEECH_CHUNK_LENGTH) {
      chunks.push(current)
      current = sentence
    } else {
      current = next
    }
  }

  if (current) {
    chunks.push(current)
  }

  return chunks.filter(Boolean)
}

const interruptCurrentSpeech = async () => {
  const instance = platform.value
  if (!instance || state.sdkHidden) return false

  holdManualStop()
  try {
    await instance.interrupt()
    temporaryPlayerMuted.value = false
    syncMutedState()
    state.speaking = false
    state.status = state.ready ? 'ready' : 'idle'
    return true
  } catch (err) {
    console.warn('[virtualHuman] interrupt failed', err)
    return false
  } finally {
    await nextTick()
  }
}

const applyPlayerMuted = (muted) => {
  const player = platform.value?.player
  if (!player) return

  try {
    player.defaultMuted = muted
    player.muted = muted
    if (!muted && typeof player.resume === 'function') {
      void player.resume().catch((err) => {
        console.warn('[virtualHuman] resume failed', err)
      })
    }
  } catch (err) {
    console.warn('[virtualHuman] sync mute failed', err)
  }
}

const syncMutedState = () => {
  applyPlayerMuted(state.muted || temporaryPlayerMuted.value)
}

const applyPlayAudioOptions = (options = {}) => {
  if (options?.forceUnmute) {
    state.muted = false
  }
  temporaryPlayerMuted.value = Boolean(options?.muteAudio)
  syncMutedState()
}

const destroyPlatform = async () => {
  const instance = platform.value
  if (!instance) return

  holdManualStop()
  chunkPlaybackActive = false
  resolvePendingFrameStop(false)
  stopResourceLoading()
  try {
    try {
      instance.stop()
    } catch (err) {
      console.warn('[virtualHuman] stop failed', err)
    }
    try {
      instance.destroy()
    } catch (err) {
      console.warn('[virtualHuman] destroy failed', err)
    }
  } finally {
    platform.value = null
    temporaryPlayerMuted.value = false
    state.ready = false
    state.speaking = false
    state.loading = false
    await nextTick()
  }
}

const handleSdkError = (err) => {
  chunkPlaybackActive = false
  resolvePendingFrameStop(false)
  stopResourceLoading()
  state.errorMessage = formatError(err)
  state.status = 'error'
  state.ready = false
  state.speaking = false
  state.loading = false
  temporaryPlayerMuted.value = false
  state.sdkHidden = true
  state.visible = true
  emit('speech-end')
  void destroyPlatform()
  console.warn('[virtualHuman] SDK unavailable', err)
}

const handleConfigError = (err) => {
  chunkPlaybackActive = false
  resolvePendingFrameStop(false)
  stopResourceLoading()
  state.errorMessage = formatError(err)
  state.status = 'config-missing'
  state.ready = false
  state.speaking = false
  state.loading = false
  temporaryPlayerMuted.value = false
  state.sdkHidden = false
  state.visible = true
  emit('speech-end')
  console.warn('[virtualHuman] config missing', err)
}

const recoverPlaybackFailure = (err) => {
  console.warn('[virtualHuman] playback failed', err)
  chunkPlaybackActive = false
  resolvePendingFrameStop(false)
  temporaryPlayerMuted.value = false
  syncMutedState()
  state.speaking = false
  state.errorMessage = ''
  state.status = state.ready ? 'ready' : 'idle'
  emit('speech-end')
}

const attachPlatformListeners = (instance) => {
  instance
    .on('connected', () => {
      if (!isCurrentPlatform(instance)) return
      state.loading = false
      state.ready = true
      state.sdkHidden = false
      state.status = 'ready'
      syncMutedState()
    })
    .on('stream_start', () => {
      if (!isCurrentPlatform(instance)) return
      state.loading = false
      state.ready = true
      state.status = 'streaming'
      syncMutedState()
    })
    .on('frame_start', () => {
      if (!isCurrentPlatform(instance)) return
      stopResourceLoading()
      state.speaking = true
      state.status = 'speaking'
    })
    .on('frame_stop', () => {
      if (!isCurrentPlatform(instance)) return
      if (chunkPlaybackActive) {
        if (Date.now() < pendingFrameStopReadyAt) return
        resolvePendingFrameStop(true)
        return
      }
      if (manualStop.value) return
      temporaryPlayerMuted.value = false
      syncMutedState()
      state.speaking = false
      state.status = 'ready'
      emit('speech-end')
    })
    .on('disconnected', (err) => {
      if (!isCurrentPlatform(instance)) return
      if (manualStop.value) return
      state.ready = false
      state.speaking = false
      state.status = 'disconnected'
      if (err) {
        handleSdkError(err)
      }
    })
    .on('error', (err) => {
      if (!isCurrentPlatform(instance)) return
      if (manualStop.value) return
      if (chunkPlaybackActive || state.speaking) {
        recoverPlaybackFailure(err)
        return
      }
      handleSdkError(err)
    })
}

const ensurePlatform = () => {
  if (platform.value) return platform.value

  const instance = new AvatarPlatform({ useInlinePlayer: true })
  attachPlatformListeners(instance)
  platform.value = instance
  return instance
}

const startPlatform = async () => {
  validateApiConfig()
  await nextTick()

  if (!stageRef.value) {
    throw new Error('Virtual human stage is not mounted')
  }

  const instance = ensurePlatform()
  instance.setApiInfo(resolvedApiConfig.value)
  instance.setGlobalParams(buildGlobalParams())

  startResourceLoading()
  state.loading = true
  state.errorMessage = ''
  state.status = 'initializing'
  await instance.start({ wrapper: stageRef.value })
  state.loading = false
  state.ready = true
  state.status = 'ready'
  syncMutedState()
  return instance
}

const init = async () => {
  if (platform.value && state.ready && !state.sdkHidden) {
    return platform.value
  }

  if (initPromise.value) {
    return initPromise.value
  }

  state.visible = true
  state.sdkHidden = false

  initPromise.value = startPlatform()
    .catch((err) => {
      if (isConfigError(err)) {
        handleConfigError(err)
      } else {
        handleSdkError(err)
      }
      throw err
    })
    .finally(() => {
      initPromise.value = null
    })

  return initPromise.value
}

const playText = async (text, options = {}) => {
  const chunks = buildSpeechChunks(text)
  if (chunks.length === 0) return false

  const runId = ++speechRunSeq
  chunkPlaybackActive = true
  resolvePendingFrameStop(false)

  if (state.sdkHidden) {
    state.sdkHidden = false
    state.errorMessage = ''
    state.status = 'idle'
  }

  const sendChunk = async (chunk) => {
    const sendWithInstance = async (instance) => {
      const frameStopPromise = waitForFrameStop(runId, chunk)
      try {
        await instance.writeText(chunk, buildPlayExtend())
      } catch (err) {
        resolvePendingFrameStop(false)
        throw err
      }
      state.speaking = true
      state.status = 'speaking'
      return frameStopPromise
    }

    try {
      return await sendWithInstance(platform.value || (await init()))
    } catch (err) {
      if (!manualStop.value) {
        throw err
      }
      console.warn('[virtualHuman] retry playText after interrupt', err)
      await destroyPlatform()
      const retryInstance = await init()
      applyPlayAudioOptions(options)
      return sendWithInstance(retryInstance)
    }
  }

  try {
    await init()
    if (state.speaking) {
      await interruptCurrentSpeech()
    }
    applyPlayAudioOptions(options)

    for (const chunk of chunks) {
      if (runId !== speechRunSeq) return false
      const completed = await sendChunk(chunk)
      if (!completed || runId !== speechRunSeq) return false
    }

    if (runId === speechRunSeq) {
      chunkPlaybackActive = false
      temporaryPlayerMuted.value = false
      syncMutedState()
      state.speaking = false
      state.status = 'ready'
      emit('speech-end')
    }
    return true
  } catch (err) {
    if (runId === speechRunSeq) {
      chunkPlaybackActive = false
      temporaryPlayerMuted.value = false
      syncMutedState()
    }
    if (isConfigError(err)) {
      handleConfigError(err)
    } else if (platform.value && state.ready && !state.sdkHidden) {
      recoverPlaybackFailure(err)
    } else {
      handleSdkError(err)
    }
    return false
  }
}

const stopPlay = async () => {
  speechRunSeq += 1
  chunkPlaybackActive = false
  resolvePendingFrameStop(false)
  const stopped = await interruptCurrentSpeech()
  emit('speech-end')
  return stopped
}

const showPanel = () => {
  state.visible = true
  if (!platform.value || !state.ready) {
    startResourceLoading()
  }
  nextTick(() => {
    ensurePanelPosition()
  })
  if (!state.sdkHidden && !platform.value && !state.loading) {
    void init().catch(() => undefined)
  }
  return true
}

const hidePanel = async () => {
  state.visible = false
  stopResourceLoading()
  await destroyPlatform()
  emit('request-close')
}

const refreshPlayerLayout = () => {
  const resize = platform.value?.player?.resize
  if (typeof resize === 'function') {
    try {
      resize.call(platform.value.player)
    } catch (err) {
      console.warn('[virtualHuman] resize failed', err)
    }
  }
}

const removeDragListeners = () => {
  if (typeof window === 'undefined') return
  window.removeEventListener('pointermove', handleDragMove)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
}

const stopDrag = () => {
  if (!dragState.dragging) return
  dragState.dragging = false
  dragState.pointerId = null
  removeDragListeners()
  persistPanelPosition()
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  refreshPlayerLayout()
}

const handleDragMove = (event) => {
  if (!dragState.dragging || event.pointerId !== dragState.pointerId) return
  const nextX = event.clientX - dragState.offsetX
  const nextY = event.clientY - dragState.offsetY
  const next = clampPanelPosition(nextX, nextY)
  state.panelX = next.x
  state.panelY = next.y
}

const startDrag = (event) => {
  if (event.button !== 0) return
  if (event.target?.closest?.('button, input, textarea, select, a, [role="button"]')) return
  if (typeof window === 'undefined') return

  ensurePanelPosition()
  dragState.dragging = true
  dragState.pointerId = event.pointerId
  dragState.offsetX = event.clientX - state.panelX
  dragState.offsetY = event.clientY - state.panelY
  event.currentTarget?.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', handleDragMove)
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'grabbing'
  event.preventDefault()
}

const handleWindowResize = () => {
  ensurePanelPosition()
  refreshPlayerLayout()
}

const toggleCollapsed = async () => {
  state.collapsed = !state.collapsed
  await nextTick()
  ensurePanelPosition()
  persistPanelPosition()
  if (!state.collapsed) {
    refreshPlayerLayout()
    setTimeout(refreshPlayerLayout, 220)
  }
}

const toggleMuted = () => {
  state.muted = !state.muted
  syncMutedState()
}

const focusQuestionInput = () => {
  if (!state.listening && !state.voiceProcessing) {
    state.questionInputVisible = true
    nextTick(() => {
      questionInputRef.value?.focus?.()
    })
  }
}

const openQuestionConsult = async () => {
  if (state.collapsed) {
    await toggleCollapsed()
  }
  focusQuestionInput()
}

const openVoiceConsult = async () => {
  if (state.collapsed) {
    await toggleCollapsed()
  }
  state.questionInputVisible = true
  await nextTick()
  if (!state.listening && !state.voiceProcessing) {
    void startVoiceInput()
  }
}

const hideQuestionInput = () => {
  if (state.listening || state.voiceProcessing) return
  if (!state.questionText.trim()) {
    state.questionInputVisible = false
    state.voiceError = ''
  }
}

const submitQuestion = (options = {}) => {
  const text = state.questionText.trim()
  if (!text || (state.voiceProcessing && !options.allowWhileProcessing)) return

  emit('submit-question', {
    text,
    done: (accepted = true) => {
      if (accepted !== false) {
        state.questionText = ''
        state.voiceError = ''
        state.questionInputVisible = false
      }
    },
  })
}

const getRecordingMime = () => {
  if (typeof MediaRecorder === 'undefined') return ''
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus'
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm'
  return ''
}

const clearVoiceTimer = () => {
  if (voiceRecordingTimer) {
    clearTimeout(voiceRecordingTimer)
    voiceRecordingTimer = null
  }
}

const stopVoiceTracks = () => {
  const stream = mediaRecorder.value?.stream
  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
  }
}

const stopVoiceActivityMonitor = () => {
  if (voiceActivityTimer) {
    clearInterval(voiceActivityTimer)
    voiceActivityTimer = null
  }
  if (voiceAudioContext) {
    void voiceAudioContext.close().catch((err) => {
      console.warn('[virtualHuman] close audio context failed', err)
    })
  }
  voiceAudioContext = null
  voiceAnalyser = null
  voiceLevelBuffer = null
}

const stopVoiceInputByNoVoice = () => {
  if (!state.listening || voiceActivityDetected) return
  stopVoiceInput({
    skipProcessing: true,
    message: '长时间无输入，已自动停止聆听',
  })
}

const calculateVoiceLevel = () => {
  if (!voiceAnalyser || !voiceLevelBuffer) return 0
  voiceAnalyser.getByteTimeDomainData(voiceLevelBuffer)
  let sum = 0
  for (const value of voiceLevelBuffer) {
    const normalized = (value - 128) / 128
    sum += normalized * normalized
  }
  return Math.sqrt(sum / voiceLevelBuffer.length)
}

const startVoiceActivityMonitor = (stream) => {
  stopVoiceActivityMonitor()
  voiceActivityDetected = false
  const startedAt = Date.now()
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext

  if (!AudioContextCtor) {
    voiceActivityTimer = setInterval(() => {
      if (Date.now() - startedAt >= NO_VOICE_TIMEOUT_MS) {
        stopVoiceInputByNoVoice()
      }
    }, 500)
    return
  }

  try {
    voiceAudioContext = new AudioContextCtor()
    voiceAnalyser = voiceAudioContext.createAnalyser()
    voiceAnalyser.fftSize = 2048
    voiceLevelBuffer = new Uint8Array(voiceAnalyser.fftSize)
    voiceAudioContext.createMediaStreamSource(stream).connect(voiceAnalyser)
    voiceActivityTimer = setInterval(() => {
      if (!state.listening || voiceActivityDetected) return
      const level = calculateVoiceLevel()
      if (level >= VOICE_ACTIVITY_THRESHOLD) {
        voiceActivityDetected = true
        stopVoiceActivityMonitor()
        return
      }
      if (Date.now() - startedAt >= NO_VOICE_TIMEOUT_MS) {
        stopVoiceInputByNoVoice()
      }
    }, 160)
  } catch (err) {
    console.warn('[virtualHuman] voice activity monitor failed', err)
    voiceActivityTimer = setInterval(() => {
      if (Date.now() - startedAt >= NO_VOICE_TIMEOUT_MS) {
        stopVoiceInputByNoVoice()
      }
    }, 500)
  }
}

const resetVoiceInput = () => {
  clearVoiceTimer()
  stopVoiceActivityMonitor()
  stopVoiceTracks()
  mediaRecorder.value = null
  state.listening = false
}

const processVoiceInput = async () => {
  const chunks = voiceChunks
  voiceChunks = []
  if (chunks.length === 0) {
    state.voiceProcessing = false
    return
  }

  state.voiceProcessing = true
  state.voiceError = ''

  try {
    const mimeType = getRecordingMime() || 'audio/webm'
    const recordedBlob = new Blob(chunks, { type: mimeType })
    const wavBlob = await audioBlobToWav16k(recordedBlob)
    const formData = new FormData()
    formData.append('file', new File([wavBlob], 'virtual-human-question.wav', { type: 'audio/wav' }))

    const token = sessionStorage.getItem('token')
    const response = await fetch('/api/audio/upload', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    })
    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}))
      const detail = typeof errBody === 'string' ? errBody : (errBody?.detail || '')
      throw new Error(detail || `HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    const text = typeof data === 'string' ? data : (data?.text || data?.detail || '')
    if (!text.trim()) {
      state.voiceError = '未识别到语音内容'
      return
    }

    state.questionText = text.trim()
    submitQuestion({ allowWhileProcessing: true })
  } catch (err) {
    state.voiceError = err.message || '语音识别失败'
    console.warn('[virtualHuman] voice input failed', err)
  } finally {
    state.voiceProcessing = false
  }
}

const stopVoiceInput = (options = {}) => {
  const recorder = mediaRecorder.value
  if (!recorder || recorder.state === 'inactive') {
    resetVoiceInput()
    if (options.message) {
      voiceChunks = []
      state.voiceProcessing = false
      state.voiceError = options.message
    }
    return
  }

  try {
    state.voiceProcessing = !options.skipProcessing
    if (options.skipProcessing) {
      recorder.onstop = null
      recorder.ondataavailable = null
    }
    if (typeof recorder.requestData === 'function') {
      recorder.requestData()
    }
    recorder.stop()
    if (options.skipProcessing) {
      voiceChunks = []
      state.voiceProcessing = false
      state.voiceError = options.message || '长时间无输入，已自动停止聆听'
    }
  } catch (err) {
    state.voiceProcessing = false
    state.voiceError = err.message || '停止录音失败'
    console.warn('[virtualHuman] stop voice input failed', err)
  } finally {
    resetVoiceInput()
  }
}

const cancelVoiceInput = () => {
  const recorder = mediaRecorder.value
  if (recorder) {
    recorder.onstop = null
    try {
      if (recorder.state !== 'inactive') {
        recorder.stop()
      }
    } catch (err) {
      console.warn('[virtualHuman] cancel voice input failed', err)
    }
  }
  voiceChunks = []
  state.voiceProcessing = false
  resetVoiceInput()
}

const startVoiceInput = async () => {
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
    state.voiceError = '当前浏览器不支持语音输入'
    return
  }
  if (typeof MediaRecorder === 'undefined') {
    state.voiceError = '当前浏览器不支持录音'
    return
  }

  let stream = null
  try {
    state.questionInputVisible = true
    state.voiceError = ''
    voiceChunks = []
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = getRecordingMime()
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
    mediaRecorder.value = recorder
    recorder.ondataavailable = (event) => {
      if (event.data?.size > 0) {
        voiceChunks.push(event.data)
      }
    }
    recorder.onstop = () => {
      void processVoiceInput()
    }
    recorder.start(250)
    state.listening = true
    startVoiceActivityMonitor(stream)
    voiceRecordingTimer = setTimeout(() => {
      stopVoiceInput()
    }, 60000)
  } catch (err) {
    stream?.getTracks?.().forEach((track) => track.stop())
    resetVoiceInput()
    state.voiceError = err.message || '无法访问麦克风'
    console.warn('[virtualHuman] start voice input failed', err)
  }
}

const toggleVoiceInput = () => {
  if (state.voiceProcessing) return
  if (state.listening) {
    stopVoiceInput()
    return
  }
  void startVoiceInput()
}

const switchAvatar = async (avatarId) => {
  const targetId = String(avatarId)
  if (targetId === state.currentAvatarId || state.loading || state.sdkHidden) return

  state.currentAvatarId = targetId
  startResourceLoading()
  if (!platform.value) {
    void init().catch(() => undefined)
    return
  }

  try {
    state.loading = true
    await destroyPlatform()
    await startPlatform()
  } catch (err) {
    if (isConfigError(err)) {
      handleConfigError(err)
    } else {
      handleSdkError(err)
    }
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', handleWindowResize)
  }
  ensurePanelPosition()
  void init().catch(() => undefined)
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleWindowResize)
  }
  stopDrag()
  cancelVoiceInput()
  stopResourceLoading()
  releaseManualStop()
  void destroyPlatform()
})

defineExpose({
  init,
  playText,
  stopPlay,
  show: showPanel,
  hide: hidePanel,
})
</script>

<style lang="less" scoped>
.virtual-human-panel {
  position: fixed;
  width: 320px;
  max-width: calc(100vw - 16px);
  height: min(720px, calc(100vh - 96px));
  min-height: 0;
  max-height: calc(100vh - 16px);
  border: 1px solid var(--main-light-3);
  border-radius: 10px;
  background: var(--bg-sider);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.16);
  z-index: 1200;
  transition: width 0.18s ease, height 0.18s ease, box-shadow 0.18s ease;
}

.virtual-human-panel.is-collapsed {
  width: 128px;
  height: 278px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  overflow: visible;
  padding: 0;
}

.vh-mini {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.vh-mini-avatar {
  width: 92px;
  padding: 0;
  border: 0;
  background: transparent;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
}

.vh-mini-avatar__figure {
  width: 70px;
  height: 70px;
  border: 3px solid rgba(24, 144, 255, 0.22);
  border-radius: 50%;
  background: linear-gradient(180deg, #e8f3ff 0%, #ffffff 100%);
  color: var(--main-500);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 26px rgba(24, 144, 255, 0.22);
}

.vh-mini-avatar__figure :deep(.anticon) {
  font-size: 28px;
}

.vh-mini-avatar__label {
  max-width: 92px;
  min-height: 24px;
  margin-top: -12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #3aa6ff;
  color: #fff;
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-shadow: 0 6px 14px rgba(24, 144, 255, 0.24);
}

.vh-mini-card {
  width: 78px;
  min-height: 174px;
  padding: 16px 8px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.96);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 13px;
  box-shadow: 0 16px 42px rgba(15, 23, 42, 0.12);
}

.vh-mini-action,
.vh-mini-close {
  border: 0;
  background: transparent;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.vh-mini-action {
  width: 100%;
  min-height: 62px;
  flex-direction: column;
  gap: 6px;
  color: #111827;
}

.vh-mini-action :deep(.anticon) {
  font-size: 24px;
}

.vh-mini-action span {
  font-size: 14px;
  line-height: 1.25;
  text-align: center;
}

.vh-mini-action:hover {
  color: var(--main-500);
}

.vh-mini-close {
  width: 30px;
  height: 30px;
  margin-top: auto;
  border-radius: 50%;
  color: var(--gray-500);
}

.vh-mini-close:hover {
  background: var(--main-light-3);
  color: var(--gray-900);
}

.vh-header {
  height: var(--header-height);
  flex: 0 0 var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 12px;
  border-bottom: 1px solid var(--main-light-3);
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.virtual-human-panel.is-dragging,
.virtual-human-panel.is-dragging .vh-header,
.virtual-human-panel.is-dragging .vh-mini {
  cursor: grabbing;
  transition: none;
}

.is-collapsed .vh-header {
  height: 100%;
  flex: 1 1 auto;
  flex-direction: column;
  justify-content: flex-start;
  padding: 0 8px;
}

.vh-brand {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.vh-brand__icon {
  flex: 0 0 auto;
  color: var(--main-500);
  font-size: 18px;
}

.vh-brand__text {
  min-width: 0;
  line-height: 1.2;
}

.vh-brand__title {
  color: var(--gray-1000);
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

.vh-brand__status {
  max-width: 130px;
  color: var(--gray-500);
  font-size: 12px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.vh-toolbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 4px;
}

.is-collapsed .vh-toolbar {
  flex-direction: column;
}

.vh-icon-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--gray-700);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.vh-icon-btn:hover {
  background: var(--main-light-3);
  color: var(--gray-1000);
}

.vh-body {
  min-height: 0;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  overflow-y: auto;
}

.vh-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 9 / 16;
  min-height: 320px;
  border: 1px solid var(--main-light-3);
  border-radius: 8px;
  background: #f8fafc;
  overflow: hidden;
}

.vh-stage__mount {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.vh-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--gray-500);
  font-size: 13px;
  text-align: center;
  padding: 16px;
  pointer-events: none;
}

.vh-placeholder :deep(.anticon) {
  font-size: 22px;
  color: var(--main-500);
}

.vh-conversation {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 16px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 8px;
}

.vh-round-btn,
.vh-send-btn {
  border: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.16s ease, background 0.16s ease, transform 0.16s ease;
}

.vh-round-btn {
  position: relative;
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  color: var(--gray-700);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
}

.vh-round-btn:hover:not(:disabled),
.vh-round-btn.active {
  color: var(--main-500);
  background: #fff;
  transform: translateY(-1px);
}

.vh-round-btn.active::before,
.vh-round-btn.active::after {
  content: '';
  position: absolute;
  inset: -5px;
  border-radius: 50%;
  border: 1px solid rgba(24, 144, 255, 0.36);
  pointer-events: none;
  animation: vh-listening-pulse 1.6s ease-out infinite;
}

.vh-round-btn.active::after {
  inset: -10px;
  animation-delay: 0.45s;
}

.vh-round-btn.active :deep(.anticon) {
  animation: vh-mic-bounce 0.9s ease-in-out infinite;
}

.vh-round-btn:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.vh-question-box {
  min-width: 0;
  height: 42px;
  flex: 1 1 auto;
  padding: 0 6px 0 14px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
}

.vh-question-box.is-listening {
  color: var(--gray-700);
}

.vh-question-input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--gray-900);
  font-size: 14px;
}

.vh-question-input::placeholder {
  color: var(--gray-400);
}

.vh-voice-text {
  min-width: 0;
  flex: 1 1 auto;
  color: var(--gray-700);
  font-size: 14px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.vh-send-btn {
  flex: 0 0 30px;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: #fff;
  background: var(--main-500);
}

.vh-send-btn:hover:not(:disabled) {
  background: var(--main-600, var(--main-500));
  transform: translateY(-1px);
}

.vh-send-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.vh-voice-error {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 62px;
  z-index: 4;
  padding: 6px 8px;
  border-radius: 8px;
  color: #b42318;
  background: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  text-align: center;
  overflow-wrap: anywhere;
}

.vh-meta {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vh-meta__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.vh-meta__label {
  color: var(--gray-500);
}

.vh-meta__value {
  min-width: 0;
  color: var(--gray-1000);
  font-weight: 600;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.vh-avatar-list {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.vh-avatar-chip {
  flex: 0 0 auto;
  max-width: 160px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--main-light-3);
  border-radius: 6px;
  background: #fff;
  color: var(--gray-700);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.vh-avatar-chip span {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.vh-avatar-chip:hover:not(:disabled) {
  border-color: var(--main-500);
  color: var(--main-500);
}

.vh-avatar-chip.active,
.vh-avatar-chip:disabled {
  border-color: var(--main-500);
  color: var(--main-500);
  background: var(--main-light-3);
  cursor: default;
}

@keyframes vh-listening-pulse {
  0% {
    opacity: 0.72;
    transform: scale(0.84);
  }
  70% {
    opacity: 0;
    transform: scale(1.18);
  }
  100% {
    opacity: 0;
    transform: scale(1.18);
  }
}

@keyframes vh-mic-bounce {
  0%,
  100% {
    transform: translateY(0) scale(1);
  }
  50% {
    transform: translateY(-2px) scale(1.08);
  }
}

@media (max-width: 1200px) {
  .virtual-human-panel {
    width: 300px;
    height: min(660px, calc(100vh - 72px));
  }

  .virtual-human-panel.is-collapsed {
    width: 128px;
    height: 278px;
  }

  .vh-stage {
    min-height: 280px;
  }
}
</style>
