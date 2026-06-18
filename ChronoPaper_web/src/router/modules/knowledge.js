import AppLayout from '@/layouts/AppLayout.vue'

export default [
  {
    path: '/database',
    name: 'database',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Database',
        component: () => import('@/views/knowledge/DataBaseView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
      {
        path: ':database_id',
        name: 'databaseInfo',
        component: () => import('@/views/knowledge/DataBaseInfoView.vue'),
        meta: { keepAlive: false, requiresAuth: true },
      },
    ],
  },
]
