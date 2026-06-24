<script setup lang="js">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import Login from "./components/Login.vue";
import Register from "./components/Register.vue";
import ForgotPassword from "./components/ForgotPassword.vue";

const status = ref("login");
const route = useRoute();

onMounted(() => {
  if (route.query.expired === "1") {
    message.warning("登录已过期，请重新登录");
  }
});
</script>

<template>
  <div class="page-wrapper">
    <!-- 统一沉浸式背景 -->
    <div class="background-canvas">
      <div class="grid-overlay"></div>
      <div class="aurora-effect"></div>
      <div class="glow-sphere sphere-1"></div>
      <div class="glow-sphere sphere-2"></div>
      <div class="glow-sphere sphere-3"></div>
    </div>

    <div class="content-container">
      <!-- 左侧品牌展示区 -->
      <div class="brand-section">
        <div class="brand-content">
          <div class="logo-wrapper">
            <img src="@/assets/image/logo.png" class="main-logo" alt="ChronoPaper">
          </div>
          <h1 class="brand-title">ChronoPaper</h1>
          <h2 class="brand-subtitle">AI-Powered Research Platform</h2>
          <p class="brand-description">Empowering Academic Discovery Through Artificial Intelligence</p>
        </div>
      </div>

      <!-- 右侧登录卡片区 -->
      <div class="auth-section">
        <div class="card-background-glow"></div>
        <div class="auth-card-wrapper">
          <div class="auth-card">
            <div class="auth-content">
              <Login 
                v-if="status === 'login'" 
                @update:status="status = $event" />
              <Register
                v-else-if="status === 'register'"
                @update:status="status = $event" />
              <ForgotPassword
                v-else-if="status === 'forgot'"
                @update:status="status = $event" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700;800&display=swap');

.page-wrapper {
  position: relative;
  min-height: 100vh;
  width: 100%;
  overflow-x: hidden;
  background: linear-gradient(135deg, #020617 0%, #071229 35%, #0B1220 70%, #020617 100%);
  font-family: 'Inter', 'HarmonyOS Sans', -apple-system, sans-serif;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 统一沉浸式背景 */
.background-canvas {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(to right, rgba(59, 130, 246, 0.03) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(59, 130, 246, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
  mask-image: radial-gradient(circle at center, black, transparent 90%);
}

.aurora-effect {
  position: absolute;
  inset: 0;
  background: 
    radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(168, 85, 247, 0.08) 0%, transparent 50%);
  filter: blur(100px);
  animation: aurora-drift 20s infinite alternate ease-in-out;
}

.glow-sphere {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.3;
}

.sphere-1 {
  width: 600px;
  height: 600px;
  background: rgba(59, 130, 246, 0.2);
  top: -200px;
  left: -100px;
}

.sphere-2 {
  width: 500px;
  height: 500px;
  background: rgba(139, 92, 246, 0.15);
  bottom: -100px;
  right: 5%;
}

.sphere-3 {
  width: 400px;
  height: 400px;
  background: rgba(96, 165, 250, 0.1);
  top: 40%;
  left: 30%;
}

.content-container {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  max-width: 1400px;
  padding: 0 60px;
  justify-content: space-between;
  align-items: center;
  animation: fade-in 1.2s ease-out;
}

/* 左侧品牌区 */
.brand-section {
  width: 50%;
  padding-right: 40px;
}

.logo-wrapper {
  margin-bottom: 40px;
  animation: logo-glow 4s infinite alternate;
}

.main-logo {
  width: 80px;
  height: 80px;
  object-fit: contain;
  filter: drop-shadow(0 0 20px rgba(59, 130, 246, 0.5));
}

.brand-title {
  font-size: 72px;
  font-weight: 800;
  margin: 0;
  letter-spacing: -2px;
  background: linear-gradient(90deg, #FFFFFF, #60A5FA, #8B5CF6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 40px rgba(96, 165, 250, 0.4);
  line-height: 1.1;
}

.brand-subtitle {
  font-size: 20px;
  font-weight: 500;
  color: #60a5fa;
  margin: 20px 0 12px;
  letter-spacing: 4px;
  text-transform: uppercase;
}

.brand-description {
  font-size: 16px;
  color: #94a3b8;
  max-width: 440px;
  line-height: 1.6;
  font-weight: 300;
}

/* 右侧登录卡片区 */
.auth-section {
  width: 480px;
  position: relative;
}

.card-background-glow {
  position: absolute;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.3) 0%, rgba(139, 92, 246, 0.2) 50%, transparent 70%);
  bottom: -150px;
  right: -100px;
  filter: blur(120px);
  opacity: 0.3;
  z-index: 0;
  pointer-events: none;
}

.auth-card-wrapper {
  position: relative;
  animation: card-float 0.8s ease-out;
}

.auth-card {
  position: relative;
  width: 100%;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  border-radius: 28px;
  padding: 48px;
  z-index: 2;
  overflow: hidden;
}

.auth-card::before {
  content: '';
  position: absolute;
  inset: -2px;
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.4), rgba(139, 92, 246, 0.3));
  filter: blur(30px);
  opacity: 0.4;
  z-index: -1;
}

/* 动画定义 */
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes card-float {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes aurora-drift {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(3%, 3%) scale(1.05); }
}

@keyframes logo-glow {
  from { filter: drop-shadow(0 0 15px rgba(59, 130, 246, 0.4)); }
  to { filter: drop-shadow(0 0 30px rgba(59, 130, 246, 0.7)); }
}

/* 响应式适配 */
@media (max-width: 1100px) {
  .content-container {
    flex-direction: column;
    padding: 60px 20px;
    text-align: center;
  }
  .brand-section {
    width: 100%;
    padding-right: 0;
    margin-bottom: 60px;
  }
  .brand-description {
    margin: 0 auto;
  }
  .auth-section {
    width: 100%;
    max-width: 480px;
  }
}
</style>
