<template>
  <div class="auth-header">
    <h1 class="auth-title">创建账号</h1>
    <p class="auth-subtitle">加入 ChronoPaper 开启智能科研之旅</p>
  </div>

  <el-form class="register-form">
    <el-form-item class="form-item">
      <el-input v-model="registerData.account" placeholder="用户名" class="custom-input">
        <template #prefix><user-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <el-input v-model="registerData.username" placeholder="账号" class="custom-input">
        <template #prefix><idcard-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <el-input v-model="registerData.password1" placeholder="设置密码" type="password" show-password class="custom-input">
        <template #prefix><lock-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <el-input v-model="registerData.password2" placeholder="确认密码" type="password" show-password class="custom-input">
        <template #prefix><check-circle-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <el-input v-model="registerData.email" placeholder="邮箱" class="custom-input">
        <template #prefix><mail-outlined /></template>
      </el-input>
    </el-form-item>
    <el-form-item class="form-item">
      <div class="captcha-wrapper">
        <el-input v-model="registerData.captcha" placeholder="验证码" class="custom-input captcha-input">
          <template #prefix><key-outlined /></template>
        </el-input>
        <el-button class="captcha-button" :disabled="countdown > 0 || isSending" @click="sendCaptcha">
          {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
        </el-button>
      </div>
    </el-form-item>
  </el-form>

  <div class="link-container">
    <el-link class="custom-link" @click="switchToLogin">
      &larr; 返回登录
    </el-link>
  </div>

  <el-button 
    class="register-button"
    :disabled="!registerData.username || !registerData.account || !registerData.password1 || !registerData.password2 || !registerData.email || !registerData.captcha"
    @click="register">
    <span class="button-text">立即注册</span>
  </el-button>
</template>

<script setup lang="js">
import { ref } from 'vue';
import { message } from 'ant-design-vue';
import { UserOutlined, LockOutlined, IdcardOutlined, MailOutlined, KeyOutlined, CheckCircleOutlined } from '@ant-design/icons-vue';

const registerData = ref({
  account: '',
  username: '',
  password1: '',
  password2: '',
  email: '',
  captcha: '',
});

const countdown = ref(0);
const isSending = ref(false);

const sendCaptcha = async () => {
  if (!registerData.value.email) {
    message.error('请先输入邮箱');
    return;
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(registerData.value.email)) {
    message.error('请输入有效的邮箱地址');
    return;
  }

  countdown.value = 60;
  const timer = setInterval(() => {
    countdown.value--;
    if (countdown.value <= 0) {
      clearInterval(timer);
    }
  }, 1000);

  isSending.value = true;
  try {
    const response = await fetch('/api/register/captcha', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: registerData.value.email })
    });
    
    if (response.ok) {
      message.success('验证码发送请求已提交，请注意查收');
    } else {
      const data = await response.json();
      message.error(data.detail || '验证码发送失败');
      countdown.value = 0;
      clearInterval(timer);
    }
  } catch (error) {
    message.error('网络请求失败');
    countdown.value = 0;
    clearInterval(timer);
  } finally {
    isSending.value = false;
  }
};

const register = async () => {
  try {
    if (registerData.value.password1 !== registerData.value.password2) {
      message.error('两次输入的密码不一致');
      return;
    }
    const response = await fetch('/api/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: registerData.value.account,
        userid: registerData.value.username,
        password: registerData.value.password1,
        email: registerData.value.email,
        captcha: registerData.value.captcha
      })
    });
    if (response.ok) {
      const data = await response.json();
      message.success(data.message || '注册成功');
      switchToLogin();
    } else {
      const data = await response.json();
      message.error(data.detail || '注册失败');
    }
  } catch (error) {
    message.error('注册请求失败');
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

.register-form {
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

.register-button {
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