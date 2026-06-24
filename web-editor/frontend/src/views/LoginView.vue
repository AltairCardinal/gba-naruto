<template>
  <div class="login-view">
    <div class="login-card">
      <h2>{{ mode === 'login' ? '登录' : '注册' }}</h2>
      <p class="hint">
        {{ mode === 'login'
          ? '使用你的账号登录编辑器'
          : '注册新账号（默认无任何权限，登录后请等待管理员授权）' }}
      </p>

      <form @submit.prevent="onSubmit">
        <div class="form-group">
          <label>用户名</label>
          <input
            v-model="username"
            required
            :disabled="busy"
            autocomplete="username"
            placeholder="2-64 字符，字母数字下划线"
          />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            required
            :disabled="busy"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            placeholder="至少 4 字符"
            minlength="4"
          />
        </div>
        <button type="submit" class="btn-primary" :disabled="busy">
          {{ busy ? '处理中…' : (mode === 'login' ? '登录' : '注册') }}
        </button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>

      <div class="switch">
        <span v-if="mode === 'login'">
          没有账号？
          <a href="#" @click.prevent="mode = 'register'">立即注册</a>
        </span>
        <span v-else>
          已有账号？
          <a href="#" @click.prevent="mode = 'login'">去登录</a>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

async function onSubmit() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  busy.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username.value, password.value)
    } else {
      await auth.register(username.value, password.value)
    }
    // Redirect to original target (if any) or to dialogues home
    const target = (route.query.redirect as string) || '/dialogues'
    router.push(target)
  } catch (e: any) {
    error.value = e?.message || '操作失败'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.login-view {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 60px 20px;
  min-height: 60vh;
}

.login-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  padding: 32px 36px;
  width: 100%;
  max-width: 420px;
}

h2 {
  margin: 0 0 8px;
  color: #333;
  font-size: 22px;
}

.hint {
  color: #666;
  font-size: 13px;
  margin: 0 0 24px;
  line-height: 1.5;
}

.form-group {
  margin-bottom: 18px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  font-size: 13px;
  color: #444;
}

.form-group input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #d0d0d6;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 0 3px rgba(0,102,204,0.12);
}

.btn-primary {
  width: 100%;
  padding: 10px 16px;
  background: #0066cc;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  margin-top: 4px;
}

.btn-primary:hover:not(:disabled) { background: #0052a3; }
.btn-primary:disabled { background: #9ec0e3; cursor: not-allowed; }

.error {
  margin-top: 12px;
  color: #b00020;
  font-size: 13px;
  background: #fde7ea;
  border: 1px solid #f5b6c0;
  padding: 8px 10px;
  border-radius: 4px;
}

.switch {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: #666;
}

.switch a {
  color: #0066cc;
  text-decoration: none;
  font-weight: 500;
}

.switch a:hover { text-decoration: underline; }
</style>
