import AppLayout from '@/layouts/AppLayout.vue'

export default [
  {
    path: '/graph',
    name: 'graph',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Graph',
        component: () => import('@/views/graph/GraphView.vue'),
        meta: { keepAlive: false, requiresAuth: true },
      },
    ],
  },
]
