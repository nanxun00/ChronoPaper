import { message } from 'ant-design-vue'

export const COPYABLE_BLOCK_BTN_CLASS = 'copyable-block__btn'

export const COPY_BLOCK_ICON_SVG = `<svg class="copyable-block__icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="1.5"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg>`

export function langDisplayLabel(lang) {
  const l = String(lang || '').toLowerCase()
  if (l === 'python' || l === 'py') return 'python'
  if (l === 'markdown' || l === 'md') return 'markdown'
  if (l === 'plaintext' || l === 'text') return 'plaintext'
  if (l) return l
  return 'plaintext'
}

export function blockCopyLabel(lang) {
  const l = String(lang || '').toLowerCase()
  if (l === 'python' || l === 'py') return 'Python'
  if (l === 'markdown' || l === 'md') return 'Markdown'
  if (l) return l
  return '代码'
}

function escapeAttr(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
}

export async function copyTextToClipboard(text) {
  const value = String(text ?? '')
  if (!value.trim()) {
    message.warning('无内容可复制')
    return false
  }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
    } else {
      const ta = document.createElement('textarea')
      ta.value = value
      ta.setAttribute('readonly', '')
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    message.success('已复制到剪贴板')
    return true
  } catch (error) {
    console.error('复制失败:', error)
    message.error('复制失败，请手动复制')
    return false
  }
}

export function handleCopyableBlockClick(event) {
  const btn = event.target.closest?.(`.${COPYABLE_BLOCK_BTN_CLASS}`)
  if (!btn) return false
  event.preventDefault()
  event.stopPropagation()
  const block = btn.closest('.copyable-block')
  if (!block) return true
  const codeEl = block.querySelector('code') || block.querySelector('pre')
  void copyTextToClipboard(codeEl?.textContent ?? '')
  return true
}

export function wrapCopyableBlock(preInnerHtml, lang) {
  const label = langDisplayLabel(lang)
  const copyLabel = blockCopyLabel(lang)
  return `<div class="copyable-block" data-lang="${escapeAttr(lang || '')}">
<div class="copyable-block__toolbar">
<span class="copyable-block__lang">${escapeAttr(label)}</span>
<div class="copyable-block__actions">
<button type="button" class="${COPYABLE_BLOCK_BTN_CLASS}" title="复制${escapeAttr(copyLabel)}" aria-label="复制${escapeAttr(copyLabel)}">
${COPY_BLOCK_ICON_SVG}
<span class="copyable-block__tooltip">复制</span>
</button>
</div>
</div>
<div class="copyable-block__body">${preInnerHtml}</div>
</div>`
}
