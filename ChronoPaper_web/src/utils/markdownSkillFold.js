/** 技能对话 Markdown：将中间 Python 脚本折叠为 details */
import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js'

const FOLD_MIN_LINES = 3

export function shouldCollapseSkillCode(message) {
  if (!message || message.role !== 'received') return false
  if (message.skill_active) return true
  const skill = message.refs?.skill
  if (skill?.skill_id) return true
  if (Array.isArray(skill?.skill_scripts) && skill.skill_scripts.length > 0) return true
  if (Array.isArray(skill?.artifacts) && skill.artifacts.length > 0) return true
  const meta = message.meta || {}
  if (meta.skill_id || meta.skill_mode === 'explicit') return true
  return false
}

function highlightCode(text, lang) {
  if (lang) {
    try {
      return hljs.highlight(text, { language: lang }).value
    } catch {
      /* fallback */
    }
  }
  return hljs.highlightAuto(text).value
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function foldPythonCodeBlock(text, lang, forceSkillFold = false) {
  const language = (lang || '').toLowerCase()
  const lineCount = text.split('\n').length
  const looksLikePython =
    language === 'python' ||
    (forceSkillFold &&
      !language &&
      lineCount >= FOLD_MIN_LINES &&
      /^\s*(import |from .+ import )/m.test(text))

  if (looksLikePython && lineCount >= FOLD_MIN_LINES) {
    const codeHtml =
      text.length > 12000
        ? escapeHtml(text)
        : highlightCode(text, 'python')
    return `<details class="skill-code-fold">
<summary class="skill-code-fold__summary">技能中间代码 (Python · ${lineCount} 行)</summary>
<div class="skill-code-fold__body"><pre><code class="hljs language-python">${codeHtml}</code></pre></div>
</details>`
  }
  if (text.length > 12000) {
    return `<pre><code>${escapeHtml(text)}</code></pre>`
  }
  const hl = highlightCode(text, language || undefined)
  const cls = language ? `hljs language-${language}` : 'hljs'
  return `<pre><code class="${cls}">${hl}</code></pre>`
}

let _defaultMarked
let _foldMarked
let _liteMarked

const LITE_PARSE_THRESHOLD = 25000

function getLiteMarked() {
  if (!_liteMarked) {
    _liteMarked = new Marked({ gfm: true, breaks: true, tables: true })
  }
  return _liteMarked
}

function getDefaultMarked() {
  if (!_defaultMarked) {
    _defaultMarked = new Marked(
      { gfm: true, breaks: true, tables: true },
      markedHighlight({
        langPrefix: 'hljs language-',
        highlight(code) {
          return hljs.highlightAuto(code).value
        },
      }),
    )
  }
  return _defaultMarked
}

function getFoldMarked() {
  if (!_foldMarked) {
    _foldMarked = new Marked({ gfm: true, breaks: true, tables: true })
    // marked v13 .use() 仍走旧式 (text, lang, escaped) 回调，勿解构为 { text, lang }
    _foldMarked.use({
      renderer: {
        code(text, lang) {
          return foldPythonCodeBlock(text, lang, true)
        },
      },
    })
  }
  return _foldMarked
}

export function parseChatMarkdown(text, message) {
  const raw = String(text ?? '')
  const fold = shouldCollapseSkillCode(message)
  const md = fold ? getFoldMarked() : getDefaultMarked()
  if (raw.length >= LITE_PARSE_THRESHOLD && !fold) {
    try {
      return getLiteMarked().parse(raw)
    } catch {
      return escapeHtml(raw).replace(/\n/g, '<br>')
    }
  }
  try {
    return md.parse(raw)
  } catch {
    if (fold) {
      try {
        return getFoldMarked().parse(raw)
      } catch {
        /* fall through */
      }
    }
    return getLiteMarked().parse(raw)
  }
}
