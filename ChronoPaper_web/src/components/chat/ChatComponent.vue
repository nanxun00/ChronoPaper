<template>
  <div class="chat" ref="chatRoot">
    <div class="header">
      <div class="header__left">
        <div v-if="!state.isSidebarOpen" class="close nav-btn" @click="state.isSidebarOpen = true">
          <MenuOutlined />
        </div>
        <a-tooltip :title="configStore.config?.model_name" placement="rightTop">
          <div class="newchat nav-btn" @click="$emit('newconv')">
            <PlusCircleOutlined /> <span class="text">新对话</span>
          </div>
        </a-tooltip>
      </div>
      <div class="header__right">
        <div class="nav-btn text metas" v-if="meta.use_graph && meta.enable_retrieval">
          <GoldOutlined /> 图数据库
        </div>
        <a-dropdown v-if="meta.enable_retrieval">
          <a class="ant-dropdown-link nav-btn" @click.prevent>
            <BookOutlined />
            <span class="text">{{ kbDisplayName }}</span>
          </a>
          <template #overlay>
            <a-menu>
              <a-menu-item v-for="(db, index) in opts.databases" :key="index" @click="useDatabase(index)">
                <a href="javascript:;">{{ db.name }}</a>
              </a-menu-item>
              <a-menu-item @click="useDatabase(null)">
                <a href="javascript:;">不使用</a>
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
        <div class="nav-btn text" @click="opts.showPanel = !opts.showPanel">
          <component :is="opts.showPanel ? FolderOpenOutlined : FolderOutlined" /> <span class="text">选项</span>
        </div>
        <div v-if="opts.showPanel" class="my-panal r0 top100 swing-in-top-fwd" ref="panel">
          <div class="flex-center">
            流式输出 <div @click.stop><a-switch v-model:checked="meta.stream" /></div>
          </div>
          <div class="flex-center" @click="meta.summary_title = !meta.summary_title">
            总结对话标题 <div @click.stop><a-switch v-model:checked="meta.summary_title" /></div>
          </div>
          <div class="flex-center" @click="meta.enable_retrieval = !meta.enable_retrieval">
            启用检索 <div @click.stop><a-switch v-model:checked="meta.enable_retrieval" /></div>
          </div>
          <div class="flex-center">
            最大历史轮数 <a-input-number id="inputNumber" v-model:value="meta.history_round" :min="1" :max="50" />
          </div>
          <a-divider v-if="meta.enable_retrieval"></a-divider>
          <div class="flex-center" v-if="configStore.config.enable_knowledge_base && meta.enable_retrieval">
            知识库
            <div @click.stop>
              <a-dropdown>
                <a class="ant-dropdown-link " @click.prevent>
                  <BookOutlined />&nbsp;
                  <span class="text">{{ kbDisplayName }}</span>
                </a>
                <template #overlay>
                  <a-menu>
                    <a-menu-item v-for="(db, index) in opts.databases" :key="index" @click="useDatabase(index)">
                      <a href="javascript:;">{{ db.name }}</a>
                    </a-menu-item>
                    <a-menu-item @click="useDatabase(null)">
                      <a href="javascript:;">不使用</a>
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </div>
          <div class="flex-center" @click="meta.use_graph = !meta.use_graph"
            v-if="configStore.config.enable_knowledge_base && meta.enable_retrieval">
            图数据库 <div @click.stop><a-switch v-model:checked="meta.use_graph" /></div>
          </div>
          <div class="flex-center" @click="meta.use_web = !meta.use_web"
            v-if="configStore.config.enable_search_engine && meta.enable_retrieval">
            搜索引擎（Bing） <div @click.stop><a-switch v-model:checked="meta.use_web" /></div>
          </div>
          <div class="flex-center" v-if="configStore.config.enable_knowledge_base && meta.enable_retrieval">
            重写查询 <a-segmented v-model:value="meta.rewriteQuery" :options="['off', 'on', 'hyde']" />
          </div>
        </div>
      </div>
    </div>
    <div class="chat-scroll" ref="chatContainer" @scroll="handleChatScroll">
    <div v-if="conv.messages.length == 0" class="chat-examples">
      <h1>你好，我是 ChronoPaper，你的论文智能助手</h1>
      <div class="opts">
        <div class="opt__button" v-for="(exp, key) in examples" :key="key" @click="conv.inputText = exp">
          {{ exp }}
        </div>
      </div>
    </div>
    <div class="chat-box">
      <div v-for="message in conv.messages" :key="message.id" class="message-box" :class="message.role">
        <!-- 思考过程 -->
        <div v-if="message.role == 'received' && message.ponder" class="ponder" v-html="ponderrenderMarkdown(message)">
        </div>
        <div v-if="message.images && message.images.length > 0" class="message-images">
          <img v-for="(imageUrl, index) in message.images" :key="index" :src="imageUrl" alt="Uploaded Image"
            class="message-image" />
        </div>
        <div v-if="message.citations && message.citations.length" class="message-citations">
          <span v-for="cite in message.citations" :key="cite.arxiv_id" class="cite-tag">
            <FileTextOutlined /> {{ cite.title }}
          </span>
        </div>
        <p v-if="message.role == 'sent'" style="white-space: pre-line" class="message-text">{{ message.text }}</p>
        <div v-else-if="message.text.length == 0 && message.status == 'init'" class="loading-dots">
          <div></div>
          <div></div>
          <div></div>
        </div>
        <div v-else-if="message.status == 'searching' && isStreaming" class="searching-msg"><i>正在检索……</i></div>
        <div v-else-if="message.status == 'error' || (message.status != 'finished' && !isStreaming)" class="err-msg"
          @click="retryMessage(message.id)">
          请求错误，请重试
        </div>
        <div v-else v-html="renderMarkdown(message)" class="message-md" @click="consoleMsg(message)"></div>
        <RefsComponent
          v-if="message.role == 'received' && message.status == 'finished'"
          :message="message"
          :disabled="isStreaming"
          @delete-turn="deleteMessageTurn"
        />
      </div>
    </div>
    </div>
    <Transition name="scroll-btn-fade">
      <button
        v-if="showScrollToBottom"
        type="button"
        class="scroll-to-bottom-btn"
        aria-label="回到底部"
        @click="scrollToBottom()"
      >
        <DownOutlined />
      </button>
    </Transition>
    <div class="bottom">
      <div class="input-box">
        <!-- 上传的图片显示位置 -->
        <div class="box-top">
          <div v-for="(file, index) in fileList" :key="index">
            <img :src="file.url" alt="Uploaded Image" class="uploaded-image">
            <span class="remove-icon" @click="handleRemove(file)" v-if="fileList.length > 0">×</span>
          </div>
        </div>
        <!-- 已引用文献 -->
        <div v-if="citedLiterature.length" class="box-citations">
          <a-tag
            v-for="cite in citedLiterature"
            :key="cite.arxiv_id"
            closable
            class="cite-chip"
            @close.prevent="removeCitation(cite.arxiv_id)"
          >
            <FileTextOutlined /> {{ truncateTitle(cite.title) }}
          </a-tag>
        </div>
        <div class="box-bottom">
          <a-textarea class="user-input" v-model:value="conv.inputText" @keydown="handleKeyDown" placeholder="输入问题……"
            :auto-size="{ minRows: 1, maxRows: 10 }" />
          <div class="icons">
            <!-- 添加图片 -->
            <el-tooltip class="box-item" effect="dark" content="添加图片" placement="top">
              <el-upload class="upload-demo" action="/api/image/upload_image" :on-preview="handlePreview" :headers="uploadHeaders"
                list-type="text" :on-success="handleSuccess" :on-error="handleerror" :show-file-list="false"
                name="file">
                <img class="icon" src="@/assets/image/ability/upload.png" alt="">
              </el-upload>
            </el-tooltip>
            <!-- 语音输入 -->
            <el-tooltip class="box-item" effect="dark" content="停止语音输入" placement="top" v-if="isRecording">
              <img class="icon" src="@/assets/image/ability/zantingluyin.png" alt="" @click="stopRecording">
            </el-tooltip>
            <el-tooltip class="box-item" effect="dark" content="语音输入" placement="top" v-else>
              <img class="icon" src="@/assets/image/ability/maikefeng.png" alt="" @click="toggleRecording">
            </el-tooltip>
          </div>

          <a-button size="large" @click="sendMessage" :disabled="(!canSend && !isStreaming)" type="link">
            <template #icon>
              <SendOutlined v-if="!isStreaming" />
              <LoadingOutlined v-else />
            </template>
          </a-button>
        </div>
        <div class="input-toolbar">
          <LiteratureCitePicker v-model="citedLiterature">
            <button type="button" class="tool-chip" :class="{ 'tool-chip--active': citedLiterature.length }">
              <FileTextOutlined />
              <span>文献</span>
              <span v-if="citedLiterature.length" class="tool-chip__count">{{ citedLiterature.length }}</span>
            </button>
          </LiteratureCitePicker>
          <SkillPicker
            :skill-mode="meta.skill_mode"
            :skill-id="meta.skill_id"
            @update:skill-mode="(v) => (meta.skill_mode = v)"
            @update:skill-id="(v) => (meta.skill_id = v)"
          />
        </div>

      </div>
      <p class="note">请注意辨别内容的可靠性 模型供应商：{{ configStore.config?.model_provider }}: {{ configStore.config?.model_name }}
      </p>
    </div>

  </div>
  <!-- <login v-if="openLoginModal" @close-login="handleCloseLogin"/> -->
</template>

<script setup>
import { reactive, ref, onMounted, toRefs, nextTick, computed, watch, toRaw } from 'vue'
import {
  SendOutlined,
  MenuOutlined,
  FormOutlined,
  LoadingOutlined,
  BookOutlined,
  BookFilled,
  CompassFilled,
  GoldenFilled,
  GoldOutlined,
  SettingOutlined,
  SettingFilled,
  PlusCircleOutlined,
  FolderOutlined,
  FolderOpenOutlined,
  GlobalOutlined,
  FileTextOutlined,
  RobotOutlined,
  DownOutlined,
} from '@ant-design/icons-vue'
import { onClickOutside } from '@vueuse/core'
import { parseChatMarkdown } from '@/utils/markdownSkillFold'
import { useConfigStore, useUserStore } from '@/stores'
import { message } from 'ant-design-vue'
import RefsComponent from '@/components/chat/RefsComponent.vue'
import LiteratureCitePicker from '@/components/chat/LiteratureCitePicker.vue'
import SkillPicker from '@/components/chat/SkillPicker.vue'
import { audioBlobToWav16k } from '@/utils/audioPcm'
import { postChat, fetchChatRefs, callChat, deleteMessageTurn as deleteMessageTurnApi } from '@/api/chat'
import hljs from 'highlight.js';
import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import 'highlight.js/styles/github.css';
// import login from '@/components/login.vue'


const token = sessionStorage.getItem('token')
const userStore = useUserStore();
// const openLoginModal = ref(false);
const props = defineProps({
  conv: Object,
  state: Object
})

const emit = defineEmits(['rename-title', 'newconv', 'conv-created']);
const configStore = useConfigStore()

const { conv, state } = toRefs(props)
const chatRoot = ref(null)
const chatContainer = ref(null)
const isStreaming = ref(false)
const showScrollToBottom = ref(false)
const autoScrollEnabled = ref(true)
const SCROLL_BOTTOM_THRESHOLD = 80

const isNearBottom = () => {
  const el = chatContainer.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_BOTTOM_THRESHOLD
}

const handleChatScroll = () => {
  const near = isNearBottom()
  autoScrollEnabled.value = near
  showScrollToBottom.value = !near && conv.value.messages.length > 0
}

const scrollToBottom = (force = true) => {
  nextTick(() => {
    requestAnimationFrame(() => {
      const el = chatContainer.value
      if (!el) return
      el.scrollTop = el.scrollHeight - el.clientHeight
      if (force) {
        autoScrollEnabled.value = true
        showScrollToBottom.value = false
      }
    })
  })
}

const scrollToBottomIfNeeded = () => {
  if (autoScrollEnabled.value) {
    scrollToBottom(false)
  } else {
    showScrollToBottom.value = true
  }
}
const citedLiterature = ref([])
const canSend = computed(() => {
  return Boolean(conv.value.inputText?.trim()) || citedLiterature.value.length > 0
})

const truncateTitle = (title, max = 36) => {
  if (!title || title.length <= max) return title
  return `${title.slice(0, max)}…`
}

const removeCitation = (arxivId) => {
  citedLiterature.value = citedLiterature.value.filter((p) => p.arxiv_id !== arxivId)
}
const panel = ref(null)
const modelCard = ref(null)
const examples = ref([
  '帮我总结一篇 Transformer 论文的核心贡献与创新点',
  '对比 RAG 与微调两种方案在文献问答中的优劣',
  '检索近一年关于大语言模型推理增强的代表性工作',
  '这篇论文的实验设计有哪些局限？请结合摘要分析',
  '根据引用的文献，写一段 Related Work 初稿',
])

const opts = reactive({
  showPanel: false,
  showModelCard: false,
  openDetail: false,
  databases: [],
})

const metaStorageKey = computed(() => `chat-meta:${userStore.username || 'guest'}`)

const DEFAULT_CHAT_META = {
  enable_retrieval: false,
  use_graph: false,
  use_web: false,
  graph_name: 'neo4j',
  rewriteQuery: 'off',
  selectedKB: null,
  kbOptOut: false,
  stream: true,
  summary_title: true,
  history_round: 10,
  skill_mode: 'auto',
  skill_id: null,
}

const meta = reactive({
  ...DEFAULT_CHAT_META,
  ...JSON.parse(localStorage.getItem(metaStorageKey.value) || '{}'),
})

const _storedMeta = JSON.parse(localStorage.getItem(metaStorageKey.value) || '{}')
if (_storedMeta.kbOptOut === undefined && Object.prototype.hasOwnProperty.call(_storedMeta, 'selectedKB') && _storedMeta.selectedKB === null) {
  meta.kbOptOut = true
}

const kbDisplayName = computed(() => {
  if (meta.kbOptOut || meta.selectedKB === null || meta.selectedKB < 0) {
    return '不使用'
  }
  return opts.databases[meta.selectedKB]?.name || '不使用'
})

const marked = new Marked(
  {
    gfm: true,
    breaks: true,
    tables: true,
  },
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code) {
      return hljs.highlightAuto(code).value;
    }
  })
);

const consoleMsg = (message) => console.log(message)
onClickOutside(panel, () => setTimeout(() => opts.showPanel = false, 30))
onClickOutside(modelCard, () => setTimeout(() => opts.showModelCard = false, 30))

const renderMarkdown = (message) => {
  const text = message.status === 'loading' ? message.text + '🟢' : message.text
  return parseChatMarkdown(text, message)
}
const ponderrenderMarkdown = (message) => {
  if (message.status === 'loading') {
    return marked.parse(message.ponder)
  } else {
    return marked.parse(message.ponder)
  }
}

const useDatabase = (index) => {
  if (index == null) {
    meta.selectedKB = null
    meta.kbOptOut = true
    meta.db_name = null
    return
  }
  const selected = opts.databases[index]
  if (configStore.config.embed_model != selected.embed_model) {
    message.error(`所选知识库的向量模型（${selected.embed_model}）与当前向量模型（${configStore.config.embed_model}) 不匹配，请重新选择`)
    return
  }
  meta.selectedKB = index
  meta.kbOptOut = false
  meta.db_name = selected?.metaname || null
}

const handleKeyDown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  } else if (e.key === 'Enter' && e.shiftKey) {
    // Insert a newline character at the current cursor position
    const textarea = e.target;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    conv.value.inputText.value = "0"
    conv.value.inputText.value.substring(0, start) +
      '\n' +
      conv.value.inputText.value.substring(end);
    nextTick(() => {
      textarea.setSelectionRange(start + 1, start + 1);
    });
  }
}

const renameTitle = () => {
  if (meta.summary_title) {
    const prompt = '请用一个很短的句子关于下面的对话内容的主题起一个名字，不要带标点符号：'
    const firstUserMessage = conv.value.messages[0].text
    const firstAiMessage = conv.value.messages[1].text
    const context = `${prompt}\n\n问题: ${firstUserMessage}\n\n回复: ${firstAiMessage}，主题是（一句话）：`
    simpleCall(context).then((data) => {
      const response = data.response.split("：")[0].replace(/^["'"']/g, '').replace(/["'"']$/g, '')
      emit('rename-title', response)
    })
  } else {
    emit('rename-title', conv.value.messages[0].text)
  }
}

const generateRandomHash = (length) => {
  let chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let hash = '';
  for (let i = 0; i < length; i++) {
    hash += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return hash;
}

const appendUserMessage = (message, images = [], citations = []) => {
  conv.value.messages.push({
    id: generateRandomHash(16),
    role: 'sent',
    text: message,
    images: images,
    citations,
    status: 'finished'
  })
  scrollToBottom()
}

const appendAiMessage = (message, refs = null) => {
  conv.value.messages.push({
    id: generateRandomHash(16),
    role: 'received',
    text: message,
    refs,
    status: "init",
    meta: {},
    skill_active: meta.skill_mode !== 'off',
  })
  scrollToBottom()
}

const updateMessage = (info) => {
  const message = conv.value.messages.find((message) => message.id === info.id);
  if (message) {
    // 只有在 text 不为空时更新
    // if (info.text !== null && info.text !== undefined && info.text !== '') {
    //   message.text = info.text;
    // }
    // 只有在 ponder 不为空时更新
    if (info.ponder !== undefined) {
      message.ponder = info.ponder;
      // 等待 ponder 内容渲染完成后更新回答
      setTimeout(() => {
        if (info.text !== undefined) {
          message.text = info.text;
        }
      }, 500); // 延迟 500 毫秒更新回答
    } else if (info.text !== undefined) {
      message.text = info.text;
    }
    // 只有在 refs 不为空时更新
    if (info.refs !== null && info.refs !== undefined) {
      message.refs = info.refs;
    }

    if (info.model_name !== null && info.model_name !== undefined && info.model_name !== '') {
      message.model_name = info.model_name;
    }

    // 只有在 status 不为空时更新
    if (info.status !== null && info.status !== undefined && info.status !== '') {
      message.status = info.status;
    }

    if (info.meta !== null && info.meta !== undefined) {
      message.meta = info.meta;
    }

    if (info.groupedResults !== null && info.groupedResults !== undefined) {
      message.groupedResults = info.groupedResults;
    }
  } else {
    console.error('Message not found');
  }

  scrollToBottomIfNeeded();
};


const resolveDbName = () => {
  if (!meta.enable_retrieval || !opts.databases?.length) return null
  if (meta.kbOptOut) return null

  let index = meta.selectedKB
  if (index == null) {
    index = opts.databases.findIndex((d) => d.is_system)
    if (index < 0) index = 0
    meta.selectedKB = index
    meta.kbOptOut = false
  } else if (index < 0 || !opts.databases[index]) {
    index = opts.databases.findIndex((d) => d.is_system)
    if (index < 0) index = 0
    meta.selectedKB = index
  }
  return opts.databases[index]?.metaname || null
}

const groupRefs = (id) => {
  const message = conv.value.messages.find((m) => m.id === id)
  if (!message) {
    scrollToBottom()
    return
  }

  const grouped = {}
  const kbResults = message?.refs?.knowledge_base?.results || []
  for (const result of kbResults) {
    const filename = result.file?.filename || result.entity?.paper_id
    if (!filename) continue
    if (!result.file) {
      result.file = { filename, type: 'pdf', created_at: Date.now() / 1000 }
    }
    if (!grouped[filename]) grouped[filename] = []
    grouped[filename].push(result)
  }

  const msgIndex = conv.value.messages.findIndex((m) => m.id === id)
  const userMsg = msgIndex > 0 ? conv.value.messages[msgIndex - 1] : null
  const citations = userMsg?.citations || message?.meta?.cited_literature || []
  for (const cite of citations) {
    const title = (cite.title || cite.arxiv_id || '').trim()
    if (!title || grouped[title]) continue
    grouped[title] = [{
      id: cite.arxiv_id || title,
      file: { filename: title, type: 'pdf', created_at: Date.now() / 1000 },
      entity: {
        text: cite.abstract || cite.full_text || '（本轮对话引用的文献）',
        paper_id: cite.arxiv_id,
      },
      distance: 1,
    }]
  }

  message.groupedResults = grouped
  updateMessage({ id, groupedResults: grouped })
  scrollToBottom()
}

const applyRefsToMessage = (cur_res_id, refs) => {
  if (!refs) return
  updateMessage({ id: cur_res_id, refs })
  groupRefs(cur_res_id)
}

const simpleCall = (messageText) => callChat(messageText)

const loadDatabases = () => {
  fetch('/api/data/', {
    method: "GET",
  })
    .then(response => response.json())
    .then(data => {
      opts.databases = data.databases || []
      if (meta.enable_retrieval && !meta.kbOptOut && meta.selectedKB == null) {
        const systemIdx = opts.databases.findIndex((d) => d.is_system)
        if (systemIdx >= 0) meta.selectedKB = systemIdx
      }
    })
}

const buildRequestMeta = (citedLiteraturePayload = []) => ({
  ...structuredClone(toRaw(meta)),
  stream: meta.stream !== false,
  db_name: resolveDbName() || meta.db_name || null,
  mode: 'search',
  maxQueryCount: 20,
  topK: 5,
  distanceThreshold: 0,
  use_llm_filter: false,
  cited_literature: citedLiteraturePayload,
})

const parseResponseContent = (responsePayload) => {
  const raw = responsePayload?.content ?? responsePayload ?? ''
  const text = typeof raw === 'string' ? raw : String(raw?.content ?? '')
  const thinkStartRegex = /<think>/
  const thinkEndRegex = /<\/think>/

  let isInThinkTag = false
  let textContent = ''
  let ponderContent = ''

  for (const line of text.split('\n')) {
    if (thinkStartRegex.test(line)) {
      isInThinkTag = true
      continue
    }
    if (thinkEndRegex.test(line)) {
      isInThinkTag = false
      continue
    }
    if (isInThinkTag) {
      ponderContent += `${line}\n`
    } else {
      textContent += `${line}\n`
    }
  }

  const reasoning = responsePayload?.reasoning_content
  if (reasoning && !ponderContent.trim()) {
    ponderContent = String(reasoning)
  }

  return {
    textContent: textContent.trim(),
    ponderContent: ponderContent.trim(),
  }
}

const applyChatPayload = (data, cur_res_id) => {
  const { textContent, ponderContent } = parseResponseContent(data.response)

  updateMessage({
    id: cur_res_id,
    ponder: ponderContent,
    model_name: data.model_name,
    status: data.status,
    meta: data.meta,
  })

  nextTick(() => {
    updateMessage({
      id: cur_res_id,
      text: textContent,
      model_name: data.model_name,
      status: data.status,
      meta: data.meta,
    })
  })

  if (data.history) {
    conv.value.history = data.history
  }
  if (data.conv_id && !conv.value.conv_id) {
    conv.value.conv_id = data.conv_id
    emit('conv-created', data.conv_id)
  }
  if (data.refs) {
    applyRefsToMessage(cur_res_id, data.refs)
  }
}

const finishChatResponse = (cur_res_id) => {
  const message = conv.value.messages.find((item) => item.id === cur_res_id)
  const useRetrieval = meta.enable_retrieval || message?.meta?.enable_retrieval
  const hasGrouped = message?.groupedResults && Object.keys(message.groupedResults).length > 0

  const finalize = () => {
    if (message && message.status !== 'finished') {
      updateMessage({ id: cur_res_id, status: 'finished' })
    }
    isStreaming.value = false
    if (conv.value.messages.length === 2) {
      renameTitle()
    }
  }

  if (!hasGrouped) {
    if (message?.refs) {
      groupRefs(cur_res_id)
    } else if (useRetrieval) {
      fetchRefs(cur_res_id)
        .then((refs) => applyRefsToMessage(cur_res_id, refs))
        .catch((err) => console.warn('fetchRefs failed', err))
        .finally(finalize)
      return
    } else {
      groupRefs(cur_res_id)
    }
  }

  finalize()
}

const fetchChatResponse = (user_input, user_msg_id, cur_res_id, citedLiteraturePayload = []) => {
  const requestMeta = buildRequestMeta(citedLiteraturePayload)
  const useStream = requestMeta.stream !== false

  postChat({
    query: user_input,
    history: conv.value.history,
    meta: requestMeta,
    cur_res_id: cur_res_id,
    conv_id: conv.value.conv_id,
    user_msg_id: user_msg_id,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`请求失败 (${response.status})`)
      }

      if (!useStream) {
        const data = await response.json()
        applyChatPayload(data, cur_res_id)
        finishChatResponse(cur_res_id)
        return
      }

      if (!response.body) throw new Error('ReadableStream not supported.')
      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      const readChunk = () => {
        return reader.read().then(({ done, value }) => {
          if (done) {
            finishChatResponse(cur_res_id)
            return
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')

          for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i].trim()
            if (!line) continue
            try {
              const data = JSON.parse(line)
              applyChatPayload(data, cur_res_id)
            } catch (e) {
              console.error('JSON 解析错误:', e, line)
            }
          }

          buffer = lines[lines.length - 1]
          return readChunk()
        })
      }
      return readChunk()
    })
    .catch((error) => {
      console.error(error);
      updateMessage({
        id: cur_res_id,
        status: "error",
      });
      isStreaming.value = false;
    });
};

const deleteMessageTurn = async (assistantMsgId) => {
  if (!conv.value.conv_id || isStreaming.value) return
  const assistantIdx = conv.value.messages.findIndex((m) => m.id === assistantMsgId)
  if (assistantIdx < 0) return

  try {
    const data = await deleteMessageTurnApi(conv.value.conv_id, assistantMsgId)
    conv.value.messages = data.messages || []
    conv.value.history = data.history || []
    message.success('已删除该轮对话')
  } catch (err) {
    message.error(err.message || '删除失败')
  }
}

const fetchRefs = (cur_res_id) => {
  return fetchChatRefs(cur_res_id).then((data) => data.refs)
}

// 更新后的 sendMessage 函数
const sendMessage = () => {
  const user_input = conv.value.inputText.trim();
  const dbName = resolveDbName();
  const images = fileList.value.map(file => file.url);
  const citations = citedLiterature.value.map((p) => ({ ...p }));
  const finalInput = ocrText.value ? `${user_input} ${ocrText.value}` : user_input;

  if (user_input || citations.length) {
    isStreaming.value = true;
    const user_msg_id = generateRandomHash(16);
    conv.value.messages.push({
      id: user_msg_id,
      role: 'sent',
      text: user_input || '请结合引用的文献回答',
      images: images,
      citations,
      status: 'finished'
    });
    scrollToBottom();
    appendAiMessage("", null);
    const cur_res_id = conv.value.messages[conv.value.messages.length - 1].id;
    conv.value.inputText = '';
    fileList.value = [];
    meta.db_name = dbName;

    fetchChatResponse(
      finalInput || '请结合引用的文献进行总结或回答',
      user_msg_id,
      cur_res_id,
      citations,
    );
    citedLiterature.value = [];
  } else {
    console.log('请输入消息');
  }
}

const retryMessage = (id) => {
  // 找到 id 对应的 message，然后删除包含 message 在内以及后面所有的 message
  const index = conv.value.messages.findIndex(message => message.id === id);
  const pastMessage = conv.value.messages[index - 1]
  console.log("retryMessage", id, pastMessage)
  conv.value.inputText = pastMessage.text
  if (index !== -1) {
    conv.value.messages = conv.value.messages.slice(0, index - 1);
  }
  console.log(conv.value.messages)
  sendMessage();
}

const autoSend = (message) => {
  conv.value.inputText = message
  sendMessage()
}

// 图片上传
let fileList = ref([]);
// 关键字的字段
let ocrText = ref("");
const handleRemove = (uploadFile, uploadFiles) => {
  console.log(uploadFile, uploadFiles);
  // 可选：从 fileList 中移除对应的文件
  fileList.value = fileList.value.filter(file => file.url !== uploadFile.url);
};

const handlePreview = (file) => {
  console.log(file)
}
const uploadHeaders = computed(() => {
  return {
    Authorization: `Bearer ${sessionStorage.getItem('token')}` 
  };
});
const handleSuccess = (response, file, localFileList) => {
  console.log(response)
  if (!response) {
    // 如果响应为null，显示错误消息并通知管理员
    message.error('图片上传失败，请重试或联系管理员');
    return;
  }
  const imageUrl = response.image_path;
  console.log(imageUrl);
  if (response.ocr_text) {
    ocrText.value = response.ocr_text; 
  }

  if (Array.isArray(fileList.value)) {
    fileList.value.push({ url: imageUrl });
  } else {
    console.error('fileList is not an array.');
  }
  scrollToBottom(); 
};
const handleerror = () => {
  console.log('error')
}

// 语音识别功能
const RECORDING_MIME = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
  ? 'audio/webm;codecs=opus'
  : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/wav')
// 是否处于正在录音的状态
let isRecording = ref(false);
// 用于录音
let mediaRecorder = ref(null);
// 用于存储录音中产生的音频数据块
let audioChunks = ref([]);
// 设置录音时长上限的定时器
let recordingTimeout = ref(null);
// 点击录音按钮
async function toggleRecording() {
  if (isRecording.value) {
    stopRecording(); // 如果正在录音，调用 stopRecording 停止录音
  } else {
    try {
      // 请求麦克风权限并获取音频流
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.value = new MediaRecorder(stream, { mimeType: RECORDING_MIME });
      audioChunks.value = [];
      mediaRecorder.value.start(250);
      isRecording.value = true; // 更新录音状态为 true

      // 添加“开始录音”消息到对话框
      appendUserMessage("开始录音...", []); // 添加消息到对话框

      mediaRecorder.value.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.value.push(event.data); // 收集音频数据块
        }
      };

      mediaRecorder.value.onstop = () => {
        processRecording(); // 处理音频数据
      };

      recordingTimeout.value = setTimeout(() => {
        stopRecording();
      }, 60000); // 限制录音时长为 60 秒
    } catch (e) {
      alert("无法访问麦克风设备，请检查设备连接");
      console.error("Error accessing microphone:", e);
    }
  }
}
// 点击暂停录音
function stopRecording() {
  if (isRecording.value) {
    if (mediaRecorder.value) {
      if (typeof mediaRecorder.value.requestData === 'function') {
        mediaRecorder.value.requestData();
      }
      mediaRecorder.value.stop();
      const stream = mediaRecorder.value.stream;
      if (stream) {
        stream.getTracks().forEach(track => track.stop()); // 停止音频流
      }
      mediaRecorder.value = null; // 清理 MediaRecorder 实例
    }
    isRecording.value = false; // 更新录音状态为 false
    clearTimeout(recordingTimeout.value); // 清除定时器

    // 将“开始录音...”更新为“音频处理中...”
    const messages = conv.value.messages;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.text === "开始录音...") {
      lastMessage.text = "音频处理中..."; // 更新最后一条消息
    }
  }
}
/**
 * 录音结束后处理数据的方法
 */
async function processRecording() {
  if (audioChunks.value.length === 0) {
    return;
  }

  try {
    const recordedBlob = new Blob(audioChunks.value, { type: RECORDING_MIME });
    const wavBlob = await audioBlobToWav16k(recordedBlob);
    const file = new File([wavBlob], 'recording.wav', { type: 'audio/wav' });
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/audio/upload', {
      method: 'POST',
      headers: uploadHeaders.value,
      body: formData,
    });
    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}))
      const detail = typeof errBody === 'string' ? errBody : (errBody?.detail || '')
      throw new Error(detail || `HTTP error! status: ${response.status}`)
    }
    const data = await response.json()
    const text = typeof data === 'string' ? data : (data?.text || data?.detail || '')

    const messages = conv.value.messages;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.text === '音频处理中...') {
      messages.pop();
    }

    if (!text) {
      message.warning('未识别到语音内容，请靠近麦克风并说话至少 1 秒');
      return
    }

    conv.value.inputText += text
  } catch (error) {
    console.error('Upload failed:', error.message);
    message.error(error.message || '语音识别失败');

    // 如果音频处理失败，更新对话框中的消息为“音频处理失败”
    const messages = conv.value.messages;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.text === "音频处理中...") {
      lastMessage.text = "音频处理失败"; // 更新最后一条消息
    }
  } finally {
    audioChunks.value = []; // 重置音频数据
  }
}
watch(
  () => conv.value?.conv_id,
  () => {
    autoScrollEnabled.value = true
    showScrollToBottom.value = false
    scrollToBottom()
  },
)

watch(
  () => conv.value?.messages?.length,
  (newLen, oldLen) => {
    if (newLen > 0 && (oldLen === 0 || oldLen === undefined)) {
      autoScrollEnabled.value = true
      scrollToBottom()
    }
  },
)

// 从本地存储加载数据
onMounted(() => {
  scrollToBottom()
  nextTick(() => handleChatScroll())
  loadDatabases()
  if (meta.stream === undefined || meta.stream === null) {
    meta.stream = true
  }
  if (!meta.skill_mode) {
    meta.skill_mode = 'auto'
  }
})

// 监听 meta 对象的变化，并保存到本地存储（不持久化临时引用）
watch(
  () => meta,
  (newMeta) => {
    const { cited_literature, ...persistMeta } = structuredClone(toRaw(newMeta))
    localStorage.setItem(metaStorageKey.value, JSON.stringify(persistMeta))
  },
  { deep: true }
)
</script>

<style lang="less" scoped>
.chat {
  position: relative;
  width: 100%;
  height: 100%;
  max-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: white;
  box-sizing: border-box;
  flex: 5 5 200px;

  .header {
    user-select: none;
    flex-shrink: 0;
    z-index: 10;
    background-color: white;
    height: var(--header-height);
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;

    .header__left,
    .header__right {
      display: flex;
      align-items: center;
    }
  }

  .nav-btn {
    height: 2.5rem;
    display: flex;
    justify-content: center;
    align-items: center;
    border-radius: 8px;
    color: var(--gray-900);
    cursor: pointer;
    font-size: 1rem;
    width: auto;
    padding: 0.5rem 1rem;

    .text {
      margin-left: 10px;
    }

    &:hover {
      background-color: var(--main-light-3);
    }
  }

}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.metas {
  display: flex;
  gap: 8px;
}

.my-panal {
  position: absolute;
  margin-top: 5px;
  background-color: white;
  border: 1px solid #ccc;
  box-shadow: 0px 0px 10px 1px rgba(0, 0, 0, 0.05);
  border-radius: 12px;
  padding: 12px;
  z-index: 11;
  width: 280px;

  .flex-center {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.3s;

    &:hover {
      background-color: var(--main-light-3);
    }
  }
}

.my-panal.r0.top100 {
  top: 100%;
  right: 0;
}

.my-panal.l0.top100 {
  top: 100%;
  left: 0;
}

.chat-examples {
  padding: 0 50px;
  text-align: center;
  position: absolute;
  top: 20%;
  width: 100%;
  z-index: 9;
  animation: slideInUp 0.5s ease-out;

  h1 {
    margin-bottom: 12px;
    font-size: 24px;
    color: #333;
  }

  &__hint {
    margin: 0 0 20px;
    font-size: 14px;
    color: var(--gray-600, #666);
  }

  .opts {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;

    .opt__button {
      background-color: var(--gray-200);
      color: #333;
      padding: .5rem 1.5rem;
      border-radius: 2rem;
      cursor: pointer;
      // border: 2px solid var(--main-light-4);
      transition: background-color 0.3s;
      // box-shadow: 0px 0px 10px 2px var(--main-light-4);


      &:hover {
        background-color: #f0f1f1;
        // box-shadow: 0px 0px 10px 1px rgba(0, 0, 0, 0.1);
      }
    }
  }

}

.chat-box {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  flex-grow: 1;
  padding: 1rem 2rem;
  display: flex;
  flex-direction: column;

  .message-box {
    display: inline-block;
    border-radius: 1.5rem;
    margin: 0.8rem 0;
    padding: 0.625rem 1.25rem;
    user-select: text;
    word-break: break-word;
    font-size: 16px;
    font-variation-settings: 'wght' 400, 'opsz' 10.5;
    font-weight: 400;
    box-sizing: border-box;
    color: black;
    /* box-shadow: 0px 0.3px 0.9px rgba(0, 0, 0, 0.12), 0px 1.6px 3.6px rgba(0, 0, 0, 0.16); */
    /* animation: slideInUp 0.1s ease-in; */

    .err-msg {
      color: #FF6B6B;
      border: 1px solid #FF6B6B;
      padding: 0.2rem 1rem;
      border-radius: 8px;
      text-align: center;
      background: #FFF0F0;
      margin-bottom: 10px;
      cursor: pointer;
    }

    .searching-msg {
      color: var(--gray-500);
    }
  }

  .message-box.sent {
    line-height: 24px;
    max-width: 95%;
    background: var(--main-light-4);
    align-self: flex-end;
  }

  .message-box.received {
    color: initial;
    width: fit-content;
    text-align: left;
    word-wrap: break-word;
    margin: 0;
    padding-bottom: 0;
    padding-top: 16px;
    padding-left: 0;
    padding-right: 0;
    text-align: justify;
  }

  p.message-text {
    max-width: 100%;
    word-wrap: break-word;
    margin-bottom: 0;
  }

  p.message-md {
    word-wrap: break-word;
    margin-bottom: 0;
  }
}

.scroll-to-bottom-btn {
  position: absolute;
  bottom: 168px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--gray-300, #e5e5e5);
  background: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gray-800, #333);
  font-size: 14px;
  transition: background 0.2s, box-shadow 0.2s;

  &:hover {
    background: var(--gray-100, #f5f5f5);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  }
}

.scroll-btn-fade-enter-active,
.scroll-btn-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.scroll-btn-fade-enter-from,
.scroll-btn-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

.bottom {
  position: relative;
  flex-shrink: 0;
  bottom: auto;
  width: 100%;
  margin: 0 auto;
  padding: 4px 2rem 0 2rem;
  background: white;

  .input-box {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: auto;
    max-width: 900px;
    margin: 0 auto;
    align-items: flex-end;
    padding: 0.25rem 0.5rem;
    // box-shadow: rgba(42, 60, 79, 0.1) 0px 6px 10px 0px;
    border: 2px solid #E5E5E5;
    border-radius: 1rem;
    background: #fcfdfd;
    transition: background 0.3s, box-shadow 0.3s;

    &:focus-within {
      border: 2px solid var(--main-500);
      background: white;
      // box-shadow: rgb(42 60 79 / 5%) 0px 4px 10px 0px;
    }

    textarea.user-input {
      flex: 1;
      height: 40px;
      padding: 0.5rem 0.5rem;
      background-color: transparent;
      border: none;
      font-size: 16px;
      margin: 0 0.6rem;
      color: #111111;
      font-variation-settings: 'wght' 400, 'opsz' 10.5;
      outline: none;
      resize: none;

      &:focus {
        outline: none;
        box-shadow: none;
      }

      &:active {
        outline: none;
      }
    }

    .box-citations {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      width: 100%;
      padding: 4px 10px 0;
    }

    .cite-chip {
      max-width: 100%;
      margin: 0;
      border-radius: 6px;
      font-size: 12px;
    }

    .input-toolbar {
      display: flex;
      align-items: center;
      gap: 6px;
      width: 100%;
      padding: 4px 8px 6px;
      border-top: 1px solid #f0f0f0;
      margin-top: 2px;
    }

    .tool-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      border: none;
      border-radius: 999px;
      background: transparent;
      color: #555;
      font-size: 13px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;

      &:hover {
        background: #f3f5f7;
        color: #222;
      }

      &--active {
        background: #eef5ff;
        color: var(--main-700, #1677ff);
      }

      &__count {
        min-width: 16px;
        height: 16px;
        padding: 0 4px;
        border-radius: 8px;
        background: var(--main-600, #1677ff);
        color: #fff;
        font-size: 11px;
        line-height: 16px;
        text-align: center;
      }
    }
  }

  button.ant-btn-icon-only {
    font-size: 1.25rem;
    cursor: pointer;
    background-color: transparent;
    border: none;
    transition: color 0.3s;
    box-shadow: none;
    color: var(--main-700);
    ;
    padding: 0;

    &:hover {
      color: var(--gray-1000);
    }

    &:disabled {
      color: #ccc;
      cursor: not-allowed;
    }
  }

  .note {
    width: 100%;
    font-size: small;
    text-align: center;
    padding: 0rem;
    color: #ccc;
    margin: 4px 0;
    user-select: none;
  }
}



.ant-dropdown-link {
  color: var(--gray-900);
  cursor: pointer;
}



.chat-scroll::-webkit-scrollbar {
  position: absolute;
  width: 4px;
}

.chat-scroll::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 4px;
}

.chat-scroll::-webkit-scrollbar-thumb {
  background: var(--gray-400);
  border-radius: 4px;
}

.chat-scroll::-webkit-scrollbar-thumb:hover {
  background: rgb(100, 100, 100);
  border-radius: 4px;
}

.chat-scroll::-webkit-scrollbar-thumb:active {
  background: rgb(68, 68, 68);
  border-radius: 4px;
}

.loading-dots {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.loading-dots div {
  width: 8px;
  height: 8px;
  margin: 0 4px;
  background-color: #666;
  border-radius: 50%;
  opacity: 0.3;
  animation: pulse 1.4s infinite ease-in-out both;
}

.loading-dots div:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots div:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes pulse {

  0%,
  80%,
  100% {
    transform: scale(0.8);
    opacity: 0.3;
  }

  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes loading {

  0%,
  80%,
  100% {
    transform: scale(0.5);
  }

  40% {
    transform: scale(1);
  }
}

.slide-out-left {
  -webkit-animation: slide-out-left .2s cubic-bezier(.55, .085, .68, .53) both;
  animation: slide-out-left .5s cubic-bezier(.55, .085, .68, .53) both
}

.swing-in-top-fwd {
  -webkit-animation: swing-in-top-fwd .2s ease-out both;
  animation: swing-in-top-fwd .2s ease-out both
}

@-webkit-keyframes swing-in-top-fwd {
  0% {
    -webkit-transform: rotateX(-100deg);
    transform: rotateX(-100deg);
    -webkit-transform-origin: top;
    transform-origin: top;
    opacity: 0
  }

  100% {
    -webkit-transform: rotateX(0deg);
    transform: rotateX(0deg);
    -webkit-transform-origin: top;
    transform-origin: top;
    opacity: 1
  }
}

@keyframes swing-in-top-fwd {
  0% {
    -webkit-transform: rotateX(-100deg);
    transform: rotateX(-100deg);
    -webkit-transform-origin: top;
    transform-origin: top;
    opacity: 0
  }

  100% {
    -webkit-transform: rotateX(0deg);
    transform: rotateX(0deg);
    -webkit-transform-origin: top;
    transform-origin: top;
    opacity: 1
  }
}

@-webkit-keyframes slide-out-left {
  0% {
    -webkit-transform: translateX(0);
    transform: translateX(0);
    opacity: 1
  }

  100% {
    -webkit-transform: translateX(-1000px);
    transform: translateX(-1000px);
    opacity: 0
  }
}

@keyframes slide-out-left {
  0% {
    -webkit-transform: translateX(0);
    transform: translateX(0);
    opacity: 1
  }

  100% {
    -webkit-transform: translateX(-1000px);
    transform: translateX(-1000px);
    opacity: 0
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes slideInUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }

  to {
    transform: translateY(0);
    opacity: 1;
  }
}

@media (max-width: 520px) {
  .chat {
    height: calc(100vh - 60px);
  }

  .chat-container .chat .header {
    background: var(--main-light-4);

    .header__left,
    .header__right {
      gap: 20px;
    }

    .nav-btn {
      font-size: 1.5rem;
      padding: 0;

      &:hover {
        background-color: transparent;
        color: black;
      }

      .text {
        display: none;
      }
    }
  }

  .bottom {
    padding: 0.5rem 0.5rem;

    .input-box {
      border-radius: 8px;
      padding: 0.5rem;

      textarea.user-input {
        padding: 0.5rem 0;
      }
    }

    .note {
      display: none;
    }
  }
}

.ponder {
  color: #b7b7b7 !important;
  /* 使用 !important 确保样式生效 */
  border-left: solid 4px #dcdada;
  padding-left: 10px;
  word-wrap: break-word;
}

.icons {
  display: flex;
  // background-color: red;
  margin-bottom: -5px;
}

.icon {
  width: 22px;
  height: 22px;
  margin-right: 9px;
  cursor: pointer;
}

.box-bottom {
  display: flex;
  width: 100%;
  align-items: center
}

.box-top {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
}

.uploaded-image {
  max-width: 80px;
  height: auto;
  margin-bottom: 10px;
  border-radius: 8px;
  margin-left: 15px;
}

.remove-icon {
  position: absolute;
  top: 0px;
  right: 0px;
  cursor: pointer;
  font-size: 16px;
  background-color: rgba(0, 0, 0, 0.5);
  color: white;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.message-image {
  max-width: 150px;
  height: auto;
  border-radius: 4px;
  margin: 5px;
}

.message-citations {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
}

.cite-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 6px;
  background: #eef5ff;
  color: #3366aa;
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<style lang="less">
.message-box pre {
  border-radius: 8px;
  font-size: 14px;
  border: 1px solid var(--main-light-3);
  padding: 1rem;

  &:has(code.hljs) {
    padding: 0;
  }
}

.message-md {

  h1,
  h2,
  h3,
  h4,
  h5,
  h6 {
    font-size: 1rem;
  }

  .skill-code-fold {
    margin: 10px 0;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    background: #f9fafb;
    overflow: hidden;
  }

  .skill-code-fold__summary {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    cursor: pointer;
    user-select: none;
    font-size: 13px;
    color: #666;
    list-style: none;

    &::-webkit-details-marker {
      display: none;
    }

    &::before {
      content: '▶';
      font-size: 10px;
      color: #999;
      transition: transform 0.15s ease;
      flex-shrink: 0;
    }
  }

  .skill-code-fold[open] > .skill-code-fold__summary::before {
    transform: rotate(90deg);
  }

  .skill-code-fold__body pre {
    margin: 0;
    border: none;
    border-radius: 0;
    border-top: 1px solid #e8e8e8;
    max-height: 480px;
    overflow: auto;
  }

  li,
  ol,
  ul {
    &>p {
      margin: 0.25rem 0;
    }
  }

  ol,
  ul {
    padding-left: 1rem;
  }
}
</style>
