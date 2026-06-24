<template>
  <div class="personal-container" :class="{ 'is-loaded': isLoaded }">
    <!-- 背景光效 -->
    <div class="background-effects">
      <div class="glow-orb"></div>
    </div>

    <div class="content-wrapper">
      <!-- 用户信息头部卡片 -->
      <div class="user-header-card glass-card">
        <div class="user-info">
          <h1 class="username">{{ userStore.username }}</h1>
          <p class="user-id">ID: {{ userStore.username || '未登录' }}</p>
        </div>
      </div>

      <!-- 主内容区域布局 -->
      <el-row :gutter="32" class="main-grid">
        <!-- 左侧：修改密码模块 -->
        <el-col :xs="24" :lg="14">
          <div class="password-section glass-card">
            <div class="section-header">
              <div class="header-icon">🔒</div>
              <div class="header-text">
                <h2>账户安全</h2>
                <p>修改登录密码</p>
                <span class="subtitle">定期更新密码有助于保护账户安全</span>
              </div>
            </div>

            <el-form 
              :model="formState" 
              label-position="top"
              class="custom-form"
              @submit.prevent="onFinish"
            >
              <el-form-item label="您的账号">
                <el-input 
                  v-model="formState.userid" 
                  placeholder="请输入当前账号"
                  class="custom-input"
                />
              </el-form-item>

              <el-form-item label="当前密码">
                <el-input 
                  v-model="formState.oldpassword" 
                  type="password" 
                  show-password
                  placeholder="请输入当前密码"
                  class="custom-input"
                />
              </el-form-item>

              <el-form-item label="新密码">
                <el-input 
                  v-model="formState.password1" 
                  type="password" 
                  show-password
                  placeholder="请输入新密码"
                  class="custom-input"
                />
                <!-- 密码强度检测 -->
                <div class="strength-meter" v-if="formState.password1">
                  <div class="meter-bar">
                    <div 
                      class="meter-fill" 
                      :style="{ width: strengthPercent + '%', backgroundColor: strengthColor }"
                    ></div>
                  </div>
                  <div class="meter-label" :style="{ color: strengthColor }">
                    密码强度：{{ strengthText }}
                  </div>
                </div>
              </el-form-item>

              <el-form-item label="确认新密码">
                <el-input 
                  v-model="formState.password2" 
                  type="password" 
                  show-password
                  placeholder="请再次输入新密码"
                  class="custom-input"
                />
              </el-form-item>

              <div class="form-actions">
                <el-button 
                  type="primary" 
                  class="submit-btn" 
                  @click="onFinish"
                  :loading="loading"
                >
                  确认修改密码
                </el-button>
              </div>
            </el-form>
          </div>
        </el-col>

        <!-- 右侧：账户安全卡片 -->
        <el-col :xs="24" :lg="10">
          <div class="security-info-card glass-card">
            <div class="section-header">
              <div class="header-icon">🛡️</div>
              <div class="header-text">
                <h2>账户信息</h2>
              </div>
            </div>

            <div class="security-list">
              <div class="security-item">
                <div class="item-icon"><UserOutlined /></div>
                <div class="item-content">
                  <span class="label">当前登录账号</span>
                  <span class="value">{{ userStore.username }}</span>
                </div>
              </div>
              <div class="security-item">
                <div class="item-icon"><SafetyCertificateOutlined /></div>
                <div class="item-content">
                  <span class="label">认证状态</span>
                  <span class="value status-active">已登录</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 危险操作区域 -->
          <div class="danger-zone glass-card">
            <div class="danger-header">
              <h3>危险操作</h3>
              <p>退出登录后需要重新验证身份</p>
            </div>
            <el-button type="danger" class="logout-btn" @click="logout">
              退出登录
            </el-button>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores';
import { ElMessage } from 'element-plus';
import { 
  UserOutlined, 
  SafetyCertificateOutlined 
} from '@ant-design/icons-vue';

const router = useRouter();
const userStore = useUserStore();
const isLoaded = ref(false);
const loading = ref(false);

const formState = reactive({
  userid: userStore.username || '',
  oldpassword: '',
  password1: '',
  password2: '',
});

onMounted(() => {
  // 触发页面进入动画
  setTimeout(() => {
    isLoaded.value = true;
  }, 50);
});

// 密码强度检测逻辑
const strengthScore = computed(() => {
  const p = formState.password1;
  if (!p) return 0;
  let score = 0;
  if (p.length >= 6) score += 1; // 基础长度
  if (p.length >= 10) score += 1; // 较长密码
  if (/[A-Z]/.test(p) && /[0-9]/.test(p)) score += 1; // 包含大小写字母和数字
  return Math.min(score, 3);
});

const strengthText = computed(() => {
  const texts = ['', '弱', '中', '强'];
  return texts[strengthScore.value];
});

const strengthColor = computed(() => {
  const colors = ['', '#ef4444', '#f59e0b', '#22c55e'];
  return colors[strengthScore.value];
});

const strengthPercent = computed(() => {
  return (strengthScore.value / 3) * 100;
});

// 修改密码逻辑
const onFinish = async () => {
  if (!formState.userid || !formState.oldpassword || !formState.password1 || !formState.password2) {
    ElMessage.warning('请填写完整信息！');
    return;
  }

  if (formState.password1 !== formState.password2) {
    ElMessage.error('两次输入的新密码不一致！');
    return;
  }

  loading.value = true;
  try {
    const requestData = {
      userid: formState.userid,
      password: formState.oldpassword,
      new_password: formState.password1,
    };

    const response = await fetch('/api/change-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
    });

    if (response.ok) {
      const data = await response.json();
      if (data.status_code === 200) {
        ElMessage.success(data.detail || '密码修改成功，请重新登录');
        // 延迟退出，让用户看清提示
        setTimeout(() => {
          logout();
        }, 1500);
      } else {
        ElMessage.error(data.detail || '密码修改失败！');
      }
    } else {
      ElMessage.error('服务响应异常，请稍后再试');
    }
  } catch (error) {
    ElMessage.error('修改失败：' + error.message);
  } finally {
    loading.value = false;
  }
};

// 退出登录逻辑
const logout = () => {
  userStore.logout();
  sessionStorage.clear();
  ElMessage.success('已安全退出登录');
  router.push('/');
};
</script>

<style scoped lang="less">
// 变量定义
@primary: #2563EB;
@primary-light: #60A5FA;
@success: #22C55E;
@warning: #F59E0B;
@danger: #EF4444;
@text-main: #0F172A;
@text-sec: #334155;
@text-muted: #64748B;
@bg-start: #f8fafc;
@bg-end: #f1f5f9;

.personal-container {
  min-height: 100vh;
  background: linear-gradient(180deg, @bg-start 0%, @bg-end 100%);
  position: relative;
  overflow-x: hidden;
  padding: 40px 20px;
  opacity: 0;
  transform: translateY(20px);
  transition: all 0.5s ease;

  &.is-loaded {
    opacity: 1;
    transform: translateY(0);
  }
}

.background-effects {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  z-index: 0;

  .glow-orb {
    position: absolute;
    top: -100px;
    right: -100px;
    width: 600px;
    height: 600px;
    background: radial-gradient(circle at center, rgba(59, 130, 246, 0.08), transparent 70%);
    border-radius: 50%;
  }
}

.content-wrapper {
  max-width: 1280px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

// 玻璃拟态卡片基础样式
.glass-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 24px;
  box-shadow: 0 10px 40px rgba(15, 23, 42, 0.08);
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 20px 50px rgba(15, 23, 42, 0.12);
  }
}

// 用户信息头部
.user-header-card {
  padding: 32px;
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 32px;

  .user-info {
    .username {
      font-size: 24px;
      font-weight: 700;
      color: @text-main;
      margin: 0 0 4px 0;
    }
    .user-id {
      font-size: 14px;
      color: @text-muted;
      margin: 0 0 12px 0;
      font-family: monospace;
    }
    .user-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      background: rgba(37, 99, 235, 0.1);
      color: @primary;
      border-radius: 100px;
      font-size: 13px;
      font-weight: 500;
    }
  }
}

// 主栅格布局
.main-grid {
  margin-bottom: 32px;
}

// 模块标题通用样式
.section-header {
  display: flex;
  gap: 16px;
  margin-bottom: 32px;

  .header-icon {
    font-size: 24px;
    width: 48px;
    height: 48px;
    background: #f1f5f9;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .header-text {
    h2 {
      font-size: 18px;
      font-weight: 600;
      color: @text-main;
      margin: 0;
    }
    p {
      font-size: 14px;
      color: @text-sec;
      margin: 2px 0;
    }
    .subtitle {
      font-size: 12px;
      color: @text-muted;
    }
  }
}

// 修改密码模块
.password-section {
  padding: 40px;
  height: 100%;
}

.custom-form {
  :deep(.el-form-item__label) {
    font-weight: 500;
    color: @text-sec;
    padding-bottom: 8px;
    font-size: 14px;
  }

  .custom-input {
    :deep(.el-input__wrapper) {
      height: 52px;
      border-radius: 14px;
      box-shadow: none;
      border: 1px solid #e2e8f0;
      transition: all 0.25s ease;
      background-color: #fff;

      &.is-focus {
        border-color: @primary;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
      }
    }
  }
}

// 密码强度计
.strength-meter {
  margin-top: 12px;

  .meter-bar {
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 6px;
  }

  .meter-fill {
    height: 100%;
    transition: all 0.3s ease;
  }

  .meter-label {
    font-size: 12px;
    font-weight: 500;
  }
}

.form-actions {
  margin-top: 40px;

  .submit-btn {
    width: 100%;
    height: 56px;
    border-radius: 14px;
    font-size: 16px;
    font-weight: 600;
    background: linear-gradient(135deg, @primary, #3b82f6);
    border: none;
    transition: all 0.25s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 10px 25px rgba(59, 130, 246, 0.25);
    }
    
    &:active {
      transform: translateY(0);
    }
  }
}

// 账户安全信息
.security-info-card {
  padding: 32px;
  margin-bottom: 24px;
}

.security-list {
  display: flex;
  flex-direction: column;
  gap: 20px;

  .security-item {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px;
    border-radius: 12px;
    transition: background 0.2s ease;

    &:hover {
      background: rgba(15, 23, 42, 0.02);
    }

    .item-icon {
      font-size: 20px;
      color: @text-muted;
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f8fafc;
      border-radius: 10px;
    }

    .item-content {
      display: flex;
      flex-direction: column;

      .label {
        font-size: 12px;
        color: @text-muted;
      }
      .value {
        font-size: 14px;
        font-weight: 500;
        color: @text-main;

        &.status-active {
          color: @success;
        }
      }
    }
  }
}

// 危险操作区
.danger-zone {
  padding: 32px;
  background: rgba(254, 242, 242, 0.8);
  border: 1px solid #fecaca;

  &:hover {
    background: rgba(254, 242, 242, 1);
  }

  .danger-header {
    margin-bottom: 24px;

    h3 {
      font-size: 16px;
      font-weight: 600;
      color: @danger;
      margin: 0 0 4px 0;
    }
    p {
      font-size: 13px;
      color: @text-sec;
      margin: 0;
    }
  }

  .logout-btn {
    width: 100%;
    height: 50px;
    border-radius: 12px;
    font-weight: 600;
    background: @danger;
    border: none;
    transition: all 0.25s ease;

    &:hover {
      background: #dc2626;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
    }
  }
}

// 响应式适配
@media (max-width: 992px) {
  .personal-container {
    padding: 20px 16px;
  }
  
  .main-grid {
    .el-col {
      margin-bottom: 24px;
    }
  }
}

@media (max-width: 640px) {
  .user-header-card {
    flex-direction: column;
    text-align: center;
    padding: 24px;
  }
  
  .section-header {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
}
</style>
