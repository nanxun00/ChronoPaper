import AppLayout from '@/layouts/AppLayout.vue'

export default [
  {
    path: '/literature',
    name: 'literature',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Literature',
        component: () => import('@/views/literature/LiteratureView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
    ],
  },
]
