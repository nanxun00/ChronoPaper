<template>
  <div class="personal-view  layout-container">
    <HeaderComponent title="个人中心" description="这里提供了修改密码和退出登录的功能。">
    </HeaderComponent>
    <div class="revise">
      <p class="title">修改密码</p>
      <div class="mima">
        <a-form :model="formState" name="basic" autocomplete="off" :label-col="labelCol" @finish="onFinish"
          @finishFailed="onFinishFailed">
          <a-form-item name="userid" :rules="[{ required: true, message: '请输入当前账号！' }]">
            <label class="form-label">您的账号：</label>
            <a-input size="large" placeholder="请输入当前账号" v-model:value="formState.userid" />
          </a-form-item>
          <a-form-item name="oldpassword" :rules="[{ required: true, message: '请输入当前密码！' }]">
            <label class="form-label">当前密码：</label>
            <a-input-password size="large" placeholder="请输入当前密码" v-model:value="formState.oldpassword" />
          </a-form-item>

          <a-form-item name="password1" :rules="[{ required: true, message: '请输入新密码！' }]">
            <label class="form-label">新密码：</label>
            <a-input-password size="large" placeholder="请输入新密码" v-model:value="formState.password1" />
          </a-form-item>
          <a-form-item name="password2" :rules="[{ required: true, message: '请再次输入新密码！' }]">
            <label class="form-label">确认新密码：</label>
            <a-input-password size="large" placeholder="请再次输入新密码" v-model:value="formState.password2" />
          </a-form-item>

          <div class="btn">
            <a-form-item>
              <a-button block type="primary" size="large" html-type="submit">确认修改</a-button>
            </a-form-item>
          </div>

        </a-form>
      </div>

    </div>
    <div class="logout">
      <div class="left">
        <p class="title1">退出登录</p>
        <p class="intro">退出当前账号，返回登录页面</p>
      </div>
      <div class="right">
        <a-button type="primary" danger size="large" block @click="logout">退出登录</a-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import HeaderComponent from '@/components/common/HeaderComponent.vue';
import { useUserStore } from '@/stores'
import { message } from 'ant-design-vue';

const router = useRouter();
const userStore = useUserStore(); // 使用用户状态管理

const formState = reactive({
  userid: '',
  oldpassword: '',
  password1: '',
  password2: '',
});

const labelCol = {
  style: {
    width: '300px',
  },
};

// 修改密码的逻辑
const onFinish = async () => {
  try {
    if (formState.password1 !== formState.password2) {
      message.error('两次输入的新密码不一致！');
      return;
    }
    // 构造请求数据
    const requestData = {
      userid: formState.userid,
      password: formState.oldpassword,
      new_password: formState.password1,
    };

    // 调用修改密码的 API
    const response = await fetch('/api/change-password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
    });

    // 处理响应
    if (response.ok) {
      const data = await response.json();
      if (data.status_code === 200) {
        // 清空表单
        formState.userid = '';
        formState.oldpassword = '';
        formState.password1 = '';
        formState.password2 = '';
        
        // 密码修改成功后退出登录
        // 展示密码修改成功的提示
        message.success(data.detail, 3).then(() => {
          // 提示框消失后退出登录
          logout();
        });
      } else {
        message.error(data.detail || '密码修改失败！');
      }
    } else {
      message.error('密码修改失败：' + response.statusText);
    }
  } catch (error) {
    message.error('密码修改失败：' + error.message);
  }
};

const onFinishFailed = () => {
  message.error('请填写完整信息！');
};

// 退出登录的逻辑
const logout = () => {
  userStore.logout();
  sessionStorage.clear();
  message.success('已退出登录');
  router.push('/'); 
};
</script>

<style scoped lang="less">
.personal-view {
  padding: 0;
}

.revise {
  width: 55%;
  height: 510px;
  background-color: #fff;
  border-radius: 15px;
  margin: 20px;
  border: 1px solid var(--gray-300);
}

.logout {
  width: 55%;
  height: 180px;
  background-color: #fff;
  margin: 15px;
  border-radius: 20px;
  border: 1px solid var(--gray-300);
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
}

.title {
  font-size: 20px;
  margin: 20px;
  color: black;
  font-weight: 500;
}

.left {
  width: 200px;
  height: 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.right {
  width: 140px;
  margin-right: 20px
}

.title1 {
  font-size: 20px;
  color: black;
  font-weight: 500;
}

.intro {
  color: #818181;
}

.mima {
  width: 90%;
  margin-left: 20px;
}

.form-label {
  color: black;
  font-size: 15px;
  letter-spacing: 0.05em;
  margin-top: 20px;
  margin-bottom: 10px;
}

.btn {
  margin-top: 50px;
}
</style>
