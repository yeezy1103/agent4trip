# 景点板块样式重构计划 (Attractions Section Redesign Plan)

## 1. 目标与现状分析 (Current State & Goals)
**目标**: 将结果页（`Result.vue`）中的每日行程景点卡片（`attraction-card`）进行视觉升级。要求将景点图片全屏铺满作为该景点的容器背景，同时景点相关的文字信息和操作按钮通过“液态玻璃 (Liquid Glass)”风格的卡片悬浮展示在图片上方。

**现状**:
- 景点列表目前由 `<a-list>` 和 `<a-card class="attraction-card">` 渲染。
- 景点图片独立存放在 `<div class="attraction-image-wrapper">` 内。
- 文字信息（地址、时长、描述、评分）和操作按钮跟随在图片下方，背景为默认的纯白色卡片。

## 2. 改造方案 (Proposed Changes)

**文件**: `/Users/yeezy/Desktop/helloagents-trip-planner2/frontend/src/views/Result.vue`

### 2.1 DOM 结构重构 (DOM Restructuring)
将原有的 `<a-card>` 替换为自定义的容器 `<div class="attraction-card-container">`：
1. **背景图片层**：保留原有的 `<img>` 标签并将其绝对定位铺满容器（以继续利用 `@error="handleImageError"` 的兜底图逻辑），设置 `object-fit: cover`。
2. **顶部角标层**：将序号徽章（`badge-number`）和价格标签（`price-tag`）通过绝对定位或 Flex 悬浮在图片顶部。
3. **液态玻璃信息层**：
   - 在容器底部悬浮一个 `<LiquidGlass>` 组件。
   - 将原本在 `a-card` 中的标题 (`item.name`)、编辑按钮 (`a-space`)、以及详细信息（地址、描述等）迁移至玻璃卡片内部。
   - 卡片比背景图片小一些，以保持视觉上的平衡。

### 2.2 样式调整 (CSS Styling)
添加并修改相关样式以支持层叠与动态效果：
- `.attraction-card-container`: 设置 `position: relative; min-height: 400px; display: flex; flex-direction: column; justify-content: flex-end; overflow: hidden; border-radius: var(--radius-xl);`
- `.attraction-bg-image`: 设置 `position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 0;` 并加上 `hover` 时轻微放大的动效。
- `.attraction-info-overlay`: 设定 `z-index: 1; padding: 12px;`，内部包裹 `LiquidGlass` 玻璃容器，使文字能够透出背后的景点图片并产生高级折射感。

### 2.3 LiquidGlass 配置 (Liquid Glass Configuration)
为了使玻璃卡片在复杂的真实照片背景下依然能保证文字的清晰可读：
- `:displacement-scale="20"`
- `:blur-amount="0.1"` (提高模糊度，增强文字对比度)
- `:elasticity="0"` (信息展示区不需过强的液体果冻感)
- 配合 `background: rgba(255, 255, 255, 0.4)` 以提亮玻璃内部。

## 3. 验证步骤 (Verification Steps)
1. 编译 Vue 组件，确保没有任何报错。
2. 在浏览器中查看行程结果，确认景点的图片成功变为背景。
3. 确认文字信息悬浮在卡片下方，且拥有清晰的毛玻璃/液态玻璃材质。
4. 测试“图片加载失败”时是否正常显示灰色占位图背景。
5. 测试“编辑模式”下表单输入框在玻璃面板内的可用性及高度适配。