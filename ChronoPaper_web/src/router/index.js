import { createRouter, createWebHistory } from 'vue-router'
import { resolvePostLoginRedirect } from '@/composables/useAuth'

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
    const redirect = to.fullPath === '/' ? undefined : to.fullPath
    return redirect
      ? { path: '/', query: { redirect } }
      : { path: '/' }
  }

  if (to.path === '/' && token) {
    const rawRedirect = typeof to.query.redirect === 'string' ? to.query.redirect : ''
    return resolvePostLoginRedirect(rawRedirect)
  }

  return true
})

export default router
