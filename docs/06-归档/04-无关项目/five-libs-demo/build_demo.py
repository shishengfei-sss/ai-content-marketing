# -*- coding: utf-8 -*-
"""
五大营销子库 · 可运行示例（SQLite 版）
========================================
对齐《五大营销子库搭建方案.md》。一条命令生成含真实感样例数据的库，
并跑出"活动官/舆情/分层/竞品/洞察"演示查询。

运行:  python build_demo.py
依赖:  仅 Python 标准库 (sqlite3)
"""
import sqlite3
import os
import textwrap

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "five_libs.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS competitor_lib (
    competitor_id TEXT, product_line TEXT, campaign TEXT, channel TEXT,
    core_message TEXT, selling_point TEXT, promo_mechanism TEXT,
    period TEXT, observed_signal TEXT, source_url TEXT, captured_at TEXT
);
CREATE TABLE IF NOT EXISTS campaign_lib (
    campaign_id TEXT, name TEXT, type TEXT, goal TEXT, channel TEXT,
    budget REAL, leads INT, mql INT, sql_deals INT, revenue REAL,
    roi REAL, win_factor TEXT, lose_factor TEXT, replay TEXT
);
CREATE TABLE IF NOT EXISTS segment_lib (
    segment_id TEXT, segment_name TEXT, rule TEXT, size_est INT,
    persona TEXT, preferred_channel TEXT, content_pref TEXT,
    pain_points TEXT, trigger_event TEXT
);
CREATE TABLE IF NOT EXISTS sentiment_lib (
    mention_id TEXT, target TEXT, platform TEXT, topic TEXT,
    volume INT, sentiment TEXT, emotion_score REAL, is_crisis INT, first_seen TEXT
);
CREATE TABLE IF NOT EXISTS insight_lib (
    insight_id TEXT, theme TEXT, title TEXT, summary TEXT,
    key_data TEXT, source TEXT, confidence TEXT, published_date TEXT, expiry TEXT
);
"""

# ---------- 样例数据（与方案文档一致） ----------
COMPETITOR = [
    ("三一重工","挖掘机 SY365","国四换新直播","抖音/视频号","旧机抵首付，换新省20万","低首付+以旧换新","旧机抵首付","2026-03","直播观看80w，留资3200","douyin.com/sany","2026-03-15"),
    ("中联重科","泵车","bauma展会","线下+公众号","绿色智能泵送","绿色+智能","现场演示","2026-04","展位客流1.2w","公众号/展会报道","2026-04-20"),
    ("卡特彼勒","装载机","省油挑战赛","抖音+经销商","一箱油多干2小时","省油","UGC投稿","2026-05","UGC投稿600+","douyin.com/cat","2026-05-08"),
]
CAMPAIGN = [
    ("C001","上海宝马展","展会","获客+品牌","线下",150,1200,350,28,480,3.2,"现场demo机+一对一顾问","展前邀约不足","高意向客户集中，顾问式转化强"),
    ("C002","白皮书下载","内容","获客","官网/SEM",8,2400,180,12,96,12.0,"高价值选题+SEM精准","表单过长流失","低成本内容获客ROI最高"),
    ("C003","抖音直播","直播","获客","抖音",20,900,60,3,18,0.9,"流量大","留资质量差、线索不精准","泛流量转化弱，需精准定向"),
]
SEGMENT = [
    ("S001","中型装备商-设备升级决策者","规模100-500人 & 角色=生产副总 & 阶段=设备更新期",1200,"务实、重ROI、怕停产","行业展+LinkedIn+技术白皮书","ROI测算/downtime对比","产能瓶颈/能耗高","设备到使用年限"),
    ("S002","大型国企-集采影响者","规模>2000人 & 角色=采购/技术",300,"重合规/关系/流程","关系拜访+招标","合规资质/标杆案例","流程长/风险顾虑","年度集采启动"),
    ("S003","海外经销商","区域=东南亚 & 角色=渠道伙伴",200,"重利润/库存周转","WhatsApp+本地展","价格政策/库存支持","汇率/物流","新区域开拓"),
]
SENTIMENT = [
    ("M001","我方","抖音","某型号液压故障投诉",5200,"负向",-0.7,1,"2026-05-10"),
    ("M002","竞品A","知乎","电动工程机械值不值",1800,"中性",0.1,0,"2026-05-12"),
    ("M003","行业","新闻","设备更新补贴政策",9500,"正向",0.6,0,"2026-03-20"),
]
INSIGHT = [
    ("I001","市场","工程机械出口高增","2026出口+18%，东南亚占35%","出口+18%，东南亚35%","海关/协会","高","2026-04-01",""),
    ("I002","政策","设备更新财政贴息","工业设备更新贴息2%","贴息2%","工信部","高","2026-03-15","2027-12-31"),
    ("I003","技术","电动化加速","电动装载机渗透率12%→25%","渗透率12%→25%","亿欧","中","2026-02-10",""),
    ("I004","客户","中小制造商痛点","68%把能耗/产能列首要痛点","68%首要痛点=能耗/产能","问卷N=800","中","2026-01-20",""),
]

def build():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    cur.executemany("INSERT INTO competitor_lib VALUES (?,?,?,?,?,?,?,?,?,?,?)", COMPETITOR)
    cur.executemany("INSERT INTO campaign_lib VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", CAMPAIGN)
    cur.executemany("INSERT INTO segment_lib VALUES (?,?,?,?,?,?,?,?,?)", SEGMENT)
    cur.executemany("INSERT INTO sentiment_lib VALUES (?,?,?,?,?,?,?,?,?)", SENTIMENT)
    cur.executemany("INSERT INTO insight_lib VALUES (?,?,?,?,?,?,?,?,?)", INSIGHT)
    conn.commit()
    conn.close()
    print(f"[OK] 已生成示例库: {DB}\n")

def q(title, sql, params=()):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    print("="*60)
    print(f"▶ {title}")
    print("="*60)
    for r in rows:
        print("  • " + " | ".join(str(x) for x in r))
    print()

def demo():
    print("\n########## 五大营销子库 · 演示查询 ##########\n")

    # 活动官：最佳 ROI 活动
    q("活动官: 哪类活动 ROI 最高？(按 type 聚合)",
      """SELECT type, COUNT(*) 活动数, ROUND(AVG(roi),2) 平均ROI, SUM(revenue) 总营收
         FROM campaign_lib GROUP BY type ORDER BY 平均ROI DESC""")

    # 活动官：自动复盘素材（最差活动）
    q("活动官: 找出 ROI<1 需复盘的活动",
      "SELECT name, roi, lose_factor FROM campaign_lib WHERE roi < 1")

    # 舆情：危机预警
    q("公关官: 列出危机舆情(is_crisis=1)",
      "SELECT target, platform, topic, volume, sentiment FROM sentiment_lib WHERE is_crisis=1")

    # 分层：内容官按层取名单规模
    q("内容官: 各分层规模与痛点",
      "SELECT segment_name, size_est, pain_points FROM segment_lib ORDER BY size_est DESC")

    # 竞品：渠道分布
    q("洞察官: 竞品都用哪些渠道打",
      "SELECT competitor_id, channel, core_message FROM competitor_lib")

    # 行业洞察：支撑出海选题
    q("策略官: 取'市场'类洞察支撑出海方向",
      "SELECT title, key_data, source FROM insight_lib WHERE theme='市场'")

    # 跨库联动：政策红利 + 痛点 -> 内容主线
    q("内容官(跨库): 用'政策贴息'+'客户痛点'定 Q3 话术主线",
      """SELECT i.key_data 政策, c.pain_points 痛点
         FROM insight_lib i, segment_lib c
         WHERE i.theme='政策' AND c.segment_id='S001'""")

if __name__ == "__main__":
    build()
    demo()
    print("提示: 用 `sqlite3 five_libs.db` 或任意 SQLite 工具可继续探查。")
