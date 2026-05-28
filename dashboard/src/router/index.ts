import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'overview',
    component: () => import('../views/OverviewView.vue'),
  },
  {
    path: '/sessions',
    name: 'sessions',
    component: () => import('../views/SessionsView.vue'),
  },
  {
    path: '/sessions/:id',
    name: 'session-detail',
    component: () => import('../views/SessionDetailView.vue'),
  },
  {
    path: '/ips/:hash',
    name: 'ip',
    component: () => import('../views/IpView.vue'),
  },
  {
    path: '/credentials',
    name: 'credentials',
    component: () => import('../views/CredentialsView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
