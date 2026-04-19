<template>
  <div class="home-container">
    <div class="bg-decoration" aria-hidden="true">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>

    <section class="hero-section">
      <div class="hero-copy">
        <div class="hero-eyebrow">
          <span class="eyebrow-dot"></span>
          Apple Glass Travel Experience
        </div>
        <div class="icon-wrapper">
          <span class="icon">
            <SmileOutlined />
          </span>
        </div>
        <h1 class="page-title">智行伴侣</h1>
        <p class="page-subtitle">
          一个面向个性化旅游规划的智能体系统。
        </p>

        <div class="hero-highlights">
          <div class="highlight-pill">多日行程自动编排</div>
          <div class="highlight-pill">天气、地图与预算联动</div>
          <div class="highlight-pill">生成后仍可继续编辑</div>
        </div>
      </div>

      <div class="hero-panel">
        <div class="hero-panel-card">
          <div class="panel-kicker">Trip Preview</div>
          <div class="panel-city">城市、预算、地图、每日安排</div>
          <div class="panel-text">
            满足你的个性化需求，生成专属的旅行计划。
          </div>
          <div class="panel-stats">
            <div class="stat-item">
              <span class="stat-label">个性化规划</span>
              <span class="stat-value">贴合偏好生成</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">多维信息整合</span>
              <span class="stat-value">路线天气预算联动</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <a-card class="form-card" :bordered="false">
      <div class="form-card-header">
        <div>
          <div class="card-kicker">Plan Your Journey</div>
          <h2 class="card-title">定制你的旅行偏好</h2>
        </div>
        <p class="card-description">
          输入你的目的地、日期与旅行偏好， 智行伴侣 会为你生成带有景点、路线、天气、预算和住宿建议的完整行程。
        </p>
      </div>

      <a-form :model="formData" layout="vertical" @finish="handleSubmit">
        <div class="form-section section-primary">
          <div class="section-header">
            <span class="section-icon">
              <EnvironmentOutlined />
            </span>
            <div>
              <div class="section-kicker">Step 01</div>
              <span class="section-title">目的地与日期</span>
            </div>
          </div>

          <a-row :gutter="24">
            <a-col :span="8">
              <a-form-item name="city" :rules="[{ required: true, message: '请输入目的地城市' }]">
                <template #label>
                  <span class="form-label">目的地城市</span>
                </template>
                <a-input
                  v-model:value="formData.city"
                  placeholder="例如: 北京"
                  size="large"
                  class="custom-input"
                >
                  <template #prefix>
                    <EnvironmentOutlined class="field-prefix" />
                  </template>
                </a-input>
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item name="start_date" :rules="[{ required: true, message: '请选择开始日期' }]">
                <template #label>
                  <span class="form-label">开始日期</span>
                </template>
                <a-date-picker
                  v-model:value="formData.start_date"
                  :disabled-date="disabledStartDate"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item name="end_date" :rules="[{ required: true, message: '请选择结束日期' }]">
                <template #label>
                  <span class="form-label">结束日期</span>
                </template>
                <a-date-picker
                  v-model:value="formData.end_date"
                  :disabled-date="disabledEndDate"
                  style="width: 100%"
                  size="large"
                  class="custom-input"
                  placeholder="选择日期"
                />
              </a-form-item>
            </a-col>
            <a-col :span="4">
              <a-form-item>
                <template #label>
                  <span class="form-label">旅行天数</span>
                </template>
                <div class="days-display-compact">
                  <span class="days-value">{{ formData.travel_days }}</span>
                  <span class="days-unit">天</span>
                </div>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <div class="form-section section-secondary">
          <div class="section-header">
            <span class="section-icon">
              <SettingOutlined />
            </span>
            <div>
              <div class="section-kicker">Step 02</div>
              <span class="section-title">偏好设置</span>
            </div>
          </div>

          <a-row :gutter="24">
            <a-col :span="8">
              <a-form-item name="transportation">
                <template #label>
                  <span class="form-label">交通方式</span>
                </template>
                <a-select v-model:value="formData.transportation" size="large" class="custom-select">
                  <a-select-option value="公共交通"><ApartmentOutlined class="option-icon" />公共交通</a-select-option>
                  <a-select-option value="自驾"><CarOutlined class="option-icon" />自驾</a-select-option>
                  <a-select-option value="步行"><AimOutlined class="option-icon" />步行</a-select-option>
                  <a-select-option value="混合"><DeploymentUnitOutlined class="option-icon" />混合</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item name="accommodation">
                <template #label>
                  <span class="form-label">住宿偏好</span>
                </template>
                <a-select v-model:value="formData.accommodation" size="large" class="custom-select">
                  <a-select-option value="经济型酒店"><WalletOutlined class="option-icon" />经济型酒店</a-select-option>
                  <a-select-option value="舒适型酒店"><HomeOutlined class="option-icon" />舒适型酒店</a-select-option>
                  <a-select-option value="豪华酒店"><StarOutlined class="option-icon" />豪华酒店</a-select-option>
                  <a-select-option value="民宿"><BankOutlined class="option-icon" />民宿</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item name="preferences">
                <template #label>
                  <span class="form-label">旅行偏好</span>
                </template>
                <div class="preference-tags">
                  <a-checkbox-group v-model:value="formData.preferences" class="custom-checkbox-group">
                    <a-checkbox value="历史文化" class="preference-tag"><BankOutlined class="option-icon" />历史文化</a-checkbox>
                    <a-checkbox value="自然风光" class="preference-tag"><PictureOutlined class="option-icon" />自然风光</a-checkbox>
                    <a-checkbox value="美食" class="preference-tag"><CoffeeOutlined class="option-icon" />美食</a-checkbox>
                    <a-checkbox value="购物" class="preference-tag"><ShopOutlined class="option-icon" />购物</a-checkbox>
                    <a-checkbox value="艺术" class="preference-tag"><HighlightOutlined class="option-icon" />艺术</a-checkbox>
                    <a-checkbox value="休闲" class="preference-tag"><HeartOutlined class="option-icon" />休闲</a-checkbox>
                  </a-checkbox-group>
                </div>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <div class="form-section section-secondary">
          <div class="section-header">
            <span class="section-icon">
              <MessageOutlined />
            </span>
            <div>
              <div class="section-kicker">Step 03</div>
              <span class="section-title">额外要求</span>
            </div>
          </div>

          <a-form-item name="free_text_input">
            <a-textarea
              v-model:value="formData.free_text_input"
              placeholder="请输入您的额外要求,例如:吃不了辣、不喜欢特种兵行程.."
              :rows="4"
              size="large"
              class="custom-textarea"
            />
          </a-form-item>
        </div>

        <div class="submit-section">
          <a-button
            type="primary"
            html-type="submit"
            :loading="loading"
            @click="handleStartClick"
            size="large"
            class="submit-button"
          >
            <template v-if="!loading">
              <SendOutlined class="button-icon" />
              <span>开始规划我的旅行</span>
            </template>
            <template v-else>
              <span>正在生成中...</span>
            </template>
          </a-button>
        </div>

        <div v-if="loading" class="loading-container">
          <a-progress
            :percent="loadingProgress"
            status="active"
            :stroke-color="{
              '0%': '#8a8fff',
              '100%': '#6d74ff',
            }"
            :stroke-width="10"
          />
          <p class="loading-status">{{ loadingStatus }}</p>
          <a-button danger ghost class="stop-button" @click="stopGeneration">
            停止生成
          </a-button>
        </div>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { generateTripPlan } from '@/services/api'
import {
  AimOutlined,
  ApartmentOutlined,
  BankOutlined,
  CarOutlined,
  CoffeeOutlined,
  DeploymentUnitOutlined,
  EnvironmentOutlined,
  HeartOutlined,
  HighlightOutlined,
  HomeOutlined,
  MessageOutlined,
  PictureOutlined,
  SendOutlined,
  SettingOutlined,
  ShopOutlined,
  SmileOutlined,
  StarOutlined,
  WalletOutlined
} from '@ant-design/icons-vue'
import type { TripFormData } from '@/types'
import type { Dayjs } from 'dayjs'

const router = useRouter()
const loading = ref(false)
const loadingProgress = ref(0)
const loadingStatus = ref('')
const dateValidationError = ref('')
const isGenerationCanceled = ref(false)
let progressInterval: ReturnType<typeof setInterval> | null = null
let requestController: AbortController | null = null

type TripFormState = Omit<TripFormData, 'start_date' | 'end_date'> & {
  start_date: Dayjs | null
  end_date: Dayjs | null
}

const formData = reactive<TripFormState>({
  city: '',
  start_date: null,
  end_date: null,
  travel_days: 1,
  transportation: '公共交通',
  accommodation: '经济型酒店',
  preferences: [],
  free_text_input: ''
})

// 监听日期变化,自动计算旅行天数
watch([() => formData.start_date, () => formData.end_date], ([start, end]) => {
  if (start && end) {
    const days = end.diff(start, 'day') + 1
    if (days > 0 && days <= 30) {
      dateValidationError.value = ''
      formData.travel_days = days
    } else if (days > 30) {
      dateValidationError.value = '旅行天数不能超过30天'
      message.warning('旅行天数不能超过30天')
      formData.end_date = null
    } else {
      dateValidationError.value = '结束日期不能早于开始日期'
      message.warning('结束日期不能早于开始日期')
      formData.end_date = null
    }
  } else if (!start && !end) {
    dateValidationError.value = ''
  }
})

const clearProgressInterval = () => {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

const resetLoadingState = () => {
  clearProgressInterval()
  requestController = null
  loading.value = false
  loadingProgress.value = 0
  loadingStatus.value = ''
  isGenerationCanceled.value = false
}

const disabledStartDate = (current: Dayjs) => {
  if (!formData.end_date) return false
  return current.isAfter(formData.end_date, 'day')
}

const disabledEndDate = (current: Dayjs) => {
  if (!formData.start_date) return false
  return current.isBefore(formData.start_date, 'day')
}

const handleStartClick = (event: MouseEvent) => {
  const city = formData.city.trim()

  if (!city) {
    event.preventDefault()
    message.warning('请输入目的地城市')
    return
  }

  if (dateValidationError.value === '结束日期不能早于开始日期') {
    event.preventDefault()
    message.warning(dateValidationError.value)
    return
  }

  if (!formData.start_date && !formData.end_date) {
    event.preventDefault()
    message.warning('请选择开始日期和结束日期')
    return
  }

  if (!formData.start_date) {
    event.preventDefault()
    message.warning('请选择开始日期')
    return
  }

  if (!formData.end_date) {
    event.preventDefault()
    message.warning('请选择结束日期')
  }
}

const stopGeneration = () => {
  isGenerationCanceled.value = true
  clearProgressInterval()
  requestController?.abort()
  message.info('已停止生成当前行程')
  resetLoadingState()
}

const handleSubmit = async () => {
  if (!formData.city.trim()) {
    message.warning('请输入目的地城市')
    return
  }

  if (dateValidationError.value === '结束日期不能早于开始日期') {
    message.warning(dateValidationError.value)
    return
  }

  if (!formData.start_date && !formData.end_date) {
    message.warning('请选择开始日期和结束日期')
    return
  }

  if (!formData.start_date) {
    message.warning('请选择开始日期')
    return
  }

  if (!formData.end_date) {
    message.warning('请选择结束日期')
    return
  }

  if (!formData.start_date || !formData.end_date) {
    return
  }

  requestController = new AbortController()
  loading.value = true
  loadingProgress.value = 0
  loadingStatus.value = '正在初始化...'
  isGenerationCanceled.value = false

  // 模拟进度更新
  progressInterval = setInterval(() => {
    if (loadingProgress.value < 90) {
      loadingProgress.value += 10

      // 更新状态文本
      if (loadingProgress.value <= 30) {
        loadingStatus.value = '正在搜索景点...'
      } else if (loadingProgress.value <= 50) {
        loadingStatus.value = '正在查询天气...'
      } else if (loadingProgress.value <= 70) {
        loadingStatus.value = '正在推荐酒店...'
      } else {
        loadingStatus.value = '正在生成行程计划...'
      }
    }
  }, 500)

  try {
    const requestData: TripFormData = {
      city: formData.city.trim(),
      start_date: formData.start_date.format('YYYY-MM-DD'),
      end_date: formData.end_date.format('YYYY-MM-DD'),
      travel_days: formData.travel_days,
      transportation: formData.transportation,
      accommodation: formData.accommodation,
      preferences: formData.preferences,
      free_text_input: formData.free_text_input
    }

    const response = await generateTripPlan(requestData, requestController.signal)

    clearProgressInterval()
    loadingProgress.value = 100
    loadingStatus.value = '已完成'

    if (response.success && response.data) {
      // 保存到sessionStorage
      sessionStorage.setItem('tripPlan', JSON.stringify(response.data))

      message.success('旅行计划生成成功!')

      // 短暂延迟后跳转
      setTimeout(() => {
        router.push('/result')
      }, 500)
    } else {
      message.error(response.message || '生成失败')
    }
  } catch (error: any) {
    clearProgressInterval()
    if (error.message === '已停止生成' || isGenerationCanceled.value) {
      return
    }
    message.error(error.message || '生成旅行计划失败,请稍后重试')
  } finally {
    const delay = isGenerationCanceled.value ? 0 : 1000
    setTimeout(() => {
      resetLoadingState()
    }, delay)
  }
}
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  padding: 48px 20px 72px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 36px;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.circle {
  position: relative;
  border-radius: 9999px;
  filter: blur(70px);
  opacity: 0.72;
  animation: floatBlob 12s ease-in-out infinite;
}

.circle-1 {
  position: absolute;
  width: 320px;
  height: 320px;
  top: 10%;
  left: -80px;
  background: radial-gradient(circle, rgba(124, 130, 255, 0.38), rgba(124, 130, 255, 0));
}

.circle-2 {
  position: absolute;
  width: 300px;
  height: 300px;
  top: 6%;
  right: 6%;
  background: radial-gradient(circle, rgba(141, 211, 255, 0.32), rgba(141, 211, 255, 0));
  animation-delay: -4s;
}

.circle-3 {
  position: absolute;
  width: 360px;
  height: 360px;
  bottom: -60px;
  left: 32%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0));
  animation-delay: -8s;
}

.hero-section {
  width: 100%;
  max-width: 1240px;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 420px);
  gap: 28px;
  align-items: stretch;
  position: relative;
  z-index: 1;
}

.hero-copy,
.hero-panel-card {
  background: rgba(255, 255, 255, 0.46);
  border: 1px solid rgba(255, 255, 255, 0.54);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  box-shadow: var(--shadow-xl);
}

.hero-copy {
  padding: 42px 44px;
  border-radius: var(--radius-3xl);
  animation: fadeInDown 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid rgba(255, 255, 255, 0.58);
  color: var(--primary-active);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.eyebrow-dot {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background: linear-gradient(135deg, #8a8fff, #6d74ff);
  box-shadow: 0 0 0 6px rgba(124, 130, 255, 0.12);
}

.icon-wrapper {
  margin: 28px 0 22px;
}

.icon {
  width: 86px;
  height: 86px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 44px;
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(255, 255, 255, 0.56));
  border: 1px solid rgba(255, 255, 255, 0.62);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.7),
    0 16px 40px rgba(124, 130, 255, 0.18);
  animation: floatIcon 4.4s ease-in-out infinite;
}

.page-title {
  margin: 0 0 18px;
  font-size: clamp(40px, 5vw, 64px);
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.03em;
  line-height: 1.05;
}

.page-subtitle {
  max-width: 720px;
  margin: 0;
  font-size: 18px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.hero-highlights {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}

.highlight-pill {
  padding: 12px 16px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.56);
  border: 1px solid rgba(255, 255, 255, 0.58);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.hero-panel {
  display: flex;
  align-items: stretch;
}

.hero-panel-card {
  width: 100%;
  border-radius: var(--radius-3xl);
  padding: 34px 30px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  animation: fadeInUp 0.9s cubic-bezier(0.16, 1, 0.3, 1);
}

.panel-kicker,
.section-kicker,
.card-kicker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--primary-active);
}

.panel-city {
  margin-top: 18px;
  font-size: 28px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.03em;
}

.panel-text {
  margin-top: 16px;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1.75;
}

.panel-stats {
  margin-top: 28px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.stat-item {
  padding: 16px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.52);
  border: 1px solid rgba(255, 255, 255, 0.56);
}

.stat-label {
  display: block;
  margin-bottom: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.stat-value {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}

.form-card {
  width: 100%;
  max-width: 1240px;
  margin: 0 auto;
  border-radius: 36px;
  box-shadow: var(--shadow-xl);
  animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  z-index: 1;
}

.form-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 30px;
}

.card-title {
  margin: 8px 0 0;
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.1;
  letter-spacing: -0.03em;
  color: var(--text-primary);
}

.card-description {
  max-width: 420px;
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.75;
}

.form-section {
  margin-bottom: 22px;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.52);
  padding: 28px 28px 10px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.section-primary {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.58), rgba(255, 255, 255, 0.34));
}

.section-secondary {
  background: rgba(255, 255, 255, 0.46);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}

.section-icon {
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  border-radius: 16px;
  color: var(--primary-color);
  background: rgba(255, 255, 255, 0.64);
  border: 1px solid rgba(255, 255, 255, 0.55);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.64);
}

.section-title {
  display: block;
  margin-top: 4px;
  font-size: 21px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.custom-input,
.custom-select {
  width: 100%;
  height: 48px;
}

:deep(.custom-input.ant-input-affix-wrapper) {
  height: 48px;
  padding: 0 14px;
  border-width: 1px !important;
}

:deep(.custom-input.ant-input-affix-wrapper .ant-input) {
  border: none !important;
  border-width: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
  outline: none !important;
}

.custom-input :deep(.ant-input-affix-wrapper .ant-input:focus) {
  border: none !important;
  border-width: 0 !important;
  box-shadow: none !important;
  outline: none !important;
}

.custom-input :deep(.ant-input),
.custom-input :deep(input) {
  height: 100%;
  background: transparent !important;
}

.custom-select :deep(.ant-select-selector) {
  height: 48px !important;
  display: flex;
  align-items: center;
}

.field-prefix {
  color: var(--primary-active);
  font-size: 16px;
}

.option-icon {
  margin-right: 8px;
  color: var(--primary-active);
  font-size: 14px;
}

.days-display-compact {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.58);
  border-radius: 18px;
  color: var(--text-primary);
  font-weight: 700;
  font-size: 18px;
  gap: 4px;
}

.days-unit {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 600;
}

.preference-tags {
  width: 100%;
}

.custom-checkbox-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  width: 100%;
}

.preference-tag {
  margin: 0;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.56);
  border-radius: 18px;
  transition: all var(--transition-fast);
  background: rgba(255, 255, 255, 0.58);
  display: flex;
  align-items: center;
  justify-content: center;
}

.preference-tag:hover {
  border-color: rgba(124, 130, 255, 0.34);
  background: rgba(255, 255, 255, 0.84);
  transform: translateY(-1px);
}

.preference-tag :deep(.ant-checkbox) {
  display: none;
}

.preference-tag :deep(span:last-child) {
  padding: 0;
  font-weight: 500;
  color: var(--text-secondary);
}

.custom-checkbox-group :deep(.ant-checkbox-wrapper-checked) {
  border-color: rgba(124, 130, 255, 0.4);
  background: rgba(124, 130, 255, 0.1);
}

.custom-checkbox-group :deep(.ant-checkbox-wrapper-checked span:last-child) {
  color: var(--primary-active);
  font-weight: 600;
}

.submit-section {
  margin-top: 34px;
  display: flex;
  justify-content: center;
}

.submit-button {
  width: min(380px, 100%);
  height: 60px !important;
  font-size: 17px !important;
  border-radius: 9999px !important;
  font-weight: 600 !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.42),
    0 20px 40px rgba(109, 116, 255, 0.3) !important;
}

.button-icon {
  margin-right: 8px;
  font-size: 18px;
}

.loading-container {
  margin-top: 24px;
  padding: 24px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.56);
  border: 1px solid rgba(255, 255, 255, 0.58);
  text-align: center;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.loading-status {
  margin-top: 16px;
  font-size: 16px;
  color: var(--primary-color);
  font-weight: 600;
  animation: pulse 1.5s ease-in-out infinite;
}

.stop-button {
  margin-top: 16px;
  min-width: 140px;
  height: 40px;
  border-radius: 9999px;
}

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes floatBlob {
  0%, 100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(24px, -18px, 0) scale(1.05);
  }
}

@keyframes floatIcon {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-8px);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

@media (max-width: 992px) {
  .hero-section {
    grid-template-columns: 1fr;
  }

  .hero-panel {
    order: -1;
  }

  .form-card-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .form-card {
    border-radius: 30px;
  }

  .custom-checkbox-group {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .home-container {
    padding: 28px 8px 48px;
  }

  .hero-copy,
  .hero-panel-card {
    padding: 28px 22px;
  }

  .page-title {
    font-size: 34px;
  }

  .page-subtitle {
    font-size: 16px;
  }

  .icon {
    width: 74px;
    height: 74px;
    border-radius: 24px;
    font-size: 38px;
  }

  .panel-stats {
    grid-template-columns: 1fr;
  }

  .form-section {
    padding: 22px 18px 6px;
  }

  .ant-col {
    width: 100% !important;
    max-width: 100% !important;
    flex: 0 0 100% !important;
    margin-bottom: 16px;
  }

  .custom-checkbox-group {
    grid-template-columns: 1fr;
  }

  .submit-button {
    width: 100%;
  }
}
</style>
