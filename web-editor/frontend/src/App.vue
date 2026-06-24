<template>
  <div id="app">
    <header>
      <div class="header-top">
        <h1>木叶战记续作 - 编辑器</h1>
        <div class="user-info" v-if="auth.isLoggedIn">
          <span class="user-name">
            <span class="role-tag" :class="auth.role">{{ auth.role }}</span>
            {{ auth.username }}
          </span>
          <router-link v-if="auth.isAdmin" to="/users" class="admin-link">用户管理</router-link>
          <button class="logout-btn" @click="onLogout">退出</button>
        </div>
        <div class="user-info" v-else>
          <router-link to="/login" class="login-link">登录</router-link>
        </div>
      </div>
      <nav v-if="auth.isLoggedIn">
        <router-link to="/story-beats">剧情节拍</router-link>
        <router-link to="/units">单位配置</router-link>
        <router-link to="/skills">技能配置</router-link>
        <router-link to="/dialogues">对话管理</router-link>
        <router-link to="/battle-configs">战斗配置</router-link>
        <router-link to="/units/place">角色放置</router-link>
        <router-link to="/map">地图编辑</router-link>
        <router-link to="/audio">音频管理</router-link>
        <router-link to="/build" class="nav-build">构建</router-link>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/authStore'

const auth = useAuthStore()
const router = useRouter()

onMounted(async () => {
  // Refresh /me on app boot so the navbar / perms are accurate after
  // a hard reload (token may still be valid but localStorage perms
  // could be stale or missing).
  if (auth.isLoggedIn) {
    try {
      await auth.fetchMe()
    } catch {
      // Token rejected — clear so the route guard sends us to /login.
      auth.logout()
    }
  }
})

function onLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
}

#app {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

header {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

header h1 {
  font-size: 24px;
  color: #333;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #555;
}

.user-name {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #333;
  font-weight: 500;
}

.role-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}
.role-tag.admin { background: #ffe0b2; color: #b08500; }
.role-tag.editor { background: #e3f2fd; color: #0066cc; }

.admin-link {
  padding: 4px 10px;
  background: #fff3cd;
  color: #b08500;
  border: 1px solid #ffe0a3;
  border-radius: 3px;
  text-decoration: none;
  font-size: 12px;
  font-weight: 500;
}
.admin-link:hover { background: #ffe69c; }

.logout-btn, .login-link {
  padding: 4px 12px;
  background: #fff;
  color: #0066cc;
  border: 1px solid #d0d0d6;
  border-radius: 3px;
  cursor: pointer;
  font-size: 13px;
  text-decoration: none;
}
.logout-btn:hover, .login-link:hover { background: #f0f7ff; }

nav {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

nav a {
  color: #0066cc;
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 4px;
}

nav a:hover {
  background: #f0f0f0;
}

nav a.router-link-active {
  background: #0066cc;
  color: #fff;
}

nav a.nav-build {
  margin-left: auto;
  background: #f59e0b;
  color: #fff;
  font-weight: 500;
}

nav a.nav-build:hover {
  background: #d97706;
}

nav a.nav-build.router-link-active {
  background: #d97706;
  color: #fff;
}

main {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
</style>
