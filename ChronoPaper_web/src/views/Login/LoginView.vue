<script setup lang="js">
import { ref } from "vue";
import Login from "./components/Login.vue";
import Register from "./components/Register.vue";

const status = ref("login");
</script>

<template>
  <div class="container">
    <div class="image-container">
      <img src="@/assets/image/logo.png" class="login-image" alt="ChronoPaper">
    </div>
    <div class="form-container">
      <div class="form-content">
        <img src="@/assets/image/logo.png" class="login-brand" alt="ChronoPaper">
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
  width: min(420px, 80%);
  height: auto;
  object-fit: contain;
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

.login-brand {
  width: min(240px, 100%);
  height: auto;
  object-fit: contain;
  margin-bottom: 8px;
}
</style>
