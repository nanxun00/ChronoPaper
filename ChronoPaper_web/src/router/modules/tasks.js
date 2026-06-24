import AppLayout from '@/layouts/AppLayout.vue'

export default [
  {
    path: '/tasks',
    name: 'tasks',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Tasks',
        component: () => import('@/views/tasks/TasksView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
    ],
  },
]
