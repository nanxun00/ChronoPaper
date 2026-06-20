import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';

import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import './assets/main.css'
import './assets/copyable-block.css'
const app = createApp(App)
const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);
app.use(pinia)
app.use(router)
app.use(Antd)
app.use(ElementPlus)
app.mount('#app')
