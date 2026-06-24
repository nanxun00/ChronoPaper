<template>
  <div class="auth-header">
    <h1 class="auth-title">重置密码</h1>
    <p class="auth-subtitle">通过验证邮箱找回您的 ChronoPaper 账号</p>
  </div>

  <el-form class="forgot-form">
    <el-form-item class="form-item">
      <el-input v-model="forgotData.userid" placeholder="账号" class="custom-input">
        <template #prefix><idcard-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <el-input v-model="forgotData.email" placeholder="绑定邮箱" class="custom-input">
        <template #prefix><mail-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <div class="captcha-wrapper">
        <el-input v-model="forgotData.captcha" placeholder="验证码" class="custom-input captcha-input">
          <template #prefix><key-outlined /></template>
        </el-input>
        <el-button class="captcha-button" :disabled="countdown > 0 || isSending" @click="sendCaptcha">
          {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
        </el-button>
      </div>
    </el-form-item>
    <el-form-item class="form-item">
      <el-input v-model="forgotData.password1" placeholder="新密码" type="password" show-password class="custom-input">
        <template #prefix><lock-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <el-input v-model="forgotData.password2" placeholder="确认新密码" type="password" show-password class="custom-input">
        <template #prefix><check-circle-outlined /></template>
      </el-input>
    </el-form-item>
  </el-form>

  <div class="link-container">
    <el-link class="custom-link" @click="switchToLogin">
      &larr; 返回登录
    </el-link>
  </div>

  <el-button 
    class="reset-button"
    :disabled="!forgotData.userid || !forgotData.email || !forgotData.captcha || !forgotData.password1 || !forgotData.password2"
    @click="handleReset">
    <span class="button-text">提交重置</span>
  </el-button>
</template>

<script setup lang="js">
import { ref } from 'vue';
import { message } from 'ant-design-vue';
import { LockOutlined, IdcardOutlined, MailOutlined, KeyOutlined, CheckCircleOutlined } from '@ant-design/icons-vue';

const forgotData = ref({
  userid: '',
  email: '',
  captcha: '',
  password1: '',
  password2: '',
});

const countdown = ref(0);
const isSending = ref(false);

const sendCaptcha = async () => {
  if (!forgotData.value.userid) {
    message.error('请先输入账号');
    return;
  }
  if (!forgotData.value.email) {
    message.error('请先输入邮箱');
    return;
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(forgotData.value.email)) {
    message.error('请输入有效的邮箱地址');
    return;
  }

  isSending.value = true;
  try {
    const response = await fetch('/api/forgot-password/captcha', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        userid: forgotData.value.userid,
        email: forgotData.value.email 
      })
    });
    
    if (response.ok) {
      message.success('验证码已发送至您的邮箱');
      countdown.value = 60;
      const timer = setInterval(() => {
        countdown.value--;
        if (countdown.value <= 0) {
          clearInterval(timer);
        }
      }, 1000);
    } else {
      const data = await response.json();
      message.error(data.detail || '验证码发送失败');
    }
  } catch (error) {
    message.error('网络请求失败');
  } finally {
    isSending.value = false;
  }
};

const handleReset = async () => {
  if (forgotData.value.password1 !== forgotData.value.password2) {
    message.error('两次输入的密码不一致');
    return;
  }

  try {
    const response = await fetch('/api/forgot-password/reset', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        userid: forgotData.value.userid,
        email: forgotData.value.email,
        captcha: forgotData.value.captcha,
        new_password: forgotData.value.password1,
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      message.success(data.message || '密码重置成功');
      switchToLogin();
    } else {
      const data = await response.json();
      message.error(data.detail || '重置失败');
    }
  } catch (error) {
    message.error('请求失败，请检查网络');
  }
};

const emit = defineEmits(['update:status']);
const switchToLogin = () => {
  emit('update:status', 'login');
};
</script>

<style scoped lang='scss'>
.auth-header {
  width: 100%;
  margin-bottom: 24px;
}

.auth-title {
  font-size: 28px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 6px;
  letter-spacing: -0.5px;
}

.auth-subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}

.forgot-form {
  width: 100%;
  margin-bottom: 16px;
}

.form-item {
  margin-bottom: 16px;
}

.captcha-wrapper {
  display: flex;
  gap: 12px;
  width: 100%;
}

.captcha-input {
  flex: 1;
}

.captcha-button {
  height: 56px;
  width: 120px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #60A5FA;
  font-weight: 500;
  transition: all 0.3s ease;

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: #60A5FA;
  }
}

:deep(.custom-input) {
  .el-input__wrapper {
    background-color: rgba(255, 255, 255, 0.05) !important;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08) inset !important;
    border-radius: 14px;
    height: 56px;
    padding: 0 16px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    
    &.is-focus {
      background-color: rgba(255, 255, 255, 0.08) !important;
      box-shadow: 0 0 0 1px #60A5FA inset, 0 0 20px rgba(96, 165, 250, 0.3) !important;
    }
  }

  .el-input__inner {
    color: #ffffff !important;
    font-size: 15px;
    &::placeholder {
      color: rgba(255, 255, 255, 0.3);
    }
  }

  .el-input__prefix-inner {
    font-size: 18px;
    color: rgba(255, 255, 255, 0.4);
    margin-right: 8px;
  }
}

.link-container {
  display: flex;
  justify-content: flex-start;
  width: 100%;
  margin-bottom: 24px;
}

.custom-link {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5) !important;
  transition: all 0.3s ease;
  
  &:hover {
    color: #60A5FA !important;
    text-decoration: none;
  }
}

.reset-button {
  width: 100%;
  height: 56px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, #3B82F6, #6366F1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  
  &:not(:disabled):hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 30px rgba(99, 102, 241, 0.4);
    opacity: 0.9;
  }
  
  &:disabled {
    opacity: 0.5;
    background: rgba(255, 255, 255, 0.1);
  }
}

.button-text {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
}
</style>
