# Argon Design System 迁移文档

本指南介绍了如何将现有的 Vue 组件或 Ant Design 组件迁移至新集成的 **Argon Design System** 风格。

## 1. 为什么选择 Argon？

Argon 提供了轻量级的 Bootstrap 4 兼容设计风格，并具有以下优点：
- 更轻量化的视觉层次（阴影、边框圆角更现代）
- 模块化的按需加载 SCSS 避免全局样式冲突
- 支持通过 `src/theme/index.ts` 动态调整 CSS 变量以实现主题切换。

## 2. 替换指南

### 2.1 按钮 (Buttons)

**旧代码 (Ant Design):**
```vue
<a-button type="primary" size="large">Primary</a-button>
```

**新代码 (ArgonButton):**
```vue
<ArgonButton type="primary" size="lg">Primary</ArgonButton>
```
*注：ArgonButton 属性包括 `type`, `size`, `outline`, `iconOnly`, `block`.*

### 2.2 卡片 (Cards)

**旧代码 (Ant Design):**
```vue
<a-card title="标题" :bordered="false" class="m# Argon Design System 迁移文档

本指南介绍了如何将现有的 Vue 组件或 Ant Design 组?>
本指南介绍了如何将现?s=
## 1. 为什么选择 Argon？

Argon 提供了轻量级的 Bootstrap 4 兼容设计风格，并具有以下优点：
- ??
Argon 提供了轻量级的 ?? 更轻量化的视觉层次（阴影、边框圆角更现代）
- 模块化的按?e- 模块化的按需加载 SCSS 避免全局样式冲突
- 支?>- 支持通过 `src/theme/index.ts` 动态调整 CSS ?f
## 2. 替换指南

### 2.1 按钮 (Buttons)

**旧代码 (Ant Design):**
```vue
代
### 2.1 按钮 (**

**旧代码 (Ant Desigs="```vue
<a-button type="pri>
<a-bu**```

**新代码 (ArgonButton):**
```vue
<ArgonButton t[