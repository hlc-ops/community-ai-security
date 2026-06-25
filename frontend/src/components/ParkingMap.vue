<template>
  <div class="parking-map">
    <!-- 头部统计 -->
    <div class="map-header">
      <div class="stat-grid">
        <div class="stat-block">
          <div class="stat-eyebrow">TOTAL</div>
          <div class="stat-num">
            <CountUp :value="total" />
          </div>
          <div class="stat-foot">总车位</div>
        </div>
        <div class="stat-block">
          <div class="stat-eyebrow">OCCUPIED</div>
          <div class="stat-num occupied">
            <CountUp :value="occupied" />
          </div>
          <div class="stat-foot">已占用</div>
        </div>
        <div class="stat-block">
          <div class="stat-eyebrow">AVAILABLE</div>
          <div class="stat-num available">
            <CountUp :value="available" />
          </div>
          <div class="stat-foot">剩余车位</div>
        </div>
        <div class="stat-block">
          <div class="stat-eyebrow">USAGE</div>
          <div class="stat-num percent">
            <CountUp :value="usagePercent" :decimals="1" suffix="%" />
          </div>
          <div class="stat-foot">使用率</div>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: usagePercent + '%', background: usageColor }"
        ></div>
        <div class="progress-text">
          <span>占用率 {{ usagePercent.toFixed(1) }}%</span>
        </div>
      </div>
    </div>

    <!-- 车位网格 -->
    <div class="slot-grid">
      <div
        v-for="slot in slots"
        :key="slot.id"
        class="slot-card"
        :class="{ occupied: slot.occupied, charging: slot.type === 'charging_slot' }"
        :title="`${slot.name} · ${slot.occupied ? '占用中' : '空闲'}`"
      >
        <div class="slot-icon">
          <el-icon v-if="slot.type === 'charging_slot'">
            <Lightning />
          </el-icon>
          <el-icon v-else>
            <Van />
          </el-icon>
        </div>
        <div class="slot-name">{{ slot.name }}</div>
        <div class="slot-status">{{ slot.occupied ? 'OCCUPIED' : 'AVAILABLE' }}</div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="legend">
      <span class="legend-item">
        <span class="legend-dot available"></span>
        空闲
      </span>
      <span class="legend-item">
        <span class="legend-dot occupied"></span>
        已占用
      </span>
      <span class="legend-item">
        <span class="legend-dot charging"></span>
        充电桩
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Van, Lightning } from '@element-plus/icons-vue'
import CountUp from './CountUp.vue'

const props = defineProps({
  slots: {
    type: Array,
    default: () => [],
    // 每个元素: { id, name, type: 'parking_slot' | 'charging_slot', occupied: bool }
  },
})

const total = computed(() => props.slots.length)
const occupied = computed(() => props.slots.filter(s => s.occupied).length)
const available = computed(() => total.value - occupied.value)
const usagePercent = computed(() =>
  total.value > 0 ? (occupied.value / total.value) * 100 : 0
)
const usageColor = computed(() => {
  const p = usagePercent.value
  if (p < 60) return 'linear-gradient(90deg, #4ecdc4, #45b1a8)'
  if (p < 85) return 'linear-gradient(90deg, #ffb74d, #f59f00)'
  return 'linear-gradient(90deg, #ff5470, #ff3358)'
})
</script>

<style scoped>
.parking-map {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* 头部统计 */
.map-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.stat-block {
  padding: var(--space-4);
  background: var(--bg-overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.stat-eyebrow {
  font-size: 10px;
  color: var(--text-3);
  font-weight: 600;
  letter-spacing: 1.5px;
  font-family: var(--font-mono);
  margin-bottom: 6px;
}
.stat-num {
  font-family: var(--font-mono);
  font-size: 32px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -1px;
  line-height: 1;
}
.stat-num.occupied { color: var(--danger); }
.stat-num.available { color: var(--success); }
.stat-num.percent { color: var(--brand); }
.stat-foot {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 6px;
}

/* 进度条 */
.progress-bar {
  position: relative;
  height: 32px;
  background: var(--bg-overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  border-radius: var(--radius-md);
  transition: width 800ms var(--ease-out), background 400ms var(--ease-out);
}
.progress-text {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: var(--text);
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: 1px;
  z-index: 1;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
}

/* 车位网格 */
.slot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--space-3);
}
.slot-card {
  position: relative;
  padding: var(--space-3);
  background: var(--bg-overlay);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  text-align: center;
  transition: all var(--duration-base) var(--ease-out);
  overflow: hidden;
}
.slot-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(78, 205, 196, 0.08), transparent 70%);
  opacity: 1;
  transition: opacity var(--duration-base) var(--ease-out);
}
.slot-card.occupied {
  background: rgba(255, 84, 112, 0.08);
  border-color: rgba(255, 84, 112, 0.3);
}
.slot-card.occupied::before {
  background: linear-gradient(135deg, rgba(255, 84, 112, 0.15), transparent 70%);
}
.slot-card.charging {
  background: rgba(255, 183, 77, 0.05);
  border-color: rgba(255, 183, 77, 0.25);
}
.slot-card.charging.occupied {
  background: rgba(255, 84, 112, 0.08);
  border-color: rgba(255, 84, 112, 0.3);
}
.slot-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
}

.slot-icon {
  position: relative;
  z-index: 1;
  font-size: 24px;
  color: var(--success);
  margin-bottom: 6px;
}
.slot-card.occupied .slot-icon { color: var(--danger); }
.slot-card.charging .slot-icon { color: var(--warning); }
.slot-card.charging.occupied .slot-icon { color: var(--danger); }

.slot-name {
  position: relative;
  z-index: 1;
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}
.slot-status {
  position: relative;
  z-index: 1;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 1.5px;
  color: var(--success);
  font-weight: 600;
}
.slot-card.occupied .slot-status { color: var(--danger); }

/* 图例 */
.legend {
  display: flex;
  justify-content: center;
  gap: var(--space-6);
  padding-top: var(--space-3);
  border-top: 1px solid var(--divider);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-2);
}
.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.legend-dot.available { background: var(--success); }
.legend-dot.occupied { background: var(--danger); }
.legend-dot.charging { background: var(--warning); }
</style>
