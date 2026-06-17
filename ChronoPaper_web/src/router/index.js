import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/user'; // 引入用户状态管理
import AppLayout from '@/layouts/AppLayout.vue';
import BlankLayout from '@/layouts/BlankLayout.vue';

// 配置路由
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: BlankLayout,
      children: [
        {
          path: '',
          name: 'Home',
          component: () => import('../views/Login/LoginView.vue'),
          meta: { keepAlive: true }
        }
      ]
    },
    {
      path: '/chat',
      name: 'chat',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Chat',
          component: () => import('../views/ChatView.vue'),
          meta: { keepAlive: true, requiresAuth: true } 
        }
      ]
    },
    {
      path: '/literature',
      name: 'literature',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Literature',
          component: () => import('../views/LiteratureView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        }
      ]
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Tasks',
          component: () => import('../views/TasksView.vue'),
          meta: { keepAlive: true, requiresAuth: true }
        }
      ]
    },
    {
      path: '/graph',
      name: 'graph',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Graph',
          component: () => import('../views/GraphView.vue'),
          meta: { keepAlive: false, requiresAuth: true } 
        }
      ]
    },
    {
      path: '/database',
      name: 'database',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Database',
          component: () => import('../views/DataBaseView.vue'),
          meta: { keepAlive: true, requiresAuth: true } 
        },
        {
          path: ':database_id',
          name: 'databaseInfo',
          component: () => import('../views/DataBaseInfoView.vue'),
          meta: { keepAlive: false, requiresAuth: true } 
        }
      ]
    },
    {
      path: '/personal',
      name: 'personal',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Personal',
          component: () => import('../views/PersonalView.vue'),
          meta: { keepAlive: true, requiresAuth: true } 
        }
      ]
    },
    {
      path: '/smartbi',
      name: 'smartbi',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Smartbi',
          component: () => import('../views/SmartBI.vue'),
          meta: { keepAlive: true, requiresAuth: true } 
        }
      ]
    },
    {
      path: '/setting',
      name: 'setting',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'Setting',
          component: () => import('../views/SettingView.vue'),
          meta: { keepAlive: true, requiresAuth: true } 
        }
      ]
    },
    {
      path: '/tools',
      name: 'tools',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'ToolsView',
          component: () => import('../views/ToolsView.vue'),
          meta: { keepAlive: true, requiresAuth: true } 
        },
        {
          path: 'text-chunking',
          name: 'TextChunking',
          component: () => import('../components/TextChunkingComponent.vue'),
          meta: { requiresAuth: true } 
        },
        {
          path: 'pdf2txt',
          name: 'PDF_to_TXT',
          component: () => import('../components/ConvertToTxtComponent.vue'),
          meta: { requiresAuth: true } 
        },
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('../views/EmptyView.vue')
    },
  ]
});

// 添加全局导航守卫
// router.beforeEach((to, from, next) => {
//   const userStore = useUserStore(); 
//   const requiresAuth = to.meta.requiresAuth;

//   if (requiresAuth && !userStore.isLoggedIn) {
//     next({ name: 'Home' }); 
//   } else {
//     // 否则允许跳转
//     next();
//   }
// });

export default router;