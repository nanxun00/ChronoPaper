<template>
  <a-popover
    v-model:open="open"
    trigger="click"
    placement="topLeft"
    overlay-class-name="skill-picker-popover"
    :arrow="false"
  >
    <template #content>
      <div class="skill-panel">
        <div class="skill-panel__search">
          <a-input
            v-model:value="keyword"
            placeholder="搜索技能名称或描述"
            allow-clear
            size="small"
          >
            <template #prefix>
              <SearchOutlined class="skill-panel__search-icon" />
            </template>
          </a-input>
        </div>

        <div class="skill-panel__modes">
          <div
            class="skill-option"
            :class="{ 'skill-option--active': props.skillMode === 'auto' }"
            @click="selectMode('auto')"
          >
            <span class="skill-option__title">自动匹配</span>
            <span class="skill-option__hint">根据问题选用技能</span>
          </div>
          <div
            class="skill-option"
            :class="{ 'skill-option--active': props.skillMode === 'off' }"
            @click="selectMode('off')"
          >
            <span class="skill-option__title">不使用技能</span>
          </div>
        </div>

        <div v-if="enabledSkills.length" class="skill-panel__divider" />

        <div class="skill-panel__list">
          <div v-if="!filteredSkills.length" class="skill-panel__empty">
            {{ keyword.trim() ? '未找到匹配的技能' : '暂无可用技能' }}
          </div>
          <div
            v-for="skill in filteredSkills"
            :key="skill.id"
            class="skill-option skill-option--skill"
            :class="{ 'skill-option--active': props.skillMode === 'explicit' && props.skillId === skill.id }"
            @click="selectSkill(skill.id)"
          >
            <span class="skill-option__title">{{ shortName(skill.id) }}</span>
            <span v-if="skill.description" class="skill-option__desc">{{ skill.description }}</span>
          </div>
        </div>
      </div>
    </template>

    <button
      type="button"
      class="tool-chip"
      :class="{ 'tool-chip--active': isActive }"
      @click.prevent
    >
      <ThunderboltOutlined />
      <span>{{ displayLabel }}</span>
      <DownOutlined class="tool-chip__caret" />
    </button>
  </a-popover>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ThunderboltOutlined, DownOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { listSkills } from '@/api/skills'

const props = defineProps({
  skillMode: { type: String, default: 'auto' },
  skillId: { type: String, default: null },
})

const emit = defineEmits(['update:skillMode', 'update:skillId'])

const skills = ref([])
const open = ref(false)
const keyword = ref('')

const enabledSkills = computed(() => skills.value.filter((s) => s.enabled))

const filteredSkills = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return enabledSkills.value
  return enabledSkills.value.filter((skill) => {
    const id = String(skill.id || '').toLowerCase()
    const name = shortName(skill.id).toLowerCase()
    const desc = String(skill.description || '').toLowerCase()
    return id.includes(q) || name.includes(q) || desc.includes(q)
  })
})

/** 仅显式选中某一技能时高亮，与「文献」一致：默认透明底 */
const isActive = computed(() => props.skillMode === 'explicit' && !!props.skillId)

const displayLabel = computed(() => {
  if (props.skillMode === 'off') return '技能'
  if (props.skillMode === 'explicit' && props.skillId) {
    return shortName(props.skillId)
  }
  return '技能·自动'
})

const shortName = (id) => String(id || '').replace(/^nature-/, '')

const loadSkills = async () => {
  try {
    const data = await listSkills()
    skills.value = data.skills || []
  } catch (e) {
    console.warn('load skills failed', e)
  }
}

const selectMode = (mode) => {
  if (mode === 'auto') {
    emit('update:skillMode', 'auto')
    emit('update:skillId', null)
  } else if (mode === 'off') {
    emit('update:skillMode', 'off')
    emit('update:skillId', null)
  }
  open.value = false
}

const selectSkill = (skillId) => {
  emit('update:skillMode', 'explicit')
  emit('update:skillId', skillId)
  open.value = false
}

onMounted(loadSkills)

watch(open, (val) => {
  if (!val) {
    keyword.value = ''
  } else if (!skills.value.length) {
    loadSkills()
  }
})

watch(
  () => props.skillMode,
  () => {
    if (!skills.value.length) loadSkills()
  },
)
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
  background: #eef5ff;
  color: var(--main-700, #1677ff);
}

.tool-chip__caret {
  font-size: 10px;
  margin-left: 2px;
  opacity: 0.55;
}

.skill-panel {
  width: 320px;
}

.skill-panel__search {
  margin-bottom: 8px;
}

.skill-panel__search-icon {
  color: #bbb;
  font-size: 12px;
}

.skill-panel__modes {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.skill-panel__divider {
  height: 1px;
  margin: 6px 0;
  background: #f0f0f0;
}

.skill-panel__list {
  max-height: 260px;
  overflow-y: auto;
  margin: 0 -4px;
  padding: 0 4px;
}

.skill-panel__empty {
  padding: 20px 8px;
  text-align: center;
  color: #999;
  font-size: 13px;
}

.skill-option {
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: #f5f7fa;
  }

  &--active {
    background: #eef5ff;
  }
}

.skill-option__title {
  display: block;
  font-weight: 500;
  font-size: 13px;
  line-height: 1.35;
  color: #222;
}

.skill-option__hint {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #999;
  line-height: 1.3;
}

.skill-option__desc {
  display: -webkit-box;
  margin-top: 2px;
  font-size: 11px;
  color: #888;
  line-height: 1.4;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

<style lang="less">
.skill-picker-popover .ant-popover-inner {
  padding: 10px 12px;
}
</style>
