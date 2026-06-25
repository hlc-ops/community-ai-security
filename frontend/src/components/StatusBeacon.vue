<template>
  <span class="status-beacon" :class="`is-${status}`" :title="title">
    <span class="dot">
      <span class="ring"></span>
    </span>
    <span v-if="label" class="label">{{ label }}</span>
  </span>
</template>

<script setup>
defineProps({
  status: {
    type: String,
    default: 'online', // online / offline / warning / standby
    validator: v => ['online', 'offline', 'warning', 'standby'].includes(v),
  },
  label: { type: String, default: '' },
  title: { type: String, default: '' },
})
</script>

<style scoped>
.status-beacon {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--fs-sm);
  font-weight: var(--fw-medium);
}

.dot {
  position: relative;
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.ring {
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  pointer-events: none;
}

/* === online === */
.is-online .dot { background: var(--success); }
.is-online .ring {
  background: var(--success);
  opacity: 0.5;
  animation: ripple 2s var(--ease-smooth) infinite;
}
.is-online .label { color: var(--success); }

/* === offline === */
.is-offline .dot { background: var(--text-3); }
.is-offline .label { color: var(--text-3); }

/* === warning === */
.is-warning .dot { background: var(--warning); }
.is-warning .ring {
  background: var(--warning);
  opacity: 0.5;
  animation: ripple 2s var(--ease-smooth) infinite;
}
.is-warning .label { color: var(--warning); }

/* === standby === */
.is-standby .dot { background: var(--info); }
.is-standby .label { color: var(--info); }

@keyframes ripple {
  0% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  100% {
    transform: scale(2.2);
    opacity: 0;
  }
}
</style>
