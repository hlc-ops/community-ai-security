<template>
  <div>
    <div class="page-title">工地安防违规目标识别</div>
    <div class="page-desc">上传图片，AI 智能识别并检测违规作业目标，结果自动存入检测记录。</div>

    <!-- 置信度 -->
    <el-card shadow="never" class="conf-card">
      <div class="conf-row">
        <span class="conf-label">置信度阈值</span>
        <el-slider
          v-model="conf"
          :min="0.1"
          :max="0.9"
          :step="0.05"
          :format-tooltip="(v) => v.toFixed(2)"
          style="width: 260px"
        />
        <span class="conf-value">{{ conf.toFixed(2) }}</span>
        <span class="conf-hint">值越高越严格（漏检多）、越低越敏感（误报多）</span>
      </div>
    </el-card>

    <el-row :gutter="20" style="margin-top: 20px">
      <!-- 上传区 -->
      <el-col :span="12">
        <el-card shadow="hover" class="box upload-card">
          <div class="box-title">
            <span>{{ originUrl ? '原图预览' : '上传图片' }}</span>
            <el-upload
              v-if="originUrl"
              :show-file-list="false"
              :auto-upload="false"
              accept="image/*"
              :on-change="onFileChange"
              style="display: inline-block"
            >
              <el-button link type="primary" size="small">重新上传</el-button>
            </el-upload>
          </div>

          <!-- 未上传：大拖拽框 -->
          <el-upload
            v-if="!originUrl"
            drag
            :show-file-list="false"
            :auto-upload="false"
            accept="image/*"
            :on-change="onFileChange"
          >
            <el-icon class="upload-ico"><UploadFilled /></el-icon>
            <div class="upload-text">将图片拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="upload-tip">支持 JPG / PNG / BMP / WEBP，建议单张 &lt; 10MB</div>
            </template>
          </el-upload>

          <!-- 已上传：原图与结果图同位置同高度 -->
          <el-image
            v-else
            :src="originUrl"
            fit="contain"
            class="result-img"
            :preview-src-list="[originUrl]"
            :preview-teleported="true"
          />
          <div v-if="originUrl" class="img-hint">点击图片可放大查看</div>
        </el-card>
      </el-col>

      <!-- 结果区 -->
      <el-col :span="12">
        <el-card shadow="hover" class="box" v-loading="loading" element-loading-text="检测中…">
          <div class="box-title">识别结果</div>

          <el-empty v-if="!result" description="暂无识别结果" />

          <template v-else>
            <el-image
              :src="result.img"
              fit="contain"
              class="result-img"
              :preview-src-list="[result.img]"
              :preview-teleported="true"
            />
            <div class="img-hint">点击图片可放大查看</div>

            <el-alert
              v-if="result.risk === 'high'"
              title="⚠️ 检测到高危违规！"
              type="error"
              :closable="false"
              show-icon
              style="margin-top: 12px"
            />
            <el-alert
              v-else-if="result.risk === 'mid'"
              title="⚠️ 检测到中危违规！"
              type="warning"
              :closable="false"
              show-icon
              style="margin-top: 12px"
            />
            <el-alert
              v-else-if="!result.safetyReview"
              title="✅ 现场安全正常"
              type="success"
              :closable="false"
              show-icon
              style="margin-top: 12px"
            />
            <!-- LLM 安全复核结果(YOLO 无检测时自动触发)-->
            <el-alert
              v-else-if="result.safetyReview?.ok && result.safetyReview.truly_safe"
              title="✅ AI 大模型复核:确认安全"
              type="success"
              :description="result.safetyReview.description"
              :closable="false"
              show-icon
              style="margin-top: 12px"
            />
            <el-alert
              v-else-if="result.safetyReview?.ok && !result.safetyReview.truly_safe"
              title="⚠️ AI 大模型发现潜在隐患"
              type="warning"
              :description="`${result.safetyReview.description}｜建议:${result.safetyReview.advice}`"
              :closable="false"
              show-icon
              style="margin-top: 12px"
            />

            <div class="cls-wrap" v-if="result.cls_list?.length">
              <span class="cls-title">命中类别：</span>
              <el-tag
                v-for="(c, i) in result.cls_list"
                :key="i"
                :type="c.startsWith('[LLM]') ? 'info' : riskTagType(c)"
                :effect="c.startsWith('[LLM]') ? 'plain' : 'dark'"
                style="margin: 4px"
              >
                {{ c }}
              </el-tag>
            </div>
            <div v-else class="cls-wrap muted">未识别到目标</div>

            <!-- LLM 自动复核标记 -->
            <div v-if="result.safetyReview?.ok" class="auto-review-badge">
              <el-icon><MagicStick /></el-icon>
              <span>YOLO 空检测 → 自动触发 AI 大模型语义复核</span>
            </div>

            <div class="saved-tip" v-if="savedId">
              <el-icon><CircleCheck /></el-icon> 已存入检测记录（#{{ savedId }}）
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 双保险工作流（卖点可视化）-->
    <el-card shadow="never" class="workflow-card" style="margin-top: 20px">
      <div class="workflow-title">
        <span class="badge">双保险</span>
        <span>YOLO 快速初筛 + 视觉大模型语义精核 —— 两道关，降误报、出建议</span>
      </div>

      <el-steps :active="currentStep" finish-status="success" align-center style="margin-top: 16px">
        <el-step title="上传图片" :description="stepDesc(0)" />
        <el-step title="YOLO 初筛" :description="stepDesc(1)" />
        <el-step title="入库归档" :description="stepDesc(2)" />
        <el-step title="AI 大模型精核" :description="stepDesc(3)" />
      </el-steps>

      <el-row :gutter="20" style="margin-top: 24px">
        <el-col :span="12">
          <div class="stage-panel yolo">
            <div class="stage-header">
              <span class="stage-num">①</span>
              <span class="stage-title">第一阶段 · YOLO 初筛</span>
              <el-tag size="small" type="success" effect="plain">快·硬件友好</el-tag>
            </div>
            <div class="stage-body">
              <div v-if="!result" class="stage-empty">等待上传图片…</div>
              <template v-else>
                <div class="kv">
                  <span class="kv-k">风险等级</span>
                  <el-tag :type="riskColor(result.risk)" effect="dark" size="small">
                    {{ riskZh(result.risk) }}
                  </el-tag>
                </div>
                <div class="kv">
                  <span class="kv-k">检出目标</span>
                  <b>{{ result.boxes?.length || result.cls_list?.length || 0 }} 个</b>
                </div>
                <div class="kv vertical" v-if="result.cls_list?.length">
                  <span class="kv-k">命中类别</span>
                  <div class="cls-row">
                    <el-tag
                      v-for="(c, i) in result.cls_list"
                      :key="i"
                      :type="riskTagType(c)"
                      effect="dark"
                      size="small"
                      style="margin: 2px"
                    >{{ c }}</el-tag>
                  </div>
                </div>
                <div v-if="savedId" class="stage-foot">
                  → 已自动入库（记录 #{{ savedId }}），等待第二阶段复核
                </div>
              </template>
            </div>
          </div>
        </el-col>

        <el-col :span="12">
          <div class="stage-panel llm">
            <div class="stage-header">
              <span class="stage-num">②</span>
              <span class="stage-title">第二阶段 · AI 大模型精核</span>
              <el-tag size="small" type="warning" effect="plain">慢·语义理解</el-tag>
              <el-button
                v-if="savedId"
                type="primary"
                size="small"
                :loading="reviewing"
                @click="doReview"
                style="margin-left: auto"
              >
                {{ llmResult ? '重新复核' : '开始复核' }}
              </el-button>
            </div>
            <div class="stage-body">
              <div v-if="!savedId" class="stage-empty">等待第一阶段完成…</div>
              <template v-else-if="!llmResult">
                <div class="stage-pending">
                  <el-icon><MagicStick /></el-icon>
                  <span>初筛已完成，可触发视觉大模型对当前画面二次研判</span>
                </div>
              </template>
              <template v-else>
                <div class="kv">
                  <span class="kv-k">研判结论</span>
                  <el-tag :type="llmResult.confirmed ? 'danger' : 'success'" effect="dark" size="small">
                    {{ llmResult.confirmed ? '确认存在隐患' : '未发现隐患（疑似误报）' }}
                  </el-tag>
                </div>
                <div class="kv vertical">
                  <span class="kv-k">画面描述</span>
                  <p class="prose">{{ llmResult.description || '—' }}</p>
                </div>
                <div class="kv vertical">
                  <span class="kv-k">整改建议</span>
                  <p class="prose">{{ llmResult.advice || '—' }}</p>
                </div>
              </template>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { detectImage, createRecord } from '@/api/detect'
import { reviewRecord } from '@/api/llm'

const conf = ref(0.5)
const loading = ref(false)
const originUrl = ref('')
const result = ref(null)
const savedId = ref(null)
const reviewing = ref(false)
const llmResult = ref(null)

// 高危类别用于标签配色
const HIGH = ['跌倒', '未戴安全帽', '吸烟']
const MID = ['打电话']
const riskTagType = (c) => (HIGH.includes(c) ? 'danger' : MID.includes(c) ? 'warning' : 'success')

// 双保险流程：当前所处步骤（0=上传, 1=YOLO, 2=入库, 3=大模型, 4=全完成）
const currentStep = computed(() => {
  if (!originUrl.value) return 0
  if (!result.value) return 1
  if (!savedId.value) return 2
  if (!llmResult.value) return 3
  return 4
})
const stepDesc = (idx) => {
  switch (idx) {
    case 0: return originUrl.value ? '已选图' : '待上传'
    case 1: return result.value ? `${result.value.cls_list?.length || 0} 目标` : '推理中'
    case 2: return savedId.value ? `#${savedId.value}` : '待入库'
    case 3: return llmResult.value ? '已复核' : '可触发'
    default: return ''
  }
}
const riskZh = (r) => ({ high: '高危', mid: '中危', low: '安全/低危' }[r] || r)
const riskColor = (r) => ({ high: 'danger', mid: 'warning', low: 'success' }[r] || 'info')

const onFileChange = async (uploadFile) => {
  const file = uploadFile.raw
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  // 原图预览
  if (originUrl.value) URL.revokeObjectURL(originUrl.value)
  originUrl.value = URL.createObjectURL(file)
  result.value = null
  savedId.value = null
  llmResult.value = null

  loading.value = true
  try {
    const res = await detectImage(file, conf.value)
    result.value = res
    await saveRecord(res)
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

const saveRecord = async (res) => {
  try {
    const now = new Date().toISOString()
    const rec = await createRecord({
      type: 'img',
      risk: res.risk,
      clsList: res.cls_list || [],
      image: res.img,
      durationSeconds: 0.3,
      startedAt: now,
      endedAt: now,
    })
    savedId.value = rec.record?.id
  } catch (e) {
    /* 拦截器已提示 */
  }
}

const doReview = async () => {
  if (!savedId.value) return
  reviewing.value = true
  try {
    const res = await reviewRecord(savedId.value)
    llmResult.value = res.result
    ElMessage.success('大模型复核完成')
  } catch (e) {
    /* 拦截器已提示（含未配置 Key 的提示）*/
  } finally {
    reviewing.value = false
  }
}
</script>

<style scoped>
.conf-card {
  border-radius: 10px;
}
.conf-row {
  display: flex;
  align-items: center;
  gap: 14px;
}
.conf-label {
  font-weight: 600;
}
.conf-value {
  font-weight: bold;
  color: #0a5a2c;
  min-width: 42px;
}
.conf-hint {
  color: #aaa;
  font-size: 12px;
}
.box {
  border-radius: 10px;
  min-height: 460px;
}
.box-title {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 14px;
  color: #0a5a2c;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
/* 让虚线拖拽框撑满卡片可用高度 */
.upload-card :deep(.el-upload),
.upload-card :deep(.el-upload-dragger) {
  width: 100%;
}
.upload-card :deep(.el-upload-dragger) {
  height: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.upload-ico {
  font-size: 50px;
  color: #c0c4cc;
}
.upload-text {
  color: #888;
}
.upload-text em {
  color: #0a5a2c;
  font-style: normal;
}
.upload-tip {
  color: #aaa;
  font-size: 12px;
  margin-top: 8px;
}
.preview {
  margin-top: 16px;
}
.preview-label {
  color: #888;
  font-size: 13px;
  margin-bottom: 6px;
}
.preview-img,
.result-img {
  display: block;
  width: 100%;
  height: 340px;
  margin-top: 16px;
  border-radius: 6px;
  background: #f5f7fa;
  border: 1px solid #eee;
  cursor: zoom-in;
}
.result-img {
  margin-top: 0;
}
.img-hint {
  text-align: center;
  color: #aaa;
  font-size: 12px;
  margin-top: 6px;
}
.cls-wrap {
  margin-top: 14px;
}
.cls-title {
  font-size: 14px;
  color: #555;
}
.cls-wrap.muted {
  color: #aaa;
}
.auto-review-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 14px;
  padding: 6px 12px;
  background: linear-gradient(135deg, rgba(22, 179, 168, 0.1), rgba(91, 155, 255, 0.1));
  border: 1px dashed rgba(22, 179, 168, 0.3);
  border-radius: 6px;
  color: #16b3a8;
  font-size: 12px;
  font-weight: 500;
}
.saved-tip {
  margin-top: 12px;
  color: #52c41a;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* ===== 双保险工作流卡片 ===== */
.workflow-card {
  border-radius: 10px;
  background: linear-gradient(180deg, #f6fbf7 0%, #ffffff 80%);
  border: 1px solid #d9f0e1;
}
.workflow-title {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #0a5a2c;
  font-weight: 600;
  font-size: 15px;
}
.workflow-title .badge {
  background: linear-gradient(90deg, #0a5a2c, #1abf80);
  color: #fff;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  letter-spacing: 1px;
}
.stage-panel {
  border-radius: 10px;
  border: 1px solid #e6e8eb;
  padding: 14px 16px;
  background: #fff;
  min-height: 180px;
  display: flex;
  flex-direction: column;
}
.stage-panel.yolo { border-top: 3px solid #52c41a; }
.stage-panel.llm { border-top: 3px solid #faad14; }
.stage-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #eee;
}
.stage-num {
  background: #0a5a2c;
  color: #fff;
  width: 22px; height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 13px;
}
.stage-panel.llm .stage-num { background: #faad14; }
.stage-title { font-weight: 600; color: #333; font-size: 14px; }
.stage-body { flex: 1; color: #444; font-size: 14px; }
.stage-empty { color: #bbb; padding: 12px 0; }
.stage-pending {
  color: #666;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
}
.stage-foot {
  margin-top: 12px;
  color: #888;
  font-size: 12px;
  padding-top: 8px;
  border-top: 1px dashed #eee;
}
.kv {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  line-height: 1.6;
}
.kv.vertical {
  display: block;
}
.kv.vertical .kv-k { display: block; margin-bottom: 2px; }
.kv-k {
  color: #888;
  min-width: 64px;
  font-size: 13px;
}
.cls-row { display: flex; flex-wrap: wrap; }
.prose {
  color: #333;
  background: #fafbfc;
  border-radius: 6px;
  padding: 8px 10px;
  margin: 4px 0 0;
  line-height: 1.7;
}
</style>
