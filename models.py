"""
A股异动监控系统 - 数据模型与类型定义
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional

class MarketType(Enum):
    SH_MAIN = "SH_MAIN"      # 沪市主板 (600, 601, 603, 605)
    SZ_MAIN = "SZ_MAIN"      # 深市主板 (000, 001, 002, 003)
    CYB = "CYB"              # 创业板 (300, 301)
    STAR = "STAR"            # 科创板 (688)

@dataclass
class MarketConfig:
    market_type: MarketType
    market_name: str
    price_limit_rate: float      # 单日涨跌幅限制 (主板 0.10, 创业板 0.20)
    normal_threshold: float      # 3日普通异动偏离值阈值 (主板 0.20, 创业板 0.30)
    index_name: str              # 官方基准指数名称
    index_code: str              # 指数代码 (如 399102)
    index_secid: str             # 东财secid (如 0.399102)
    stock_prefix: str            # 东财secid前缀 ("0." 或 "1.")
    tencent_market: str          # 腾讯市场前缀 ("sz" 或 "sh")
    tencent_index: str           # 腾讯指数代码 ("sz399107", "sz399102", "sh000002")

@dataclass
class KLineBar:
    date: str
    open: float
    close: float
    high: float
    low: float
    pct_change: float = 0.0      # 涨跌幅 (%)
    volume: float = 0.0          # 成交量 (手 / 股)

@dataclass
class WindowDeviationDetail:
    window_days: int             # 窗口天数 (如 3, 10, 30)
    target_period_label: str     # 目标期标签 ("今日收盘" 或 "下一交易日")
    start_date: str              # 窗口基期日期 (T-N 日)
    base_stock_price: float      # 基期股票收盘价 (P0)
    base_index_price: float      # 基期指数收盘点位 (I0)
    crit_price: float            # 触碰异动的临界收盘价 (元)
    daily_rise_threshold_pct: float # 目标日涨跌幅红线 (%) - 相对于已确认收盘价(昨收)
    remaining_rise_from_realtime_pct: float # 从当前实时现价还能再涨 (%)
    curr_realtime_deviation_pct: float # 当前实时累计偏离度 (%)
    threshold_pct: float         # 监管阈值 (%)
    status: str                  # 状态判定 (安全/预警/已触发)

@dataclass
class FutureDayProjection:
    day_index: int               # 未来第几天 (1, 2, 3...)
    target_date_label: str       # 标签 (如 "未来第1天")
    allowed_cum_rise_pct: float  # 累计允许涨幅上限 (%)
    crit_price: float            # 对应临界价格
    allowed_daily_rise_pct: float # 当日允许涨幅上限 (%)
    limit_up_price: float        # 若连续涨停的理论价格
    will_trigger_if_limit_up: bool # 若连续涨停是否会在该日首次触发异动

# ==============================================================================
# 🎮 沙盘推演模型 (What-If 控盘模拟 与 目标连板倒推)
# ==============================================================================

@dataclass
class WhatIfDayStep:
    day_index: int               # 未来第几天 (1: 明日, 2: 后天...)
    date_label: str              # 标签 (如 "明日 (T+1)")
    base_date: str               # 该日10日窗口对应的基期日期
    base_price: float            # 基期股票收盘价 (P0)
    crit_price: float            # 该日10日严重异动临界收盘价 (元)
    streak_limit_up_price: float # 若连续涨停的收盘价 (元)
    can_limit_up: bool           # 该日能否涨停而不吃10日严重异动
    max_allowed_rise_pct: float  # 相对于前一日的最大允许涨幅 (%)
    buffer_margin_pct: float     # 涨停价距离临界价的缓冲安全边际 (%) (正数表示安全，负数表示超额)

@dataclass
class ReverseLimitUpPlan:
    target_streak_days: int      # 目标连续涨停天数 (如 1天, 2天, 3天...)
    max_today_price: float       # 今日最高允许收盘价 (元)
    max_today_rise_pct: float    # 今日最高允许涨幅 (%)
    is_achievable: bool          # 是否可以通过控盘达成 (跌停板以内可控)
    level_type: str              # "safe" (安全正涨幅), "pressure" (需压盘收绿), "impossible" (无法达成)
    action_advice: str           # 控盘建议结论
    bottleneck_day: int          # 导致受限的瓶颈交易日 (0表示今日受限, 1..N表示未来某天)
    bottleneck_desc: str         # 瓶颈原因说明

@dataclass
class SandtableSimulation:
    assumed_today_rise_pct: float  # 当前推演设定的今日收盘涨幅 (%)
    assumed_today_price: float     # 对应的今日收盘模拟价 (元)
    what_if_steps: List[WhatIfDayStep] # 基于假设今日涨幅推演出的未来逐日走势
    reverse_plans: List[ReverseLimitUpPlan] # 目标未来连续涨停倒推矩阵
    max_sustainable_streak_days: int # 极限跌停控盘下最多能维持连续涨停几天

@dataclass
class AnomalyAnalysisReport:
    symbol: str
    stock_name: str
    market_name: str
    price_limit_pct: float       # 涨跌幅限制 (10% 或 20%)
    
    # 时段与价格区分 (严格区分盘中实时现价与最新已确认收盘价)
    is_intraday: bool            # 当前是否处于盘中交易时段
    market_session_text: str     # "盘中交易中" 或 "盘后已收盘"
    confirmed_date: str          # 最新已确认收盘价的日期 (盘中为昨日，盘后为今日)
    confirmed_close: float       # 最新已确认收盘价 (盘中为昨日收盘价/昨收，盘后为今日收盘价)
    realtime_price: float        # 当前实时最新现价 (盘中为现价，盘后与confirmed_close一致)
    realtime_pct_change: float   # 盘中实时涨跌幅 (%)
    
    # 官方基准指数
    benchmark_name: str
    benchmark_code: str
    confirmed_index_close: float # 基准指数已确认收盘点位
    realtime_index_price: float  # 基准指数当前实时点位
    realtime_index_pct_change: float # 基准指数实时涨跌幅 (%)

    # 监控窗口
    normal_3d: WindowDeviationDetail
    severe_10d: WindowDeviationDetail
    severe_30d: WindowDeviationDetail

    # 未来推演与历史
    future_projections: List[FutureDayProjection]
    history_bars: List[Dict[str, Any]]
    
    # 完整K线数据 (供给前端K线图表直接渲染)
    kline_chart_data: List[Dict[str, Any]]

    # 🎮 异动推演沙盘
    sandtable: Optional[SandtableSimulation] = None
