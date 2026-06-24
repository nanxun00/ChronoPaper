<template>
  <div class="chat-container">
    <div class="conversations" :class="['conversations', { 'is-open': state.isSidebarOpen }]">
      <div class="actions">
        <span style="font-weight: bold; user-select: none;">对话历史</span>
        <div class="action close" @click="state.isSidebarOpen = false"><MenuOutlined /></div>
      </div>
      <div class="conversation-list">
        <div
          class="conversation"
          v-for="conv in convs"
          :key="conv.conv_id"
          :class="{ active: curConvId === conv.conv_id }"
          @click="goToConversation(conv.conv_id)"
        >
          <div class="conversation__title"><CommentOutlined /> &nbsp;{{ conv.title }}</div>
          <div class="conversation__delete" @click.stop="delConv(conv.conv_id)"><DeleteOutlined /></div>
        </div>
      </div>
    </div>
    <div class="chat-main-area">
      <ChatComponent
        v-if="activeConv"
        ref="chatComponentRef"
        :key="curConvId"
        :conv="activeConv"
        :state="state"
        :virtual-human-enabled="virtualHumanEnabled"
        :speaking-message-id="speakingMessageId"
        @rename-title="renameTitle"
        @newconv="addNewConv"
        @conv-created="onConvCreated"
        @load-older="loadOlderMessages"
        @toggle-virtual-human="setVirtualHumanEnabled"
        @speak-message="handleSpeakMessage"
        @assistant-finished="handleAssistantFinished"
      />
      <VirtualHumanPanel
        v-if="virtualHumanEnabled"
        ref="virtualHumanRef"
        :api-config="virtualHumanApiConfig"
        :avatar-options="virtualHumanAvatarOptions"
        :default-avatar-id="virtualHumanDefaults.defaultAvatarId"
        :default-vcn="virtualHumanDefaults.defaultVcn"
        @request-close="handleVirtualHumanClose"
        @speech-end="clearSpeakingMessage"
        @submit-question="handleVirtualHumanQuestion"
      />
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, nextTick, onMounted, onActivated, onUnmounted } from 'vue'
import { MenuOutlined, DeleteOutlined, CommentOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import ChatComponent from '@/components/chat/ChatComponent.vue'
import VirtualHumanPanel from '@/components/chat/VirtualHumanPanel.vue'
import {
  virtualHumanApiConfig,
  virtualHumanAvatarOptions,
  virtualHumanDefaults,
} from '@/config/virtualHuman'
import {
  listConversations,
  createConversation,
  getConversation,
  updateConversation,
  deleteConversation,
} from '@/api/chat'

const convs = reactive([])
const state = reactive({
  isSidebarOpen: true,
  loading: false,
})
const curConvId = ref(null)
const chatComponentRef = ref(null)
const virtualHumanRef = ref(null)
const speakingMessageId = ref(null)
const speechRequestId = ref(0)
const virtualHumanReplyAutoSpeak = ref(false)
const INITIAL_MESSAGE_LIMIT = 8
const VIRTUAL_HUMAN_ENABLED_KEY = 'chat-virtual-human-enabled'
const virtualHumanEnabled = ref(localStorage.getItem(VIRTUAL_HUMAN_ENABLED_KEY) === 'true')

const emptyConv = () => ({
  conv_id: null,
  title: '新对话',
  history: [],
  messages: [],
  inputText: '',
  detailLoaded: false,
  detailLoading: false,
  loadingOlder: false,
  messagesHasMore: false,
  oldestMsgId: null,
  messagesTotal: 0,
})

const activeConv = computed(() => convs.find((c) => c.conv_id === curConvId.value) || null)

const setVirtualHumanEnabled = (enabled) => {
  const nextEnabled = Boolean(enabled)
  virtualHumanEnabled.value = nextEnabled
  localStorage.setItem(VIRTUAL_HUMAN_ENABLED_KEY, nextEnabled ? 'true' : 'false')
}

const stopBrowserSpeech = () => {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
}

const speakWithBrowser = (text, { onEnd } = {}) => {
  if (
    typeof window === 'undefined' ||
    !window.speechSynthesis ||
    typeof window.SpeechSynthesisUtterance !== 'function'
  ) {
    message.warning('当前浏览器不支持语音播放')
    return false
  }

  stopBrowserSpeech()
  const utterance = new window.SpeechSynthesisUtterance(text)
  const voices = window.speechSynthesis.getVoices?.() || []
  const voice = voices.find((item) => /^zh/i.test(item.lang)) || voices[0]
  if (voice) {
    utterance.voice = voice
  }
  utterance.lang = voice?.lang || 'zh-CN'
  utterance.rate = 1
  utterance.pitch = 1
  utterance.volume = 1
  utterance.onerror = (event) => {
    console.warn('Browser speech playback failed:', event)
    onEnd?.()
  }
  utterance.onend = () => onEnd?.()
  window.speechSynthesis.speak(utterance)
  window.speechSynthesis.resume?.()
  return true
}

const clearSpeakingMessage = () => {
  speakingMessageId.value = null
}

const handleVirtualHumanClose = () => {
  clearSpeakingMessage()
  setVirtualHumanEnabled(false)
}

const handleVirtualHumanQuestion = async (payload) => {
  const text = String((typeof payload === 'string' ? payload : payload?.text) ?? '').trim()
  const done = typeof payload?.done === 'function' ? payload.done : null
  if (!text) {
    done?.(false)
    return
  }

  if (!activeConv.value) {
    await addNewConv()
    await nextTick()
  }

  const submitted = chatComponentRef.value?.submitExternalMessage?.(text) === true
  if (submitted) {
    virtualHumanReplyAutoSpeak.value = true
  }
  done?.(submitted)
}

const handleAssistantFinished = (assistantMessage) => {
  if (!virtualHumanReplyAutoSpeak.value) return
  virtualHumanReplyAutoSpeak.value = false
  if (!virtualHumanEnabled.value) return

  if (
    assistantMessage?.role === 'received' &&
    assistantMessage?.status === 'finished' &&
    String(assistantMessage?.text || '').trim()
  ) {
    void handleSpeakMessage(assistantMessage)
  }
}

const stopCurrentSpeech = async () => {
  speechRequestId.value += 1
  speakingMessageId.value = null
  stopBrowserSpeech()

  const player = virtualHumanRef.value
  if (player?.stopPlay) {
    try {
      await player.stopPlay()
    } catch (err) {
      console.warn('Virtual human stopPlay failed:', err)
    }
  }
}

const getVirtualHumanPlayer = async () => {
  if (!virtualHumanEnabled.value) {
    setVirtualHumanEnabled(true)
    await nextTick()
  }
  if (!virtualHumanRef.value) {
    await nextTick()
  }
  return virtualHumanRef.value
}

const handleSpeakMessage = async (speakerMessage) => {
  const text = String(speakerMessage?.text ?? '')
  if (!text.trim()) return
  const nextMessageId = speakerMessage?.id ?? null

  if (nextMessageId != null && String(speakingMessageId.value) === String(nextMessageId)) {
    await stopCurrentSpeech()
    return
  }

  speechRequestId.value += 1
  const requestId = speechRequestId.value
  speakingMessageId.value = nextMessageId
  stopBrowserSpeech()
  const player = await getVirtualHumanPlayer()

  if (requestId !== speechRequestId.value) return

  if (player?.playText) {
    try {
      const played = await player.playText(text, { forceUnmute: true })
      if (requestId !== speechRequestId.value) return
      if (played) return
      console.warn('Virtual human playText returned false, fallback to browser speech')
    } catch (err) {
      if (requestId !== speechRequestId.value) return
      console.warn('Virtual human playText failed:', err)
    }
  }

  if (requestId !== speechRequestId.value) return
  const spoken = speakWithBrowser(text, {
    onEnd: () => {
      if (requestId === speechRequestId.value) {
        clearSpeakingMessage()
      }
    },
  })
  if (!spoken) {
    clearSpeakingMessage()
  }
}

const mapConvSummary = (row) => ({
  conv_id: row.conv_id,
  title: row.title || '新对话',
  history: [],
  messages: [],
  inputText: '',
  detailLoaded: false,
  detailLoading: false,
  loadingOlder: false,
  messagesHasMore: false,
  oldestMsgId: null,
  messagesTotal: 0,
})

const normalizeMessages = (rows) => {
  if (!Array.isArray(rows)) return []
  return rows.map((item) => ({
    id: item.id || item.msg_id || `msg-${Math.random().toString(36).slice(2)}`,
    role: item.role === 'user' ? 'sent' : item.role === 'assistant' ? 'received' : (item.role || 'received'),
    text: item.text ?? item.content ?? '',
    images: item.images || [],
    citations: item.citations || [],
    ponder: item.ponder || item.reasoning_content || '',
    refs: item.refs ?? null,
    model_name: item.model_name,
    status: item.status || 'finished',
    meta: item.meta || {},
    skill_active: Boolean(item.skill_active || item.meta?.skill_id || item.refs?.skill?.skill_id),
  }))
}

const applyConversationDetail = (target, detail, { prepend = false } = {}) => {
  target.title = detail.title || target.title
  target.history = Array.isArray(detail.history) ? detail.history : []
  const normalized = normalizeMessages(detail.messages)
  target.messages = prepend ? [...normalized, ...target.messages] : normalized
  target.messagesHasMore = Boolean(detail.messages_has_more)
  target.oldestMsgId = detail.oldest_msg_id || (target.messages[0]?.id ?? null)
  target.messagesTotal = detail.messages_total ?? target.messages.length
}

const loadConversationDetail = async (convId, { force = false, beforeMsgId = null } = {}) => {
  const target = convs.find((c) => c.conv_id === convId)
  if (!target) return
  if (!beforeMsgId && target.detailLoaded && !force) return

  if (beforeMsgId) {
    if (target.loadingOlder || !target.messagesHasMore) return
    target.loadingOlder = true
  } else {
    target.detailLoading = true
  }

  try {
    const detail = await getConversation(convId, {
      message_limit: INITIAL_MESSAGE_LIMIT,
      before_msg_id: beforeMsgId || undefined,
    })
    const refreshed = convs.find((c) => c.conv_id === convId)
    if (!refreshed) return

    applyConversationDetail(refreshed, detail, { prepend: Boolean(beforeMsgId) })
    if (!beforeMsgId) {
      refreshed.detailLoaded = true
    }
  } catch (err) {
    if (!beforeMsgId) {
      message.error(err.message || '加载对话详情失败')
    }
    throw err
  } finally {
    const refreshed = convs.find((c) => c.conv_id === convId)
    if (refreshed) {
      refreshed.detailLoading = false
      refreshed.loadingOlder = false
    }
  }
}

const loadOlderMessages = async ({ onLoaded, onError } = {}) => {
  if (!curConvId.value) return
  const conv = convs.find((c) => c.conv_id === curConvId.value)
  if (!conv?.oldestMsgId || !conv.messagesHasMore || conv.loadingOlder) return
  try {
    await loadConversationDetail(curConvId.value, { beforeMsgId: conv.oldestMsgId })
    onLoaded?.()
  } catch (err) {
    message.error(err.message || '加载更早消息失败')
    onError?.()
  }
}

const ensureActiveConversationLoaded = async ({ force = false } = {}) => {
  if (!curConvId.value) return
  try {
    await loadConversationDetail(curConvId.value, { force })
  } catch (err) {
    message.error(err.message || '加载对话详情失败')
  }
}

const loadConversations = async () => {
  state.loading = true
  try {
    const data = await listConversations()
    const rows = data.conversations || []
    convs.splice(0, convs.length, ...rows.map(mapConvSummary))
    if (convs.length === 0) {
      await addNewConv()
    } else {
      curConvId.value = convs[0].conv_id
      try {
        await loadConversationDetail(curConvId.value)
      } catch (err) {
        message.error(err.message || '加载对话详情失败')
      }
    }
  } catch (err) {
    message.error(err.message || '加载对话失败')
    convs.splice(0, convs.length, emptyConv())
    curConvId.value = null
  } finally {
    state.loading = false
  }
}

const renameTitle = async (newTitle) => {
  const conv = activeConv.value
  if (!conv?.conv_id || !newTitle) return
  conv.title = newTitle
  try {
    await updateConversation(conv.conv_id, { title: newTitle })
  } catch (err) {
    console.error(err)
  }
}

const goToConversation = async (convId) => {
  curConvId.value = convId
  const conv = convs.find((c) => c.conv_id === convId)
  if (!conv) return
  if (conv.detailLoaded) return
  conv.detailLoading = true
  await ensureActiveConversationLoaded()
}

const addNewConv = async () => {
  if (convs.length > 0 && convs[0].messages.length === 0) {
    curConvId.value = convs[0].conv_id
    return
  }
  try {
    const row = await createConversation({ title: '新对话' })
    const conv = mapConvSummary(row)
    convs.unshift(conv)
    curConvId.value = conv.conv_id
  } catch (err) {
    message.error(err.message || '创建对话失败')
  }
}

const onConvCreated = (convId) => {
  const conv = activeConv.value
  if (conv && !conv.conv_id) {
    conv.conv_id = convId
  }
  if (!convs.find((c) => c.conv_id === convId) && conv) {
    conv.conv_id = convId
    convs.unshift(conv)
  }
  curConvId.value = convId
}

const delConv = async (convId) => {
  const index = convs.findIndex((c) => c.conv_id === convId)
  if (index === -1) return
  try {
    if (convId) {
      await deleteConversation(convId)
    }
    convs.splice(index, 1)
    if (curConvId.value === convId) {
      curConvId.value = convs[0]?.conv_id || null
      if (curConvId.value) {
        await loadConversationDetail(curConvId.value)
      }
    }
    if (convs.length === 0) {
      await addNewConv()
    }
  } catch (err) {
    message.error(err.message || '删除对话失败')
  }
}

onMounted(() => {
  loadConversations()
})

onActivated(() => {
  if (convs.length === 0) {
    loadConversations()
    return
  }
  const conv = activeConv.value
  if (conv && !conv.detailLoaded) {
    ensureActiveConversationLoaded()
  }
})

onUnmounted(() => {
  stopBrowserSpeech()
})
</script>

<style lang="less" scoped>
@import '@/assets/main.css';

.chat-container {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  position: relative;
}

.chat-main-area {
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.chat-main-area :deep(.chat) {
  flex: 1 1 auto;
  min-width: 0;
}

.chat-container .conversations:not(.is-open) {
  width: 0;
  opacity: 0;
  flex: 0 0 0;
}

.chat-container .conversations.is-open {
  overflow: hidden;
  white-space: nowrap;
  flex: 1 1 auto;
}
.conversations {
  width: 230px;
  max-width: 230px;
  border-right: 1px solid var(--main-light-3);
  overflow: hidden;
  max-height: 100%;
  background-color: var(--bg-sider);

  & .actions {
    height: var(--header-height);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    z-index: 9;
    border-bottom: 1px solid var(--main-light-3);

    .action {
      font-size: 1.2rem;
      width: 2.5rem;
      height: 2.5rem;
      display: flex;
      justify-content: center;
      align-items: center;
      border-radius: 8px;
      color: var(--gray-800);
      cursor: pointer;

      &:hover {
        background-color: var(--main-light-3);
      }
    }
  }

  .conversation-list {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    max-height: 100%;
  }

  .conversation-list .conversation {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    cursor: pointer;
    width: 100%;
    user-select: none;
    transition: background-color 0.2s ease-in-out;

    &__title {
      color: var(--gray-700);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    &__delete {
      display: none;
      color: var(--gray-500);
      transition: all 0.2s ease-in-out;

      &:hover {
        color: #F93A37;
        background-color: #EEE;
      }
    }

    &.active {
      border-right: 3px solid var(--main-500);
      padding-right: 13px;
      background-color: var(--gray-200);

      & .conversation__title {
        color: var(--gray-1000);
      }
    }

    &:not(.active):hover {
      background-color: var(--main-light-3);

      & .conversation__delete {
        display: block;
      }
    }

  }
}

.conversation-list::-webkit-scrollbar {
  position: absolute;
  width: 4px;
}

.conversation-list::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 4px;
}

.conversation-list::-webkit-scrollbar-thumb {
  background: var(--gray-400);
  border-radius: 4px;
}

.conversation-list::-webkit-scrollbar-thumb:hover {
  background: rgb(100, 100, 100);
  border-radius: 4px;
}

.conversation-list::-webkit-scrollbar-thumb:active {
  background: rgb(68, 68, 68);
  border-radius: 4px;
}

@media (max-width: 520px) {
  .conversation {
    position: absolute;
    z-index: 101;
    width: 300px;
    border-radius: 0 16px 16px 0;
    box-shadow: 0 0 10px 1px rgba(0, 0, 0, 0.05);
  }
}
</style>
