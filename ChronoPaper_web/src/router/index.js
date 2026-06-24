import { createRouter, createWebHistory } from 'vue-router'

import authRoutes from './modules/auth'
import chatRoutes from './modules/chat'
import literatureRoutes from './modules/literature'
import tasksRoutes from './modules/tasks'
import settingsRoutes from './modules/settings'
import knowledgeRoutes from './modules/knowledge'
import graphRoutes from './modules/graph'
import toolsRoutes from './modules/tools'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    ...authRoutes,
    ...chatRoutes,
    ...literatureRoutes,
    ...tasksRoutes,
    ...settingsRoutes,
    ...knowledgeRoutes,
    ...graphRoutes,
    ...toolsRoutes,
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/error/EmptyView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const token = sessionStorage.getItem('token')
  const needsAuth = to.matched.some((record) => record.meta.requiresAuth)

  if (needsAuth && !token) {
    return {
      path: '/',
      query: { redirect: to.fullPath },
    }
  }
  return true
})

export default router
