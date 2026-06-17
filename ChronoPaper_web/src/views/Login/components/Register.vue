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
});

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
        password: registerData.value.password1
      })
    });
    if (response.ok) {
      const data = await response.json();
      console.log(data)
      if (data.status_code == 200) {
        message.success(data.detail);
        switchToLogin();
      } else {
        message.error(data.detail || '注册失败');
      }
    } else {
      message.error('注册失败');
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
      <el-input v-model="registerData.password1" placeholder="请输入登录密码" />
    </el-form-item>
    <el-form-item class="form-item">
      <label class="form-label">确认密码：</label>
      <el-input v-model="registerData.password2" placeholder="请再次输入登录密码" />
    </el-form-item>
  </el-form>
  <div class="link-container">
    <el-link class="link" @click="switchToLogin" type="primary">
      << 返回登录 </el-link>
        <span></span>
  </div>
  <el-button class="register-button"
    :disabled="!registerData.username || !registerData.account || !registerData.password1 || !registerData.password2"
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