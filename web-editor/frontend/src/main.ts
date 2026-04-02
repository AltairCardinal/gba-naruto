import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dialogues' },
    { path: '/dialogues', component: () => import('./views/DialogueListView.vue') },
    { path: '/dialogues/:key', component: () => import('./views/DialogueEditorView.vue') }
  ]
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.mount('#app')