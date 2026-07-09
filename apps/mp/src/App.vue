<script>
export default {
  onLaunch() {
    console.log('智营获客 App Launch')
  },
}
</script>

<style>
html,
body,
#app {
  height: 100%;
}

page {
  min-height: 100%;
  background-color: #f0f2f5;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
  overflow-y: auto;
}

/* uni-app 默认 button 在 H5 上样式较丑，统一重置 */
button {
  margin: 0;
  padding: 0;
  line-height: inherit;
  font-size: inherit;
  background: transparent;
}

button::after {
  border: none;
}

uni-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
}

uni-page-body {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
  box-sizing: border-box;
}

/* H5 底部 Tab 栏：更大图标与文字 */
.uni-tabbar {
  box-shadow: 0 -2px 12px rgba(15, 23, 42, 0.06);
}

.uni-tabbar-border {
  background-color: #eef2f6 !important;
}

.uni-tabbar__item {
  padding: 4px 0 2px;
}

.uni-tabbar__icon,
.uni-tabbar__icon.uni-tabbar__icon__diff {
  width: 28px !important;
  height: 28px !important;
  margin-top: 2px !important;
}

.uni-tabbar__icon img {
  width: 28px !important;
  height: 28px !important;
}

.uni-tabbar__label {
  font-size: 11px !important;
  margin-top: 3px !important;
  line-height: 1.2 !important;
}

/* 创作 Tab 略突出 */
.uni-tabbar__item:nth-child(3) .uni-tabbar__icon,
.uni-tabbar__item:nth-child(3) .uni-tabbar__icon img {
  width: 32px !important;
  height: 32px !important;
}

/* H5：确保表单输入框可点击、可输入 */
uni-input,
uni-textarea {
  pointer-events: auto !important;
}

uni-input .uni-input-input,
uni-textarea .uni-textarea-textarea {
  pointer-events: auto !important;
  -webkit-user-select: text !important;
  user-select: text !important;
}
</style>
