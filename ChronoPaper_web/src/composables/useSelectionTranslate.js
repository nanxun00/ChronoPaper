import { onBeforeUnmount } from 'vue'
import { useTranslateStore } from '@/stores'

/**
 * mouseup 后读取选中文本并触发 DeepSeek 流式翻译。
 */
export function useSelectionTranslate(options = {}) {
  const { minLength = 2, delay = 300 } = options
  const translateStore = useTranslateStore()
  let selectionTimer = null

  const handleTextSelection = () => {
    if (selectionTimer) {
      clearTimeout(selectionTimer)
    }
    selectionTimer = setTimeout(() => {
      const text = window.getSelection()?.toString().trim()
      if (text && text.length >= minLength) {
        translateStore.translateText(text)
      }
    }, delay)
  }

  onBeforeUnmount(() => {
    if (selectionTimer) {
      clearTimeout(selectionTimer)
    }
  })

  return { handleTextSelection }
}
