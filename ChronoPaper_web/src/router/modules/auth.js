import AppLayout from '@/layouts/AppLayout.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'

export default [
  {
    path: '/',
    name: 'home',
    component: BlankLayout,
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('@/views/auth/LoginView.vue'),
        meta: { keepAlive: true },
      },
    ],
  },
]
