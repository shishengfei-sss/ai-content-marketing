"""商城全量测试配置：测试用例定义、Mock/Stub 配置、期望结果。

被 run_shop_all.py 导入，定义 7 个 Round 的全部测试用例、外部服务 Stub
配置（微信支付 / 抖音 / 短信）以及每个用例的期望结果。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


# ── Round 枚举 ────────────────────────────────────────────────────

class TestRound(IntEnum):
    """7 轮测试的枚举值，与 CLI ``--round N`` 一一对应。"""

    BACKEND_API = 1        # 后端 API 验收（verify_shop_m0 ~ m8）
    FRONTEND_WEB = 2       # Web 端 UI 测试（Playwright）
    FRONTEND_MP = 3        # 小程序 UI 测试（Playwright mobile）
    E2E_INTEGRATION = 4    # E2E 集成流程（F0-F12）
    MOCK_EXTERNAL = 5      # Mock 外部集成（微信支付 + 抖音 + 短信）
    SECURITY_PII = 6       # 安全 & PII 测试
    REGRESSION = 7         # 回归测试（CRM + Agent + M0）


ROUND_NAMES: dict[int, str] = {
    1: "Round 1: 后端 API 验收 (verify_shop_m0 ~ m8)",
    2: "Round 2: Web 端 UI 测试 (Playwright)",
    3: "Round 3: 小程序 UI 测试 (Playwright Mobile)",
    4: "Round 4: E2E 集成流程 (F0-F12)",
    5: "Round 5: Mock 外部集成 (微信支付 + 抖音 + 短信)",
    6: "Round 6: 安全 & PII 测试",
    7: "Round 7: 回归测试 (CRM + Agent + M0)",
}

# ── 里程碑顺序（--through 参数可选值）──────────────────────────────

# 执行顺序（依赖驱动，非 PRD 编号顺序）
# M0 → M1(套餐) → M2(状态) → M4(商品) → M5(订单) → M3(支付) → M6(核销) → M7(公域) → M8(可选)
MILESTONE_ORDER: list[str] = [
    "M0", "M0f", "M1", "M2", "M4", "M5", "M3", "M6", "M7", "Mx", "M8",
]


# ── 数据类 ────────────────────────────────────────────────────────

@dataclass
class TestCaseDef:
    """单个测试用例定义。

    Attributes:
        test_id:          唯一标识，如 ``SH-BE-M0-001``。
        name:             人类可读名称。
        category:         分类标签（permissions / onboarding / order 等）。
        round:            所属 Round（1-7）。
        script:           对应脚本或测试文件名。
        milestone:        关联里程碑（仅 Round 1），用于 ``--through`` 过滤。
        expected_status:  期望结果 — ``"pass"`` 或 ``"skip"``。
        expected_http:    期望 HTTP 状态码（若有）。
        expected_fields:  期望响应中包含的字段及值。
        detail:           补充说明。
    """

    test_id: str
    name: str
    category: str
    round: int
    script: str
    milestone: str | None = None
    expected_status: str = "pass"
    expected_http: int | None = None
    expected_fields: dict[str, Any] = field(default_factory=dict)
    detail: str = ""


@dataclass
class RoundStep:
    """Round 内的单个执行步骤（一个脚本或 pytest 文件）。

    Attributes:
        name:      显示名称。
        script:    脚本文件名（相对于 tests/ 目录）。
        milestone: 关联里程碑（仅 Round 1）。
        runner:    执行方式 — ``"subprocess"`` 或 ``"pytest"``。
    """

    name: str
    script: str
    milestone: str | None = None
    runner: str = "subprocess"


@dataclass
class StubEndpoint:
    """Mock Stub 的单个端点定义。"""

    method: str
    path: str
    response_status: int
    response_body: dict[str, Any]
    description: str = ""


@dataclass
class StubConfig:
    """外部服务 Mock Stub 完整配置。

    Attributes:
        name:        Stub 标识（wechat_pay / douyin / sms）。
        description: 用途说明。
        base_url:    Mock 服务基础 URL。
        endpoints:   端点列表。
        env_vars:    启用 Stub 需要设置的环境变量。
    """

    name: str
    description: str
    base_url: str
    endpoints: list[StubEndpoint]
    env_vars: dict[str, str]


# ── Mock / Stub 配置 ──────────────────────────────────────────────

WECHAT_PAY_STUB = StubConfig(
    name="wechat_pay",
    description="微信支付 Mock Stub — 模拟统一下单、查询、退款、回调通知",
    base_url="http://mock.wechat-pay.local",
    endpoints=[
        StubEndpoint(
            method="POST",
            path="/v3/pay/transactions/native",
            response_status=200,
            response_body={
                "code": "SUCCESS",
                "message": "OK",
                "code_url": "weixin://wxpay/bizpayurl?pr=mock_p_001",
                "transaction_id": "mock_txn_4200000000202401010001",
                "out_trade_no": "SHOP_MOCK_{timestamp}",
            },
            description="Native 支付下单 — 返回二维码链接和模拟交易号",
        ),
        StubEndpoint(
            method="GET",
            path="/v3/pay/transactions/out-trade-no/{out_trade_no}",
            response_status=200,
            response_body={
                "code": "SUCCESS",
                "trade_state": "SUCCESS",
                "transaction_id": "mock_txn_4200000000202401010001",
                "amount": {"total": 9900, "currency": "CNY"},
                "payer": {"openid": "mock_openid_001"},
                "success_time": "2024-01-01T12:00:00+08:00",
            },
            description="查询订单支付状态 — 返回 SUCCESS 状态",
        ),
        StubEndpoint(
            method="POST",
            path="/v3/refund/domestic/refunds",
            response_status=200,
            response_body={
                "code": "SUCCESS",
                "refund_id": "mock_refund_5000000000202401010001",
                "out_refund_no": "SHOP_REFUND_{timestamp}",
                "refund_status": "PROCESSING",
                "amount": {"refund": 9900, "total": 9900, "currency": "CNY"},
            },
            description="申请退款 — 返回退款处理中状态",
        ),
        StubEndpoint(
            method="POST",
            path="/v3/notify/pay",
            response_status=200,
            response_body={
                "id": "mock_evt_001",
                "event_type": "TRANSACTION.SUCCESS",
                "resource": {
                    "transaction_id": "mock_txn_4200000000202401010001",
                    "trade_state": "SUCCESS",
                    "amount": {"total": 9900},
                },
            },
            description="支付回调通知 — 模拟微信支付成功回调",
        ),
        StubEndpoint(
            method="GET",
            path="/v3/bill/tradebill",
            response_status=200,
            response_body={
                "code": "SUCCESS",
                "download_url": "https://mock.wechat-pay.local/bill/tradebill_001.csv",
                "hash_type": "SHA1",
                "hash_value": "mock_hash_001",
            },
            description="下载交易账单 — 返回模拟下载链接",
        ),
    ],
    env_vars={
        "WECHAT_PAY_MOCK": "1",
        "WECHAT_PAY_MOCK_BASE_URL": "http://mock.wechat-pay.local",
        "WECHAT_PAY_APPID": "wx_mock_appid_001",
        "WECHAT_PAY_MCHID": "mock_mchid_001",
        "WECHAT_PAY_API_KEY": "mock_api_key_001",
    },
)

DOUYIN_STUB = StubConfig(
    name="douyin",
    description="抖音 Mock Stub — 模拟内容发布、状态查询、数据同步",
    base_url="http://mock.douyin.local",
    endpoints=[
        StubEndpoint(
            method="POST",
            path="/api/publish",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {
                    "task_id": "mock_dy_task_001",
                    "item_id": "mock_dy_item_001",
                    "publish_status": "publishing",
                },
            },
            description="发布内容到抖音 — 返回任务ID和发布中状态",
        ),
        StubEndpoint(
            method="GET",
            path="/api/status/{task_id}",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {
                    "task_id": "mock_dy_task_001",
                    "item_id": "mock_dy_item_001",
                    "publish_status": "published",
                    "video_url": "https://mock.douyin.local/video/001.mp4",
                    "cover_url": "https://mock.douyin.local/cover/001.jpg",
                },
            },
            description="查询发布状态 — 返回已发布状态",
        ),
        StubEndpoint(
            method="POST",
            path="/api/data/sync",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {
                    "sync_id": "mock_sync_001",
                    "synced_at": "2024-01-01T12:00:00+08:00",
                    "metrics": {
                        "views": 15280,
                        "likes": 1024,
                        "comments": 56,
                        "shares": 128,
                    },
                },
            },
            description="同步数据指标 — 返回播放量、点赞、评论、分享数",
        ),
        StubEndpoint(
            method="GET",
            path="/api/video/list",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {
                    "total": 2,
                    "items": [
                        {
                            "item_id": "mock_dy_item_001",
                            "title": "商城新品上线",
                            "cover_url": "https://mock.douyin.local/cover/001.jpg",
                            "create_time": "2024-01-01T12:00:00+08:00",
                        },
                        {
                            "item_id": "mock_dy_item_002",
                            "title": "限时折扣活动",
                            "cover_url": "https://mock.douyin.local/cover/002.jpg",
                            "create_time": "2024-01-02T14:00:00+08:00",
                        },
                    ],
                },
            },
            description="查询已发布视频列表 — 返回 2 条视频",
        ),
        StubEndpoint(
            method="DELETE",
            path="/api/video/{item_id}",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {"deleted": True, "item_id": "mock_dy_item_001"},
            },
            description="删除已发布视频 — 返回删除成功",
        ),
    ],
    env_vars={
        "DOUYIN_MOCK": "1",
        "DOUYIN_MOCK_BASE_URL": "http://mock.douyin.local",
        "DOUYIN_CLIENT_KEY": "mock_dy_client_key_001",
        "DOUYIN_CLIENT_SECRET": "mock_dy_client_secret_001",
    },
)

SMS_STUB = StubConfig(
    name="sms",
    description="短信 Mock Stub — 模拟验证码发送与校验（复用 sms_service 内存 Store）",
    base_url="http://mock.sms.local",
    endpoints=[
        StubEndpoint(
            method="POST",
            path="/sms/send-code",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {
                    "sent": True,
                    "phone": "139****0099",
                    "expire_seconds": 300,
                    "stub": True,
                },
            },
            description="发送验证码 — 返回脱敏手机号和过期时间",
        ),
        StubEndpoint(
            method="POST",
            path="/sms/verify-code",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {"verified": True, "phone": "139****0099"},
            },
            description="校验验证码 — 返回验证成功",
        ),
        StubEndpoint(
            method="POST",
            path="/sms/send-notify",
            response_status=200,
            response_body={
                "code": 0,
                "message": "success",
                "data": {
                    "sent": True,
                    "phone": "139****0099",
                    "template_id": "SHOP_ORDER_NOTIFY",
                    "stub": True,
                },
            },
            description="发送通知短信 — 返回发送成功和模板ID",
        ),
    ],
    env_vars={
        "SMS_MOCK": "1",
        "SMS_SEND_INTERVAL_SEC": "0",
    },
)

ALL_STUBS: dict[str, StubConfig] = {
    "wechat_pay": WECHAT_PAY_STUB,
    "douyin": DOUYIN_STUB,
    "sms": SMS_STUB,
}


# ── Round 步骤定义 ────────────────────────────────────────────────

ROUND_STEPS: dict[int, list[RoundStep]] = {
    # ── Round 1: 后端 API 验收（按依赖执行顺序）──
    1: [
        RoundStep("M0 权限入驻基线", "verify_shop_m0.py", "M0"),
        RoundStep("M0f 前端壳与联测冒烟", "verify_shop_m0f.py", "M0f"),
        RoundStep("M1 套餐订阅", "verify_shop_m1.py", "M1"),
        RoundStep("M2 商家状态管理", "verify_shop_m2.py", "M2"),
        RoundStep("M4 商品内容管理", "verify_shop_m4.py", "M4"),
        RoundStep("M5 订单与权益", "verify_shop_m5.py", "M5"),
        RoundStep("M3 支付硬验收", "verify_shop_m3.py", "M3"),
        RoundStep("M6 核销与开票", "verify_shop_m6.py", "M6"),
        RoundStep("M7 公域Mx对接", "verify_shop_m7.py", "M7"),
        RoundStep("A14 暂停同步与日志", "verify_shop_a14.py", "M7"),
        RoundStep("A14-A 三步向导新建映射", "verify_shop_a14a.py", "M7"),
        RoundStep("A14-B 拒审原因与重提", "verify_shop_a14b.py", "M7"),
        RoundStep("Mx Mock首演附录B", "verify_shop_mx.py", "Mx"),
        RoundStep("买家履约页 M06/M10/M13", "verify_shop_mp_fulfill.py", "M6"),
        RoundStep("买家店首页 M02～M05", "verify_shop_mp_storefront.py", "M5"),
        RoundStep("开箱交付 D1/D2/D7", "verify_shop_box.py", "M0"),
        RoundStep("A02 商品列表§0b", "verify_shop_a02.py", "M4"),
        RoundStep("P04 平台类目与A03提审", "verify_shop_p04.py", "M4"),
        RoundStep("P04-E/P08-F 编码规则", "verify_shop_p04e.py", "M4"),
        RoundStep("A19 单店设置", "verify_shop_a19.py", "M4"),
        RoundStep("A17 店铺管理/开业闸", "verify_shop_a17.py", "M4"),
        RoundStep("A18 套餐信息", "verify_shop_a18.py", "M4"),
        RoundStep("A15 支付与进件", "verify_shop_a15.py", "M4"),
        RoundStep("A15-S 短信与领权", "verify_shop_a15s.py", "M4"),
        RoundStep("A16 角色与成员", "verify_shop_a16.py", "M4"),
        RoundStep("A-SET 设置中心", "verify_shop_aset.py", "M4"),
        RoundStep("A01 交易看板", "verify_shop_a01.py", "M4"),
        RoundStep("P06 商户支付进件", "verify_shop_p06.py", "M7"),
        RoundStep("P12 短信管理", "verify_shop_p12.py", "M7"),
        RoundStep("A23 公域对接设置", "verify_shop_a23.py", "M7"),
        RoundStep("P01 平台经营看板", "verify_shop_p01.py", "M7"),
        RoundStep("P05 清结算", "verify_shop_p05.py", "M7"),
        RoundStep("P07 违规稽查", "verify_shop_p07.py", "M7"),
        RoundStep("P11 订阅台账", "verify_shop_p11.py", "M7"),
        RoundStep("P02-B 商家详情", "verify_shop_p02b.py", "M7"),
        RoundStep("P10 套餐配置", "verify_shop_p10.py", "M7"),
        RoundStep("P09 商品审核", "verify_shop_p09.py", "M7"),
        RoundStep("P08 角色与编码", "verify_shop_p08.py", "M7"),
        RoundStep("P03 入驻审核", "verify_shop_p03.py", "M7"),
        RoundStep("P02-C/D/F 暂停恢复清退", "verify_shop_p02c.py", "M7"),
        RoundStep("P02-E/T 分配管家与标签", "verify_shop_p02e.py", "M7"),
        RoundStep("A03 商品编辑挂CMS引用", "verify_shop_a03.py", "M4"),
        RoundStep("A04–A06 专栏课时资料包CMS", "verify_shop_a04.py", "M4"),
        RoundStep("A10 订单详情", "verify_shop_a10.py", "M5"),
        RoundStep("A11/A12 买家与权益", "verify_shop_a11.py", "M5"),
        RoundStep("A13 开票申请处理", "verify_shop_a13.py", "M6"),
        RoundStep("A09-A/B/C 写操作弹窗", "verify_shop_a09abc.py", "M5"),
        RoundStep("M11/M12 买家订单中心", "verify_shop_m11.py", "M5"),
        RoundStep("A07 服务时段与真槽预约", "verify_shop_a07.py", "M6"),
        RoundStep("A08 核销台与核销记录", "verify_shop_a08.py", "M6"),
    ],
    # ── Round 2: Web 端 UI 测试（Playwright）──
    2: [
        RoundStep("平台端-商家列表与入驻审核", "automated/ui/test_ui_shop_admin.py", runner="pytest"),
        RoundStep("商家端-控制台与店铺设置", "automated/ui/test_ui_shop_merchant.py", runner="pytest"),
        RoundStep("商家端-商品与内容管理", "automated/ui/test_ui_shop_catalog.py", runner="pytest"),
        RoundStep("商家端-订单与权益管理", "automated/ui/test_ui_shop_orders.py", runner="pytest"),
        RoundStep("平台端-数据看板与结算", "automated/ui/test_ui_shop_dashboard.py", runner="pytest"),
        RoundStep("M0f 联测壳 FE-P02/P03/A20", "automated/ui/test_ui_shop_m0f_fe.py", runner="pytest"),
        RoundStep("02 金标准写操作联测 FE-*", "automated/ui/test_ui_shop_fe_gold.py", runner="pytest"),
        RoundStep("02 金标准写库主路径 FE-*", "automated/ui/test_ui_shop_fe_gold_write.py", runner="pytest"),
    ],
    # ── Round 3: 小程序 UI 测试（Playwright Mobile）──
    3: [
        RoundStep("小程序-首页与商品浏览", "automated/ui/test_ui_shop_mp_home.py", runner="pytest"),
        RoundStep("小程序-商品详情与SKU", "automated/ui/test_ui_shop_mp_product.py", runner="pytest"),
        RoundStep("小程序-下单与支付流程", "automated/ui/test_ui_shop_mp_order.py", runner="pytest"),
        RoundStep("小程序-个人中心与订单", "automated/ui/test_ui_shop_mp_profile.py", runner="pytest"),
        RoundStep("小程序-履约学课预约开票领权", "automated/ui/test_ui_shop_mp_fulfill.py", runner="pytest"),
    ],
    # ── Round 4: E2E 集成流程 ──
    4: [
        RoundStep("F0 入驻→审核→开店全流程", "verify_shop_e2e_f0.py"),
        RoundStep("F1 套餐订阅→权益开通", "verify_shop_e2e_f1.py"),
        RoundStep("F2 商品上架→内容发布", "verify_shop_e2e_f2.py"),
        RoundStep("F3 买家下单→权益生成", "verify_shop_e2e_f3.py"),
        RoundStep("F4 支付回调→权益激活(Mock)", "verify_shop_e2e_f4.py"),
        RoundStep("F5 核销码生成→店员核销", "verify_shop_e2e_f5.py"),
        RoundStep("F6 退款→权益撤销", "verify_shop_e2e_f6.py"),
        RoundStep("F7 商家暂停→已购不阻断", "verify_shop_e2e_f7.py"),
        RoundStep("F8 套餐叠加→权益合并", "verify_shop_e2e_f8.py"),
        RoundStep("F9 多店权益→跨店核销", "verify_shop_e2e_f9.py"),
        RoundStep("F10 清结算→对账闭环", "verify_shop_e2e_f10.py"),
        RoundStep("F11 开票申请→电子发票", "verify_shop_e2e_f11.py"),
        RoundStep("F12 公域Mx端到端闭环(Mock)", "verify_shop_e2e_f12.py"),
    ],
    # ── Round 5: Mock 外部集成（虚拟对接测试）──
    5: [
        RoundStep("微信支付 Mock(下单/回调/退款/账单)", "verify_shop_mock_wechat_pay.py"),
        RoundStep("抖音公域 Mock(发布/数据/视频管理)", "verify_shop_mock_douyin.py"),
        RoundStep("短信通知 Mock(验证码/通知)", "verify_shop_mock_sms.py"),
    ],
    # ── Round 6: 安全 & PII 测试 ──
    6: [
        RoundStep("权限隔离与越权防护", "verify_shop_security_permissions.py"),
        RoundStep("PII脱敏(手机号/身份证/银行卡)", "verify_shop_security_pii.py"),
        RoundStep("支付安全(幂等/签名/密钥)", "verify_shop_security_payment.py"),
        RoundStep("注入防护(SQL/XSS/CSRF)", "verify_shop_security_injection.py"),
    ],
    # ── Round 7: 回归测试 ──
    7: [
        RoundStep("CRM 全量回归", "run_crm_all.py"),
        RoundStep("Agent T0+A0~C6 回归", "run_agent_a_c.py"),
        RoundStep("商城 M0 回归", "verify_shop_m0.py"),
    ],
}


# ── 测试用例列表 ──────────────────────────────────────────────────

TEST_CASES: list[TestCaseDef] = [
    # ══════════════════════════════════════════════════════════════
    # Round 1: 后端 API 验收
    # ══════════════════════════════════════════════════════════════

    # ── M0: 权限与入驻（源自 verify_shop_m0.py VS-1 ~ VS-26）──
    TestCaseDef("SH-BE-M0-001", "shop商家权限数量37", "permissions", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-002", "platform.shop权限数量19", "permissions", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-003", "ALL含shop不含platform", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-004", "内置角色数4", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-005", "管家无subscription.manage", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-006", "运营无onboarding.initiate", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-007", "管家有onboarding.initiate", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-008", "管家/运营有merchant.tag", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-009", "仅运营可新建标签名", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-010", "店员仅核销", "permissions", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-011", "租户me含shop权限", "auth", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-012", "商家catalog", "permissions", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-013", "商家角色列表", "permissions", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-014", "平台me含platform_shop", "auth", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-015", "平台catalog", "permissions", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-016", "平台商家列表", "merchant", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-017", "续费待办", "merchant", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-018", "入驻租户候选", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-019", "入驻预填", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-020", "发起入驻", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=201),
    TestCaseDef("SH-BE-M0-021", "重复入驻409", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=409),
    TestCaseDef("SH-BE-M0-022", "审核中详情", "merchant", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-023", "已入驻详情", "merchant", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-024", "详情含店铺", "merchant", 1, "verify_shop_m0.py", "M0"),
    TestCaseDef("SH-BE-M0-025", "P03待审列表", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-026", "平台OCR stub", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-027", "P03审核通过", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-028", "商家OCR stub", "onboarding", 1, "verify_shop_m0.py", "M0", expected_http=200),
    TestCaseDef("SH-BE-M0-029", "续费申请", "merchant", 1, "verify_shop_m0.py", "M0", expected_http=201),
    TestCaseDef("SH-BE-M0-030", "服务跟进备注", "merchant", 1, "verify_shop_m0.py", "M0", expected_http=201),
    # ── M0f: 前端壳 + API 冒烟 ──
    TestCaseDef("SH-BE-M0F-001", "路由与页面文件存在", "frontend", 1, "verify_shop_m0f.py", "M0f"),
    TestCaseDef("SH-BE-M0F-002", "平台token商家列表200", "frontend", 1, "verify_shop_m0f.py", "M0f", expected_http=200),
    TestCaseDef("SH-BE-M0F-003", "商家token调平台403", "frontend", 1, "verify_shop_m0f.py", "M0f", expected_http=403),
    TestCaseDef("SH-BE-M0F-004", "入驻全流程API冒烟", "frontend", 1, "verify_shop_m0f.py", "M0f"),
    TestCaseDef("SH-BE-M0F-005", "switchWorkspace后workspace_mode", "frontend", 1, "verify_shop_m0f.py", "M0f"),

    # ── M1: 商家自助入驻 ──
    TestCaseDef("SH-BE-M1-001", "商家提交入驻申请", "onboarding", 1, "verify_shop_m1.py", "M1", expected_http=201),
    TestCaseDef("SH-BE-M1-002", "上传营业执照OCR", "onboarding", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-003", "资质文件上传", "onboarding", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-004", "申请状态查询", "onboarding", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-005", "审核驳回后补充材料", "onboarding", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-006", "合同签订与确认", "onboarding", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-007", "初始店铺自动创建", "store", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-008", "默认角色权限分配", "permissions", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-009", "入驻欢迎消息", "notification", 1, "verify_shop_m1.py", "M1", expected_http=200),
    TestCaseDef("SH-BE-M1-010", "入驻后引导设置", "onboarding", 1, "verify_shop_m1.py", "M1", expected_http=200),

    # ── M2: 店铺管理 ──
    TestCaseDef("SH-BE-M2-001", "创建店铺", "store", 1, "verify_shop_m2.py", "M2", expected_http=201),
    TestCaseDef("SH-BE-M2-002", "店铺列表分页", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-003", "更新店铺信息", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-004", "店铺启停状态切换", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-005", "营业时间配置", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-006", "配送区域设置", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-007", "店铺logo上传", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-008", "店铺额度校验", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-009", "店员管理", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),
    TestCaseDef("SH-BE-M2-010", "店铺数据统计", "store", 1, "verify_shop_m2.py", "M2", expected_http=200),

    # ── M3: 商品目录与库存 ──
    TestCaseDef("SH-BE-M3-001", "创建商品分类", "product", 1, "verify_shop_m3.py", "M3", expected_http=201),
    TestCaseDef("SH-BE-M3-002", "创建商品SPU", "product", 1, "verify_shop_m3.py", "M3", expected_http=201),
    TestCaseDef("SH-BE-M3-003", "创建商品SKU", "product", 1, "verify_shop_m3.py", "M3", expected_http=201),
    TestCaseDef("SH-BE-M3-004", "商品上下架", "product", 1, "verify_shop_m3.py", "M3", expected_http=200),
    TestCaseDef("SH-BE-M3-005", "库存增减", "inventory", 1, "verify_shop_m3.py", "M3", expected_http=200),
    TestCaseDef("SH-BE-M3-006", "库存预警阈值", "inventory", 1, "verify_shop_m3.py", "M3", expected_http=200),
    TestCaseDef("SH-BE-M3-007", "商品批量导入", "product", 1, "verify_shop_m3.py", "M3", expected_http=200),
    TestCaseDef("SH-BE-M3-008", "商品搜索与筛选", "product", 1, "verify_shop_m3.py", "M3", expected_http=200),
    TestCaseDef("SH-BE-M3-009", "SKU规格组合", "product", 1, "verify_shop_m3.py", "M3", expected_http=200),
    TestCaseDef("SH-BE-M3-010", "库存盘点", "inventory", 1, "verify_shop_m3.py", "M3", expected_http=200),

    # ── M4: 订单管理 ──
    TestCaseDef("SH-BE-M4-001", "创建订单", "order", 1, "verify_shop_m4.py", "M4", expected_http=201),
    TestCaseDef("SH-BE-M4-002", "订单详情查询", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-003", "订单状态流转", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-004", "订单发货", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-005", "订单确认收货", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-006", "订单取消", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-007", "订单列表筛选", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-008", "核销码验证", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-009", "订单导出", "order", 1, "verify_shop_m4.py", "M4", expected_http=200),
    TestCaseDef("SH-BE-M4-010", "售后工单创建", "order", 1, "verify_shop_m4.py", "M4", expected_http=201),

    # ── M5: 支付与结算 ──
    TestCaseDef("SH-BE-M5-001", "发起支付", "payment", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-002", "支付回调处理", "payment", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-003", "退款申请", "payment", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-004", "退款回调处理", "payment", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-005", "结算单生成", "settlement", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-006", "佣金计算", "settlement", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-007", "对账文件下载", "settlement", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-008", "支付方式配置", "payment", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-009", "交易流水查询", "payment", 1, "verify_shop_m5.py", "M5", expected_http=200),
    TestCaseDef("SH-BE-M5-010", "提现申请", "settlement", 1, "verify_shop_m5.py", "M5", expected_http=201),

    # ── M6: 促销与优惠券 ──
    TestCaseDef("SH-BE-M6-001", "创建促销活动", "promotion", 1, "verify_shop_m6.py", "M6", expected_http=201),
    TestCaseDef("SH-BE-M6-002", "促销活动上下线", "promotion", 1, "verify_shop_m6.py", "M6", expected_http=200),
    TestCaseDef("SH-BE-M6-003", "创建优惠券模板", "coupon", 1, "verify_shop_m6.py", "M6", expected_http=201),
    TestCaseDef("SH-BE-M6-004", "发放优惠券", "coupon", 1, "verify_shop_m6.py", "M6", expected_http=200),
    TestCaseDef("SH-BE-M6-005", "核销优惠券", "coupon", 1, "verify_shop_m6.py", "M6", expected_http=200),
    TestCaseDef("SH-BE-M6-006", "满减规则校验", "promotion", 1, "verify_shop_m6.py", "M6", expected_http=200),
    TestCaseDef("SH-BE-M6-007", "折扣叠加规则", "promotion", 1, "verify_shop_m6.py", "M6", expected_http=200),
    TestCaseDef("SH-BE-M6-008", "促销效果统计", "promotion", 1, "verify_shop_m6.py", "M6", expected_http=200),
    TestCaseDef("SH-BE-M6-009", "优惠券过期处理", "coupon", 1, "verify_shop_m6.py", "M6", expected_http=200),
    TestCaseDef("SH-BE-M6-010", "限时秒杀活动", "promotion", 1, "verify_shop_m6.py", "M6", expected_http=200),

    # ── M7: 数据看板 ──
    TestCaseDef("SH-BE-M7-001", "店铺概览数据", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-002", "销售趋势图表", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-003", "商品销量排行", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-004", "客户画像分析", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-005", "流量来源分析", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-006", "转化漏斗数据", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-007", "平台汇总报表", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-008", "数据导出CSV", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-009", "实时订单监控", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),
    TestCaseDef("SH-BE-M7-010", "预警通知配置", "analytics", 1, "verify_shop_m7.py", "M7", expected_http=200),

    # ── M8: 通知与消息 ──
    TestCaseDef("SH-BE-M8-001", "订单状态通知", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-002", "支付成功通知", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-003", "发货通知", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-004", "退款通知", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-005", "库存预警通知", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-006", "促销活动通知", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-007", "站内信列表", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-008", "消息已读标记", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-009", "通知模板配置", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),
    TestCaseDef("SH-BE-M8-010", "推送渠道管理", "notification", 1, "verify_shop_m8.py", "M8", expected_http=200),

    # ══════════════════════════════════════════════════════════════
    # Round 2: Web 端 UI 测试 (Playwright)
    # ══════════════════════════════════════════════════════════════
    TestCaseDef("SH-WEB-001", "平台商家列表页渲染", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-002", "平台商家详情页", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-003", "入驻审核操作", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-004", "商家控制台首页", "ui_web", 2, "test_ui_shop_merchant.py"),
    TestCaseDef("SH-WEB-005", "店铺设置页面", "ui_web", 2, "test_ui_shop_merchant.py"),
    TestCaseDef("SH-WEB-006", "商品列表页", "ui_web", 2, "test_ui_shop_catalog.py"),
    TestCaseDef("SH-WEB-007", "商品编辑弹窗", "ui_web", 2, "test_ui_shop_catalog.py"),
    TestCaseDef("SH-WEB-008", "库存管理页面", "ui_web", 2, "test_ui_shop_catalog.py"),
    TestCaseDef("SH-WEB-009", "订单列表页", "ui_web", 2, "test_ui_shop_orders.py"),
    TestCaseDef("SH-WEB-010", "订单详情弹窗", "ui_web", 2, "test_ui_shop_orders.py"),
    TestCaseDef("SH-WEB-011", "订单发货操作", "ui_web", 2, "test_ui_shop_orders.py"),
    TestCaseDef("SH-WEB-012", "促销活动列表", "ui_web", 2, "test_ui_shop_promotions.py"),
    TestCaseDef("SH-WEB-013", "创建促销活动", "ui_web", 2, "test_ui_shop_promotions.py"),
    TestCaseDef("SH-WEB-014", "优惠券管理", "ui_web", 2, "test_ui_shop_promotions.py"),
    TestCaseDef("SH-WEB-015", "数据看板图表", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-016", "渠道与支付进件页", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-017", "短信管理页", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-018", "商家公域对接设置", "ui_web", 2, "test_ui_shop_merchant.py"),
    TestCaseDef("SH-WEB-019", "平台经营看板", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-020", "平台清结算列表", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-021", "平台违规稽查列表", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-022", "平台订阅台账与续费待办", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-023", "平台商家详情六Tab与写跟进", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-024", "平台套餐配置字典与模板", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-025", "平台商品审核待审队列与面板", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-026", "平台角色与编码及商城权限抽屉", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-027", "平台类目与费率列表完备与禁用确认", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-028", "平台入驻审核列表完备与通过驳回栏位", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-029", "平台商家列表暂停恢复清退确认", "ui_web", 2, "test_ui_shop_admin.py"),
    TestCaseDef("SH-WEB-030", "平台分配管家与编辑标签抽屉", "ui_web", 2, "test_ui_shop_admin.py"),

    # ══════════════════════════════════════════════════════════════
    # Round 3: 小程序 UI 测试 (Playwright Mobile)
    # ══════════════════════════════════════════════════════════════
    TestCaseDef("SH-MP-001", "小程序首页加载", "ui_mp", 3, "test_ui_shop_mp_home.py"),
    TestCaseDef("SH-MP-002", "商品分类导航", "ui_mp", 3, "test_ui_shop_mp_home.py"),
    TestCaseDef("SH-MP-003", "搜索商品", "ui_mp", 3, "test_ui_shop_mp_home.py"),
    TestCaseDef("SH-MP-003b", "店首页排序 Chip", "ui_mp", 3, "test_ui_shop_mp_home.py"),
    TestCaseDef("SH-MP-004", "商品详情页", "ui_mp", 3, "test_ui_shop_mp_product.py"),
    TestCaseDef("SH-MP-004b", "未购试看进播放器", "ui_mp", 3, "test_ui_shop_mp_product.py"),
    TestCaseDef("SH-MP-005", "SKU选择", "ui_mp", 3, "test_ui_shop_mp_product.py"),
    TestCaseDef("SH-MP-006", "加入购物车", "ui_mp", 3, "test_ui_shop_mp_product.py"),
    TestCaseDef("SH-MP-007", "购物车页面", "ui_mp", 3, "test_ui_shop_mp_order.py"),
    TestCaseDef("SH-MP-008", "下单结算页", "ui_mp", 3, "test_ui_shop_mp_order.py"),
    TestCaseDef("SH-MP-009", "订单列表页", "ui_mp", 3, "test_ui_shop_mp_order.py"),
    TestCaseDef("SH-MP-010", "个人中心页面", "ui_mp", 3, "test_ui_shop_mp_profile.py"),
    TestCaseDef("SH-MP-011", "课时目录 M07", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-012", "播放器 M08", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-013", "资料领取 M09", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-014", "服务预约 M10", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-015", "核销码 M10b", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-016", "我的预约列表", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-017", "支付结果 M05", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-018", "订单详情 M12", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-019", "申请开票 M13", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-MP-020", "领权页 M14", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-FE-A21", "FE-A21 登录联测", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-A22", "FE-A22 注册边界", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-A22-W", "FE-A22 注册写库主路径", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-A20-W", "FE-A20 入驻上传写库", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-A02", "FE-A02 存草稿联测", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-A02-S1", "FE-A02 提交审核写库", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-P02A", "FE-P02A 发起入驻边界", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-P02A-W", "FE-P02A 代发起入驻写库", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-P03", "FE-P03 驳回空原因", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-P03-W", "FE-P03 审核通过写库", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-P09", "FE-P09 人审驳回拦截", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-P09-W", "FE-P09 人审通过写库", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-P11", "FE-P11 人工开通抽屉", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-P11-W", "FE-P11 确认开通写库", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-A10", "FE-A10 退款原因拦截", "ui_web", 2, "test_ui_shop_fe_gold.py"),
    TestCaseDef("SH-FE-A10-W", "FE-A10 商家退款写库", "ui_web", 2, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-M12-W", "FE-M12 买家退款写库", "ui_mp", 3, "test_ui_shop_fe_gold_write.py"),
    TestCaseDef("SH-FE-M03", "FE-M03 确认支付联测", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-FE-M12", "FE-M12 退款原因拦截", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),
    TestCaseDef("SH-FE-M14", "FE-M14 领权联测", "ui_mp", 3, "test_ui_shop_mp_fulfill.py"),

    # ══════════════════════════════════════════════════════════════
    # Round 4: E2E 集成流程 (F0-F12)
    # ══════════════════════════════════════════════════════════════
    TestCaseDef("SH-E2E-F0", "F0 商家注册全流程", "e2e", 4, "verify_shop_e2e_f0.py"),
    TestCaseDef("SH-E2E-F1", "F1 商品上架全流程", "e2e", 4, "verify_shop_e2e_f1.py"),
    TestCaseDef("SH-E2E-F2", "F2 购物车流程", "e2e", 4, "verify_shop_e2e_f2.py"),
    TestCaseDef("SH-E2E-F3", "F3 下单创建流程", "e2e", 4, "verify_shop_e2e_f3.py"),
    TestCaseDef("SH-E2E-F4", "F4 支付流程", "e2e", 4, "verify_shop_e2e_f4.py"),
    TestCaseDef("SH-E2E-F5", "F5 订单履约流程", "e2e", 4, "verify_shop_e2e_f5.py"),
    TestCaseDef("SH-E2E-F6", "F6 退款流程", "e2e", 4, "verify_shop_e2e_f6.py"),
    TestCaseDef("SH-E2E-F7", "F7 评价评分流程", "e2e", 4, "verify_shop_e2e_f7.py"),
    TestCaseDef("SH-E2E-F8", "F8 促销活动申请流程", "e2e", 4, "verify_shop_e2e_f8.py"),
    TestCaseDef("SH-E2E-F9", "F9 优惠券使用流程", "e2e", 4, "verify_shop_e2e_f9.py"),
    TestCaseDef("SH-E2E-F10", "F10 数据看板流程", "e2e", 4, "verify_shop_e2e_f10.py"),
    TestCaseDef("SH-E2E-F11", "F11 通知推送流程", "e2e", 4, "verify_shop_e2e_f11.py"),
    TestCaseDef("SH-E2E-F12", "F12 全生命周期流程", "e2e", 4, "verify_shop_e2e_f12.py"),

    # ══════════════════════════════════════════════════════════════
    # Round 5: Mock 外部集成
    # ══════════════════════════════════════════════════════════════

    # ── 微信支付 Stub ──
    TestCaseDef("SH-MOCK-WP-001", "微信支付统一下单", "mock_wechat_pay", 5, "verify_shop_mock_wechat_pay.py", expected_http=200,
                expected_fields={"code": "SUCCESS", "code_url": True}),
    TestCaseDef("SH-MOCK-WP-002", "微信支付查询订单", "mock_wechat_pay", 5, "verify_shop_mock_wechat_pay.py", expected_http=200,
                expected_fields={"trade_state": "SUCCESS"}),
    TestCaseDef("SH-MOCK-WP-003", "微信支付申请退款", "mock_wechat_pay", 5, "verify_shop_mock_wechat_pay.py", expected_http=200,
                expected_fields={"refund_status": "PROCESSING"}),
    TestCaseDef("SH-MOCK-WP-004", "微信支付回调通知", "mock_wechat_pay", 5, "verify_shop_mock_wechat_pay.py", expected_http=200,
                expected_fields={"event_type": "TRANSACTION.SUCCESS"}),
    TestCaseDef("SH-MOCK-WP-005", "微信支付账单下载", "mock_wechat_pay", 5, "verify_shop_mock_wechat_pay.py", expected_http=200,
                expected_fields={"download_url": True}),

    # ── 抖音 Stub ──
    TestCaseDef("SH-MOCK-DY-001", "抖音内容发布", "mock_douyin", 5, "verify_shop_mock_douyin.py", expected_http=200,
                expected_fields={"publish_status": "publishing"}),
    TestCaseDef("SH-MOCK-DY-002", "抖音发布状态查询", "mock_douyin", 5, "verify_shop_mock_douyin.py", expected_http=200,
                expected_fields={"publish_status": "published"}),
    TestCaseDef("SH-MOCK-DY-003", "抖音数据同步", "mock_douyin", 5, "verify_shop_mock_douyin.py", expected_http=200,
                expected_fields={"synced_at": True}),
    TestCaseDef("SH-MOCK-DY-004", "抖音视频列表查询", "mock_douyin", 5, "verify_shop_mock_douyin.py", expected_http=200,
                expected_fields={"total": 2}),
    TestCaseDef("SH-MOCK-DY-005", "抖音视频删除", "mock_douyin", 5, "verify_shop_mock_douyin.py", expected_http=200,
                expected_fields={"deleted": True}),

    # ── 短信 Stub ──
    TestCaseDef("SH-MOCK-SMS-001", "短信验证码发送", "mock_sms", 5, "verify_shop_mock_sms.py", expected_http=200,
                expected_fields={"sent": True, "stub": True}),
    TestCaseDef("SH-MOCK-SMS-002", "短信验证码校验", "mock_sms", 5, "verify_shop_mock_sms.py", expected_http=200,
                expected_fields={"verified": True}),
    TestCaseDef("SH-MOCK-SMS-003", "短信通知发送", "mock_sms", 5, "verify_shop_mock_sms.py", expected_http=200,
                expected_fields={"sent": True, "stub": True}),

    # ══════════════════════════════════════════════════════════════
    # Round 6: 安全 & PII 测试
    # ══════════════════════════════════════════════════════════════
    TestCaseDef("SH-SEC-001", "商家间数据隔离", "security", 6, "verify_shop_security_permissions.py", expected_http=200),
    TestCaseDef("SH-SEC-002", "平台管理员越权访问商家数据", "security", 6, "verify_shop_security_permissions.py", expected_http=403),
    TestCaseDef("SH-SEC-003", "店员仅可核销不可管理", "security", 6, "verify_shop_security_permissions.py", expected_http=403),
    TestCaseDef("SH-SEC-004", "API Key 加密存储", "security", 6, "verify_shop_security_encryption.py"),
    TestCaseDef("SH-SEC-005", "支付密钥加密存储", "security", 6, "verify_shop_security_encryption.py"),
    TestCaseDef("SH-SEC-006", "密码哈希不可逆", "security", 6, "verify_shop_security_encryption.py"),
    TestCaseDef("SH-SEC-007", "手机号脱敏显示", "pii", 6, "verify_shop_security_pii.py"),
    TestCaseDef("SH-SEC-008", "身份证号脱敏显示", "pii", 6, "verify_shop_security_pii.py"),
    TestCaseDef("SH-SEC-009", "银行卡号脱敏显示", "pii", 6, "verify_shop_security_pii.py"),
    TestCaseDef("SH-SEC-010", "API响应中PII字段过滤", "pii", 6, "verify_shop_security_pii.py"),
    TestCaseDef("SH-SEC-011", "SQL注入防护", "security", 6, "verify_shop_security_injection.py", expected_http=400),
    TestCaseDef("SH-SEC-012", "XSS输入过滤", "security", 6, "verify_shop_security_injection.py"),
    TestCaseDef("SH-SEC-013", "CSRF Token校验", "security", 6, "verify_shop_security_injection.py", expected_http=403),
    TestCaseDef("SH-SEC-014", "文件上传类型校验", "security", 6, "verify_shop_security_injection.py", expected_http=400),
    TestCaseDef("SH-SEC-015", "速率限制防刷", "security", 6, "verify_shop_security_injection.py", expected_http=429),

    # ══════════════════════════════════════════════════════════════
    # Round 7: 回归测试
    # ══════════════════════════════════════════════════════════════
    TestCaseDef("SH-REG-001", "M0-M8 全量回归", "regression", 7, "run_m0_m8.py"),
    TestCaseDef("SH-REG-002", "Agent T0+A0~C6 回归", "regression", 7, "run_agent_a_c.py"),
    TestCaseDef("SH-REG-003", "CRM 全量回归", "regression", 7, "run_crm_all.py"),
    TestCaseDef("SH-REG-004", "商城 M0 回归", "regression", 7, "verify_shop_m0.py"),
    TestCaseDef("SH-REG-005", "商城权限种子回归", "regression", 7, "verify_shop_m0.py"),
]


# ── 期望结果查询 ──────────────────────────────────────────────────

def build_expected_results() -> dict[str, dict[str, Any]]:
    """构建 ``{test_id: {expected_status, expected_http, expected_fields}}`` 映射。"""
    return {
        tc.test_id: {
            "expected_status": tc.expected_status,
            "expected_http": tc.expected_http,
            "expected_fields": tc.expected_fields,
        }
        for tc in TEST_CASES
    }


EXPECTED_RESULTS: dict[str, dict[str, Any]] = build_expected_results()


# ── 查询辅助函数 ──────────────────────────────────────────────────

def get_round_steps(round_num: int, through: str | None = None) -> list[RoundStep]:
    """获取指定 Round 的步骤列表。

    Args:
        round_num: Round 编号（1-7）。
        through:   仅 Round 1 生效 — 截断到指定里程碑（含）。
    """
    steps = list(ROUND_STEPS.get(round_num, []))
    if round_num == 1 and through:
        if through not in MILESTONE_ORDER:
            raise ValueError(f"无效里程碑: {through}，可选: {MILESTONE_ORDER}")
        idx = MILESTONE_ORDER.index(through)
        allowed = set(MILESTONE_ORDER[: idx + 1])
        steps = [s for s in steps if s.milestone in allowed]
    return steps


def get_test_cases_by_round(round_num: int) -> list[TestCaseDef]:
    """获取指定 Round 的全部测试用例。"""
    return [tc for tc in TEST_CASES if tc.round == round_num]


def get_test_cases_by_script(script: str) -> list[TestCaseDef]:
    """获取指定脚本包含的全部测试用例。"""
    return [tc for tc in TEST_CASES if tc.script == script]


def get_stub_env_vars() -> dict[str, str]:
    """汇总全部 Stub 的环境变量（供 runner 注入）。"""
    env: dict[str, str] = {}
    for stub in ALL_STUBS.values():
        env.update(stub.env_vars)
    return env


def total_test_count() -> int:
    """返回测试用例总数。"""
    return len(TEST_CASES)
