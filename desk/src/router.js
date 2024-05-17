import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/pages/Home.vue'),
  },
  {
    // /desk/User
		// /desk/:doctype?config=id
    path: '/:doctype', 
    name: 'List',
    component: () => import('@/pages/List.vue'),
  },
]

let router = createRouter({
  history: createWebHistory('/desk'),
  routes,
})

export default router
