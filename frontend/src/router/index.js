import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import ModelView from '../views/ModelView.vue'
import ConnectionsView from '../views/ConnectionsView.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: DashboardView, meta: { title: '检测面板' } },
  { path: '/model', name: 'model', component: ModelView, meta: { title: '模型评估' } },
  { path: '/connections', name: 'connections', component: ConnectionsView, meta: { title: '连接记录' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title || ''} - 入侵检测系统`
})

export default router
