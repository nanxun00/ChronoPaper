<script setup lang="js">
import { ref } from 'vue';
import { useUserStore } from '@/stores'
import { useRouter, useRoute } from "vue-router";
import { message } from 'ant-design-vue';
// import { ElMessage } from 'element-plus';
const userStore = useUserStore();
const router = useRouter();
const route = useRoute();
const status = ref('');
const loginData = ref({
    account: '',
    password: ''
});

const login = async () => {
    try {
        const formData = new URLSearchParams();
        formData.append("username", loginData.value.account);
        formData.append("password", loginData.value.password);
        formData.append("grant_type", "password");

        const response = await fetch('/api/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData.toString()
        });

        if (response.ok) {
            const data = await response.json();
            console.log(data);
            const token = data.Token.access_token;
            const roleid = data.roleid; 
            sessionStorage.setItem('token', token);
            sessionStorage.setItem('roleid', roleid); 
            if (data.Token.access_token) {
                userStore.login(loginData.value.account, loginData.value.password);
                message.success("登录成功");
                const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/chat';
                router.push(redirect);
            } else {
                message.error(data.detail || '登录失败');
            }
        } else {
            message.error('登录失败');
        }
    } catch (error) {
        console.error('登录请求失败', error);
        message.error('登录请求失败');
    }
};
const emit = defineEmits(['update:status']);
const switchToRegister = () => {
    emit('update:status', 'register');
};
const switchToForgot = () => {
    emit('update:status', 'forgot');
};
</script>

<template>
    <span class="sign-in-title">Sign In</span>
    <el-form class="login-form">
        <el-form-item class="form-item">
            <label class="form-label">账号：</label>
            <el-input v-model="loginData.account" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item class="form-item">
            <label class="form-label">密码：</label>
            <el-input v-model="loginData.password" type="password" placeholder="请输入登录密码" />
        </el-form-item>
    </el-form>
    <div class="link-container">
        <el-link class="link" @click="switchToRegister">注册账号</el-link>
        <el-link class="link" @click="switchToForgot">忘记密码？</el-link>
    </div>
    <el-button class="login-button" :disabled="!loginData.account || !loginData.password" color="#3b82f6" size="large"
        @click="login">
        <span class="button-text">登录</span>
    </el-button>
</template>

<style scoped lang='scss'>
.sign-in-title {
    font-size: 30px;
    width: 100%;
    color: #152c5b;
    font-weight: bold;
}

.login-form {
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

.login-button {
    width: 100%;
    background-color: #3b82f6;
    border-color: #3b82f6;
}

.button-text {
    padding: 0 16px;
    font-size: 16px;
}

.el-input {
    height: 40px;
}
</style>