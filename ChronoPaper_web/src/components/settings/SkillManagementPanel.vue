<template>
  <div class="skill-mgmt">
    <div class="skill-mgmt__toolbar">
      <p class="skill-mgmt__hint">
        已启用技能会参与对话中的<strong>自动路由</strong>，并出现在聊天框技能下拉里。
        技能通过上传 zip 安装到 <code>data/skills/user/</code>。
        对话中可自动执行 <code>scripts/</code>；脚本写入 <code>output/</code>、<code>references/</code> 的文件会出现在消息引用区，可预览或下载。
      </p>
      <div class="skill-mgmt__actions">
        <a-button :loading="loading" @click="loadSkills">
          <ReloadOutlined /> 刷新列表
        </a-button>
        <input
          ref="fileInputRef"
          type="file"
          accept=".zip"
          class="skill-upload-input"
          @change="onUpload"
        />
        <a-button :loading="uploading" @click="openUpload">
          <UploadOutlined /> 上传技能包
        </a-button>
      </div>
    </div>

    <a-spin :spinning="loading">
      <div v-if="!skills.length && !loading" class="skill-mgmt__empty">
        暂无技能。请上传 zip：可为单个技能目录、<code>skills/</code> 文件夹，或整个 nature-skills 仓库。
      </div>

      <div v-else class="skill-list">
        <div
          v-for="skill in skills"
          :key="skill.id"
          class="skill-row"
          :class="{ 'skill-row--disabled': !skill.enabled }"
        >
          <div class="skill-row__main">
            <div class="skill-row__title">
              <span class="skill-row__name">{{ skill.id }}</span>
              <a-tag v-if="skill.version" color="default">v{{ skill.version }}</a-tag>
            </div>
            <p class="skill-row__desc">{{ skill.description || '（无描述）' }}</p>
          </div>
          <a-switch
            :checked="skill.enabled"
            :loading="togglingId === skill.id"
            checked-children="启用"
            un-checked-children="禁用"
            @change="(checked) => onToggle(skill, checked)"
          />
        </div>
      </div>
    </a-spin>

    <p v-if="skills.length" class="skill-mgmt__footer">
      共 {{ skills.length }} 个技能，已启用 {{ enabledCount }} 个
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, UploadOutlined } from '@ant-design/icons-vue'
import { listSkills, patchSkill, reloadSkills, uploadSkillZip } from '@/api/skills'

const skills = ref([])
const loading = ref(false)
const uploading = ref(false)
const togglingId = ref(null)
const fileInputRef = ref(null)

const enabledCount = computed(() => skills.value.filter((s) => s.enabled).length)

const loadSkills = async () => {
  loading.value = true
  try {
    const data = await listSkills()
    skills.value = data.skills || []
  } catch (e) {
    message.error(e.message || '加载技能列表失败')
  } finally {
    loading.value = false
  }
}

const onToggle = async (skill, enabled) => {
  togglingId.value = skill.id
  const prev = skill.enabled
  skill.enabled = enabled
  try {
    await patchSkill(skill.id, enabled)
    message.success(enabled ? `已启用 ${skill.id}` : `已禁用 ${skill.id}`)
  } catch (e) {
    skill.enabled = prev
    message.error(e.message || '更新失败')
  } finally {
    togglingId.value = null
  }
}

const openUpload = () => {
  fileInputRef.value?.click()
}

const onUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  uploading.value = true
  try {
    await uploadSkillZip(file)
    await reloadSkills()
    await loadSkills()
    message.success('技能包已安装')
  } catch (e) {
    message.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

defineExpose({ loadSkills })

loadSkills()
</script>

<style scoped>
.skill-mgmt__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.skill-mgmt__hint {
  margin: 0;
  flex: 1;
  min-width: 240px;
  font-size: 13px;
  color: var(--gray-700);
  line-height: 1.5;
}

.skill-mgmt__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.skill-upload-input {
  display: none;
}

.skill-mgmt__empty {
  padding: 32px;
  text-align: center;
  color: var(--gray-600);
  background: var(--gray-10);
  border: 1px dashed var(--gray-300);
  border-radius: 8px;
}

.skill-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skill-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--gray-300);
  border-radius: 8px;
  transition: opacity 0.15s;
}

.skill-row--disabled {
  opacity: 0.72;
  background: var(--gray-10);
}

.skill-row__main {
  flex: 1;
  min-width: 0;
}

.skill-row__title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.skill-row__name {
  font-weight: 600;
  font-size: 14px;
  color: var(--gray-1000);
}

.skill-row__desc {
  margin: 0;
  font-size: 12px;
  color: var(--gray-600);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-mgmt__footer {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--gray-500);
}
</style>
