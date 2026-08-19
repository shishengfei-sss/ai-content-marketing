<script setup>
/**
 * M15-B 用户协议 / 隐私。对照 PRD 02-买家端UI.html #m15b
 * 店铺未配置独立 URL 时展示站内只读文本。
 */
function goBack() {
  uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/shop/mine' }) })
}
</script>

<template>
  <view class="page">
    <scroll-view scroll-y class="body">
      <text class="h">《用户服务协议》</text>
      <text class="p">
        本服务由商家通过内容获客店铺向你提供课程、资料与到店/预约类服务。下单、支付、退款与履约以订单页展示及商家公示规则为准。请勿将账号转借他人使用。
      </text>
      <text class="h">《隐私政策》</text>
      <text class="p">
        为完成登录、下单与履约，店铺会处理你的微信标识与绑定手机号（脱敏展示）。信息仅用于本店交易与售后，不向无关第三方出售。你可在「我的」退出登录以清除本机会话。
      </text>
    </scroll-view>
    <button class="btn" @click="goBack">关闭</button>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: #f3f5f9;
  padding: 16px 16px 24px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}
.body {
  flex: 1;
  max-height: 70vh;
  background: #fff;
  border-radius: 16px;
  padding: 16px;
  box-sizing: border-box;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
.h {
  display: block;
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 8px;
}
.p {
  display: block;
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
  margin-bottom: 16px;
}
.btn {
  margin-top: 16px;
  background: #fff;
  color: #334155;
  border-radius: 999px;
  font-weight: 600;
}
</style>
