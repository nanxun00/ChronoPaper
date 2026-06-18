<template>
  <div class="chat" ref="chatContainer">
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
        <a-dropdown v-if="meta.selectedKB !== null && meta.enable_retrieval">
          <a class="ant-dropdown-link nav-btn" @click.prevent>
            <!-- <component :is="meta.selectedKB === null ? BookOutlined : BookFilled" /> -->
            <BookOutlined />
            <span class="text">{{ meta.selectedKB === null ? '不使用' : opts.databases[meta.selectedKB]?.name }}</span>
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
          <div class="flex-center" @click="meta.stream = !meta.stream">
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
                  <!-- <component :is="meta.selectedKB === null ? BookOutlined : BookFilled" />&nbsp; -->
                  <BookOutlined />&nbsp;
                  <span class="text">{{ meta.selectedKB === null ? '不使用' : opts.databases[meta.selectedKB]?.name
                    }}</span>
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
        <RefsComponent v-if="message.role == 'received' && message.status == 'finished'" :message="message" />
      </div>
    </div>
    <div class="bottom">
      <div class="input-box">
        <!-- 上传的图片显示位置 -->
        <div class="box-top">
          <div v-for="(file, index) in fileList" :key="index">
            <img :src="file.url" alt="Uploaded Image" class="uploaded-image">
            <span class="remove-icon" @click="handleRemove(file)" v-if="fileList.length > 0">×</span>
          </div>
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

          <a-button size="large" @click="sendMessage" :disabled="(!conv.inputText && !isStreaming)" type="link">
            <template #icon>
              <SendOutlined v-if="!isStreaming" />
              <LoadingOutlined v-else />
            </template>
          </a-button>
        </div>

      </div>
      <p class="note">请注意辨别内容的可靠性 模型供应商：{{ configStore.config?.model_provider }}: {{ configStore.config?.model_name }}
      </p>
    </div>

  </div>
  <!-- <login v-if="openLoginModal" @close-login="handleCloseLogin"/> -->
</template>

<script setup>
import { reactive, ref, onMounted, toRefs, nextTick, computed, watch } from 'vue'
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
} from '@ant-design/icons-vue'
import { onClickOutside } from '@vueuse/core'
import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import { useConfigStore } from '@/stores'
import { message } from 'ant-design-vue'
import RefsComponent from '@/components/chat/RefsComponent.vue'
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';
// import login from '@/components/login.vue'
import { useUserStore } from '@/stores'


const token = sessionStorage.getItem('token')
const userStore = useUserStore();
// const openLoginModal = ref(false);
const props = defineProps({
  conv: Object,
  state: Object
})

const emit = defineEmits(['rename-title', 'newconv']);
const configStore = useConfigStore()

const { conv, state } = toRefs(props)
const chatContainer = ref(null)
const isStreaming = ref(false)
const panel = ref(null)
const modelCard = ref(null)
const examples = ref([
  '写一个冒泡排序',
  '肉碱的分子量是多少？直接回答',
  '总结大蒜的功效是什么？',
  '今天天气怎么样？',
  '吃饭吃出苍蝇可以索赔吗？',
  '帮我写一个请假条',
  '贾宝玉今年多少岁？',
])

const opts = reactive({
  showPanel: false,
  showModelCard: false,
  openDetail: false,
  databases: [],
})

const meta = reactive(JSON.parse(localStorage.getItem('meta')) || {
  enable_retrieval: false,
  use_graph: false,
  use_web: false,
  graph_name: "neo4j",
  rewriteQuery: "off",
  selectedKB: null,
  stream: true,
  summary_title: true,
  history_round: 5,
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
  if (message.status === 'loading') {
    return marked.parse(message.text + '🟢')
  } else {
    return marked.parse(message.text)
  }
}
const ponderrenderMarkdown = (message) => {
  if (message.status === 'loading') {
    return marked.parse(message.ponder)
  } else {
    return marked.parse(message.ponder)
  }
}

const useDatabase = (index) => {
  const selected = opts.databases[index]
  console.log(selected)
  if (index != null && configStore.config.embed_model != selected.embed_model) {
    console.log(selected.embed_model, configStore.config.embed_model)
    message.error(`所选知识库的向量模型（${selected.embed_model}）与当前向量模型（${configStore.config.embed_model}) 不匹配，请重新选择`)
  } else {
    meta.selectedKB = index
  }
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

const scrollToBottom = () => {
  setTimeout(() => {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight - chatContainer.value.clientHeight
  }, 10)
}

const generateRandomHash = (length) => {
  let chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let hash = '';
  for (let i = 0; i < length; i++) {
    hash += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return hash;
}

const appendUserMessage = (message, images = []) => {
  conv.value.messages.push({
    id: generateRandomHash(16),
    role: 'sent',
    text: message,
    images: images, // 添加图片 URL
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
  } else {
    console.error('Message not found');
  }

  scrollToBottom();
};


const groupRefs = (id) => {
  const message = conv.value.messages.find((message) => message.id === id)
  if (message.refs && message.refs.knowledge_base.results.length > 0) {
    message.groupedResults = message.refs.knowledge_base.results
      .filter(result => result.file && result.file.filename)
      .reduce((acc, result) => {
        const { filename } = result.file;
        if (!acc[filename]) {
          acc[filename] = []
        }
        acc[filename].push(result)
        return acc;
      }, {})
  }
  scrollToBottom()
}

const simpleCall = (message) => {
  return new Promise((resolve, reject) => {
    fetch('/api/chat/call', {
      method: 'POST',
      body: JSON.stringify({ query: message, }),
      headers: { 'Content-Type': 'application/json' }
    })
      .then((response) => response.json())
      .then((data) => resolve(data))
      .catch((error) => reject(error))
  })
}

const loadDatabases = () => {
  fetch('/api/data/', {
    method: "GET",
  })
    .then(response => response.json())
    .then(data => {
      console.log(data)
      opts.databases = data.databases
    })
}

// 新函数用于处理 fetch 请求
const fetchChatResponse = (user_input, cur_res_id) => {
  fetch('/api/chat/', {
    method: 'POST',
    body: JSON.stringify({
      query: user_input,
      history: conv.value.history,
      meta: meta,
      cur_res_id: cur_res_id,
    }),
    headers: {
      'Content-Type': 'application/json',
    }
  })
    .then((response) => {
      console.log(response);
      if (!response.body) throw new Error("ReadableStream not supported.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = '';

      const readChunk = () => {
        return reader.read().then(({ done, value }) => {
          if (done) {
            const message = conv.value.messages.find((message) => message.id === cur_res_id);
            console.log(message);
            if (message.meta.enable_retrieval) {
              console.log("fetching refs");
              fetchRefs(cur_res_id).then((data) => {
                console.log(data);
                updateMessage({
                  id: cur_res_id,
                  refs: data,
                  status: "finished",
                });
                groupRefs(cur_res_id);
              });
            } else {
              updateMessage({
                id: cur_res_id,
                status: "finished",
              });
            }
            isStreaming.value = false;
            if (conv.value.messages.length === 2) { renameTitle(); }
            return;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');

          // 处理除最后一行外的所有完整行
          for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i].trim();
            if (line) {
              try {
                const data = JSON.parse(line);

                // 定义正则表达式来检测和提取 <think> 标签的内容
                const thinkStartRegex = /<think>/;
                const thinkEndRegex = /<\/think>/;

                // 初始化状态变量
                let isInThinkTag = false;
                let textContent = ""; // 用于存储非 <think> 部分的内容
                let ponderContent = ""; // 用于存储 <think> 部分的内容

                // 按行解析 data.response.content
                const lines = data.response.content.split('\n');
                for (let i = 0; i < lines.length; i++) {
                  const line = lines[i];

                  if (thinkStartRegex.test(line)) {
                    // 遇到 <think> 标签，开始记录 ponderContent
                    isInThinkTag = true;
                    continue; // 跳过当前行
                  }

                  if (thinkEndRegex.test(line)) {
                    // 遇到 </think> 标签，停止记录 ponderContent
                    isInThinkTag = false;
                    continue; // 跳过当前行
                  }

                  if (isInThinkTag) {
                    // 当前处于 <think> 标签内，将内容添加到 ponderContent
                    ponderContent += line + '\n';
                  } else {
                    // 当前不在 <think> 标签内，将内容添加到 textContent
                    textContent += line + '\n';
                  }
                }

                // 去掉多余的换行符
                ponderContent = ponderContent.trim();
                textContent = textContent.trim();

                console.log("textContent:", textContent);
                console.log("ponderContent:", ponderContent);

                // 更新消息
                updateMessage({
                  id: cur_res_id,
                  ponder: ponderContent, // 先更新 ponder
                  model_name: data.model_name,
                  status: data.status,
                  meta: data.meta,
                });

                // 等待 DOM 更新完成
                nextTick(() => {
                  updateMessage({
                    id: cur_res_id,
                    text: textContent, // 再更新 text
                    model_name: data.model_name,
                    status: data.status,
                    meta: data.meta,
                  });
                });

                // 如果存在 history，更新 conv.value.history
                if (data.history) {
                  conv.value.history = data.history;
                }
              } catch (e) {
                console.error('JSON 解析错误:', e, line);
              }
            }
          }

          // 保留最后一个可能不完整的行
          buffer = lines[lines.length - 1];

          return readChunk(); // 继续读取
        });
      };
      readChunk();
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

const fetchRefs = (cur_res_id) => {
  return new Promise((resolve, reject) => {
    fetch(`/api/chat/refs?cur_res_id=${cur_res_id}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json"
      },
    }).then(response => response.json())
      .then(data => {
        resolve(data.refs)
      })
      .catch((error) => {
        reject(error)
      })
  })
}

// 更新后的 sendMessage 函数
const sendMessage = () => {
  // 文本内容
  const user_input = conv.value.inputText.trim();
  const dbName = opts.databases.length > 0 ? opts.databases[meta.selectedKB]?.metaname : null;

  // 获取图片列表
  const images = fileList.value.map(file => file.url);

  // 如果有 ocr_text，则将其添加到 user_input 中，但不显示在文本框中
  const finalInput = ocrText.value ? `${user_input} ${ocrText.value}` : user_input;

  if (user_input) {
    isStreaming.value = true;
    appendUserMessage(user_input, images);
    appendAiMessage("", null);
    const cur_res_id = conv.value.messages[conv.value.messages.length - 1].id;
    conv.value.inputText = '';
    fileList.value = []; // 清空图片列表，避免重复上传
    meta.db_name = dbName;

    fetchChatResponse(finalInput, cur_res_id)
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
      mediaRecorder.value = new MediaRecorder(stream);
      mediaRecorder.value.start(); // 开始录音
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
      mediaRecorder.value.stop(); // 停止录音
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

  // 合并音频数据块为一个完整的音频文件
  const audioBlob = new Blob(audioChunks.value, { type: "audio/wav" });
  const file = new File([audioBlob], "recording.wav", { type: "audio/wav" });
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/api/audio/upload", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json(); // 获取识别结果

    // 更新输入框内容
    conv.value.inputText += data;

    // 如果音频处理成功，删除对话框中的“音频处理中...”消息
    const messages = conv.value.messages;
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && lastMessage.text === "音频处理中...") {
      messages.pop(); // 删除最后一条消息
    }
  } catch (error) {
    console.error("Upload failed:", error.message);

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
// 从本地存储加载数据
onMounted(() => {
  scrollToBottom()
  loadDatabases()
  const storedMeta = localStorage.getItem('meta');
  if (storedMeta) {
    const parsedMeta = JSON.parse(storedMeta);
    Object.assign(meta, parsedMeta);
  }
});

// 监听 meta 对象的变化，并保存到本地存储
watch(
  () => meta,
  (newMeta) => {
    localStorage.setItem('meta', JSON.stringify(newMeta));
  },
  { deep: true }
);
</script>

<style lang="less" scoped>
.chat {
  position: relative;
  width: 100%;
  max-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  background: white;
  position: relative;
  box-sizing: border-box;
  flex: 5 5 200px;
  overflow-y: scroll;

  .header {
    user-select: none;
    position: sticky;
    top: 0;
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
    margin-bottom: 20px;
    font-size: 24px;
    color: #333;
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

.bottom {
  position: sticky;
  bottom: 0;
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
      font-size: 1.2rem;
      margin: 0 0.6rem;
      color: #111111;
      font-size: 16px;
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



.chat::-webkit-scrollbar {
  position: absolute;
  width: 4px;
}

.chat::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 4px;
}

.chat::-webkit-scrollbar-thumb {
  background: var(--gray-400);
  border-radius: 4px;
}

.chat::-webkit-scrollbar-thumb:hover {
  background: rgb(100, 100, 100);
  border-radius: 4px;
}

.chat::-webkit-scrollbar-thumb:active {
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
  /* 设置最大宽度为 50px */
  height: auto;
  /* 保持高度自适应 */
  border-radius: 4px;
  /* 可选：添加圆角效果 */
  margin: 5px;
  /* 可选：添加一些外边距 */
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
