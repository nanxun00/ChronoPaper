<template>
  <button
    type="button"
    class="tool-chip"
    :class="{ 'tool-chip--active': open }"
    @click="open = true"
  >
    <ExperimentOutlined />
    <span>提示增强</span>
  </button>

  <a-drawer
    v-model:open="open"
    title="Prompt 提示实验室"
    placement="right"
    width="600"
    class="prompt-enhancer-drawer"
  >
    <div class="enhancer">
      <div v-if="contextItems.length" class="context-card">
        <div class="context-card__title">当前上下文</div>
        <ul class="context-card__list">
          <li v-for="item in contextItems" :key="item">{{ item }}</li>
        </ul>
      </div>

      <a-tabs v-model:activeKey="activeCategory" size="small" class="enhancer__tabs">
        <a-tab-pane
          v-for="category in categories"
          :key="category"
          :tab="category"
        />
      </a-tabs>

      <div class="template-list">
        <button
          v-for="template in visibleTemplates"
          :key="template.id"
          type="button"
          class="template-option"
          :class="{ 'template-option--active': template.id === selectedTemplateId }"
          @click="selectedTemplateId = template.id"
        >
          <span class="template-option__title">{{ template.name }}</span>
          <span class="template-option__desc">{{ template.description }}</span>
        </button>
      </div>

      <div class="style-panel">
        <div class="field-block__label">增强风格</div>
        <div class="style-list">
          <button
            v-for="style in promptStyles"
            :key="style.id"
            type="button"
            class="style-option"
            :class="{ 'style-option--active': style.id === selectedStyleId }"
            @click="selectedStyleId = style.id"
          >
            <span class="style-option__title">{{ style.name }}</span>
            <span class="style-option__desc">{{ style.description }}</span>
          </button>
        </div>
      </div>

      <div class="field-block">
        <label class="field-block__label">原始提示词</label>
        <a-textarea
          v-model:value="sourcePrompt"
          :rows="5"
          placeholder="输入需要增强的原始需求"
          allow-clear
        />
      </div>

      <div class="enhancer__main-action">
        <a-button type="primary" @click="generatePrompt">
          <template #icon><ThunderboltOutlined /></template>
          增强
        </a-button>
        <a-button @click="generateVariants">
          <template #icon><ExperimentOutlined /></template>
          生成三套方案
        </a-button>
        <a-button :disabled="isStreaming" @click="generateAndSend">
          <template #icon><SendOutlined /></template>
          增强并发送
        </a-button>
      </div>

      <div class="field-block field-block--result">
        <label class="field-block__label">增强结果</label>
        <a-textarea
          v-model:value="enhancedPrompt"
          :rows="14"
          placeholder="增强后的提示词会显示在这里"
        />
      </div>

      <div class="enhancer__actions">
        <a-button :disabled="!hasResult" @click="copyResult">
          <template #icon><CopyOutlined /></template>
          复制
        </a-button>
        <a-button :disabled="!hasResult" @click="openSaveModal">
          <template #icon><SaveOutlined /></template>
          保存到提示词库
        </a-button>
        <a-button :disabled="!hasResult" @click="applyResult('replace')">
          <template #icon><SwapOutlined /></template>
          替换输入
        </a-button>
        <a-button :disabled="!hasResult" @click="applyResult('insert')">
          <template #icon><EnterOutlined /></template>
          插入
        </a-button>
        <a-button :disabled="!sourcePrompt.trim()" @click="regeneratePrompt">
          <template #icon><ReloadOutlined /></template>
          重新生成
        </a-button>
      </div>
    </div>
  </a-drawer>

  <a-modal
    v-model:open="saveModalOpen"
    title="保存到提示词库"
    ok-text="保存"
    cancel-text="取消"
    :confirm-loading="savingPrompt"
    @ok="saveToPromptLibrary"
  >
    <div class="save-form">
      <label class="field-block__label">提示词标题</label>
      <a-input
        v-model:value="saveTitle"
        placeholder="例如：文献总结增强模板"
        @press-enter="saveToPromptLibrary"
      />
    </div>
  </a-modal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CopyOutlined,
  EnterOutlined,
  ExperimentOutlined,
  ReloadOutlined,
  SaveOutlined,
  SendOutlined,
  SwapOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { useConfigStore } from '@/stores'

const props = defineProps({
  currentInput: {
    type: String,
    default: '',
  },
  contextInfo: {
    type: Object,
    default: () => ({}),
  },
  isStreaming: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['apply'])
const configStore = useConfigStore()

const withContext = (input, contextBlock) => contextBlock
  ? `当前上下文：
${contextBlock}

用户原始需求：
${input}`
  : input

const taskIntentMap = {
  knowledge_summary: '结构化总结、关键知识提炼、可复用知识沉淀',
  knowledge_qa: '基于知识库或文献上下文进行可引用问答',
  memory_extract: '从内容中提取长期记忆、项目事实和用户偏好',
  memory_recall: '结合历史记忆与当前上下文生成连续回答',
}

const buildInputBlock = (input, contextBlock) => `输入内容：
${withContext(input, contextBlock)}`

const templates = [
  {
    id: 'knowledge_summary',
    name: '知识总结',
    category: '知识管理',
    description: '将普通总结请求增强为结构化知识整理提示词',
    build: ({ input, contextBlock }) => `角色：
请你作为一名学术研究助手和知识管理专家。

任务：
基于用户提供的内容完成结构化总结，提炼可复用的知识点。

背景：
用户正在使用 ChronoPaper 进行文献阅读、知识库问答或研究资料整理。

${buildInputBlock(input, contextBlock)}

约束条件：
1. 不编造原文没有的信息。
2. 如果已选择文献或知识库，优先基于这些资料回答。
3. 保留关键术语、方法名称、数据结论和限制条件。
4. 对不确定内容明确标注“信息不足”。

输出格式：
1. 核心结论
2. 背景与问题
3. 方法/流程
4. 关键证据
5. 可复用知识点
6. 后续追问建议

质量要求：
语言准确、层次清晰、适合直接放入知识库。`,
  },
  {
    id: 'knowledge_qa',
    name: '知识问答',
    category: '知识管理',
    description: '把模糊问题增强为可检索、可引用的知识库问答',
    build: ({ input, contextBlock }) => `角色：
请你作为严谨的知识库问答助手。

任务：
围绕用户问题检索、归纳并回答，必要时给出依据和可验证线索。

背景：
用户正在使用 ChronoPaper 进行文献阅读、知识库问答或研究资料整理。

${buildInputBlock(input, contextBlock)}

约束条件：
1. 优先使用已选择的文献、知识库片段或当前上下文资料。
2. 如果资料不足，先说明缺口，再给出合理的下一步检索方向。
3. 避免泛泛而谈，回答必须贴合问题。

输出格式：
1. 直接答案
2. 依据摘要
3. 关键概念
4. 风险与不确定性
5. 可继续追问的问题

质量要求：
回答应准确、可追踪、便于用户继续研究。`,
  },
  {
    id: 'memory_extract',
    name: '记忆提炼',
    category: '记忆增强',
    description: '从对话或材料中提取值得长期保存的用户偏好与事实',
    build: ({ input, contextBlock }) => `角色：
请你作为长期记忆整理助手。

任务：
从输入内容中提取值得保存的事实、偏好、项目上下文和待办线索。

背景：
用户希望 AI 在后续对话中能够记住重要背景，但不保存无关闲聊。

${buildInputBlock(input, contextBlock)}

约束条件：
1. 只提取稳定、可复用的信息。
2. 不保存敏感信息、临时情绪或未经确认的猜测。
3. 每条记忆都要简短、明确、便于后续检索。

输出格式：
1. 长期记忆候选
2. 短期上下文
3. 用户偏好
4. 项目事实
5. 不建议保存的信息

质量要求：
去重、准确、粒度适中，避免把一句话拆成过多碎片。`,
  },
  {
    id: 'memory_recall',
    name: '记忆调用',
    category: '记忆增强',
    description: '把需求改写为适合结合历史记忆回答的提示词',
    build: ({ input, contextBlock }) => `角色：
请你作为具备上下文记忆能力的研究助手。

任务：
结合当前问题与可用历史记忆，给出连续、一致且贴合用户偏好的回答。

背景：
用户可能已经在之前对话中提供过项目目标、写作偏好、技术栈或研究方向。

${buildInputBlock(input, contextBlock)}

约束条件：
1. 优先使用与当前问题直接相关的记忆和当前上下文。
2. 不要强行套用无关历史信息。
3. 当记忆与当前输入冲突时，以当前输入为准，并指出差异。

输出格式：
1. 当前问题理解
2. 可用记忆/上下文
3. 结合记忆后的回答
4. 需要用户确认的信息

质量要求：
保持上下文连续，减少重复提问，让回答更贴合用户习惯。`,
  },
]

const promptStyles = [
  {
    id: 'standard',
    name: '标准结构',
    description: '角色、任务、约束、输出格式完整展开',
    build: ({ template, input, contextBlock }) => template.build({ input, contextBlock }),
  },
  {
    id: 'brief',
    name: '简洁执行',
    description: '减少铺垫，适合快速发送和日常问答',
    build: ({ template, input, contextBlock }) => `请直接完成以下任务，回答要清楚、可执行、避免无关展开。

任务类型：
${template.name}，重点是${taskIntentMap[template.id] || template.description}。

${buildInputBlock(input, contextBlock)}

硬性要求：
1. 先给结论，再补充必要依据。
2. 不编造输入或资料中不存在的信息。
3. 信息不足时直接标注，并给出最少量的补充问题。
4. 保留关键术语、文件名、字段名、方法名和数据结论。

输出格式：
1. 结论
2. 要点
3. 下一步`,
  },
  {
    id: 'academic',
    name: '学术严谨',
    description: '强调证据、边界、术语和可验证表达',
    build: ({ template, input, contextBlock }) => `角色：
请你作为严谨的学术研究助手，使用准确、审慎、可验证的表达。

研究任务：
${template.name}。请围绕“${taskIntentMap[template.id] || template.description}”完成分析。

${buildInputBlock(input, contextBlock)}

分析原则：
1. 优先依据已选择文献、知识库、引用片段或当前上下文。
2. 区分事实、推断和建议，不把推测写成结论。
3. 对关键概念、方法、实验设置、限制条件和适用范围进行保留。
4. 如资料不足，请明确写出缺失信息和可能影响。

输出格式：
1. 摘要结论
2. 背景与研究问题
3. 方法或机制
4. 证据与依据
5. 局限性
6. 可继续研究的问题`,
  },
  {
    id: 'rag',
    name: '知识库/RAG',
    description: '优先使用文献、知识库和当前检索上下文',
    build: ({ template, input, contextBlock }) => `角色：
请你作为 ChronoPaper 的知识库/RAG 问答助手。

目标：
把用户需求改写为适合检索增强回答的提示词，并要求回答严格依据可用资料。

任务类型：
${template.name}，重点是${taskIntentMap[template.id] || template.description}。

${buildInputBlock(input, contextBlock)}

资料使用优先级：
1. 已选文献、知识库片段、图数据库结果。
2. 当前对话上下文和用户提供的材料。
3. 通用知识只能作为补充，且需要标注为“基于一般知识”。

回答约束：
1. 引用或概括资料时说明依据来源，不要伪造出处。
2. 资料不足时先说明不足，再给出检索关键词或补充问题。
3. 不要脱离用户原始问题扩写到无关主题。

输出格式：
1. 直接回答
2. 依据来源
3. 关键片段/概念
4. 不确定信息
5. 推荐追问`,
  },
  {
    id: 'deep',
    name: '深度分析',
    description: '拆成多角度推理，适合复杂问题',
    build: ({ template, input, contextBlock }) => `角色：
请你作为擅长复杂问题拆解的分析助手。

分析目标：
围绕“${template.name}”进行多角度分析，重点覆盖${taskIntentMap[template.id] || template.description}。

${buildInputBlock(input, contextBlock)}

分析步骤：
1. 先复述你对任务的理解，确认分析边界。
2. 将问题拆成 3 到 5 个关键维度。
3. 每个维度给出依据、推理过程和可执行结论。
4. 标注不确定点、风险点和需要补充的信息。
5. 最后给出最值得优先处理的下一步。

输出格式：
1. 问题理解
2. 维度拆解
3. 综合判断
4. 风险与缺口
5. 下一步行动`,
  },
  {
    id: 'technical',
    name: '技术实现',
    description: '偏工程落地，适合代码、接口和流程设计',
    build: ({ template, input, contextBlock }) => `角色：
请你作为资深工程实现顾问，回答要能直接指导开发或排查。

任务目标：
基于“${template.name}”完成技术化分析，重点是${taskIntentMap[template.id] || template.description}。

${buildInputBlock(input, contextBlock)}

实现约束：
1. 先说明涉及的模块、接口、数据结构或流程。
2. 给出可落地步骤，必要时提供伪代码、接口字段或配置示例。
3. 明确兼容性、异常情况、边界条件和验证方法。
4. 不确定的实现细节要标注“需确认”，不要臆造项目不存在的路径或接口。

输出格式：
1. 目标拆解
2. 实现方案
3. 关键数据/接口
4. 风险点
5. 验证方式`,
  },
]

const variantPlans = [
  {
    title: '方案 A｜简洁可执行',
    styleId: 'brief',
  },
  {
    title: '方案 B｜学术严谨',
    styleId: 'academic',
  },
  {
    title: '方案 C｜知识库/RAG 优化',
    styleId: 'rag',
  },
]

const categories = [...new Set(templates.map((item) => item.category))]

const open = ref(false)
const activeCategory = ref(categories[0])
const selectedTemplateId = ref(templates[0].id)
const selectedStyleId = ref(promptStyles[0].id)
const sourcePrompt = ref('')
const enhancedPrompt = ref('')
const saveModalOpen = ref(false)
const saveTitle = ref('')
const savingPrompt = ref(false)
const lastGeneratedMode = ref('single')

const visibleTemplates = computed(() =>
  templates.filter((item) => item.category === activeCategory.value),
)

const selectedTemplate = computed(() =>
  templates.find((item) => item.id === selectedTemplateId.value) || visibleTemplates.value[0] || templates[0],
)

const selectedStyle = computed(() =>
  promptStyles.find((item) => item.id === selectedStyleId.value) || promptStyles[0],
)

const citations = computed(() => {
  const raw = props.contextInfo?.citations
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item) => item && (item.title || item.arxiv_id))
    .slice(0, 6)
    .map((item) => ({
      title: String(item.title || item.arxiv_id || '').trim(),
      arxiv_id: String(item.arxiv_id || '').trim(),
      year: item.year ? String(item.year) : '',
    }))
})

const contextItems = computed(() => {
  const info = props.contextInfo || {}
  const items = []

  if (info.knowledgeBaseActive && info.knowledgeBaseName) {
    items.push(`知识库：${info.knowledgeBaseName}`)
  }
  if (info.useGraph) items.push('图数据库：已启用')
  if (info.useWeb) items.push('搜索引擎：已启用')
  if (info.memoryEnabled) items.push('记忆：已启用')
  if (citations.value.length) {
    items.push(`已选文献：${citations.value.length} 篇`)
  }

  return items
})

const contextBlock = computed(() => {
  const lines = [...contextItems.value]
  if (citations.value.length) {
    lines.push('文献列表：')
    citations.value.forEach((item, index) => {
      const suffix = [item.year, item.arxiv_id].filter(Boolean).join(' · ')
      lines.push(`${index + 1}. ${item.title}${suffix ? `（${suffix}）` : ''}`)
    })
  }
  return lines.length ? lines.map((line) => `- ${line}`).join('\n') : ''
})

const hasResult = computed(() => Boolean(enhancedPrompt.value.trim()))

watch(open, (visible) => {
  if (!visible) return
  if (!sourcePrompt.value.trim() && props.currentInput?.trim()) {
    sourcePrompt.value = props.currentInput.trim()
  }
})

watch(activeCategory, () => {
  selectedTemplateId.value = visibleTemplates.value[0]?.id || templates[0].id
})

const buildStyledPrompt = (template, style, input, activeContextBlock) => style.build({
  template,
  input,
  contextBlock: activeContextBlock,
})

const generatePrompt = (options = {}) => {
  const input = sourcePrompt.value.trim()
  if (!input) {
    message.warning('请输入需要增强的原始提示词')
    return false
  }
  enhancedPrompt.value = buildStyledPrompt(
    selectedTemplate.value,
    selectedStyle.value,
    input,
    contextBlock.value,
  )
  lastGeneratedMode.value = 'single'
  if (!options.silent) {
    message.success(`已生成${selectedStyle.value.name}增强提示词`)
  }
  return true
}

const generateVariants = () => {
  const input = sourcePrompt.value.trim()
  if (!input) {
    message.warning('请输入需要增强的原始提示词')
    return false
  }

  enhancedPrompt.value = variantPlans
    .map((plan) => {
      const style = promptStyles.find((item) => item.id === plan.styleId) || promptStyles[0]
      return `${plan.title}

${buildStyledPrompt(selectedTemplate.value, style, input, contextBlock.value)}`
    })
    .join('\n\n---\n\n')
  lastGeneratedMode.value = 'variants'
  message.success('已生成三套增强方案')
  return true
}

const regeneratePrompt = () => {
  if (lastGeneratedMode.value === 'variants') {
    generateVariants()
    return
  }
  generatePrompt()
}

const generateAndSend = () => {
  const ok = generatePrompt({ silent: true })
  if (!ok) return
  applyResult('send')
}

const copyResult = async () => {
  const text = enhancedPrompt.value.trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制')
  } catch (err) {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    message.success('已复制')
  }
}

const applyResult = (mode) => {
  const text = enhancedPrompt.value.trim()
  if (!text) return
  emit('apply', { mode, content: text })
  open.value = false
}

const generateId = () => `prompt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

const normalizePrompts = (raw) => {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      id: String(item.id || generateId()),
      title: String(item.title || '').trim(),
      content: String(item.content || '').trim(),
    }))
    .filter((item) => item.title && item.content)
}

const openSaveModal = () => {
  if (!hasResult.value) return
  saveTitle.value = lastGeneratedMode.value === 'variants'
    ? `${selectedTemplate.value.name}多方案增强`
    : `${selectedTemplate.value.name}-${selectedStyle.value.name}增强`
  saveModalOpen.value = true
}

const saveToPromptLibrary = async () => {
  const title = saveTitle.value.trim()
  const content = enhancedPrompt.value.trim()

  if (!title || !content) {
    message.warning('请填写标题并生成提示词内容')
    return
  }

  savingPrompt.value = true
  try {
    const existing = normalizePrompts(configStore.config?.custom_prompts)
    const next = [
      ...existing,
      {
        id: generateId(),
        title,
        content,
      },
    ]
    await configStore.setConfigValue('custom_prompts', next)
    saveModalOpen.value = false
    message.success('已保存到提示词库')
  } catch (err) {
    message.error(err.message || '保存失败')
  } finally {
    savingPrompt.value = false
  }
}
</script>

<style scoped lang="less">
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
}

.tool-chip:hover {
  background: #f3f5f7;
  color: #222;
}

.tool-chip--active {
  background: #fff7e6;
  color: #d46b08;
}

.enhancer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.context-card {
  padding: 10px 12px;
  border: 1px solid #ffe7ba;
  border-radius: 8px;
  background: #fffaf2;
}

.context-card__title {
  margin-bottom: 6px;
  color: #92400e;
  font-size: 13px;
  font-weight: 600;
}

.context-card__list {
  margin: 0;
  padding-left: 18px;
  color: #6b4b16;
  font-size: 12px;
  line-height: 1.6;
}

.enhancer__tabs {
  margin-bottom: -6px;
}

.template-list,
.style-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.template-option,
.style-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  gap: 5px;
  padding: 10px 12px;
  border: 1px solid #edf0f5;
  border-radius: 8px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}

.template-option {
  min-height: 74px;
}

.style-option {
  min-height: 66px;
}

.template-option:hover,
.style-option:hover {
  border-color: #ffd591;
  background: #fffaf2;
}

.template-option--active,
.style-option--active {
  border-color: #faad14;
  background: #fff7e6;
  box-shadow: 0 0 0 2px rgba(250, 173, 20, 0.12);
}

.template-option__title,
.style-option__title {
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
}

.template-option__desc,
.style-option__desc {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.45;
}

.style-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-block,
.save-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-block__label {
  color: #374151;
  font-size: 13px;
  font-weight: 600;
}

.field-block--result :deep(textarea) {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.65;
}

.enhancer__main-action {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: -2px;
}

.enhancer__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

:deep(.ant-drawer-body) {
  padding-top: 16px;
}

@media (max-width: 640px) {
  .template-list,
  .style-list,
  .enhancer__main-action {
    grid-template-columns: 1fr;
  }
}
</style>
