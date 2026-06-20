<template>
  <div class="message-md-layer">
    <p v-if="!html" class="message-plain-preview">{{ fullText }}</p>
    <div
      v-else
      class="message-md"
      v-html="html"
      @click="onMarkdownClick"
    ></div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { parseChatMarkdown } from '@/utils/markdownSkillFold'
import { enqueueMarkdownRender } from '@/utils/markdownRenderQueue'
import { handleCopyableBlockClick } from '@/utils/copyBlock'

const renderCache = new Map()
const props = defineProps({
  message: { type: Object, required: true },
  priority: { type: Number, default: 0 },
})

const html = ref('')
const signal = { cancelled: false }
let generation = 0

const fullText = computed(() => (props.message?.text || '').trim())

const onMarkdownClick = (event) => {
  handleCopyableBlockClick(event)
}

const cacheKeyFor = (msg) => {
  if (!msg) return ''
  const skillKey =
    msg.skill_active ||
    msg.meta?.skill_id ||
    msg.refs?.skill?.skill_id ||
    ''
  return `${msg.id}::${msg.text?.length || 0}::${msg.status}::${skillKey}`
}

const applyCached = (key) => {
  if (key && renderCache.has(key)) {
    html.value = renderCache.get(key)
    return true
  }
  return false
}

const scheduleRender = () => {
  signal.cancelled = true
  signal.cancelled = false
  const gen = ++generation
  const msg = props.message
  if (!msg?.text) {
    html.value = ''
    return
  }

  if (msg.status !== 'finished') {
    const key = cacheKeyFor(msg)
    const text = `${msg.text}🟢`
    try {
      const rendered = parseChatMarkdown(text, msg)
      renderCache.set(key, rendered)
      html.value = rendered
    } catch {
      html.value = ''
    }
    return
  }

  const key = cacheKeyFor(msg)
  if (applyCached(key)) return

  html.value = ''

  enqueueMarkdownRender(
    () => {
      const text = msg.text
      const rendered = parseChatMarkdown(text, msg)
      renderCache.set(key, rendered)
      return rendered
    },
    { priority: props.priority, signal },
  ).then((rendered) => {
    if (gen !== generation || signal.cancelled) return
    if (rendered) {
      html.value = rendered
    }
  })
}

watch(
  () => [
    props.message?.id,
    props.message?.text,
    props.message?.status,
    props.message?.skill_active,
    props.message?.refs?.skill?.skill_id,
    props.message?.meta?.skill_id,
    props.priority,
  ],
  scheduleRender,
  { immediate: true },
)

onBeforeUnmount(() => {
  signal.cancelled = true
})
</script>

<style scoped>
.message-plain-preview {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--gray-800);
  font-size: 14px;
  line-height: 1.6;
}
</style>
