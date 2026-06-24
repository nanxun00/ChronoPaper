    <template>
    <div class="auth-header">
        <h1 class="auth-title">欢迎回来</h1>
        <p class="auth-subtitle">登录 ChronoPaper 开启智能科研之旅</p>
    </div>
    
    <el-form class="login-form">
        <el-form-item class="form-item">
            <el-input 
                v-model="loginData.account" 
                placeholder="账号" 
                class="custom-input">
                <template #prefix>
                    <user-outlined />
                </template>
            </el-input>
        </el-form-item>
        <el-form-item class="form-item">
            <el-input 
                v-model="loginData.password" 
                type="password" 
                placeholder="密码" 
                show-password
                class="custom-input">
                <template #prefix>
                    <lock-outlined />
                </template>
            </el-input>
        </el-form-item>
    </el-form>

    <div class="link-container">
        <el-link class="custom-link" @click="switchToRegister">注册账号</el-link>
        <el-link class="custom-link" @click="switchToForgot">忘记密码？</el-link>
    </div>

    <el-button 
        class="login-button" 
        :disabled="!loginData.account || !loginData.password" 
        @click="login">
        <span class="button-text">登录</span>
    </el-button>
</template>

<script setup lang="js">
import { ref } from 'vue';
import { useUserStore } from '@/stores'
import { useRouter, useRoute } from "vue-router";
import { message } from 'ant-design-vue';
import { UserOutlined, LockOutlined } from '@ant-design/icons-vue';

const userStore = useUserStore();
const router = useRouter();
const route = useRoute();
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

<style scoped lang='scss'>
.auth-header {
    width: 100%;
    margin-bottom: 32px;
}

.auth-title {
    font-size: 32px;
    font-weight: 700;
    color: #ffffff;
    margin: 0 0 8px;
    letter-spacing: -0.5px;
}

.auth-subtitle {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
    margin: 0;
}

.login-form {
    width: 100%;
    margin-bottom: 20px;
}

.form-item {
    margin-bottom: 20px;
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
        font-size: 16px;
        &::placeholder {
            color: rgba(255, 255, 255, 0.3);
        }
    }

    .el-input__prefix-inner {
        font-size: 20px;
        color: rgba(255, 255, 255, 0.4);
        margin-right: 8px;
    }
}

.link-container {
    display: flex;
    justify-content: space-between;
    width: 100%;
    margin-bottom: 32px;
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

.login-button {
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