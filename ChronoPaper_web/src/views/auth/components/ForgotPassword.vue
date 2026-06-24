<script setup lang="js">
import { ref } from 'vue';
import { message } from 'ant-design-vue';

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
      // 开始倒计时
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

<template>
  <span class="forgot-title">Reset Password</span>
  <el-form class="forgot-form">
    <el-form-item class="form-item">
      <label class="form-label">账号：</label>
      <el-input v-model="forgotData.userid" placeholder="请输入您的账号" />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">绑定邮箱：</label>
      <el-input v-model="forgotData.email" placeholder="请输入绑定的邮箱" />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">验证码：</label>
      <div style="display: flex; gap: 8px; width: 100%;">
        <el-input v-model="forgotData.captcha" placeholder="6位验证码" style="flex: 1;" />
        <el-button :disabled="countdown > 0 || isSending" @click="sendCaptcha" style="width: 120px;">
          {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
        </el-button>
      </div>
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">新密码：</label>
      <el-input v-model="forgotData.password1" placeholder="请输入新密码" type="password" show-password />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">确认密码：</label>
      <el-input v-model="forgotData.password2" placeholder="请再次输入新密码" type="password" show-password />
    </el-form-item>
  </el-form>
  <div class="link-container">
    <el-link class="link" @click="switchToLogin" type="primary">
      << 返回登录 </el-link>
  </div>
  <el-button class="reset-button"
    :disabled="!forgotData.userid || !forgotData.email || !forgotData.captcha || !forgotData.password1 || !forgotData.password2"
    color="#3b82f6" size="large" @click="handleReset">
    <span class="button-text">提交重置</span>
  </el-button>
</template>

<style scoped lang='scss'>
.forgot-title {
  font-size: 30px;
  width: 100%;
  color: #152c5b;
  font-weight: bold;
}

.forgot-form {
  width: 100%;
}

.form-item {
  width: 100%;
}

.form-label {
  color: #152c5b;
  font-weight: bold;
  letter-spacing: 0.05em;
}

.link-container {
  display: flex;
  justify-content: space-between;
  width: 100%;
  margin-bottom: 16px;
}

.link {
  font-size: 12px;
}

.reset-button {
  width: 100%;
  background-color: #3b82f6;
  border-color: #3b82f6;
}

.button-text {
  padding: 0 16px;
  font-size: 16px;
}
</style>
