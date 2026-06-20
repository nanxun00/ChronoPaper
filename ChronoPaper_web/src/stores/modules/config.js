import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export const useCounterStore = defineStore('counter', () => {
  const count = ref(0)
  const doubleCount = computed(() => count.value * 2)
  function increment() {
    count.value++
  }

  return { count, doubleCount, increment }
})


export const useConfigStore = defineStore('config', () => {
  const config = ref({})
  function setConfig(newConfig) {
    config.value = newConfig
  }
  function setConfigValue(key, value) {
    config.value[key] = value
    return fetch('/api/config', {
      method: 'POST',
      body: JSON.stringify({ key, value }),
      headers: {
        'Content-Type': 'application/json',
      }
    })
    .then(response => {
      if (!response.ok) {
        return response.json().then((data) => {
          throw new Error(data.detail || `保存失败 (${response.status})`)
        })
      }
      return response.json()
    })
    .then(data => {
      setConfig(data)
      return data
    })
  }

  function refreshConfig() {
    fetch('/api/config')
    .then(response => response.json())
    .then(data => {
      console.log("config", data)
      setConfig(data)
    })
  }

  return { config, setConfig, setConfigValue, refreshConfig }
})