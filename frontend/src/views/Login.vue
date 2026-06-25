<template>
  <div class="login-page">
    <!-- 背景光晕(纯 CSS 渐变,无图)-->
    <div class="bg-glow glow-1"></div>
    <div class="bg-glow glow-2"></div>
    <div class="bg-glow glow-3"></div>
    <div class="bg-grid"></div>

    <!-- 顶部品牌 -->
    <div class="top-brand">
      <div class="brand-mark">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M3 21V9l9-7 9 7v12h-6v-7H9v7H3z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="brand-text">
        <span class="brand-name">{{ brand.name || '智慧物业' }}</span>
        <span class="brand-tag">SMART COMMUNITY</span>
      </div>
    </div>

    <!-- 中心登录卡 -->
    <div class="login-wrap">
      <div class="login-card">
        <div class="login-header">
          <div class="header-badge">PROPERTY MANAGEMENT</div>
          <h1>欢迎回来</h1>
          <p>登录账户继续访问物业管理平台</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          @keyup.enter="onSubmit"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="用户名"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              class="login-btn"
              :loading="loading"
              @click="onSubmit"
            >
              <span>登录</span>
              <el-icon class="btn-arrow"><ArrowRight /></el-icon>
            </el-button>
          </el-form-item>
        </el-form>

        <div class="login-footer">
          <div class="hint-row">
            <span class="hint-label">默认管理员</span>
            <span class="hint-value">hlc / 123456</span>
          </div>
          <div class="register-row">
            还没有账号?
            <a class="register-link" @click="onRegister">立即注册</a>
          </div>
        </div>
      </div>

      <!-- 底部 footer -->
      <div class="footer-meta">
        <span>© 2026 Smart Community</span>
        <span class="dot">·</span>
        <span>v1.0</span>
        <span class="dot">·</span>
        <span>Powered by YOLO + LLM</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, ArrowRight } from '@element-plus/icons-vue'
import { login } from '@/api/auth'
import { useAuthStore } from '@/store/auth'
import { useBrandStore } from '@/store/brand'

const brand = useBrandStore()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const onSubmit = async () => {
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      const res = await login({ ...form })
      auth.setAuth(res.token, res.user)
      ElMessage.success('登录成功')
      router.push(route.query.redirect || '/')
    } catch (e) {
      // 错误提示已由 axios 拦截器统一处理
    } finally {
      loading.value = false
    }
  })
}

const onRegister = () => {
  ElMessage.info('注册功能将在后续开放')
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #fafbfc;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 背景光晕(白底版,克制配色)*/
.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  pointer-events: none;
  z-index: 0;
}
.glow-1 {
  top: -200px;
  left: -100px;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(22, 179, 168, 0.12), transparent 70%);
  animation: float-1 20s var(--ease-smooth) infinite;
}
.glow-2 {
  bottom: -200px;
  right: -100px;
  width: 700px;
  height: 700px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.08), transparent 70%);
  animation: float-2 25s var(--ease-smooth) infinite;
}
.glow-3 {
  top: 30%;
  left: 50%;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.06), transparent 70%);
  animation: float-3 18s var(--ease-smooth) infinite;
}
@keyframes float-1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(100px, 80px) scale(1.1); }
}
@keyframes float-2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-80px, -60px) scale(1.15); }
}
@keyframes float-3 {
  0%, 100% { transform: translate(-50%, -50%) scale(1); }
  50% { transform: translate(-30%, -70%) scale(1.2); }
}

/* 网格背景(亮色版,深一档让纹理可见)*/
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(15, 23, 42, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 23, 42, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, black, transparent 70%);
  -webkit-mask-image: radial-gradient(ellipse at center, black, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

/* 顶部品牌 */
.top-brand {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 28px 48px;
}
.brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-gradient);
  color: white;
  box-shadow: 0 8px 24px rgba(22, 179, 168, 0.25);
}
.brand-mark svg {
  width: 22px;
  height: 22px;
}
.brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.brand-name {
  color: var(--text);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.2px;
}
.brand-tag {
  color: var(--brand);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2px;
  font-family: var(--font-mono);
}

/* 中心登录区 */
.login-wrap {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 44px;
  box-shadow: 0 16px 48px rgba(15, 23, 42, 0.08),
              0 0 0 1px rgba(15, 23, 42, 0.04);
  animation: card-in 0.8s var(--ease-out) both;
  position: relative;
  overflow: hidden;
}

/* 卡片顶部渐变线 */
.login-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 20%;
  right: 20%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--brand), transparent);
  opacity: 0.8;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.login-header {
  margin-bottom: 32px;
}
.header-badge {
  display: inline-block;
  padding: 4px 10px;
  background: var(--brand-soft);
  border: 1px solid var(--border-brand);
  border-radius: var(--radius-xs);
  color: var(--brand);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.5px;
  font-family: var(--font-mono);
  margin-bottom: 16px;
}
.login-header h1 {
  color: var(--text);
  font-size: 28px;
  font-weight: 600;
  letter-spacing: -0.5px;
  line-height: 1.2;
  margin-bottom: 8px;
}
.login-header p {
  color: var(--text-2);
  font-size: 14px;
  line-height: 1.5;
}

.login-btn {
  width: 100%;
  height: 46px !important;
  font-size: 14px !important;
  font-weight: 600 !important;
  letter-spacing: 1px;
  display: flex !important;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.btn-arrow {
  font-size: 16px;
  transition: transform 0.2s var(--ease-out);
}
.login-btn:hover .btn-arrow {
  transform: translateX(3px);
}

.login-footer {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--divider);
}
.hint-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-overlay);
  border-radius: var(--radius-md);
  border: 1px dashed var(--border);
  margin-bottom: 14px;
}
.hint-label {
  color: var(--text-3);
  font-size: 11px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.hint-value {
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 500;
}

.register-row {
  text-align: center;
  font-size: 13px;
  color: var(--text-3);
}
.register-link {
  color: var(--brand);
  cursor: pointer;
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
  transition: color 0.15s ease;
}
.register-link:hover {
  color: var(--brand-2);
  text-decoration: underline;
}

.footer-meta {
  margin-top: 32px;
  font-size: 12px;
  color: var(--text-3);
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-meta .dot { opacity: 0.4; }
</style>
