// stores/user.js
import { defineStore } from 'pinia';

export const useUserStore = defineStore('user', {
  state: () => ({
    isLoggedIn: false, // 登录状态，默认为 false
    username: '', // 用户账号
    password: '', // 用户密码
    token: '' // 添加 token 属性
  }),
  actions: {
    login(username, password, token) {
      this.isLoggedIn = true;
      this.username = username;
      this.password = password;
    },
    logout() {
      this.isLoggedIn = false;
      this.username = '';
      this.password = '';
      sessionStorage.removeItem('token');
      sessionStorage.removeItem('roleid');
    }
  },
  persist: {
    key: 'user-store', // 自定义存储的键名
    storage: localStorage, // 使用 localStorage
    paths: ['isLoggedIn', 'username', 'password'] 
  }
});