<script setup lang="js">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import Login from "./components/Login.vue";
import Register from "./components/Register.vue";

const status = ref("login");
const route = useRoute();

onMounted(() => {
  if (route.query.expired === "1") {
    message.warning("登录已过期，请重新登录");
  }
});
</script>

<template>
  <div class="container">
    <div class="image-container">
      <img src="@/assets/image/logo.png" class="login-image" alt="ChronoPaper">
    </div>
    <div class="form-container">
      <div class="form-content">
        <div class="brand-row">
          <img src="@/assets/image/logo.png" class="login-brand" alt="">
          <h1 class="brand-title">ChronoPaper</h1>
        </div>
        <Login 
      v-if="status === 'login'" 
      @update:status="status = $event" />
    <Register
      v-else-if="status === 'register'"
      @update:status="status = $event" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  display: flex;
  height: 100vh;
  width: 100%;
  background-color: #0a0e17;
  justify-content: space-between;
  align-items: center;
}

.image-container {
  height: 100%;
  width: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at center, #1a2744 0%, #0a0e17 70%);
}

.login-image {
  width: min(280px, 55%);
  height: auto;
  object-fit: contain;
  border-radius: 16px;
}

.form-container {
  height: 80%;
  width: 35%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(255, 255, 255, 0.92);
  border-radius: 30px;
  margin-right: 10%;
}

.form-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 500px;
  width: 75%;
  justify-content: space-between;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.login-brand {
  width: 48px;
  height: 48px;
  object-fit: contain;
  border-radius: 10px;
}

.brand-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  color: #0c2c69;
  letter-spacing: 0.5px;
}
</style>
