<template>
  <div>
    <div class="page-title">系统设置</div>
    <div class="page-desc">报警推送、品牌定制、检测灵敏度、告警声音的全局配置。</div>

    <el-card shadow="never" class="box">
      <el-tabs v-model="activeTab">

        <!-- =============== 报警推送 =============== -->
        <el-tab-pane name="alert" label="报警推送">
          <el-form v-loading="loading.alert" :model="form" label-width="120px" style="max-width: 640px">
            <el-form-item label="启用推送">
              <el-switch v-model="form.enabled" />
              <span class="tip">检测到高危违规时自动推送到群机器人</span>
            </el-form-item>
            <el-form-item label="推送渠道">
              <el-radio-group v-model="form.channel">
                <el-radio-button value="dingtalk">钉钉</el-radio-button>
                <el-radio-button value="wecom">企业微信</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="Webhook 地址">
              <el-input v-model="form.webhook" type="textarea" :rows="2" placeholder="粘贴群机器人的 Webhook 地址" />
              <div class="tip">
                {{ form.channel === 'dingtalk'
                  ? '钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义 → 复制 Webhook'
                  : '企业微信群 → 右上角 → 添加群机器人 → 复制 Webhook 地址' }}
              </div>
            </el-form-item>
            <el-form-item label="推送冷却(秒)">
              <el-input-number v-model="form.cooldown" :min="0" :max="3600" />
              <span class="tip">两次推送的最小间隔，防止刷屏</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving.alert" @click="saveAlert">保存</el-button>
              <el-button :loading="testing" @click="testAlertCfg">测试发送</el-button>
            </el-form-item>
          </el-form>
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 8px"
            title="钉钉机器人若设置了「自定义关键词」，关键词须包含「工地安防」" />
          <el-alert type="success" :closable="false" show-icon
            title="企业微信支持自动附带违规截图；钉钉机器人仅文字告警（不支持本地图片）" />
        </el-tab-pane>

        <!-- =============== 品牌定制 =============== -->
        <el-tab-pane name="brand" label="品牌定制">
          <el-form v-loading="loading.brand" :model="brandForm" label-width="120px" style="max-width: 640px">
            <el-form-item label="Logo">
              <div class="logo-row">
                <div class="logo-preview">
                  <img v-if="brandForm.logoUrl" :src="brandForm.logoUrl" alt="logo" />
                  <span v-else class="logo-empty">无 Logo</span>
                </div>
                <el-upload
                  :auto-upload="false"
                  :show-file-list="false"
                  accept="image/*"
                  :on-change="onLogoChange"
                >
                  <el-button type="primary" plain :loading="uploading.logo">上传 Logo</el-button>
                </el-upload>
                <el-button v-if="brandForm.logoUrl" @click="brandForm.logoUrl = ''">清除</el-button>
              </div>
              <div class="tip">支持 PNG/JPG/SVG/WebP，&lt; 2MB；建议背景透明、长宽比接近 1:1 或 3:1</div>
            </el-form-item>
            <el-form-item label="系统名称">
              <el-input v-model="brandForm.name" maxlength="32" show-word-limit placeholder="如：XX 集团智慧工地安防系统" />
            </el-form-item>
            <el-form-item label="副标题">
              <el-input v-model="brandForm.subtitle" maxlength="60" show-word-limit
                placeholder="如：基于深度学习的智慧工地安全监管平台" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving.brand" @click="saveBrandCfg">保存</el-button>
              <span class="tip">保存后浏览器标签标题、登录页、侧栏 Logo 都会刷新</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- =============== 检测灵敏度 =============== -->
        <el-tab-pane name="sensitivity" label="检测灵敏度">
          <div v-loading="loading.confs" style="max-width: 720px">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px"
              title="每个类别可单独调置信度阈值。值越高越严格（漏检多），越低越敏感（误报多）。" />
            <div v-for="name in CLASS_NAMES" :key="name" class="sens-row">
              <div class="sens-label">
                <el-tag :type="riskTagType(name)" effect="dark" size="small">{{ name }}</el-tag>
                <span class="sens-note">{{ riskNote(name) }}</span>
              </div>
              <el-slider
                v-model="classConfs[name]"
                :min="0.1" :max="0.9" :step="0.05"
                :format-tooltip="(v) => v.toFixed(2)"
                style="flex: 1; margin: 0 16px"
              />
              <span class="sens-val">{{ (classConfs[name] || 0.5).toFixed(2) }}</span>
            </div>
            <el-form-item style="margin-top: 16px">
              <el-button type="primary" :loading="saving.confs" @click="saveConfsCfg">保存</el-button>
              <el-button @click="resetConfs">恢复默认 (0.50)</el-button>
            </el-form-item>
          </div>
        </el-tab-pane>

        <!-- =============== 告警声音 =============== -->
        <el-tab-pane name="sound" label="告警声音">
          <div v-loading="loading.sound" style="max-width: 640px">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px"
              title="未上传时使用内置蜂鸣声。上传一段短促的 wav/mp3（&lt; 1MB），适合工地警报提示。" />

            <div class="sound-row">
              <div class="sound-status">
                <span class="tip-label">当前：</span>
                <el-tag v-if="soundUrl" type="success">已设置自定义声音</el-tag>
                <el-tag v-else type="info">使用内置蜂鸣</el-tag>
              </div>
              <audio v-if="soundUrl" :src="soundUrl" controls preload="auto" style="margin-top: 12px" />
            </div>

            <el-form-item style="margin-top: 16px">
              <el-upload
                :auto-upload="false"
                :show-file-list="false"
                accept="audio/*"
                :on-change="onSoundChange"
              >
                <el-button type="primary" plain :loading="uploading.sound">上传音频</el-button>
              </el-upload>
              <el-button type="success" plain @click="previewSound" :disabled="!soundUrl">试听</el-button>
              <el-button type="danger" plain @click="clearSound" :disabled="!soundUrl">清除（回到默认）</el-button>
            </el-form-item>
          </div>
        </el-tab-pane>

        <!-- =============== AI 告警分级 =============== -->
        <el-tab-pane name="triage" label="AI 告警分级">
          <div v-loading="loading.triage" style="max-width: 720px">
            <el-alert type="warning" :closable="false" show-icon style="margin-bottom: 16px"
              title="开启后，每条高危告警会触发一次视觉大模型分析（成本约 ¥0.01-0.02/次），由模型判断紧急度，仅 immediate/high 才推送钉钉/企微。关闭则维持原行为：所有高危都推送。" />

            <el-form label-width="120px">
              <el-form-item label="启用智能分级">
                <el-switch v-model="triageEnabled" @change="saveTriageCfg" />
                <span class="tip">{{ triageEnabled ? '高危告警将经 AI 评估真实紧急度' : '高危告警直接推送（传统行为）' }}</span>
              </el-form-item>
              <el-form-item label="分级规则">
                <div class="rule-list">
                  <div class="rule-item"><el-tag type="danger" size="small">立即处置</el-tag>可能立即造成伤亡（高空、临边、机械碾压等）</div>
                  <div class="rule-item"><el-tag type="warning" size="small">紧急</el-tag>多人违规或危险区域</div>
                  <div class="rule-item"><el-tag type="info" size="small">一般</el-tag>普通违规</div>
                  <div class="rule-item"><el-tag size="small">可缓</el-tag>远处或轻微违规</div>
                </div>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>

        <!-- =============== 复核 LLM 服务商 =============== -->
        <el-tab-pane name="llm" label="复核 LLM 服务商">
          <div v-loading="loading.llm">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px"
              title="管理用于「自动安全复核」的视觉大模型(YOLO 判定安全时由 LLM 兜底)。可配置多家服务商,勾选一个作为主用。API Key 仅末位可见,不可读取。" />

            <div style="margin-bottom: 12px">
              <el-button type="primary" @click="openLLMAdd">+ 添加服务商</el-button>
              <span class="tip" style="margin-left: 12px">当前已配置 {{ llm.providers.length }} 个</span>
            </div>

            <el-table :data="llm.providers" stripe>
              <el-table-column width="70" label="主用">
                <template #default="{ row }">
                  <el-radio
                    :model-value="llm.preferred_id"
                    :label="row.id"
                    :value="row.id"
                    @click="setLLMMain(row)"
                  >&nbsp;</el-radio>
                </template>
              </el-table-column>
              <el-table-column prop="name" label="显示名称" min-width="140" />
              <el-table-column label="厂商" width="160">
                <template #default="{ row }">
                  <el-tag :type="providerTagType(row.provider)" effect="dark">{{ providerLabel(row.provider) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="model" label="模型" min-width="160" />
              <el-table-column label="API Key" width="180">
                <template #default="{ row }">
                  <span class="muted" style="font-family: monospace">{{ row.api_key_masked || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="240" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openLLMEdit(row)">编辑</el-button>
                  <el-button link type="success" :loading="row._testing" @click="doLLMTest(row)">测试</el-button>
                  <el-button link type="danger" @click="doLLMDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-empty v-if="!llm.providers.length" description="还没有配置任何服务商" :image-size="80" />

            <!-- 新增/编辑弹窗 -->
            <el-dialog v-model="llmDlg.visible" :title="llmDlg.isEdit ? '编辑服务商' : '添加服务商'" width="560px">
              <el-form :model="llmDlg.form" label-width="100px">
                <el-form-item label="显示名称">
                  <el-input v-model="llmDlg.form.name" placeholder="例:线上通义千问 / 测试智谱" maxlength="64" />
                </el-form-item>
                <el-form-item label="厂商">
                  <el-select v-model="llmDlg.form.provider" style="width: 100%" @change="onLLMProviderChange">
                    <el-option v-for="s in llm.supported" :key="s.provider" :label="s.label" :value="s.provider" />
                  </el-select>
                </el-form-item>
                <el-form-item label="Base URL">
                  <el-input v-model="llmDlg.form.base_url" placeholder="留空则用厂商默认值" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="llmDlg.form.model" placeholder="留空则用厂商默认视觉模型" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input
                    v-model="llmDlg.form.api_key"
                    :type="llmDlg.showKey ? 'text' : 'password'"
                    :placeholder="llmDlg.isEdit ? '留空保持原密钥不变' : '填写 sk-... / app-... 等'"
                    show-password
                  />
                </el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="llmDlg.visible = false">取消</el-button>
                <el-button type="primary" :loading="llmDlg.saving" @click="doLLMSave">保存</el-button>
              </template>
            </el-dialog>
          </div>
        </el-tab-pane>

        <!-- =============== 数据保留 =============== -->
        <el-tab-pane name="retention" label="数据保留">
          <div v-loading="loading.retention" style="max-width: 720px">
            <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px"
              title="超期数据会被自动清理（每天凌晨）。设置过短会丢失取证素材，过长会占满磁盘。" />

            <el-form label-width="160px">
              <el-form-item label="检测记录保留">
                <el-input-number v-model="retention.retention_records" :min="7" :max="3650" />
                <span class="tip">天 · 含截图，超期记录会一并删除</span>
              </el-form-item>
              <el-form-item label="视频片段保留">
                <el-input-number v-model="retention.retention_clips" :min="1" :max="3650" />
                <span class="tip">天 · mp4 体积大，建议短于记录保留</span>
              </el-form-item>
              <el-form-item label="审计日志保留">
                <el-input-number v-model="retention.retention_audits" :min="30" :max="3650" />
                <span class="tip">天 · 合规建议至少 180 天</span>
              </el-form-item>
              <el-form-item label="数据库备份保留">
                <el-input-number v-model="retention.retention_backups" :min="3" :max="365" />
                <span class="tip">天 · 每日生成 1 份 sqlite 快照</span>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="saving.retention" @click="saveRetentionCfg">保存</el-button>
                <el-button :loading="running.cleanup" @click="runCleanupNow">立即清理</el-button>
              </el-form-item>
            </el-form>

            <el-alert v-if="lastCleanup" type="success" :closable="false" show-icon
              :title="`上次清理：记录 ${lastCleanup.records_deleted}，截图 ${lastCleanup.snaps_deleted}，视频 ${lastCleanup.clips_deleted}，审计 ${lastCleanup.audits_deleted}${lastCleanup.db_backed_up ? '；已备份数据库' : ''}`" />
          </div>
        </el-tab-pane>

        <!-- =============== 系统健康 =============== -->
        <el-tab-pane name="health" label="系统健康">
          <div v-loading="loading.health">
            <el-button :icon="Refresh" :loading="loading.health" @click="loadHealth" style="margin-bottom: 16px">
              刷新
            </el-button>

            <el-row :gutter="16">
              <el-col :span="6">
                <div class="hk-card">
                  <div class="hk-eyebrow">磁盘使用</div>
                  <div class="hk-num">{{ health.diskUsedGB || '—' }}<span class="hk-of">/{{ health.diskTotalGB || '—' }} GB</span></div>
                  <el-progress
                    :percentage="health.diskPercent || 0"
                    :status="diskStatus"
                    :stroke-width="6"
                    style="margin-top: 6px"
                  />
                </div>
              </el-col>
              <el-col :span="6">
                <div class="hk-card">
                  <div class="hk-eyebrow">数据库大小</div>
                  <div class="hk-num">{{ health.dbSizeMB || '—' }}<span class="hk-of"> MB</span></div>
                  <div class="hk-sub">{{ health.counts?.records || 0 }} 条记录</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="hk-card">
                  <div class="hk-eyebrow">进程内存</div>
                  <div class="hk-num">{{ health.memoryMB || '—' }}<span class="hk-of"> MB</span></div>
                  <div class="hk-sub">CPU {{ health.cpuPercent || 0 }}%</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="hk-card">
                  <div class="hk-eyebrow">活跃拉流</div>
                  <div class="hk-num">{{ health.activeStreams || 0 }}<span class="hk-of"> / {{ health.totalStreams || 0 }}</span></div>
                  <div class="hk-sub">摄像头 {{ health.counts?.cameras || 0 }} 台</div>
                </div>
              </el-col>
            </el-row>

            <el-row :gutter="16" style="margin-top: 16px">
              <el-col :span="6"><div class="hk-card mini"><div class="hk-eyebrow">截图占用</div><div class="hk-num small">{{ health.snapshotsMB || 0 }}<span class="hk-of"> MB</span></div></div></el-col>
              <el-col :span="6"><div class="hk-card mini"><div class="hk-eyebrow">视频片段</div><div class="hk-num small">{{ health.clipsMB || 0 }}<span class="hk-of"> MB</span></div></div></el-col>
              <el-col :span="6"><div class="hk-card mini"><div class="hk-eyebrow">上传文件</div><div class="hk-num small">{{ health.uploadsMB || 0 }}<span class="hk-of"> MB</span></div></div></el-col>
              <el-col :span="6"><div class="hk-card mini"><div class="hk-eyebrow">数据库备份</div><div class="hk-num small">{{ health.backupsMB || 0 }}<span class="hk-of"> MB</span></div></div></el-col>
            </el-row>
          </div>
        </el-tab-pane>

      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import {
  getAlertConfig, saveAlertConfig, testAlert,
  getBrand, saveBrand, uploadBrandLogo,
  getAlertSound, uploadAlertSound, clearAlertSound,
  getClassConfs, saveClassConfs,
  getRetention, saveRetention, runCleanup, getHealthDetail,
  getTriageEnabled, saveTriageEnabled,
  listLLMProviders, createLLMProvider, updateLLMProvider, deleteLLMProvider,
  setLLMPreferred, testLLMProvider,
} from '@/api/settings'
import { ElMessageBox } from 'element-plus'
import { useBrandStore } from '@/store/brand'
import { setCustomSound } from '@/utils/realtimeAlerts'

const activeTab = ref('alert')
const loading = reactive({ alert: false, brand: false, confs: false, sound: false, retention: false, health: false, triage: false, llm: false })
const saving = reactive({ alert: false, brand: false, confs: false, retention: false })
const running = reactive({ cleanup: false })
const uploading = reactive({ logo: false, sound: false })
const testing = ref(false)

// ---- 报警推送 ----
const form = reactive({ enabled: false, channel: 'dingtalk', webhook: '', cooldown: 30 })
const loadAlert = async () => {
  loading.alert = true
  try { Object.assign(form, (await getAlertConfig()).config) } catch (e) {} finally { loading.alert = false }
}
const saveAlert = async () => {
  saving.alert = true
  try { await saveAlertConfig({ ...form }); ElMessage.success('已保存') } catch (e) {} finally { saving.alert = false }
}
const testAlertCfg = async () => {
  if (!form.webhook.trim()) return ElMessage.warning('请先填写 Webhook 地址')
  testing.value = true
  try { const r = await testAlert({ channel: form.channel, webhook: form.webhook }); ElMessage.success(r.msg) }
  catch (e) {} finally { testing.value = false }
}

// ---- 品牌定制 ----
const brand = useBrandStore()
const brandForm = reactive({ name: '', subtitle: '', logoUrl: '' })
const loadBrand = async () => {
  loading.brand = true
  try { Object.assign(brandForm, (await getBrand()).config) } catch (e) {} finally { loading.brand = false }
}
const onLogoChange = async (uploadFile) => {
  const file = uploadFile.raw
  if (!file) return
  uploading.logo = true
  try {
    const r = await uploadBrandLogo(file)
    brandForm.logoUrl = r.logoUrl
    ElMessage.success('Logo 已上传')
  } catch (e) {} finally { uploading.logo = false }
}
const saveBrandCfg = async () => {
  saving.brand = true
  try {
    const r = await saveBrand({ ...brandForm })
    brand.apply(r.config)
    ElMessage.success('已保存')
  } catch (e) {} finally { saving.brand = false }
}

// ---- 检测灵敏度 ----
const CLASS_NAMES = ['反光衣', '跌倒', '未戴安全帽', '安全帽', '打电话', '吸烟']
const HIGH = ['跌倒', '未戴安全帽', '吸烟']
const MID = ['打电话']
const riskTagType = (c) => (HIGH.includes(c) ? 'danger' : MID.includes(c) ? 'warning' : 'success')
const riskNote = (c) => (HIGH.includes(c) ? '高危' : MID.includes(c) ? '中危' : '合规/低危')
const classConfs = reactive({})
const loadConfs = async () => {
  loading.confs = true
  try {
    const r = await getClassConfs()
    for (const n of CLASS_NAMES) classConfs[n] = r.config[n] ?? 0.5
  } catch (e) {} finally { loading.confs = false }
}
const saveConfsCfg = async () => {
  saving.confs = true
  try { await saveClassConfs({ ...classConfs }); ElMessage.success('已保存，立即生效') }
  catch (e) {} finally { saving.confs = false }
}
const resetConfs = () => { for (const n of CLASS_NAMES) classConfs[n] = 0.5 }

// ---- 告警声音 ----
const soundUrl = ref('')
const loadSound = async () => {
  loading.sound = true
  try { soundUrl.value = (await getAlertSound()).url || '' } catch (e) {} finally { loading.sound = false }
}
const onSoundChange = async (uploadFile) => {
  const file = uploadFile.raw
  if (!file) return
  uploading.sound = true
  try {
    const r = await uploadAlertSound(file)
    soundUrl.value = r.url
    setCustomSound(r.url)
    ElMessage.success('告警音已更新，立即生效')
  } catch (e) {} finally { uploading.sound = false }
}
const previewSound = () => {
  if (!soundUrl.value) return
  const a = new Audio(soundUrl.value)
  a.play().catch(() => ElMessage.warning('浏览器拒绝自动播放，点击页面后再试'))
}
const clearSound = async () => {
  try {
    await clearAlertSound()
    soundUrl.value = ''
    setCustomSound('')
    ElMessage.success('已恢复内置蜂鸣')
  } catch (e) {}
}

// ---- 数据保留 ----
const retention = reactive({
  retention_records: 90, retention_clips: 30, retention_audits: 180, retention_backups: 30,
})
const lastCleanup = ref(null)
const loadRetention = async () => {
  loading.retention = true
  try { Object.assign(retention, (await getRetention()).config) } catch (e) {} finally { loading.retention = false }
}
const saveRetentionCfg = async () => {
  saving.retention = true
  try { await saveRetention({ ...retention }); ElMessage.success('已保存') }
  catch (e) {} finally { saving.retention = false }
}
const runCleanupNow = async () => {
  running.cleanup = true
  try {
    const r = await runCleanup()
    lastCleanup.value = r.stats
    ElMessage.success('清理完成')
  } catch (e) {} finally { running.cleanup = false }
}

// ---- 系统健康 ----
const health = reactive({})
const loadHealth = async () => {
  loading.health = true
  try { Object.assign(health, (await getHealthDetail()).metrics) } catch (e) {} finally { loading.health = false }
}
const diskStatus = computed(() => {
  const p = health.diskPercent || 0
  if (p > 90) return 'exception'
  if (p > 75) return 'warning'
  return 'success'
})

// =============== AI 告警分级 ===============
const triageEnabled = ref(false)
const loadTriage = async () => {
  loading.triage = true
  try {
    const r = await getTriageEnabled()
    triageEnabled.value = !!r.enabled
  } catch (e) { /* */ } finally { loading.triage = false }
}
const saveTriageCfg = async () => {
  try {
    await saveTriageEnabled(triageEnabled.value)
    ElMessage.success(triageEnabled.value ? '已启用 AI 告警分级' : '已关闭 AI 告警分级')
  } catch (e) { /* */ }
}

// =============== 复核 LLM 服务商 ===============
const llm = reactive({ providers: [], preferred_id: '', supported: [] })
const llmDlg = reactive({
  visible: false, isEdit: false, saving: false, showKey: false,
  form: { id: '', name: '', provider: 'qwen', base_url: '', model: '', api_key: '' },
})
const PROVIDER_META = {
  qwen:   { label: '通义千问', tag: 'success' },
  zhipu:  { label: '智谱 GLM', tag: 'primary' },
  openai: { label: 'OpenAI', tag: 'info' },
  doubao: { label: '豆包 Vision', tag: 'warning' },
}
const providerLabel = (p) => PROVIDER_META[p]?.label || p
const providerTagType = (p) => PROVIDER_META[p]?.tag || 'info'

const loadLLM = async () => {
  loading.llm = true
  try {
    const r = await listLLMProviders()
    // 给每行加个 _testing 字段方便控制 loading
    llm.providers = (r.providers || []).map((p) => ({ ...p, _testing: false }))
    llm.preferred_id = r.preferred_id || ''
    llm.supported = r.supported || []
  } catch (e) { /* */ } finally { loading.llm = false }
}

const openLLMAdd = () => {
  llmDlg.isEdit = false
  llmDlg.form = { id: '', name: '', provider: 'qwen', base_url: '', model: '', api_key: '' }
  // 默认填厂商对应 base_url / model
  onLLMProviderChange('qwen')
  llmDlg.visible = true
}

const openLLMEdit = (row) => {
  llmDlg.isEdit = true
  llmDlg.form = {
    id: row.id, name: row.name, provider: row.provider,
    base_url: row.base_url || '', model: row.model || '', api_key: '',
  }
  llmDlg.visible = true
}

const onLLMProviderChange = (p) => {
  const sup = llm.supported.find((s) => s.provider === p)
  if (sup) {
    if (!llmDlg.form.base_url) llmDlg.form.base_url = sup.base_url
    if (!llmDlg.form.model) llmDlg.form.model = sup.default_model
  }
}

const doLLMSave = async () => {
  const f = llmDlg.form
  if (!f.name.trim()) return ElMessage.warning('请填写显示名称')
  if (!llmDlg.isEdit && !f.api_key.trim()) return ElMessage.warning('请填写 API Key')
  llmDlg.saving = true
  try {
    if (llmDlg.isEdit) {
      await updateLLMProvider(f.id, {
        name: f.name, provider: f.provider, base_url: f.base_url,
        model: f.model, api_key: f.api_key,
      })
    } else {
      await createLLMProvider({
        name: f.name, provider: f.provider, base_url: f.base_url,
        model: f.model, api_key: f.api_key,
      })
    }
    llmDlg.visible = false
    ElMessage.success('已保存')
    await loadLLM()
  } catch (e) { /* */ } finally { llmDlg.saving = false }
}

const doLLMDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除「${row.name}」?`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await deleteLLMProvider(row.id)
    ElMessage.success('已删除')
    await loadLLM()
  } catch (e) { /* */ }
}

const setLLMMain = async (row) => {
  if (llm.preferred_id === row.id) return
  try {
    await setLLMPreferred(row.id)
    llm.preferred_id = row.id
    ElMessage.success(`已切换主用 LLM 为「${row.name}」`)
  } catch (e) { /* */ }
}

const doLLMTest = async (row) => {
  row._testing = true
  try {
    const r = await testLLMProvider(row.id)
    if (r.ok) ElMessage.success('✅ ' + r.msg)
    else ElMessage.error('❌ ' + r.msg)
  } catch (e) {
    ElMessage.error('❌ 测试失败')
  } finally { row._testing = false }
}

onMounted(() => {
  loadAlert()
  loadBrand()
  loadConfs()
  loadSound()
  loadRetention()
  loadHealth()
  loadTriage()
  loadLLM()
})
</script>

<style scoped>
.box { border-radius: 10px; }
.tip { color: #aaa; font-size: 12px; margin-left: 10px; }
.tip-label { color: #888; margin-right: 6px; }
.logo-row { display: flex; align-items: center; gap: 12px; }
.logo-preview {
  width: 80px; height: 80px;
  border: 1px dashed #d0d6df;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  background: #fafbfc;
}
.logo-preview img { max-width: 100%; max-height: 100%; object-fit: contain; }
.logo-empty { color: #bbb; font-size: 12px; }
.sens-row {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed #f0f0f0;
}
.sens-label {
  width: 160px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sens-note { color: #aaa; font-size: 12px; }
.sens-val {
  font-weight: bold;
  color: #0a5a2c;
  min-width: 44px;
  font-family: Consolas, monospace;
}
.sound-row { display: flex; flex-direction: column; gap: 6px; }

/* ===== 系统健康 KPI 卡 ===== */
.hk-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
}
.hk-card.mini { padding: 10px 14px; }
.hk-eyebrow {
  color: var(--text-3);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.hk-num {
  font-size: 26px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--text);
  line-height: 1;
}
.hk-num.small { font-size: 20px; }
.hk-of { font-size: 12px; color: var(--text-3); font-weight: 400; margin-left: 2px; }
.hk-sub { color: var(--text-3); font-size: 12px; margin-top: 6px; }
</style>
