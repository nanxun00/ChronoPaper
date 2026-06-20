import { message } from 'ant-design-vue'

export const COPYABLE_BLOCK_BTN_CLASS = 'copyable-block__btn'

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
  const label = blockCopyLabel(lang)
  return `<div class="copyable-block" data-lang="${escapeAttr(lang || '')}">
<button type="button" class="${COPYABLE_BLOCK_BTN_CLASS}" title="复制${escapeAttr(label)}">复制</button>
${preInnerHtml}
</div>`
}
