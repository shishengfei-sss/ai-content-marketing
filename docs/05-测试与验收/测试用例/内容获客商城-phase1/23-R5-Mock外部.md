# 23 · R5 Mock 外部对接（六段式 · 全量）

| 字段 | 值 |
|------|-----|
| 文档版本 | **v3.2** |
| 说明 | 吸收他方 MOCK 全量（支付/抖店/短信等） |

---

### MOCK-01: 微信支付 Mock - 统一下单

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- 环境变量: `WECHAT_PAY_MODE=stub`
- 商家已配置支付信息 (mch_id, api_key, cert)
- 买家已创建订单 (order_no=TEST_ORDER_001, status=pending)

**测试步骤**:

```
Step 1: 调用统一下单 API
  POST /api/v1/shop/orders/TEST_ORDER_001/prepay
  Headers: Authorization: Bearer BUYER_TOKEN
  Assert: 200

Step 2: 验证 stub 返回格式
  Assert: body.prepay_id 以 'wx_stub_' 开头
  Assert: body.prepay_id 格式: wx_stub_{order_no}_{timestamp}
  Assert: body.nonce_str 非空 (32位随机字符串)
  Assert: body.sign 非空
  Assert: body.sign_type = 'MD5'
  Assert: body.trade_type = 'JSAPI'

Step 3: 验证 stub 不实际调用微信
  Assert: 无外部 HTTP 请求发出 (通过 mock interceptor 验证)
  Assert: 响应延迟 < 100ms (stub 即时返回)

Step 4: 验证 prepay 记录写入数据库
  SELECT * FROM shop_prepay_records WHERE order_no = 'TEST_ORDER_001'
  Assert: prepay_id 以 'wx_stub_' 开头
  Assert: created_at 非空
```

**期望结果**:
- stub 模式返回 wx_stub_ 前缀的 prepay_id
- 返回格式符合微信支付 JSAPI 规范
- 无外部请求
- prepay 记录入库

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-01-S1 | stub统一下单 | WECHAT_PAY_MODE=stub | prepay | wx_stub_ prepay_id |
| MOCK-01-S2 | 格式校验 | stub返回 | 检查字段 | 符合JSAPI规范 |
| MOCK-01-S3 | 无外部请求 | stub模式 | 检查 | 无HTTP外发 |

---

### MOCK-02: 微信支付 Mock - prepay_id 格式

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`
- 买家已创建订单

**测试步骤**:

```
Step 1: 创建多个订单并 prepay
  POST /api/v1/shop/orders (order_no=ORDER_A)
  POST /api/v1/shop/orders/ORDER_A/prepay
  Assert: body.prepay_id = 'wx_stub_ORDER_A_{timestamp}'

  POST /api/v1/shop/orders (order_no=ORDER_B)
  POST /api/v1/shop/orders/ORDER_B/prepay
  Assert: body.prepay_id = 'wx_stub_ORDER_B_{timestamp}'

Step 2: 验证 prepay_id 唯一性
  Assert: ORDER_A 的 prepay_id != ORDER_B 的 prepay_id

Step 3: 验证 prepay_id 包含 order_no
  Assert: prepay_id 包含对应 order_no

Step 4: 验证同一订单重复 prepay
  POST /api/v1/shop/orders/ORDER_A/prepay (再次)
  Assert: 200, 新的 prepay_id (timestamp 不同)
```

**期望结果**:
- prepay_id 格式: wx_stub_{order_no}_{timestamp}
- 每个订单的 prepay_id 唯一
- prepay_id 可追溯 order_no

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-02-S1 | 不同订单 | 2个订单 | prepay | prepay_id不同 |
| MOCK-02-S2 | 同订单重复 | 1个订单 | prepay2次 | 新prepay_id |
| MOCK-02-S3 | 格式验证 | stub返回 | 检查 | wx_stub_{order}_{ts} |

---

### MOCK-03: 微信支付 Mock - 回调验签

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`
- 订单已 prepay (order_no=TEST_ORDER_001)
- 测试密钥: `TEST_SIGN_KEY`

**测试步骤**:

```
Step 1: stub 自动触发回调 (有效签名)
  (stub 模式下 prepay 后自动调用 notify, 使用测试密钥签名)
  Assert: 订单状态变为 paid

Step 2: 手动模拟回调 (正确签名)
  计算签名: sign = MD5(sorted_params + TEST_SIGN_KEY)
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "result_code": "SUCCESS",
    "sign": "{calculated_sign}"
  }
  Assert: 200 (幂等, 不重复处理)

Step 3: 验证签名验证逻辑
  Assert: 服务端使用 TEST_SIGN_KEY 验签
  Assert: 验签通过后处理业务逻辑

Step 4: 验证回调数据格式
  Assert: 回调包含 out_trade_no, transaction_id, result_code, sign
```

**期望结果**:
- stub 模式自动触发有效签名回调
- 回调验签使用测试密钥
- 验签通过后处理业务
- 回调数据格式正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-03-S1 | 正确签名 | stub自动 | 回调 | 验签通过 |
| MOCK-03-S2 | 幂等处理 | 已paid | 回调 | 200不重复 |
| MOCK-03-S3 | 签名格式 | stub返回 | 检查 | 包含sign字段 |

---

### MOCK-04: 微信支付 Mock - 退款

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`
- 订单已支付 (status=paid)

**测试步骤**:

```
Step 1: 发起退款
  POST /api/v1/shop/orders/TEST_ORDER_001/refund
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Body: { "reason": "测试退款", "amount": 99.00 }
  Assert: 200, body.status='refunding'

Step 2: 验证 stub 退款回调
  Assert: stub 自动完成退款 (等待3秒)
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='refunded', body.refunded_at 非空

Step 3: 验证退款记录
  GET /api/v1/admin/shop/refunds?order_no=TEST_ORDER_001
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items[0].status='success'
  Assert: body.items[0].refund_id 以 'wx_stub_refund_' 开头
  Assert: body.items[0].amount=99.00

Step 4: 验证 stub 退款不实际调用微信
  Assert: 无外部 HTTP 请求
```

**期望结果**:
- stub 退款自动完成
- 退款记录包含 wx_stub_refund_ 前缀
- 无外部请求

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-04-S1 | 正常退款 | paid | 退款 | refunded |
| MOCK-04-S2 | 重复退款 | refunded | 退款 | 422 |
| MOCK-04-S3 | 部分退款 | paid=99 | 退49 | 成功(如支持) |

---

### MOCK-05: 微信支付 Mock - 查单

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`
- 订单已支付 (status=paid, transaction_id=wx_stub_tx_001)

**测试步骤**:

```
Step 1: 调用查单 API
  GET /api/v1/shop/orders/TEST_ORDER_001/payment-status
  Headers: Authorization: Bearer MERCHANT_TOKEN
  Assert: 200, body.trade_state='SUCCESS'
  Assert: body.transaction_id='wx_stub_tx_001'

Step 2: 验证 stub 查单返回
  Assert: body.trade_state='SUCCESS' (已支付)
  Assert: body.out_trade_no='TEST_ORDER_001'

Step 3: 未支付订单查单
  (另一订单 status=pending)
  GET /api/v1/shop/orders/ORDER_PENDING/payment-status
  Assert: 200, body.trade_state='NOTPAY'

Step 4: 已退款订单查单
  (另一订单 status=refunded)
  GET /api/v1/shop/orders/ORDER_REFUNDED/payment-status
  Assert: 200, body.trade_state='REFUND'
```

**期望结果**:
- stub 查单返回正确状态
- paid → SUCCESS, pending → NOTPAY, refunded → REFUND
- transaction_id 正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-05-S1 | 已支付查单 | paid | 查单 | SUCCESS |
| MOCK-05-S2 | 未支付查单 | pending | 查单 | NOTPAY |
| MOCK-05-S3 | 已退款查单 | refunded | 查单 | REFUND |

---

### MOCK-06: 微信支付 Mock - 验签失败 400

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`
- 订单已 prepay (order_no=TEST_ORDER_001)

**测试步骤**:

```
Step 1: 发送错误签名的回调
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "result_code": "SUCCESS",
    "sign": "invalid_sign_xxx"
  }
  Assert: 400, body.detail 包含 '签名验证失败'

Step 2: 发送无签名的回调
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "result_code": "SUCCESS"
  }
  Assert: 400, body.detail 包含 '签名' 或 'sign'

Step 3: 发送篡改数据的回调
  计算正确签名后, 修改 amount 字段
  POST /api/v1/payment/wx/notify
  Body: {
    "out_trade_no": "TEST_ORDER_001",
    "transaction_id": "wx_stub_tx_001",
    "total_fee": 1,  // 篡改金额
    "sign": "{原签名}"  // 用原数据计算的签名
  }
  Assert: 400 (签名不匹配)

Step 4: 验证订单状态未变
  GET /api/v1/shop/orders/TEST_ORDER_001
  Assert: body.status='pending' (验签失败不影响订单)
```

**期望结果**:
- 错误签名返回 400
- 无签名返回 400
- 篡改数据签名不匹配返回 400
- 验签失败不影响订单状态

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-06-S1 | 错误签名 | pending | 回调 | 400 |
| MOCK-06-S2 | 无签名 | pending | 回调 | 400 |
| MOCK-06-S3 | 篡改数据 | pending | 回调 | 400 |
| MOCK-06-S4 | 状态不变 | 验签失败 | 检查 | 仍pending |

---

### MOCK-07: 抖店 Webhook Mock - 下单

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `DOUYIN_WEBHOOK_MODE=stub`
- 商品已映射 (PRODUCT_001 → DY_PROD_001)

**测试步骤**:

```
Step 1: 模拟抖店下单 Webhook
  POST /api/v1/webhooks/douyin/order
  Headers: X-Douyin-Signature: {test_signature}
  Body: {
    "event": "order.create",
    "timestamp": 1691827200,
    "data": {
      "douyin_order_id": "DY_ORDER_001",
      "douyin_product_id": "DY_PROD_001",
      "buyer_mobile": "13700000000",
      "amount": 9900,
      "pay_time": "2026-08-12 10:00:00"
    }
  }
  Assert: 200

Step 2: 验证 claim_pending 订单创建
  GET /api/v1/admin/shop/orders?source=douyin&status=claim_pending
  Assert: body.items[-1].source='douyin'
  Assert: body.items[-1].external_order_id='DY_ORDER_001'
  Assert: body.items[-1].status='claim_pending'

Step 3: 验证订单金额
  Assert: body.items[-1].amount=99.00 (9900分 → 99.00元)
```

**期望结果**:
- Webhook 正确创建 claim_pending 订单
- source='douyin', external_order_id 正确
- 金额转换正确 (分→元)

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-07-S1 | 正常webhook | 已映射 | webhook | claim_pending |
| MOCK-07-S2 | 金额转换 | 9900分 | 检查 | 99.00元 |
| MOCK-07-S3 | 缺少字段 | 无buyer_mobile | webhook | 400 |

---

### MOCK-08: 抖店 Webhook Mock - claim_pending + claim_token

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `DOUYIN_WEBHOOK_MODE=stub`, `SMS_MODE=stub`
- 抖店下单 Webhook 已触发

**测试步骤**:

```
Step 1: 验证 claim_token 生成
  GET /api/v1/admin/shop/orders?source=douyin&status=claim_pending
  Assert: body.items[-1].claim_token 非空
  Assert: len(claim_token) >= 32
  Assert: claim_token 是 URL-safe 字符串

Step 2: 验证 claim_token 唯一性
  (触发另一个 webhook)
  POST /api/v1/webhooks/douyin/order
  Body: { ... "douyin_order_id": "DY_ORDER_002" ... }
  Assert: 新的 claim_token != 之前的 claim_token

Step 3: 验证 claim_token 过期时间
  Assert: claim_token 有 expiry 字段
  Assert: expiry 默认 24 小时 (或配置值)

Step 4: 验证 sms_log 生成
  GET /api/v1/admin/shop/sms-logs?type=claim_link
  Assert: body.items[-1].content 包含 claim_token
  Assert: body.items[-1].mobile = '137****0000' (脱敏)
```

**期望结果**:
- claim_token 唯一, >= 32字符, URL-safe
- 有过期时间
- 短信内容包含 claim_token
- 手机号脱敏

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-08-S1 | token生成 | webhook后 | 检查 | >=32字符 |
| MOCK-08-S2 | token唯一 | 2个webhook | 检查 | 不同token |
| MOCK-08-S3 | token过期 | 过期后 | 领权 | 422 |
| MOCK-08-S4 | sms_log | webhook后 | 检查 | 含token+脱敏 |

---

### MOCK-09: 抖店 Webhook Mock - 退款

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `DOUYIN_WEBHOOK_MODE=stub`
- 有抖店订单已领权 (status=paid, entitlement active)

**测试步骤**:

```
Step 1: 模拟抖店退款 Webhook
  POST /api/v1/webhooks/douyin/order
  Body: {
    "event": "order.refund",
    "data": {
      "douyin_order_id": "DY_ORDER_001",
      "refund_amount": 9900,
      "refund_time": "2026-08-12 12:00:00"
    }
  }
  Assert: 200

Step 2: 验证订单状态变为 refunded
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_001
  Assert: body.items[0].status='refunded'

Step 3: 验证 entitlement 被撤销
  GET /api/v1/shop/entitlements?order_no={order_no}
  Assert: body.items[0].status='revoked'
  Assert: body.items[0].revoke_reason='douyin_refund'

Step 4: 验证 enrollment 被撤销
  GET /api/v1/shop/entitlements/{ent_id}/enrollments
  Assert: 所有 enrollment status='revoked'
```

**期望结果**:
- 退款 Webhook 后订单 status=refunded
- entitlement status=revoked
- enrollment 全部 revoked

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-09-S1 | 正常退款webhook | paid | webhook | refunded+revoked |
| MOCK-09-S2 | 已退款再退 | refunded | webhook | 幂等 |
| MOCK-09-S3 | 未领权退款 | claim_pending | webhook | refunded(无entitlement) |

---

### MOCK-10: 抖店 Webhook Mock - 重复幂等

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `DOUYIN_WEBHOOK_MODE=stub`
- 已处理过一次下单 Webhook (DY_ORDER_001)

**测试步骤**:

```
Step 1: 发送重复 Webhook (相同 douyin_order_id)
  POST /api/v1/webhooks/douyin/order
  Body: {
    "event": "order.create",
    "data": { "douyin_order_id": "DY_ORDER_001", ... (与首次相同) }
  }
  Assert: 200 (幂等, 不重复创建)

Step 2: 验证未创建重复订单
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_001
  Assert: body.items 数量 = 1 (仍只有1条)

Step 3: 发送第3次重复
  POST /api/v1/webhooks/douyin/order
  Body: { ... 同上 ... }
  Assert: 200 (幂等)

Step 4: 验证 claim_token 未重新生成
  Assert: claim_token 与首次相同 (未重新生成)
```

**期望结果**:
- 重复 Webhook 幂等处理 (200)
- 不创建重复订单
- claim_token 不重新生成

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-10-S1 | 重复2次 | 已处理 | webhook | 幂等200 |
| MOCK-10-S2 | 重复3次 | 已处理2次 | webhook | 幂等200 |
| MOCK-10-S3 | 无重复订单 | 重复后 | 检查 | 仍1条 |

---

### MOCK-11: 抖店 Webhook Mock - 未映射商品拒单

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `DOUYIN_WEBHOOK_MODE=stub`
- 抖店商品 ID DY_UNMAPPED_001 未在系统映射

**测试步骤**:

```
Step 1: 发送未映射商品的 Webhook
  POST /api/v1/webhooks/douyin/order
  Body: {
    "event": "order.create",
    "data": {
      "douyin_order_id": "DY_ORDER_UNMAPPED_001",
      "douyin_product_id": "DY_UNMAPPED_001",
      "buyer_mobile": "13700000000",
      "amount": 9900
    }
  }
  Assert: 200, body.action='rejected'
  Assert: body.reason 包含 '商品未映射' 或 '未找到映射'

Step 2: 验证未创建订单
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_UNMAPPED_001
  Assert: body.items 数量 = 0

Step 3: 验证拒单记录
  GET /api/v1/admin/shop/webhook-logs?external_order_id=DY_ORDER_UNMAPPED_001
  Assert: body.items[0].action='rejected'
  Assert: body.items[0].reason 包含 '未映射'
```

**期望结果**:
- 未映射商品 Webhook 被拒单
- 不创建订单
- 拒单记录留痕

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-11-S1 | 未映射拒单 | 无映射 | webhook | rejected |
| MOCK-11-S2 | 映射已禁用 | mapping disabled | webhook | rejected |
| MOCK-11-S3 | 拒单记录 | rejected后 | 检查 | 有日志 |

---

### MOCK-12: 抖店 Webhook Mock - 领权 token 流转

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `DOUYIN_WEBHOOK_MODE=stub`, `SMS_MODE=stub`
- claim_pending 订单已创建, claim_token 已生成

**测试步骤**:

```
Step 1: 验证 token 在 sms_log 中
  GET /api/v1/admin/shop/sms-logs?type=claim_link&order_no=DY_ORDER_001
  Assert: body.items[0].content 包含 claim_token
  Assert: body.items[0].content 包含领权URL

Step 2: 使用 token 领权
  POST /api/v1/shop/claims/confirm
  Body: { "claim_token": "{token}", "mobile": "13700000000" }
  Assert: 200

Step 3: 验证 token 状态变为 used
  GET /api/v1/admin/shop/claims?token={token}
  Assert: body.status='used', body.used_at 非空

Step 4: 再次使用已用 token
  POST /api/v1/shop/claims/confirm
  Body: { "claim_token": "{token}", "mobile": "13700000000" }
  Assert: 422, body.detail 包含 '已使用' 或 '已领取'

Step 5: 验证完整流转链路
  webhook → claim_pending → sms_log → claim → paid → entitlement
  Assert: 每步数据一致
```

**期望结果**:
- token 从生成到使用完整流转
- 使用后 token 失效
- 完整链路数据一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-12-S1 | token流转 | claim_pending | 领权 | paid+active |
| MOCK-12-S2 | 重复使用 | used | 领权 | 422 |
| MOCK-12-S3 | 链路一致 | 领权后 | 检查 | 数据一致 |

---

### MOCK-13: 短信 Mock - 领权短信

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `SMS_MODE=stub`
- claim_pending 订单已创建

**测试步骤**:

```
Step 1: 验证领权短信自动发送
  GET /api/v1/admin/shop/sms-logs?type=claim_link
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items 数量 >= 1

Step 2: 验证 sms_log 结构
  Assert: body.items[0].type='claim_link'
  Assert: body.items[0].mobile = '137****0000' (脱敏)
  Assert: body.items[0].content 非空
  Assert: body.items[0].content 包含领权URL
  Assert: body.items[0].status='sent'
  Assert: body.items[0].created_at 非空

Step 3: 验证 stub 不实际发送
  Assert: 无外部 SMS API 调用
  Assert: sms_log.provider='stub'

Step 4: 验证短信内容格式
  Assert: content 格式: '您购买的商品{product_name}已到账，请点击链接领取：{claim_url}'
  Assert: claim_url 包含 claim_token
```

**期望结果**:
- 领权短信自动发送 (stub)
- sms_log 结构完整
- 手机号脱敏
- 内容包含领权URL+token
- 无外部调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-13-S1 | 自动发送 | claim_pending | 检查 | sms_log已发送 |
| MOCK-13-S2 | 内容格式 | sms_log | 检查 | 含URL+token |
| MOCK-13-S3 | 脱敏 | sms_log | 检查 | 137****0000 |
| MOCK-13-S4 | 无外发 | stub模式 | 检查 | 无外部调用 |

---

### MOCK-14-N: 短信 Mock - 通知短信

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `SMS_MODE=stub`
- 买家已支付订单 (触发通知短信)

**测试步骤**:

```
Step 1: 验证通知短信发送
  GET /api/v1/admin/shop/sms-logs?type=notify
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: body.items 数量 >= 1

Step 2: 验证通知短信结构
  Assert: body.items[-1].type='notify'
  Assert: body.items[-1].mobile = '137****0000' (脱敏)
  Assert: body.items[-1].content 非空
  Assert: body.items[-1].status='sent'

Step 3: 验证通知类型
  Assert: 通知短信包含: 支付成功通知/发货通知/退款通知等
  Assert: 不同事件触发不同 type 的通知短信

Step 4: 验证 stub 模式
  Assert: sms_log.provider='stub'
  Assert: 无外部 SMS API 调用
```

**期望结果**:
- 通知短信自动发送 (stub)
- sms_log.type='notify'
- 手机号脱敏
- 无外部调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-14-N-S1 | 支付通知 | paid | 检查 | notify sms_log |
| MOCK-14-N-S2 | 退款通知 | refunded | 检查 | notify sms_log |
| MOCK-14-N-S3 | 脱敏 | sms_log | 检查 | 137****0000 |

---

### MOCK-15-N: 短信 Mock - 额度校验超额 422

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `SMS_MODE=stub`
- 商家套餐短信额度=100条/月, 已用100条

**测试步骤**:

```
Step 1: 验证当前额度
  GET /api/v1/shop/subscription
  Assert: body.entitlements.sms_quota=100
  Assert: body.entitlements.sms_used=100

Step 2: 触发短信发送 (额度已满)
  (触发一个需要发短信的事件, 如抖店领权)
  POST /api/v1/webhooks/douyin/order
  Body: { ... }
  Assert: 200 (webhook本身成功)

Step 3: 验证短信发送失败
  GET /api/v1/admin/shop/sms-logs?order_no=DY_ORDER_NEW
  Assert: sms_log.status='failed' 或 无 sms_log
  Assert: 失败原因='额度不足'

Step 4: 验证额度校验逻辑
  Assert: 发送前检查 sms_used >= sms_quota → 拒绝
  Assert: 返回 422 (如果是 API 直接调用发短信)
```

**期望结果**:
- 短信额度用完时发送失败
- sms_log 记录失败状态
- 或直接返回 422

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-15-N-S1 | 额度满 | used=100/quota=100 | 发送 | 失败/422 |
| MOCK-15-N-S2 | 额度余1 | used=99/quota=100 | 发送 | 成功, used=100 |
| MOCK-15-N-S3 | 无限额度 | quota=-1 | 发送 | 成功 |

---

### MOCK-16-N: 课程库 Mock - 支付回调

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `COURSE_LIB_MODE=stub`
- 有课程库关联的商品

**测试步骤**:

```
Step 1: 模拟课程库支付回调
  POST /api/v1/webhooks/course-lib/payment
  Body: {
    "event": "payment.success",
    "data": {
      "course_id": "CL_COURSE_001",
      "buyer_id": "BUYER_001",
      "amount": 9900,
      "transaction_id": "CL_TX_001"
    }
  }
  Assert: 200

Step 2: 验证 entitlement 创建
  GET /api/v1/shop/entitlements?buyer_id=BUYER_001
  Assert: body.items[-1].source='course_lib'
  Assert: body.items[-1].status='active'

Step 3: 验证 stub 模式不实际调用课程库
  Assert: 无外部 HTTP 请求
  Assert: 回调直接处理

Step 4: 验证幂等
  POST /api/v1/webhooks/course-lib/payment (重复)
  Body: { ... 相同 transaction_id ... }
  Assert: 200 (幂等, 不重复创建)
```

**期望结果**:
- 课程库回调创建 entitlement
- source='course_lib'
- stub 模式无外部调用
- 幂等处理

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-16-N-S1 | 正常回调 | stub模式 | webhook | entitlement创建 |
| MOCK-16-N-S2 | 重复回调 | 已处理 | webhook | 幂等 |
| MOCK-16-N-S3 | 无效课程 | 不存在course_id | webhook | 400 |

---

### MOCK-17-N: 微信支付 Mock - 回调成功处理

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`
- 订单已 prepay (status=pending)

**测试步骤**:

```
Step 1: 等待 stub 自动回调
  (prepay 后 stub 自动调用 notify, 等待3秒)
  Assert: 订单状态变为 paid

Step 2: 验证回调处理流程
  Assert: 1. 验签通过
  Assert: 2. 更新订单 status=paid, paid_at=now
  Assert: 3. 创建支付记录 (transaction_id, amount, status=success)
  Assert: 4. 创建 entitlement (status=active)
  Assert: 5. 创建 enrollment (课程类型)
  Assert: 6. 发送通知短信 (如有)

Step 3: 验证各步骤数据一致
  GET /api/v1/shop/orders/{order_no}
  Assert: status='paid', paid_at 非空

  GET /api/v1/admin/shop/payments?order_no={order_no}
  Assert: items[0].status='success', transaction_id 以 'wx_stub_' 开头

  GET /api/v1/shop/entitlements?order_no={order_no}
  Assert: items[0].status='active'
```

**期望结果**:
- 回调成功后完整执行业务流程
- 订单/支付/权益/选课全部创建
- 数据一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-17-N-S1 | 回调全流程 | pending | 自动回调 | paid+ent+enr |
| MOCK-17-N-S2 | 数据一致 | paid后 | 检查 | 各表一致 |
| MOCK-17-N-S3 | 通知发送 | paid后 | 检查 | sms_log已发 |

---

### MOCK-18-N: 抖店 Webhook Mock - 退款 entitlement revoked

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `DOUYIN_WEBHOOK_MODE=stub`
- 抖店订单已领权 (status=paid, entitlement active, enrollment active)

**测试步骤**:

```
Step 1: 模拟退款 Webhook
  POST /api/v1/webhooks/douyin/order
  Body: { "event": "order.refund", "data": { "douyin_order_id": "DY_ORDER_001", "refund_amount": 9900 } }
  Assert: 200

Step 2: 验证 entitlement 撤销
  GET /api/v1/shop/entitlements?order_no={order_no}
  Assert: items[0].status='revoked'
  Assert: items[0].revoke_reason='douyin_refund'
  Assert: items[0].revoked_at 非空

Step 3: 验证 enrollment 撤销
  GET /api/v1/shop/entitlements/{ent_id}/enrollments
  Assert: 所有 items[].status='revoked'

Step 4: 验证买家无法学习
  POST /api/v1/shop/entitlements/{ent_id}/progress
  Assert: 403

Step 5: 验证退款金额一致
  GET /api/v1/admin/shop/orders?external_order_id=DY_ORDER_001
  Assert: items[0].status='refunded'
  Assert: items[0].refund_amount=99.00
```

**期望结果**:
- 退款 Webhook 后权益和选课全部撤销
- 买家无法继续学习
- 退款金额正确

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-18-N-S1 | 退款撤销权益 | paid | refund webhook | revoked |
| MOCK-18-N-S2 | 无法学习 | revoked | progress | 403 |
| MOCK-18-N-S3 | 金额一致 | refunded | 检查 | 99.00 |

---

### MOCK-19-N: 短信 Mock - sms_log 结构验证

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `SMS_MODE=stub`
- 已有多条 sms_log 记录

**测试步骤**:

```
Step 1: 查询全部 sms_log
  GET /api/v1/admin/shop/sms-logs
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200

Step 2: 验证 sms_log 字段结构
  对每条记录验证:
  Assert: id 非空
  Assert: type in ['claim_link', 'notify']
  Assert: mobile 格式为脱敏 (如 137****0000)
  Assert: content 非空
  Assert: status in ['sent', 'failed']
  Assert: provider='stub'
  Assert: created_at 非空
  Assert: merchant_id 非空 (关联商家)

Step 3: 验证按类型筛选
  GET /api/v1/admin/shop/sms-logs?type=claim_link
  Assert: 所有记录 type='claim_link'

  GET /api/v1/admin/shop/sms-logs?type=notify
  Assert: 所有记录 type='notify'

Step 4: 验证按状态筛选
  GET /api/v1/admin/shop/sms-logs?status=sent
  Assert: 所有记录 status='sent'

Step 5: 验证时间范围筛选
  GET /api/v1/admin/shop/sms-logs?start_date=2026-08-01&end_date=2026-08-31
  Assert: 所有记录在时间范围内
```

**期望结果**:
- sms_log 结构完整
- 手机号脱敏
- provider='stub'
- 支持类型/状态/时间筛选

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-19-N-S1 | 字段完整 | 有记录 | 检查 | 所有字段非空 |
| MOCK-19-N-S2 | 类型筛选 | 有2种类型 | 筛选 | 准确过滤 |
| MOCK-19-N-S3 | 脱敏验证 | 有记录 | 检查 | 137****0000 |
| MOCK-19-N-S4 | 时间范围 | 有记录 | 筛选31天 | 准确 |

---

### MOCK-20-N: 课程库 Mock - stub 模式验证

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `COURSE_LIB_MODE=stub`

**测试步骤**:

```
Step 1: 验证环境变量
  Assert: os.environ['COURSE_LIB_MODE'] == 'stub'

Step 2: 验证 stub 不发起外部请求
  (通过 mock interceptor 或日志验证)
  Assert: 无向课程库真实地址的 HTTP 请求

Step 3: 验证 stub 返回固定数据
  GET /api/v1/shop/course-lib/courses
  Assert: 200, body.items 为 stub 预设数据

Step 4: 验证 stub 支付回调
  POST /api/v1/webhooks/course-lib/payment
  Body: { "event": "payment.success", "data": { ... } }
  Assert: 200 (stub 直接处理)

Step 5: 切换为非 stub 模式
  (设置 COURSE_LIB_MODE=real, 重启)
  Assert: API 尝试调用真实课程库地址 (预期失败, 因为无真实服务)
```

**期望结果**:
- stub 模式不发起外部请求
- 返回预设数据
- 直接处理回调
- 非 stub 模式尝试真实调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-20-N-S1 | stub无外发 | COURSE_LIB_MODE=stub | 检查 | 无HTTP |
| MOCK-20-N-S2 | stub固定数据 | stub模式 | 查询 | 预设数据 |
| MOCK-20-N-S3 | 非stub调用 | COURSE_LIB_MODE=real | 查询 | 尝试真实调用 |

---

### MOCK-21-N: 微信支付 Mock - stub 模式环境变量

**前置条件**:
- FastAPI API server 可启动
- 可修改环境变量

**测试步骤**:

```
Step 1: 验证 stub 模式环境变量
  Assert: os.environ['WECHAT_PAY_MODE'] == 'stub'

Step 2: stub 模式下 prepay
  POST /api/v1/shop/orders/{order_no}/prepay
  Assert: 200, prepay_id 以 'wx_stub_' 开头

Step 3: 验证 stub 使用测试密钥
  Assert: 验签使用 TEST_SIGN_KEY (非真实密钥)
  Assert: 密钥来自环境变量或配置

Step 4: 验证 stub 响应延迟
  Assert: prepay 响应时间 < 100ms (即时返回)

Step 5: (可选) 验证非 stub 模式
  设置 WECHAT_PAY_MODE=real
  Assert: prepay 尝试调用真实微信 API (预期超时/失败)
```

**期望结果**:
- WECHAT_PAY_MODE=stub 时使用 stub 逻辑
- 使用测试密钥
- 即时响应
- 非 stub 模式尝试真实调用

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-21-N-S1 | stub环境变量 | WECHAT_PAY_MODE=stub | 检查 | stub逻辑 |
| MOCK-21-N-S2 | 测试密钥 | stub模式 | 验签 | TEST_SIGN_KEY |
| MOCK-21-N-S3 | 响应延迟 | stub模式 | 计时 | <100ms |

---

### MOCK-22-N: 抖店 Webhook Mock - stub 模式环境变量

**前置条件**:
- FastAPI API server 可启动
- 可修改环境变量

**测试步骤**:

```
Step 1: 验证 stub 模式环境变量
  Assert: os.environ['DOUYIN_WEBHOOK_MODE'] == 'stub'

Step 2: stub 模式下接收 webhook
  POST /api/v1/webhooks/douyin/order
  Body: { "event": "order.create", "data": { ... } }
  Assert: 200 (stub 直接处理, 不验证真实抖店签名)

Step 3: 验证 stub 不验证真实签名
  Assert: webhook 请求不需要真实抖店签名
  Assert: 或使用测试签名密钥

Step 4: 验证 stub 模式完整流程
  webhook → claim_pending → sms_log → claim → paid → entitlement
  Assert: 全流程在 stub 模式下可完成

Step 5: (可选) 非 stub 模式
  设置 DOUYIN_WEBHOOK_MODE=real
  Assert: webhook 需要验证真实抖店签名 (预期验签失败)
```

**期望结果**:
- DOUYIN_WEBHOOK_MODE=stub 时使用 stub 逻辑
- 不验证真实签名
- 全流程可完成

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-22-N-S1 | stub环境变量 | DOUYIN_WEBHOOK_MODE=stub | 检查 | stub逻辑 |
| MOCK-22-N-S2 | 不验证签名 | stub模式 | webhook | 200 |
| MOCK-22-N-S3 | 全流程 | stub模式 | 完整流程 | 全通 |

---

### MOCK-23-N: Mock 服务 - 并发幂等

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`, `DOUYIN_WEBHOOK_MODE=stub`
- 并发测试工具 (pytest-asyncio / httpx async)

**测试步骤**:

```
Step 1: 并发发送相同抖店 webhook
  (同时发送5个相同 douyin_order_id 的 webhook)
  async def concurrent_webhooks():
    tasks = [client.post('/api/v1/webhooks/douyin/order', json=same_body) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    return results

  Assert: 所有响应 200
  Assert: 仅创建1条订单 (幂等)

Step 2: 并发发送相同微信回调
  (同时发送5个相同 transaction_id 的 notify)
  Assert: 所有响应 200
  Assert: 订单状态仅更新一次

Step 3: 并发领权
  (同时用相同 claim_token 领权)
  Assert: 仅1个成功 (200), 其余 422
  Assert: entitlement 仅创建1条

Step 4: 验证数据库一致性
  SELECT COUNT(*) FROM shop_orders WHERE external_order_id = 'DY_ORDER_CONCURRENT'
  Assert: count = 1
```

**期望结果**:
- 并发请求幂等处理
- 不创建重复数据
- 数据库一致

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-23-N-S1 | 并发webhook | stub模式 | 5并发 | 1条订单 |
| MOCK-23-N-S2 | 并发回调 | stub模式 | 5并发 | 1次更新 |
| MOCK-23-N-S3 | 并发领权 | 有效token | 5并发 | 1成功4失败 |

---

### MOCK-24-N: Mock 服务 - 错误重试

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- `WECHAT_PAY_MODE=stub`
- 可模拟 stub 返回错误

**测试步骤**:

```
Step 1: 模拟 stub 支付回调处理失败
  (通过测试钩子让 stub 首次回调处理失败)
  POST /api/v1/payment/wx/notify
  Body: { "out_trade_no": "TEST_RETRY_001", ..., "simulate_failure": true }
  Assert: 500 (首次失败)

Step 2: 验证重试机制
  (stub 或系统自动重试)
  Assert: 第2次回调成功
  GET /api/v1/shop/orders/TEST_RETRY_001
  Assert: body.status='paid'

Step 3: 模拟抖店 webhook 处理失败
  POST /api/v1/webhooks/douyin/order
  Body: { ..., "simulate_failure": true }
  Assert: 500 (首次失败)

Step 4: 验证 webhook 重试
  (重试 webhook)
  POST /api/v1/webhooks/douyin/order
  Body: { ... (相同, 无 simulate_failure) }
  Assert: 200

Step 5: 验证最终数据一致
  Assert: 订单正确创建, 数据完整
```

**期望结果**:
- 失败后可重试
- 重试后数据一致
- 不产生重复数据

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-24-N-S1 | 回调失败重试 | 模拟失败 | 重试 | 成功 |
| MOCK-24-N-S2 | webhook失败重试 | 模拟失败 | 重试 | 成功 |
| MOCK-24-N-S3 | 重试不重复 | 失败后 | 重试 | 无重复 |

---

### MOCK-25-N: Mock 服务 - 清理重置

**前置条件**:
- FastAPI API server 已启动 (API live 常 8003)
- 所有 Mock 模式开启
- 测试数据已产生

**测试步骤**:

```
Step 1: 清理测试数据
  POST /api/v1/test/reset-mock-data
  Headers: Authorization: Bearer ADMIN_TOKEN
  Assert: 200

Step 2: 验证清理结果
  GET /api/v1/admin/shop/sms-logs
  Assert: body.items 数量 = 0

  GET /api/v1/admin/shop/orders?source=douyin
  Assert: body.items 数量 = 0

  GET /api/v1/admin/shop/webhook-logs
  Assert: body.items 数量 = 0

Step 3: 验证 stub 状态重置
  GET /api/v1/test/mock-status
  Assert: stub 计数器归零
  Assert: stub 状态干净

Step 4: 重新执行完整流程
  (重新执行 F1 私域支付开权全流程)
  Assert: 流程正常完成
  Assert: 数据正确生成

Step 5: 验证无残留数据影响
  Assert: 新数据与清理前无关联
  Assert: claim_token 全新生成
```

**期望结果**:
- 清理后所有 mock 数据清空
- stub 状态重置
- 重新执行流程正常
- 无残留数据

**边界值/场景测试**:

| 场景ID | 场景 | 前置状态 | 操作 | 期望结果 |
|--------|------|---------|------|---------|
| MOCK-25-N-S1 | 清理数据 | 有数据 | reset | 清空 |
| MOCK-25-N-S2 | 重置stub | 有计数 | reset | 归零 |
| MOCK-25-N-S3 | 重新执行 | 清理后 | 执行流程 | 正常 |
| MOCK-25-N-S4 | 无残留 | 清理后 | 检查 | 无关联 |

---

## Round 6: Security/PII 安全测试用例

> 覆盖加密存储/日志脱敏/API脱敏/权限隔离/敏感字段揭露/保留期, 共 30 个用例 (15 existing + 15 new)
> 测试框架: pytest + SQLAlchemy (数据库验证) + grep (日志验证)
> 加密密钥: SHOP_PII_KEY 环境变量

---

