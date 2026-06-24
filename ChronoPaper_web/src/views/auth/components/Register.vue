<script setup lang="js">
import { ref } from 'vue';
// import useChatStore from '@/stores/chat';
// import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
// import { postRegister } from '@/services/user';

// const chatStore = useChatStore();
// const router = useRouter();
import { message } from 'ant-design-vue';
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

  // 立即开始倒计时
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
      // 如果后端报错（如邮箱已注册），重置倒计时
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

const imageUrl = ref('');
const beforeAvatarUpload = (rawFile) => {
  // 文件类型及文件大小校验
  // if (rawFile.type !== 'image/jpeg') {
  //   ElMessage.error('Avatar picture must be JPG format!');
  //   return false;
  // } else if (rawFile.size / 1024 / 1024 > 2) {
  //   ElMessage.error('Avatar picture size can not exceed 2MB!');
  //   return false;
  // }
  return true;
};

const upload = (uploadFile) => {
  imageUrl.value = URL.createObjectURL(uploadFile.raw);
  console.log(imageUrl.value);
};

const status = ref('');
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
      console.log(data)
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

<template>
  <span class="sign-up-title">Sign Up</span>
  <el-form class="register-form">
    <el-form-item class="form-item">
      <label class="form-label">用户名：</label>
      <el-input v-model="registerData.account" placeholder="请输入用户名" />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">账号：</label>
      <el-input v-model="registerData.username" placeholder="请输入账号" />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">设置密码：</label>
      <el-input v-model="registerData.password1" placeholder="请输入登录密码" type="password" show-password />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">确认密码：</label>
      <el-input v-model="registerData.password2" placeholder="请再次输入登录密码" type="password" show-password />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">邮箱：</label>
      <el-input v-model="registerData.email" placeholder="请输入邮箱地址" />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">验证码：</label>
      <div style="display: flex; gap: 8px; width: 100%;">
        <el-input v-model="registerData.captcha" placeholder="6位验证码" style="flex: 1;" />
        <el-button :disabled="countdown > 0 || isSending" @click="sendCaptcha" style="width: 120px;">
          {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
        </el-button>
      </div>
    </el-form-item>
  </el-form>
  <div class="link-container">
    <el-link class="link" @click="switchToLogin" type="primary">
      << 返回登录 </el-link>
        <span></span>
  </div>
  <el-button class="register-button"
    :disabled="!registerData.username || !registerData.account || !registerData.password1 || !registerData.password2 || !registerData.email || !registerData.captcha"
    color="#3b82f6" size="large" @click="register">
    <span class="button-text">注册</span>
  </el-button>
</template>

<style scoped lang='scss'>
.sign-up-title {
  font-size: 30px;
  width: 100%;
  color: #152c5b;
  font-weight: bold;
}

.register-form {
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

.register-button {
  width: 100%;
  background-color: #3b82f6;
  border-color: #3b82f6;
}

.button-text {
  padding: 0 16px;
  font-size: 16px;
}
</style>