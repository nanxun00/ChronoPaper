import AppLayout from '@/layouts/AppLayout.vue'

export default [
  {
    path: '/personal',
    name: 'personal',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Personal',
        component: () => import('@/views/personal/PersonalView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
    ],
  },
  {
    path: '/setting',
    name: 'setting',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Setting',
        component: () => import('@/views/settings/SettingView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
    ],
  },
]
