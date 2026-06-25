<template>
  <div class="premium-card" :class="{ 'is-hoverable': hoverable, 'has-glow': glow }">
    <div v-if="glow" class="card-glow" :style="glowStyle"></div>
    <div v-if="$slots.header || title" class="card-header">
      <slot name="header">
        <div class="header-left">
          <span v-if="icon" class="card-icon">
            <component :is="icon" />
          </span>
          <div>
            <div class="card-title">{{ title }}</div>
            <div v-if="subtitle" class="card-subtitle">{{ subtitle }}</div>
          </div>
        </div>
        <div class="header-right">
          <slot name="extra" />
        </div>
      </slot>
    </div>
    <div class="card-body" :style="bodyStyle">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  icon: { type: [Object, Function], default: null },
  hoverable: { type: Boolean, default: true },
  glow: { type: Boolean, default: true },
  glowColor: { type: String, default: '' },
  padding: { type: String, default: '' },
})

const glowStyle = computed(() => {
  if (!props.glowColor) return {}
  return {
    background: `radial-gradient(ellipse at top right, ${props.glowColor}, transparent 60%)`,
  }
})

const bodyStyle = computed(() => {
  if (props.padding) return { padding: props.padding }
  return {}
})
</script>

<style scoped>
.premium-card {
  position: relative;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color var(--duration-base) var(--ease-out),
              transform var(--duration-base) var(--ease-out),
              box-shadow var(--duration-base) var(--ease-out);
}

.premium-card.is-hoverable:hover {
  border-color: var(--border-brand);
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}

.card-glow {
  position: absolute;
  top: 0;
  right: 0;
  width: 70%;
  height: 70%;
  background: var(--gradient-mesh);
  pointer-events: none;
  opacity: 0.6;
  transition: opacity var(--duration-base) var(--ease-out);
  z-index: 0;
}

.is-hoverable.has-glow:hover .card-glow { opacity: 1; }

.card-header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--divider);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 18px;
}

.card-title {
  font-size: var(--fs-md);
  font-weight: var(--fw-semibold);
  color: var(--text);
  letter-spacing: var(--letter-tight);
}

.card-subtitle {
  font-size: var(--fs-sm);
  color: var(--text-3);
  margin-top: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.card-body {
  position: relative;
  z-index: 1;
  padding: var(--space-5);
}
</style>
