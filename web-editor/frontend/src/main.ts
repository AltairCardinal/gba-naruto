import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dialogues' },
    { path: '/dialogues', component: () => import('./views/DialogueListView.vue') },
    { path: '/dialogues/:key', component: () => import('./views/DialogueEditorView.vue') },
    { path: '/build', component: () => import('./views/BuildView.vue') },
    { path: '/map', component: () => import('./views/MapEditorView.vue') },
    { path: '/battle-configs', component: () => import('./views/BattleConfigView.vue') },
    { path: '/units', component: () => import('./views/UnitListView.vue') },
    { path: '/skills', component: () => import('./views/SkillListView.vue') },
    { path: '/story-beats', component: () => import('./views/StoryBeatListView.vue') },
    { path: '/audio', component: () => import('./views/AudioView.vue') },
    { path: '/users', component: () => import('./views/UserListView.vue') }
  ]
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.mount('#app')