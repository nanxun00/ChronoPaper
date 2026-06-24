import { defineStore } from 'pinia'
import { streamTranslate } from '@/api/translate'

export const useTranslateStore = defineStore('translate', {
  state: () => ({
    visible: false,
    sourceText: '',
    result: '',
    loading: false,
    error: '',
    targetLang: 'zh',
    modelName: 'deepseek-chat',
    _abort: null,
  }),

  actions: {
    showPanel() {
      this.visible = true
    },

    hidePanel() {
      this.visible = false
      this.cancel()
    },

    cancel() {
      if (this._abort) {
        this._abort.abort()
        this._abort = null
      }
      this.loading = false
    },

    clear() {
      this.cancel()
      this.sourceText = ''
      this.result = ''
      this.error = ''
    },

    async translateText(text, options = {}) {
      const trimmed = (text || '').trim()
      if (!trimmed || trimmed.length < 2) return

      if (options.targetLang) {
        this.targetLang = options.targetLang
      }

      this.cancel()
      this.visible = true
      this.sourceText = trimmed
      this.result = ''
      this.error = ''
      this.loading = true

      const controller = new AbortController()
      this._abort = controller

      try {
        await streamTranslate({
          text: trimmed,
          targetLang: this.targetLang,
          signal: controller.signal,
          onChunk: ({ content, error, done }) => {
            if (error) {
              this.error = error
              return
            }
            if (content) {
              this.result += content
            }
            if (done) {
              this.loading = false
            }
          },
        })
      } catch (err) {
        if (err.name === 'AbortError') return
        this.error = err.message || '翻译失败'
      } finally {
        this.loading = false
        this._abort = null
      }
    },
  },
})
