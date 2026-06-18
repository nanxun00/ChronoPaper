import AppLayout from '@/layouts/AppLayout.vue'

export default [
  {
    path: '/translate',
    redirect: '/tools/translate',
  },
  {
    path: '/smartbi',
    redirect: '/tools/smartbi',
  },
  {
    path: '/tools',
    name: 'tools',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'ToolsView',
        component: () => import('@/views/tools/ToolsView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
      {
        path: 'translate',
        name: 'Translate',
        component: () => import('@/views/translate/TranslateView.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
      {
        path: 'smartbi',
        name: 'Smartbi',
        component: () => import('@/views/smartbi/SmartBI.vue'),
        meta: { keepAlive: true, requiresAuth: true },
      },
      {
        path: 'text-chunking',
        name: 'TextChunking',
        component: () => import('@/components/tools/TextChunkingComponent.vue'),
        meta: { requiresAuth: true },
      },
      {
        path: 'pdf2txt',
        name: 'PDF_to_TXT',
        component: () => import('@/components/tools/ConvertToTxtComponent.vue'),
        meta: { requiresAuth: true },
      },
    ],
  },
]
