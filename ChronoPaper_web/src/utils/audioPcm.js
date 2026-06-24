/** 浏览器端将录音 Blob 转为 16kHz 单声道 WAV（无需服务端 ffmpeg）。 */
const TARGET_RATE = 16000

function pcm16ToWav(pcm16, sampleRate) {
  const dataSize = pcm16.length * 2
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(offset + i, str.charCodeAt(i))
    }
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, dataSize, true)

  let offset = 44
  for (let i = 0; i < pcm16.length; i += 1, offset += 2) {
    view.setInt16(offset, pcm16[i], true)
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

export async function audioBlobToWav16k(blob) {
  const arrayBuffer = await blob.arrayBuffer()
  const decodeCtx = new AudioContext()
  let audioBuffer
  try {
    audioBuffer = await decodeCtx.decodeAudioData(arrayBuffer.slice(0))
  } finally {
    await decodeCtx.close()
  }

  const frameCount = Math.max(1, Math.ceil(audioBuffer.duration * TARGET_RATE))
  const offline = new OfflineAudioContext(1, frameCount, TARGET_RATE)
  const source = offline.createBufferSource()
  source.buffer = audioBuffer
  source.connect(offline.destination)
  source.start(0)
  const rendered = await offline.startRendering()

  const samples = rendered.getChannelData(0)
  const pcm16 = new Int16Array(samples.length)
  for (let i = 0; i < samples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, samples[i]))
    pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  }

  return pcm16ToWav(pcm16, TARGET_RATE)
}
