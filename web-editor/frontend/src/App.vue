<template>
  <div id="app">
    <header>
      <h1>木叶战记续作 - 编辑器</h1>
      <nav>
        <router-link to="/dialogues">对话管理</router-link>
        <router-link to="/battle-configs">战斗配置</router-link>
        <router-link to="/units">单位配置</router-link>
        <router-link to="/units/place">角色放置</router-link>
        <router-link to="/skills">技能配置</router-link>
        <router-link to="/story-beats">剧情节拍</router-link>
        <router-link to="/audio">音频管理</router-link>
        <router-link to="/build">构建</router-link>
        <router-link to="/map">地图编辑</router-link>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
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

header h1 {
  font-size: 24px;
  margin-bottom: 10px;
  color: #333;
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

main {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
</style>