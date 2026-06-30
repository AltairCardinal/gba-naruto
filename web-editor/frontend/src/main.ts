import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { useAuthStore } from './stores/authStore'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dialogues' },
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
    { path: '/dialogues', component: () => import('./views/DialogueListView.vue') },
    { path: '/dialogues/:key', component: () => import('./views/DialogueEditorView.vue') },
    { path: '/build', component: () => import('./views/BuildView.vue') },
    { path: '/map', component: () => import('./views/MapEditorView.vue') },
    { path: '/battle-configs', component: () => import('./views/BattleConfigView.vue') },
    { path: '/units', component: () => import('./views/UnitListView.vue') },
    { path: '/units/place', component: () => import('./views/UnitPlacementView.vue') },
    { path: '/skills', component: () => import('./views/SkillListView.vue') },
    { path: '/story-beats', component: () => import('./views/StoryBeatListView.vue') },
    { path: '/audio', component: () => import('./views/AudioView.vue') },
    { path: '/rom-explorer', component: () => import('./views/RomExplorerView.vue') },
    {
      path: '/users',
      component: () => import('./views/UserManagementView.vue'),
      meta: { adminOnly: true },
    },
  ],
})

// Route guards.
// - Public routes (login) → accessible without auth, redirect elsewhere if already logged in.
// - Admin-only routes (users) → require admin role.
// - Everything else → require login.
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta?.public) {
    // /login: if already logged in, bounce to home
    if (auth.isLoggedIn && to.path === '/login') return '/dialogues'
    return true
  }
  if (!auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta?.adminOnly && !auth.isAdmin) {
    return { path: '/dialogues' }  // bounce to home with a 403-like redirect
  }
  return true
})

const pinia = createPinia()
const app = createApp(App)

// Pinia must be installed before the router is set up so the auth store
// inside the beforeEach hook can resolve. (Vue's createApp order is OK
// since use(pinia) is called before the router is registered.)
app.use(pinia)
app.use(router)
app.config.errorHandler = (err, _instance, info) => {
  console.error(err, info)
}
app.mount('#app')
