<template>
  <div id="app">
    <div class="app-background" aria-hidden="true">
      <div class="orb orb-primary"></div>
      <div class="orb orb-secondary"></div>
      <div class="orb orb-accent"></div>
      <div class="grid-overlay"></div>
    </div>

    <a-layout class="app-shell">
      <a-layout-header class="app-header">
        <div class="brand-lockup">
          <div class="brand-badge">
            <CompassOutlined />
          </div>
          <div class="brand-copy">
            <div class="brand-title">《智行伴侣：一个面向个性化旅游规划的智能体系统》</div>
          </div>
        </div>
      </a-layout-header>

      <a-layout-content class="app-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { CompassOutlined } from '@ant-design/icons-vue'
</script>

<style>
#app {
  position: relative;
  min-height: 100vh;
  font-family: var(--font-family);
}

.app-shell {
  position: relative;
  min-height: 100vh;
  background: transparent !important;
}

.app-background {
  position: fixed;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.orb {
  position: absolute;
  border-radius: 9999px;
  filter: blur(80px);
  opacity: 0.7;
  animation: drift 18s ease-in-out infinite;
}

.orb-primary {
  top: -8%;
  left: -6%;
  width: 36rem;
  height: 36rem;
  background: radial-gradient(circle, rgba(120, 119, 255, 0.48) 0%, rgba(120, 119, 255, 0) 72%);
}

.orb-secondary {
  top: 18%;
  right: -8%;
  width: 30rem;
  height: 30rem;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.38) 0%, rgba(96, 165, 250, 0) 70%);
  animation-delay: -6s;
}

.orb-accent {
  bottom: -10%;
  left: 28%;
  width: 34rem;
  height: 34rem;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.3) 0%, rgba(255, 255, 255, 0) 75%);
  animation-delay: -11s;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.75), transparent 78%);
}

.app-header {
  position: sticky;
  top: 16px;
  z-index: 20;
  width: min(1440px, calc(100% - 32px));
  margin: 16px auto 0 !important;
  padding: 0 24px !important;
  border-radius: 28px;
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-badge {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.55));
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.7),
    0 12px 24px rgba(79, 70, 229, 0.12);
  color: #4f46e5;
  font-size: 18px;
  line-height: 1;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
  justify-content: center;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}

.app-content {
  position: relative;
  z-index: 1;
}

@keyframes drift {
  0%, 100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(18px, -24px, 0) scale(1.04);
  }
}

@media (max-width: 768px) {
  .app-header {
    top: 12px;
    width: calc(100% - 20px);
    margin-top: 10px !important;
    padding: 0 18px !important;
    border-radius: 22px;
  }

  .brand-title {
    font-size: 16px;
  }

  .brand-badge {
    width: 38px;
    height: 38px;
    border-radius: 14px;
  }
}
</style>
