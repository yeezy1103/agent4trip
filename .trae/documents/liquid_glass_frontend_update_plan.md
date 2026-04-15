# Liquid Glass Vue 前端更新与重构计划

## 1. 核心库学习与现状分析

### 1.1 `liquid-glass-vue` 核心功能与最佳实践
通过深入研究 `liquid_glass_vue_README-zh.md` 文档，该库具备以下特性：
* **核心效果**：提供类似 Apple 风格的液体玻璃折射、边缘弯曲、色差和弹性（液体）悬停反馈。
* **主要参数**：支持自定义位移强度 (`displacementScale`)、模糊度 (`blurAmount`)、色彩饱和度 (`saturation`)、色差 (`aberrationIntensity`) 和弹性 (`elasticity`)。
* **渲染模式**：分为基础的 CSS/SVG 混合模式 (`standard`) 和基于 WebGL 着色器的模式 (`shader`)，后者视觉更精准但可能有兼容性问题。
* **最佳实践**：
  1. **背景依赖**：折射效果必须建立在**色彩丰富、有纹理或动态的背景**之上（如果背景是纯色，玻璃的折射将不可见）。
  2. **性能考量**：在大型卡片容器上建议使用 `mode="standard"`，在小尺寸交互组件（如 Button）上可尝试 `mode="shader"`。
  3. **交互增强**：可以通过绑定 `mouseContainer` 让玻璃折射效果响应全屏/父容器的鼠标移动，增强 3D 空间感。

### 1.2 当前前端现状 (Current State)
* 我们的前端刚刚完成了设计系统的现代化重构（基于 `design-system.css`），目前主要使用**纯色背景**（`var(--bg-app)` 为 `Slate 50` 浅灰色），这种极简的扁平化风格无法发挥 Liquid Glass 的折射特性。
* 若要引入该库，必须在界面的视觉底层（Z-index: 0）重新引入一些**动态的色彩弥散圆(Mesh Gradient/Blobs)** 或环境光，让前方的 Liquid Glass 组件有内容可折射。

---

## 2. 前端更新方案 (Proposed Changes)

为了将液体玻璃的惊艳效果无缝融入当前的业务流程中，建议分三个层级进行改造：

### 2.1 依赖与全局注册
* **操作**：运行 `npm install @wxperia/liquid-glass-vue`。
* **修改 `main.ts`**：引入 `import LiquidGlass from 'liquid-glass-vue'` 并通过 `app.use(LiquidGlass)` 进行全局注册。

### 2.2 Home.vue (首页) 视觉重塑：动态弥散背景 + 液体表单卡片
* **重构背景**：在 `.home-container` 底部添加 2-3 个缓慢移动的 CSS 渐变光球（如使用 `--primary-color` 和 `--info-color`），为玻璃效果提供折射源。
* **表单主卡片玻璃化**：
  * 将现有的纯白 `<a-card class="form-card">` 替换/包裹为 `<LiquidGlass>` 组件。
  * **参数建议**：`:displacement-scale="40" :blur-amount="0.08" :elasticity="0.1" :corner-radius="24"`（大半径圆角与现有设计系统呼应）。
* **提交按钮特效**：
  * 将“🚀 开始规划我的旅行”按钮替换为带有 `mode="shader"` 的 LiquidGlass 按钮。
  * **参数建议**：加入高弹性 `:elasticity="0.4"`，让用户点击时产生果冻般的液体反弹反馈。

### 2.3 Result.vue (结果页) 局部点缀：毛玻璃侧边栏与悬浮小组件
* **侧边导航栏 (Side Nav)**：
  * 结果页内容较多，不建议全部玻璃化以免干扰阅读。但可以将左侧悬浮的 `side-nav` 菜单用 `<LiquidGlass>` 包裹，使其在滚动时能隐约折射背后的页面内容。
* **预算汇总区 / 天气横幅**：
  * 将 `.budget-total`（总费用高亮区）或 `.day-weather-banner` 改造为彩色玻璃材质，提升信息层级和质感。
* **返回顶部按钮 (Back Top)**：
  * 使用小圆角 LiquidGlass 组件重构，配置高色差 `:aberration-intensity="3"`，打造精致的微交互。

### 2.4 交互升级：全局鼠标响应 (Mouse Tracking)
* 在 `App.vue` 或 `Home.vue` 的最外层容器声明一个 `ref`，并将其作为 `:mouse-container="containerRef"` 传递给内部的 LiquidGlass 组件。
* 这会让所有的玻璃元素随着用户鼠标在屏幕上的移动，产生统一方向的轻微折射偏移，实现高级的空间联动。

---

## 3. 潜在风险与应对 (Risks & Mitigations)

1. **浏览器兼容性**：README 明确指出 Safari 和 Firefox 对位移效果支持有限。
   * **应对**：我们需要保留现有的 fallback 样式（如半透明 `rgba(255,255,255, 0.8)` + `backdrop-filter: blur(12px)`），确保在不支持的高级特性的浏览器上依然是美观的普通毛玻璃。
2. **性能负担**：大量的 Shader 或高强度的位移滤镜可能导致滚动掉帧。
   * **应对**：严格控制 LiquidGlass 的使用面积。结果页的主体内容（长列表、地图）保持普通渲染，仅在固定悬浮层（导航、特定强调卡片）使用。

---

## 4. 下一步执行计划 (Next Steps)
1. 确认该方案的修改范围（是否同意在首页增加动态色彩背景以支持折射？）。
2. 执行依赖安装与全局注册。
3. 逐个重构 `Home.vue` 与 `Result.vue` 中的目标组件。
4. 在不同浏览器中验证视觉效果和性能。