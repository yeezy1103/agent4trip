<template>
  <div class="result-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <a-button class="back-button" size="large" @click="goBack">
        ← 返回首页
      </a-button>
      <a-space size="middle">
        <a-button v-if="!editMode" @click="toggleEditMode" type="default">
          ✏️ 编辑行程
        </a-button>
        <a-button v-else @click="saveChanges" type="primary">
          💾 保存修改
        </a-button>
        <a-button v-if="editMode" @click="cancelEdit" type="default">
          ❌ 取消编辑
        </a-button>

        <!-- 导出按钮 -->
        <a-dropdown v-if="!editMode">
          <template #overlay>
            <a-menu>
              <a-menu-item key="image" @click="exportAsImage">
                📷 导出为图片
              </a-menu-item>
              <a-menu-item key="pdf" @click="exportAsPDF">
                📄 导出为PDF
              </a-menu-item>
            </a-menu>
          </template>
          <a-button type="default">
            📥 导出行程 <DownOutlined />
          </a-button>
        </a-dropdown>
      </a-space>
    </div>

    <div v-if="tripPlan" class="content-wrapper">
      <!-- 侧边导航 -->
      <div class="side-nav">
        <a-affix :offset-top="80">
          <a-menu mode="inline" :selectedKeys="[activeSection]" :defaultOpenKeys="['days']" @click="scrollToSection">
            <a-menu-item key="overview">
              <span>📋 行程概览</span>
            </a-menu-item>
            <a-menu-item key="budget" v-if="tripPlan.budget">
              <span>💰 预算明细</span>
            </a-menu-item>
            <a-menu-item key="map">
              <span>📍 景点地图</span>
            </a-menu-item>
            <a-sub-menu key="days" title="📅 每日行程">
              <a-menu-item v-for="(day, index) in tripPlan.days" :key="`day-${index}`">
                第{{ day.day_index + 1 }}天
              </a-menu-item>
            </a-sub-menu>

          </a-menu>
        </a-affix>
      </div>

      <!-- 主内容区 -->
      <div class="main-content">
        <!-- 行程概览 -->
        <a-card id="overview" :title="`${tripPlan.city}旅行计划`" :bordered="false" class="overview-card">
          <div class="overview-content">
            <div class="info-item">
              <span class="info-label">📅 日期:</span>
              <span class="info-value">{{ tripPlan.start_date }} 至 {{ tripPlan.end_date }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">💡 建议:</span>
              <span class="info-value">{{ tripPlan.overall_suggestions }}</span>
            </div>
          </div>
        </a-card>

        <!-- 预算明细 -->
        <a-card id="budget" v-if="tripPlan.budget" title="💰 预算明细" :bordered="false" class="budget-card">
          <div class="budget-grid">
            <div class="budget-item">
              <div class="budget-label">景点门票</div>
              <div class="budget-value">¥{{ tripPlan.budget.total_attractions }}</div>
            </div>
            <div class="budget-item">
              <div class="budget-label">酒店住宿</div>
              <div class="budget-value">¥{{ tripPlan.budget.total_hotels }}</div>
            </div>
            <div class="budget-item">
              <div class="budget-label">餐饮费用</div>
              <div class="budget-value">¥{{ tripPlan.budget.total_meals }}</div>
            </div>
            <div class="budget-item">
              <div class="budget-label">交通费用</div>
              <div class="budget-value">¥{{ tripPlan.budget.total_transportation }}</div>
            </div>
          </div>
          <div class="budget-total">
            <span class="total-label">预估总费用</span>
            <span class="total-value">¥{{ tripPlan.budget.total }}</span>
          </div>
        </a-card>

        <!-- 景点地图 -->
        <a-card id="map" title="📍 景点地图" :bordered="false" class="map-card">
          <div id="amap-container" style="width: 100%; height: 100%"></div>
        </a-card>

        <!-- 每日行程:可折叠 -->
        <a-card title="📅 每日行程" :bordered="false" class="days-card">
          <a-collapse v-model:activeKey="activeDays" accordion>
            <a-collapse-panel
              v-for="(day, index) in tripPlan.days"
              :key="index"
              :id="`day-${index}`"
            >
              <template #header>
                <div class="day-header">
                  <span class="day-title">第{{ day.day_index + 1 }}天</span>
                  <span class="day-date">{{ day.date }}</span>
                </div>
              </template>

              <!-- 每日天气整合区块 -->
              <div class="day-weather-banner" v-if="getWeatherForDay(day.date)">
                <div class="weather-item">
                  <span class="weather-icon">☀️</span>
                  <div class="weather-details">
                    <span class="weather-time">白天</span>
                    <span class="weather-temp">{{ getWeatherForDay(day.date)?.day_weather }} {{ getWeatherForDay(day.date)?.day_temp }}°C</span>
                  </div>
                </div>
                <div class="weather-divider"></div>
                <div class="weather-item">
                  <span class="weather-icon">🌙</span>
                  <div class="weather-details">
                    <span class="weather-time">夜间</span>
                    <span class="weather-temp">{{ getWeatherForDay(day.date)?.night_weather }} {{ getWeatherForDay(day.date)?.night_temp }}°C</span>
                  </div>
                </div>
                <div class="weather-divider"></div>
                <div class="weather-item wind-info">
                  <span class="weather-icon">💨</span>
                  <div class="weather-details">
                    <span class="weather-time">风向风力</span>
                    <span class="weather-temp">{{ getWeatherForDay(day.date)?.wind_direction }} {{ getWeatherForDay(day.date)?.wind_power }}</span>
                  </div>
                </div>
              </div>

              <!-- 行程基本信息 -->
              <div class="day-info">
                <div class="info-row">
                  <span class="label">📝 行程描述:</span>
                  <span class="value">{{ day.description }}</span>
                </div>
                <div class="info-row">
                  <span class="label">🚗 交通方式:</span>
                  <span class="value">{{ day.transportation }}</span>
                </div>
                <div class="info-row">
                  <span class="label">🏨 住宿:</span>
                  <span class="value">{{ day.accommodation }}</span>
                </div>
              </div>

              <!-- 景点安排 -->
              <a-divider orientation="left">🎯 景点安排</a-divider>
              <a-list
                :data-source="day.attractions"
                :grid="{ gutter: 16, column: 2 }"
              >
                <template #renderItem="{ item, index }">
                  <a-list-item>
                    <div class="attraction-card-container">
                      <!-- 背景图片 -->
                      <img
                        :src="getAttractionImage(item.name, index)"
                        :alt="item.name"
                        class="attraction-bg-image"
                        @error="handleImageError"
                      />

                      <!-- 顶部角标层 -->
                      <div class="attraction-top-badges">
                        <div class="attraction-badge">
                          <span class="badge-number">{{ index + 1 }}</span>
                        </div>
                        <div v-if="item.ticket_price" class="price-tag">
                          ¥{{ item.ticket_price }}
                        </div>
                      </div>

                      <!-- 底部信息液态玻璃层 -->
                      <div class="attraction-info-overlay">
                        <LiquidGlass
                          :displacement-scale="40"
                          :blur-amount="0.15"
                          :saturation="120"
                          :aberration-intensity="2"
                          :elasticity="0.1"
                          :corner-radius="24"
                          style="width: 100%;"
                        >
                          <div class="attraction-content-glass">
                            <div class="attraction-header">
                              <h3 class="attraction-title">{{ item.name }}</h3>
                              <!-- 编辑模式下的操作按钮 -->
                              <a-space v-if="editMode" class="attraction-actions">
                                <a-button
                                  size="small"
                                  @click="moveAttraction(day.day_index, index, 'up')"
                                  :disabled="index === 0"
                                >
                                  ↑
                                </a-button>
                                <a-button
                                  size="small"
                                  @click="moveAttraction(day.day_index, index, 'down')"
                                  :disabled="index === day.attractions.length - 1"
                                >
                                  ↓
                                </a-button>
                                <a-button
                                  size="small"
                                  danger
                                  @click="deleteAttraction(day.day_index, index)"
                                >
                                  🗑️
                                </a-button>
                              </a-space>
                            </div>

                            <div class="attraction-body" :class="{ 'edit-mode': editMode }">
                              <!-- 编辑模式下可编辑的字段 -->
                              <div v-if="editMode">
                                <p><strong>地址:</strong></p>
                                <a-input v-model:value="item.address" size="small" style="margin-bottom: 8px; background: rgba(255,255,255,0.8);" />

                                <p><strong>游览时长(分钟):</strong></p>
                                <a-input-number v-model:value="item.visit_duration" :min="10" :max="480" size="small" style="width: 100%; margin-bottom: 8px; background: rgba(255,255,255,0.8);" />

                                <p><strong>描述:</strong></p>
                                <a-textarea v-model:value="item.description" :rows="2" size="small" style="margin-bottom: 8px; background: rgba(255,255,255,0.8);" />
                              </div>

                              <!-- 查看模式 -->
                              <div v-else>
                                <p><strong>地址:</strong> {{ item.address }}</p>
                                <p><strong>游览时长:</strong> {{ item.visit_duration }}分钟</p>
                                <p class="description-text"><strong>描述:</strong> {{ item.description }}</p>
                                <p v-if="item.rating"><strong>评分:</strong> {{ item.rating }}⭐</p>
                              </div>
                            </div>
                          </div>
                        </LiquidGlass>
                      </div>
                    </div>
                  </a-list-item>
                </template>
              </a-list>

              <!-- 酒店推荐 -->
              <a-divider v-if="day.hotel" orientation="left">🏨 住宿推荐</a-divider>
              <a-card v-if="day.hotel" size="small" class="hotel-card">
                <template #title>
                  <span class="hotel-title">{{ day.hotel.name }}</span>
                </template>
                <a-descriptions :column="2" size="small">
                  <a-descriptions-item label="地址">{{ day.hotel.address }}</a-descriptions-item>
                  <a-descriptions-item label="类型">{{ day.hotel.type }}</a-descriptions-item>
                  <a-descriptions-item label="价格范围">{{ day.hotel.price_range }}</a-descriptions-item>
                  <a-descriptions-item label="评分">{{ day.hotel.rating }}⭐</a-descriptions-item>
                  <a-descriptions-item label="距离" :span="2">{{ day.hotel.distance }}</a-descriptions-item>
                </a-descriptions>
              </a-card>

              <!-- 餐饮安排 -->
              <a-divider orientation="left">🍽️ 餐饮安排</a-divider>
              <a-descriptions :column="1" bordered size="small">
                <a-descriptions-item
                  v-for="meal in day.meals"
                  :key="meal.type"
                  :label="getMealLabel(meal.type)"
                >
                  {{ meal.name }}
                  <span v-if="meal.description"> - {{ meal.description }}</span>
                </a-descriptions-item>
              </a-descriptions>
            </a-collapse-panel>
          </a-collapse>
        </a-card>


      </div>
    </div>

    <a-empty v-else description="没有找到旅行计划数据">
      <template #image>
        <div style="font-size: 80px;">🗺️</div>
      </template>
      <template #description>
        <span style="color: #999;">暂无旅行计划数据,请先创建行程</span>
      </template>
      <a-button type="primary" @click="goBack">返回首页创建行程</a-button>
    </a-empty>

    <!-- 回到顶部按钮 -->
    <a-back-top :visibility-height="300">
      <div class="back-top-button">
        ↑
      </div>
    </a-back-top>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { DownOutlined } from '@ant-design/icons-vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'
import type { TripPlan } from '@/types'

const router = useRouter()
const tripPlan = ref<TripPlan | null>(null)
const editMode = ref(false)
const originalPlan = ref<TripPlan | null>(null)
const attractionPhotos = ref<Record<string, string>>({})
const activeSection = ref('overview')
const activeDays = ref<number[]>([0]) // 默认展开第一天
let map: any = null

onMounted(async () => {
  const data = sessionStorage.getItem('tripPlan')
  if (data) {
    tripPlan.value = JSON.parse(data)
    // 等待DOM渲染完成后初始化地图
    await nextTick()
    setTimeout(() => {
      initMap()
    }, 100) // 给DOM一个微小的稳定时间，避免由于高度/宽度未及时计算导致地图渲染失败
    // 并行加载景点图片，不阻塞地图初始化
    loadAttractionPhotos()
  }
})

const goBack = () => {
  router.push('/')
}

// 滚动到指定区域
const scrollToSection = ({ key }: { key: string }) => {
  activeSection.value = key
  const element = document.getElementById(key)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// 切换编辑模式
const toggleEditMode = () => {
  editMode.value = true
  // 保存原始数据用于取消编辑
  originalPlan.value = JSON.parse(JSON.stringify(tripPlan.value))
  message.info('进入编辑模式')
}

// 保存修改
const saveChanges = () => {
  editMode.value = false
  // 更新sessionStorage
  if (tripPlan.value) {
    sessionStorage.setItem('tripPlan', JSON.stringify(tripPlan.value))
  }
  message.success('修改已保存')

  // 重新初始化地图以反映更改
  if (map) {
    map.destroy()
  }
  nextTick(() => {
    initMap()
  })
}

// 获取某天的天气
const getWeatherForDay = (date: string) => {
  if (!tripPlan.value?.weather_info) return null
  return tripPlan.value.weather_info.find(w => w.date === date)
}

// 取消编辑
const cancelEdit = () => {
  if (originalPlan.value) {
    tripPlan.value = JSON.parse(JSON.stringify(originalPlan.value))
  }
  editMode.value = false
  message.info('已取消编辑')
}

// 删除景点
const deleteAttraction = (dayIndex: number, attrIndex: number) => {
  if (!tripPlan.value) return

  const day = tripPlan.value.days[dayIndex]
  if (day.attractions.length <= 1) {
    message.warning('每天至少需要保留一个景点')
    return
  }

  day.attractions.splice(attrIndex, 1)
  message.success('景点已删除')
}

// 移动景点顺序
const moveAttraction = (dayIndex: number, attrIndex: number, direction: 'up' | 'down') => {
  if (!tripPlan.value) return

  const day = tripPlan.value.days[dayIndex]
  const attractions = day.attractions

  if (direction === 'up' && attrIndex > 0) {
    [attractions[attrIndex], attractions[attrIndex - 1]] = [attractions[attrIndex - 1], attractions[attrIndex]]
  } else if (direction === 'down' && attrIndex < attractions.length - 1) {
    [attractions[attrIndex], attractions[attrIndex + 1]] = [attractions[attrIndex + 1], attractions[attrIndex]]
  }
}

const getMealLabel = (type: string): string => {
  const labels: Record<string, string> = {
    breakfast: '早餐',
    lunch: '午餐',
    dinner: '晚餐',
    snack: '小吃'
  }
  return labels[type] || type
}

// 加载所有景点图片
const loadAttractionPhotos = async () => {
  if (!tripPlan.value) return

  const promises: Promise<void>[] = []

  tripPlan.value.days.forEach(day => {
    day.attractions.forEach(attraction => {
      const promise = fetch(`http://localhost:8000/api/poi/photo?name=${encodeURIComponent(attraction.name)}`)
        .then(res => res.json())
        .then(data => {
          if (data.success && data.data.photo_url) {
            attractionPhotos.value[attraction.name] = data.data.photo_url
          }
        })
        .catch(err => {
          console.error(`获取${attraction.name}图片失败:`, err)
        })

      promises.push(promise)
    })
  })

  await Promise.all(promises)
}

// 获取景点图片
const localImageModules = import.meta.glob('@/assets/images/attractions/*.{png,jpg,jpeg,webp,svg}', { eager: true, query: '?url', import: 'default' })
const localImages = Object.values(localImageModules) as string[]

const getAttractionImage = (name: string, index: number): string => {
  // 如果已加载真实图片,返回真实图片
  if (attractionPhotos.value[name]) {
    return attractionPhotos.value[name]
  }

  // 接口请求失败时，从本地随机图库目录中选择一张图片作为后备
  if (localImages.length > 0) {
    // 使用景点名称的哈希值或索引来选择图片，确保同一个景点总是显示相同的随机图片
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const imageIndex = Math.abs(hash) % localImages.length;
    return localImages[imageIndex];
  }

  // 返回一个纯色占位图(避免跨域问题)
  const colors = [
    { start: '#667eea', end: '#764ba2' },
    { start: '#f093fb', end: '#f5576c' },
    { start: '#4facfe', end: '#00f2fe' },
    { start: '#43e97b', end: '#38f9d7' },
    { start: '#fa709a', end: '#fee140' }
  ]
  const colorIndex = index % colors.length
  const { start, end } = colors[colorIndex]

  // 使用base64编码避免中文问题
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300">
    <defs>
      <linearGradient id="grad${index}" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style="stop-color:${start};stop-opacity:1" />
        <stop offset="100%" style="stop-color:${end};stop-opacity:1" />
      </linearGradient>
    </defs>
    <rect width="400" height="300" fill="url(#grad${index})"/>
    <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="24" font-weight="bold" fill="white">${name}</text>
  </svg>`

  return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`
}

// 图片加载失败时的处理
const handleImageError = (event: Event) => {
  const img = event.target as HTMLImageElement
  // 使用灰色占位图
  img.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300"%3E%3Crect width="400" height="300" fill="%23f0f0f0"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="18" fill="%23999"%3E图片加载失败%3C/text%3E%3C/svg%3E'
}

const removeMapSectionForExport = (exportContainer: HTMLElement) => {
  const mapCard = exportContainer.querySelector('#map') as HTMLElement | null
  if (mapCard) {
    mapCard.remove()
  }

  const rightMap = exportContainer.querySelector('.right-map') as HTMLElement | null
  if (rightMap) {
    rightMap.remove()
  }

  const topInfoSection = exportContainer.querySelector('.top-info-section') as HTMLElement | null
  if (topInfoSection) {
    topInfoSection.style.setProperty('display', 'block')
  }

  const leftInfo = exportContainer.querySelector('.left-info') as HTMLElement | null
  if (leftInfo) {
    leftInfo.style.setProperty('width', '100%')
    leftInfo.style.setProperty('max-width', '100%')
  }
}



// 导出为图片
const exportAsImage = async () => {
  try {
    message.loading({ content: '正在生成导出内容...', key: 'export', duration: 0 })

    const element = document.querySelector('.main-content') as HTMLElement
    if (!element) {
      throw new Error('未找到内容元素')
    }

    // 创建一个独立的容器
    const exportContainer = document.createElement('div')
    exportContainer.style.width = element.offsetWidth + 'px'
    exportContainer.style.backgroundColor = '#f5f7fa'
    exportContainer.style.padding = '20px'

    // 复制所有内容
    exportContainer.innerHTML = element.innerHTML

    // 导出时移除地图板块
    removeMapSectionForExport(exportContainer)

    // 移除所有ant-card类,替换为纯div
    const cards = exportContainer.querySelectorAll('.ant-card')
    cards.forEach((card) => {
      const cardEl = card as HTMLElement
      try {
        cardEl.className = '' // 移除所有类
        cardEl.style.setProperty('background-color', '#ffffff')
        cardEl.style.setProperty('border-radius', '12px')
        cardEl.style.setProperty('box-shadow', '0 4px 12px rgba(0, 0, 0, 0.1)')
        cardEl.style.setProperty('margin-bottom', '20px')
        cardEl.style.setProperty('overflow', 'hidden')
      } catch (err) {
        console.error('设置卡片样式失败:', err)
      }
    })

    // 处理卡片头部
    const cardHeads = exportContainer.querySelectorAll('.ant-card-head')
    cardHeads.forEach((head) => {
      const headEl = head as HTMLElement
      try {
        headEl.style.setProperty('background-color', '#667eea')
        headEl.style.setProperty('color', '#ffffff')
        headEl.style.setProperty('padding', '16px 24px')
        headEl.style.setProperty('font-size', '18px')
        headEl.style.setProperty('font-weight', '600')
      } catch (err) {
        console.error('设置卡片头部样式失败:', err)
      }
    })

    // 处理卡片内容
    const cardBodies = exportContainer.querySelectorAll('.ant-card-body')
    cardBodies.forEach((body) => {
      const bodyEl = body as HTMLElement
      bodyEl.style.setProperty('background-color', '#ffffff')
      bodyEl.style.setProperty('padding', '24px')
    })

    // 处理酒店卡片头部
    const hotelCards = exportContainer.querySelectorAll('.hotel-card')
    hotelCards.forEach((card) => {
      const head = card.querySelector('.ant-card-head') as HTMLElement
      if (head) {
        head.style.setProperty('background-color', '#1976d2')
      }
      (card as HTMLElement).style.setProperty('background-color', '#e3f2fd')
    })

    // 处理天气卡片
    const weatherCards = exportContainer.querySelectorAll('.weather-card')
    weatherCards.forEach((card) => {
      (card as HTMLElement).style.setProperty('background-color', '#e0f7fa')
    })

    // 处理预算总计
    const budgetTotal = exportContainer.querySelector('.budget-total')
    if (budgetTotal) {
      const el = budgetTotal as HTMLElement
      el.style.setProperty('background-color', '#667eea')
      el.style.setProperty('color', '#ffffff')
      el.style.setProperty('padding', '20px')
      el.style.setProperty('border-radius', '12px')
      el.style.setProperty('margin-bottom', '20px')
    }

    // 处理预算项
    const budgetItems = exportContainer.querySelectorAll('.budget-item')
    budgetItems.forEach((item) => {
      const el = item as HTMLElement
      el.style.setProperty('background-color', '#f5f7fa')
      el.style.setProperty('padding', '16px')
      el.style.setProperty('border-radius', '8px')
      el.style.setProperty('margin-bottom', '12px')
    })

    // 添加到body(隐藏)
    exportContainer.style.position = 'absolute'
    exportContainer.style.left = '-9999px'
    document.body.appendChild(exportContainer)

    const canvas = await html2canvas(exportContainer, {
      backgroundColor: '#f5f7fa',
      scale: 2,
      logging: false,
      useCORS: true,
      allowTaint: true
    })

    // 移除容器
    document.body.removeChild(exportContainer)

    // 转换为图片并下载
    const link = document.createElement('a')
    link.download = `旅行计划_${tripPlan.value?.city}_${new Date().getTime()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()

    message.success({ content: '图片导出成功!', key: 'export' })
  } catch (error: any) {
    console.error('导出图片失败:', error)
    message.error({ content: `导出图片失败: ${error.message}`, key: 'export' })
  }
}

// 导出为PDF
const exportAsPDF = async () => {
  try {
    message.loading({ content: '正在生成导出内容...', key: 'export', duration: 0 })

    const element = document.querySelector('.main-content') as HTMLElement
    if (!element) {
      throw new Error('未找到内容元素')
    }

    // 创建一个独立的容器
    const exportContainer = document.createElement('div')
    exportContainer.style.width = element.offsetWidth + 'px'
    exportContainer.style.backgroundColor = '#f5f7fa'
    exportContainer.style.padding = '20px'

    // 复制所有内容
    exportContainer.innerHTML = element.innerHTML

    // 导出时移除地图板块
    removeMapSectionForExport(exportContainer)

    // 移除所有ant-card类,替换为纯div
    const cards = exportContainer.querySelectorAll('.ant-card')
    cards.forEach((card) => {
      const cardEl = card as HTMLElement
      try {
        cardEl.className = ''
        cardEl.style.setProperty('background-color', '#ffffff')
        cardEl.style.setProperty('border-radius', '12px')
        cardEl.style.setProperty('box-shadow', '0 4px 12px rgba(0, 0, 0, 0.1)')
        cardEl.style.setProperty('margin-bottom', '20px')
        cardEl.style.setProperty('overflow', 'hidden')
      } catch (err) {
        console.error('设置卡片样式失败:', err)
      }
    })

    // 处理卡片头部
    const cardHeads = exportContainer.querySelectorAll('.ant-card-head')
    cardHeads.forEach((head) => {
      const headEl = head as HTMLElement
      try {
        headEl.style.setProperty('background-color', '#667eea')
        headEl.style.setProperty('color', '#ffffff')
        headEl.style.setProperty('padding', '16px 24px')
        headEl.style.setProperty('font-size', '18px')
        headEl.style.setProperty('font-weight', '600')
      } catch (err) {
        console.error('设置卡片头部样式失败:', err)
      }
    })

    // 处理卡片内容
    const cardBodies = exportContainer.querySelectorAll('.ant-card-body')
    cardBodies.forEach((body) => {
      const bodyEl = body as HTMLElement
      bodyEl.style.setProperty('background-color', '#ffffff')
      bodyEl.style.setProperty('padding', '24px')
    })

    // 处理酒店卡片头部
    const hotelCards = exportContainer.querySelectorAll('.hotel-card')
    hotelCards.forEach((card) => {
      const head = card.querySelector('.ant-card-head') as HTMLElement
      if (head) {
        head.style.setProperty('background-color', '#1976d2')
      }
      (card as HTMLElement).style.setProperty('background-color', '#e3f2fd')
    })

    // 处理天气卡片
    const weatherCards = exportContainer.querySelectorAll('.weather-card')
    weatherCards.forEach((card) => {
      (card as HTMLElement).style.setProperty('background-color', '#e0f7fa')
    })

    // 处理预算总计
    const budgetTotal = exportContainer.querySelector('.budget-total')
    if (budgetTotal) {
      const el = budgetTotal as HTMLElement
      el.style.setProperty('background-color', '#667eea')
      el.style.setProperty('color', '#ffffff')
      el.style.setProperty('padding', '20px')
      el.style.setProperty('border-radius', '12px')
      el.style.setProperty('margin-bottom', '20px')
    }

    // 处理预算项
    const budgetItems = exportContainer.querySelectorAll('.budget-item')
    budgetItems.forEach((item) => {
      const el = item as HTMLElement
      el.style.setProperty('background-color', '#f5f7fa')
      el.style.setProperty('padding', '16px')
      el.style.setProperty('border-radius', '8px')
      el.style.setProperty('margin-bottom', '12px')
    })

    // 添加到body(隐藏)
    exportContainer.style.position = 'absolute'
    exportContainer.style.left = '-9999px'
    document.body.appendChild(exportContainer)

    const canvas = await html2canvas(exportContainer, {
      backgroundColor: '#f5f7fa',
      scale: 2,
      logging: false,
      useCORS: true,
      allowTaint: true
    })

    // 移除容器
    document.body.removeChild(exportContainer)

    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4'
    })

    const imgWidth = 210 // A4宽度(mm)
    const imgHeight = (canvas.height * imgWidth) / canvas.width

    // 如果内容高度超过一页,分页处理
    let heightLeft = imgHeight
    let position = 0

    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
    heightLeft -= 297 // A4高度

    while (heightLeft > 0) {
      position = heightLeft - imgHeight
      pdf.addPage()
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
      heightLeft -= 297
    }

    pdf.save(`旅行计划_${tripPlan.value?.city}_${new Date().getTime()}.pdf`)

    message.success({ content: 'PDF导出成功!', key: 'export' })
  } catch (error: any) {
    console.error('导出PDF失败:', error)
    message.error({ content: `导出PDF失败: ${error.message}`, key: 'export' })
  }
}

// 初始化地图
const initMap = async () => {
  try {
    const container = document.getElementById('amap-container')
    if (!container) {
      console.error('地图容器不存在')
      return
    }
    // 强制给容器一个最小高度以防渲染失败
    if (container.clientHeight === 0) {
      container.style.height = '500px'
    }

    const AMap = await AMapLoader.load({
      key: import.meta.env.VITE_AMAP_WEB_JS_KEY,  // 高德地图Web端(JS API) Key
      version: '2.0',
      plugins: ['AMap.Marker', 'AMap.Polyline', 'AMap.InfoWindow']
    })

    // 创建地图实例
    map = new AMap.Map('amap-container', {
      zoom: 12,
      center: [116.397128, 39.916527], // 默认中心点(北京)
      viewMode: '3D'
    })

    // 添加景点标记
    addAttractionMarkers(AMap)

    message.success('地图加载成功')
  } catch (error) {
    console.error('地图加载失败:', error)
    message.error('地图加载失败')
  }
}

// 添加景点标记
const addAttractionMarkers = (AMap: any) => {
  if (!tripPlan.value) return

  const markers: any[] = []
  const allAttractions: any[] = []

  // 收集所有景点
  tripPlan.value.days.forEach((day, dayIndex) => {
    day.attractions.forEach((attraction, attrIndex) => {
      if (attraction.location && attraction.location.longitude && attraction.location.latitude) {
        allAttractions.push({
          ...attraction,
          dayIndex,
          attrIndex
        })
      }
    })
  })

  // 创建标记
  allAttractions.forEach((attraction, index) => {
    const marker = new AMap.Marker({
      position: [attraction.location.longitude, attraction.location.latitude],
      title: attraction.name,
      label: {
        content: `<div style="background: #4CAF50; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">${index + 1}</div>`,
        offset: new AMap.Pixel(0, -30)
      }
    })

    // 创建信息窗口
    const infoWindow = new AMap.InfoWindow({
      content: `
        <div style="padding: 10px;">
          <h4 style="margin: 0 0 8px 0;">${attraction.name}</h4>
          <p style="margin: 4px 0;"><strong>地址:</strong> ${attraction.address}</p>
          <p style="margin: 4px 0;"><strong>游览时长:</strong> ${attraction.visit_duration}分钟</p>
          <p style="margin: 4px 0;"><strong>描述:</strong> ${attraction.description}</p>
          <p style="margin: 4px 0; color: #1890ff;"><strong>第${attraction.dayIndex + 1}天 景点${attraction.attrIndex + 1}</strong></p>
        </div>
      `,
      offset: new AMap.Pixel(0, -30)
    })

    // 点击标记显示信息窗口
    marker.on('click', () => {
      infoWindow.open(map, marker.getPosition())
    })

    markers.push(marker)
  })

  // 添加标记到地图
  map.add(markers)

  // 自动调整视野以包含所有标记
  if (allAttractions.length > 0) {
    map.setFitView(markers)
  }

  // 绘制路线
  drawRoutes(AMap, allAttractions)
}

// 绘制路线
const drawRoutes = (AMap: any, attractions: any[]) => {
  if (attractions.length < 2) return

  // 按天分组绘制路线
  const dayGroups: any = {}
  attractions.forEach(attr => {
    if (!dayGroups[attr.dayIndex]) {
      dayGroups[attr.dayIndex] = []
    }
    dayGroups[attr.dayIndex].push(attr)
  })

  // 为每天的景点绘制路线
  Object.values(dayGroups).forEach((dayAttractions: any) => {
    if (dayAttractions.length < 2) return

    const path = dayAttractions.map((attr: any) => [
      attr.location.longitude,
      attr.location.latitude
    ])

    const polyline = new AMap.Polyline({
      path: path,
      strokeColor: '#1890ff',
      strokeWeight: 4,
      strokeOpacity: 0.8,
      strokeStyle: 'solid',
      showDir: true // 显示方向箭头
    })

    map.add(polyline)
  })
}
</script>

<style scoped>
.result-container {
  min-height: 100vh;
  background: var(--bg-app);
  padding: 40px 20px;
}

.page-header {
  max-width: 1400px;
  margin: 0 auto 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  animation: fadeInDown 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.back-button {
  border-radius: var(--radius-md);
  font-weight: 500;
  color: var(--text-secondary);
}

.back-button:hover {
  color: var(--primary-color);
}

/* 内容布局 */
.content-wrapper {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  gap: 32px;
}

.side-nav {
  width: 240px;
  flex-shrink: 0;
}

.side-nav :deep(.ant-menu) {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  background: var(--bg-card);
  padding: 12px 8px;
}

.side-nav :deep(.ant-menu-item) {
  margin: 4px 0;
  border-radius: var(--radius-md);
  transition: all var(--transition-fast);
  color: var(--text-secondary);
}

.side-nav :deep(.ant-menu-item-selected) {
  background: rgba(79, 70, 229, 0.08);
  color: var(--primary-color);
  font-weight: 600;
}

.side-nav :deep(.ant-menu-item:hover) {
  background: var(--bg-card-hover);
}

.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 景点卡片重构样式 */
.attraction-card-container {
  position: relative;
  border-radius: var(--radius-xl);
  overflow: hidden;
  min-height: 400px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-base);
}

.attraction-card-container:hover {
  box-shadow: var(--shadow-md);
}

.attraction-bg-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
  transition: transform var(--transition-slow);
}

.attraction-card-container:hover .attraction-bg-image {
  transform: scale(1.05);
}

.attraction-top-badges {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  z-index: 1;
}

.attraction-badge {
  background: var(--primary-color);
  color: white;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  box-shadow: var(--shadow-sm);
}

.badge-number {
  font-size: 16px;
}

.price-tag {
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(4px);
  color: white;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  font-weight: 600;
  font-size: 13px;
  box-shadow: var(--shadow-sm);
  height: fit-content;
}

.attraction-info-overlay {
  position: relative;
  z-index: 1;
  padding: 24px;
  margin-top: auto;
}

.attraction-content-glass {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  color: #ffffff;
  text-align: left;
  border-radius: 20px;
  padding: 16px 20px;
}

.attraction-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding-bottom: 8px;
}

.attraction-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
  text-shadow: 0 2px 4px rgba(0,0,0,0.5);
  letter-spacing: -0.01em;
}

.attraction-body p {
  margin-bottom: 6px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.95);
  line-height: 1.4;
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}

.attraction-body strong {
  font-weight: 600;
  color: #ffffff;
}

.description-text {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 每日天气区块样式 */
.day-weather-banner {
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: linear-gradient(to right, rgba(79, 70, 229, 0.05), rgba(79, 70, 229, 0.02));
  border-radius: var(--radius-lg);
  padding: 16px 24px;
  margin-bottom: 24px;
  border: 1px solid var(--border-color);
}

.weather-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.weather-icon {
  font-size: 28px;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
}

.weather-details {
  display: flex;
  flex-direction: column;
}

.weather-time {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  margin-bottom: 2px;
}

.weather-temp {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.weather-divider {
  width: 1px;
  height: 32px;
  background: var(--border-color);
}

/* 回到顶部按钮 */
.back-top-button {
  width: 48px;
  height: 48px;
  background: var(--primary-color);
  color: white;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: bold;
  box-shadow: var(--shadow-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.back-top-button:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-lg);
  background: var(--primary-hover);
}

/* 酒店卡片样式 */
.hotel-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color) !important;
}

.hotel-card :deep(.ant-card-head) {
  background: var(--bg-app) !important;
  border-bottom: 1px solid var(--border-color) !important;
}

.hotel-title {
  color: var(--text-primary) !important;
  font-weight: 600;
}



/* 行程概览卡片 */
.overview-card {
  height: fit-content;
}

.overview-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.info-value {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.6;
  font-weight: 500;
}

/* 预算卡片 */
.budget-card {
  height: fit-content;
}

.budget-card :deep(.ant-card-body) {
  padding: 20px 24px !important;
}

.budget-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.budget-item {
  text-align: left;
  padding: 12px 16px;
  background: var(--bg-app);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.budget-item:hover {
  border-color: var(--primary-color);
  background: white;
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.budget-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  font-weight: 500;
}

.budget-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.budget-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--primary-color);
  border-radius: var(--radius-md);
  color: white;
  box-shadow: var(--shadow-sm);
}

.total-label {
  font-size: 15px;
  font-weight: 600;
  opacity: 0.9;
}

.total-value {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1;
}

/* 地图卡片 */
.map-card {
  height: 100%;
  min-height: 540px;
  display: flex;
  flex-direction: column;
}

.map-card :deep(.ant-card-body) {
  flex: 1;
  padding: 0 !important;
  overflow: hidden;
  border-bottom-left-radius: var(--radius-xl);
  border-bottom-right-radius: var(--radius-xl);
}

/* 每日行程卡片 */
.day-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.day-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.day-date {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}

.day-info {
  margin-bottom: 24px;
  padding: 20px;
  background: var(--bg-app);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.info-row {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  align-items: flex-start;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 90px;
  font-size: 14px;
}

.info-row .value {
  color: var(--text-primary);
  flex: 1;
  font-size: 15px;
  line-height: 1.5;
}

/* 卡片样式优化 */
:deep(.ant-card) {
  border-radius: var(--radius-xl) !important;
  box-shadow: var(--shadow-sm) !important;
  border: 1px solid var(--border-color) !important;
  margin-bottom: 0;
  transition: all var(--transition-base);
  animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  background: var(--bg-card) !important;
}

:deep(.ant-card:hover) {
  box-shadow: var(--shadow-md) !important;
  border-color: var(--border-hover) !important;
}

:deep(.ant-card-head) {
  background: transparent !important;
  color: var(--text-primary) !important;
  border-bottom: 1px solid var(--border-color) !important;
  padding: 0 24px !important;
  min-height: 64px !important;
}

:deep(.ant-card-head-title) {
  color: var(--text-primary) !important;
  font-size: 16px !important;
  font-weight: 700 !important;
}

/* 响应式设计 */


@media (max-width: 992px) {
  .content-wrapper {
    flex-direction: column;
  }

  .side-nav {
    width: 100%;
    position: static;
  }

  .side-nav :deep(.ant-affix) {
    position: static !important;
  }

  .side-nav :deep(.ant-menu) {
    display: flex;
    overflow-x: auto;
    white-space: nowrap;
    padding: 8px;
  }

  .side-nav :deep(.ant-menu-item) {
    display: inline-block;
    width: auto !important;
    margin: 0 4px !important;
  }

  .budget-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .result-container {
    padding: 24px 16px;
  }

  .budget-grid {
    grid-template-columns: 1fr;
  }

  .day-weather-banner {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }

  .weather-divider {
    display: none;
  }

  .weather-item {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>