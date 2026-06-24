/** 全局 Markdown 渲染队列，避免 idle 回调饿死、保证每条消息最终都会渲染 */
const queue = []
let pumping = false

function sortQueue() {
  queue.sort((a, b) => b.priority - a.priority)
}

async function pump() {
  if (pumping) return
  pumping = true
  while (queue.length) {
    const job = queue.shift()
    if (job.cancelled) {
      job.resolve(null)
      continue
    }
    try {
      const html = await job.run()
      if (!job.cancelled) {
        job.resolve(html)
      } else {
        job.resolve(null)
      }
    } catch (err) {
      console.warn('markdown render failed', err)
      job.resolve(null)
    }
    await new Promise((r) => setTimeout(r, 0))
  }
  pumping = false
}

/**
 * @param {() => string} run
 * @param {{ priority?: number, signal?: { cancelled: boolean } }} options
 */
export function enqueueMarkdownRender(run, { priority = 0, signal } = {}) {
  return new Promise((resolve) => {
    const job = {
      priority,
      run: () => Promise.resolve().then(run),
      resolve,
      get cancelled() {
        return Boolean(signal?.cancelled)
      },
    }
    queue.push(job)
    sortQueue()
    pump()
  })
}
