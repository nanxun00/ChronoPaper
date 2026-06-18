import AppLayout from '@/layouts/AppLayout.vue'

export default [
  {
    path: '/chat',
    name: 'chat',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Chat',
        component: () => import('@/views/chat/ChatView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
    ],
  },
]
