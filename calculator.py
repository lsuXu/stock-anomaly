"""
A股异动监控系统 - 核心计算引擎 (严谨区分盘中实时现价与已确认收盘价，支持专业炒股软件口径)
"""
from typing import List, Dict, Any, Optional
from models import (
    MarketConfig,
    KLineBar,
    WindowDeviationDetail,
    FutureDayProjection,
    WhatIfDayStep,
    ReverseLimitUpPlan,
    SandtableSimulation,
    AnomalyAnalysisReport
)

class AnomalyCalculator:
    """股票交易异常波动及严重异常波动计算与推演引擎"""

    @classmethod
    def calculate_window(
        cls,
        confirmed_stock_klines: List[KLineBar],
        confirmed_index_klines: List[KLineBar],
        realtime_stock_price: float,
        realtime_index_price: float,
        window_days: int,
        threshold: float,
        price_limit_rate: float,
        is_intraday: bool,
        base_mode: str = "window_start",
        assume_index_change: float = 0.0
    ) -> WindowDeviationDetail:
        """
        计算指定窗口 (3天、10天、30天) 的异动指标:
        :param base_mode:
            - 'window_start' (主流专业炒股软件口径，如同花顺、开盘啦、通达信):
              包含今日在内整整 N 个交易日，取第 1 个交易日(倒数第 N 天)的收盘价作为期初基准价。
              例如 10 日严重异动: 取 2026-10-12 (5.21元) 作为基期，算出今日涨超 +4.85% 触发异动。
            - 'pre_window' (窗口前一日收盘价法):
              取这 N 个交易日前一天的收盘价(倒数第 N+1 天)作为基准。
        """
        if base_mode == "window_start":
            # 窗口首日收盘价法 (专业炒股软件口径):
            # 若今日是第 N 天，则首日在 confirmed_stock(截止昨日) 中的索引为 -(window_days - 1)
            offset = max(1, window_days - 1)
            base_idx = -offset
        else:
            # 窗口前一日收盘价法:
            base_idx = -window_days

        if abs(base_idx) > len(confirmed_stock_klines) or abs(base_idx) > len(confirmed_index_klines):
            raise ValueError(f"历史数据不足以支撑 {window_days} 天的异动计算")

        base_stock = confirmed_stock_klines[base_idx]
        base_index = confirmed_index_klines[base_idx]
        p0 = base_stock.close
        i0 = base_index.close

        confirmed_close = confirmed_stock_klines[-1].close
        confirmed_index_close = confirmed_index_klines[-1].close

        target_label = "今日收盘" if is_intraday else "下一交易日"

        if is_intraday:
            target_index = realtime_index_price * (1.0 + assume_index_change)
            curr_dev = ((realtime_stock_price / p0 - 1.0) - (realtime_index_price / i0 - 1.0)) * 100.0
        else:
            target_index = confirmed_index_close * (1.0 + assume_index_change)
            curr_dev = ((confirmed_close / p0 - 1.0) - (confirmed_index_close / i0 - 1.0)) * 100.0

        crit_price = round(p0 * (threshold + (target_index / i0)), 2)
        daily_rise_threshold_pct = (crit_price / confirmed_close - 1.0) * 100.0
        remaining_rise_from_realtime_pct = (crit_price / realtime_stock_price - 1.0) * 100.0
        limit_pct = price_limit_rate * 100.0

        if daily_rise_threshold_pct >= limit_pct:
            status = f"安全 ({target_label}涨停+{int(limit_pct)}%也不会触发)"
        elif daily_rise_threshold_pct > 0:
            status = f"预警 ({target_label}涨幅达+{round(daily_rise_threshold_pct, 2)}%将触发异动)"
        else:
            status = f"临界 ({target_label}已达临界边缘)"

        return WindowDeviationDetail(
            window_days=window_days,
            target_period_label=target_label,
            start_date=base_stock.date,
            base_stock_price=round(p0, 2),
            base_index_price=round(i0, 2),
            crit_price=crit_price,
            daily_rise_threshold_pct=round(daily_rise_threshold_pct, 2),
            remaining_rise_from_realtime_pct=round(remaining_rise_from_realtime_pct, 2),
            curr_realtime_deviation_pct=round(curr_dev, 2),
            threshold_pct=round(threshold * 100.0, 1),
            status=status
        )

    @classmethod
    def simulate_future_days(
        cls,
        confirmed_stock_klines: List[KLineBar],
        confirmed_index_klines: List[KLineBar],
        base_calc_price: float,
        base_calc_index: float,
        future_days: int,
        price_limit_rate: float,
        assume_daily_index_change: float = 0.0
    ) -> List[FutureDayProjection]:
        """推演未来第 1 到第 N 天在 10 日严重异动红线下的空间"""
        projections: List[FutureDayProjection] = []
        threshold_10d = 1.00 # 10日累计偏离 +100%

        streak_price = base_calc_price
        first_limit_up_triggered = False

        for k in range(1, future_days + 1):
            hist_offset = 10 - k
            if hist_offset > 0:
                base_idx = -hist_offset
            else:
                base_idx = -1

            p0 = confirmed_stock_klines[base_idx].close
            i0 = confirmed_index_klines[base_idx].close

            future_index = base_calc_index * ((1.0 + assume_daily_index_change) ** k)
            crit_price = round(p0 * (threshold_10d + (future_index / i0)), 2)

            allowed_cum_rise = (crit_price / base_calc_price - 1.0) * 100.0
            if allowed_cum_rise > -99.0 and k > 0:
                daily_ratio = (1.0 + allowed_cum_rise / 100.0) ** (1.0 / k) - 1.0
                allowed_daily_rise = daily_ratio * 100.0
            else:
                allowed_daily_rise = allowed_cum_rise

            streak_price = round(streak_price * (1.0 + price_limit_rate), 2)
            will_trigger = False
            if streak_price >= crit_price and not first_limit_up_triggered:
                will_trigger = True
                first_limit_up_triggered = True

            projections.append(FutureDayProjection(
                day_index=k,
                target_date_label=f"未来第{k}个交易日",
                allowed_cum_rise_pct=round(allowed_cum_rise, 2),
                crit_price=crit_price,
                allowed_daily_rise_pct=round(allowed_daily_rise, 2),
                limit_up_price=streak_price,
                will_trigger_if_limit_up=will_trigger
            ))

        return projections

    @classmethod
    def calculate_sandtable(
        cls,
        confirmed_stock_klines: List[KLineBar],
        confirmed_index_klines: List[KLineBar],
        confirmed_close: float,
        realtime_price: float,
        confirmed_index_close: float,
        realtime_index_price: float,
        price_limit_rate: float,
        is_intraday: bool,
        base_mode: str = "window_start",
        assume_index_change: float = 0.0,
        assumed_today_rise_pct: Optional[float] = None
    ) -> SandtableSimulation:
        """
        异动推演沙盘核心算法：
        1. 推演 A (What-If 控盘模拟):
           假设今日(或下个交易日)收在指定涨跌幅，推演未来第 1~5 天天天涨停的价格路径与能否涨停
        2. 推演 B (目标连板倒推矩阵):
           设定未来连续涨停 1~5 天，严谨倒推今日最高允许收盘价与涨幅红线，并判定是否在跌停板以内可控达成
        """
        hist_offset = 9 if base_mode == "window_start" else 10
        target_day_label = "今日" if is_intraday else "下一交易日"

        crit_prices: Dict[int, float] = {}
        base_prices: Dict[int, float] = {}
        base_dates: Dict[int, str] = {}

        idx_0 = realtime_index_price if is_intraday else confirmed_index_close

        for k in range(0, 6):
            offset_k = hist_offset - k
            if offset_k > 0 and offset_k <= len(confirmed_stock_klines):
                base_stock = confirmed_stock_klines[-offset_k]
                base_index = confirmed_index_klines[-offset_k]
            else:
                base_stock = confirmed_stock_klines[-1]
                base_index = confirmed_index_klines[-1]

            p0 = base_stock.close
            i0 = base_index.close
            fut_idx = idx_0 * ((1.0 + assume_index_change) ** k)
            crit_p = round(p0 * (1.00 + (fut_idx / i0)), 2)
            
            crit_prices[k] = crit_p
            base_prices[k] = round(p0, 2)
            base_dates[k] = base_stock.date

        p_prev = confirmed_close
        if assumed_today_rise_pct is None:
            if is_intraday:
                assumed_today_rise_pct = round(((realtime_price / p_prev) - 1.0) * 100.0, 2)
            else:
                assumed_today_rise_pct = 0.0

        assumed_today_price = round(p_prev * (1.0 + assumed_today_rise_pct / 100.0), 2)

        # 4. 推演 A: What-If 假设控盘逐日推演
        what_if_steps: List[WhatIfDayStep] = []
        prev_streak_price = assumed_today_price
        streak_valid = True

        for k in range(1, 6):
            if is_intraday:
                date_label = "明日 (T+1)" if k == 1 else (f"后天 (T+2)" if k == 2 else f"未来第{k}天 (T+{k})")
            else:
                date_label = "下下交易日 (T+2)" if k == 1 else f"未来第{k+1}天 (T+{k+1})"

            crit_k = crit_prices[k]
            streak_price = round(prev_streak_price * (1.0 + price_limit_rate), 2)
            
            can_up = streak_valid and (streak_price < crit_k)
            if not can_up:
                streak_valid = False

            max_allowed_rise = round(((crit_k - 0.01) / prev_streak_price - 1.0) * 100.0, 2)
            buffer_margin_pct = round(((crit_k - streak_price) / prev_streak_price) * 100.0, 2)

            what_if_steps.append(WhatIfDayStep(
                day_index=k,
                date_label=date_label,
                base_date=base_dates[k],
                base_price=base_prices[k],
                crit_price=crit_k,
                streak_limit_up_price=streak_price,
                can_limit_up=can_up,
                max_allowed_rise_pct=max_allowed_rise,
                buffer_margin_pct=buffer_margin_pct
            ))

            prev_streak_price = streak_price

        # 5. 推演 B: 目标未来 1~5 连板倒推矩阵
        reverse_plans: List[ReverseLimitUpPlan] = []
        limit_pct = price_limit_rate * 100.0

        for M in range(1, 6):
            candidates = []
            for j in range(0, M + 1):
                allowed_p = (crit_prices[j] - 0.01) / ((1.0 + price_limit_rate) ** j)
                candidates.append((j, allowed_p))

            bottleneck_day, max_today_price_raw = min(candidates, key=lambda x: x[1])
            max_today_price = round(max_today_price_raw, 2)
            max_today_rise_pct = round(((max_today_price / p_prev) - 1.0) * 100.0, 2)

            if max_today_rise_pct >= limit_pct:
                is_achievable = True
                level_type = "safe"
                action_advice = f"毫无压力：{target_day_label}即使涨停(+{int(limit_pct)}%)收盘，未来{M}天仍可连续涨停而不触发严重异动"
            elif max_today_rise_pct >= 0.0:
                is_achievable = True
                level_type = "control_green"
                action_advice = f"可达成(需红盘控涨)：{target_day_label}涨幅须控制在 ≤ +{max_today_rise_pct:.2f}% (收盘 ≤ {max_today_price:.2f}元)"
            elif max_today_rise_pct >= -limit_pct:
                is_achievable = True
                level_type = "pressure_red"
                action_advice = f"须压盘收跌：{target_day_label}须收绿压盘，涨幅须 ≤ {max_today_rise_pct:.2f}% (收盘 ≤ {max_today_price:.2f}元)"
            else:
                is_achievable = False
                level_type = "impossible"
                action_advice = f"无法达成！即使{target_day_label}直接跌停(-{int(limit_pct)}%)，未来仍会在第{bottleneck_day}天撞上异动红线"

            if bottleneck_day == 0:
                bottleneck_desc = f"{target_day_label}自身10日严重异动临界线 ({crit_prices[0]:.2f}元)"
            elif bottleneck_day == 1:
                bottleneck_desc = f"明日(T+1) 10日严重异动临界线 ({crit_prices[1]:.2f}元)"
            else:
                bottleneck_desc = f"未来第{bottleneck_day}天(T+{bottleneck_day}) 10日严重异动临界线 ({crit_prices[bottleneck_day]:.2f}元)"

            reverse_plans.append(ReverseLimitUpPlan(
                target_streak_days=M,
                max_today_price=max_today_price,
                max_today_rise_pct=max_today_rise_pct,
                is_achievable=is_achievable,
                level_type=level_type,
                action_advice=action_advice,
                bottleneck_day=bottleneck_day,
                bottleneck_desc=bottleneck_desc
            ))

        max_sustainable = max([p.target_streak_days for p in reverse_plans if p.is_achievable], default=0)

        return SandtableSimulation(
            assumed_today_rise_pct=assumed_today_rise_pct,
            assumed_today_price=assumed_today_price,
            what_if_steps=what_if_steps,
            reverse_plans=reverse_plans,
            max_sustainable_streak_days=max_sustainable
        )

    @classmethod
    def generate_full_report(
        cls,
        symbol: str,
        stock_name: str,
        config: MarketConfig,
        stock_klines: List[KLineBar],
        index_klines: List[KLineBar],
        is_intraday: bool,
        future_days: int = 5,
        assume_index_change: float = 0.0,
        base_mode: str = "window_start",
        assumed_today_rise_pct: Optional[float] = None
    ) -> AnomalyAnalysisReport:
        """生成全面的异动分析报告 (含长周期日K线序列及口径匹配)"""

        if is_intraday:
            realtime_bar_stock = stock_klines[-1]
            realtime_bar_index = index_klines[-1]
            
            confirmed_stock = stock_klines[:-1]
            confirmed_index = index_klines[:-1]

            confirmed_close_date = confirmed_stock[-1].date
            confirmed_close_price = confirmed_stock[-1].close
            realtime_price = realtime_bar_stock.close
            realtime_pct = round(((realtime_price / confirmed_close_price) - 1.0) * 100.0, 2)

            confirmed_index_close = confirmed_index[-1].close
            realtime_index_price = realtime_bar_index.close
            realtime_index_pct = round(((realtime_index_price / confirmed_index_close) - 1.0) * 100.0, 2)

            session_text = "盘中交易中"
        else:
            confirmed_stock = stock_klines
            confirmed_index = index_klines

            confirmed_close_date = stock_klines[-1].date
            confirmed_close_price = stock_klines[-1].close
            realtime_price = confirmed_close_price
            realtime_pct = stock_klines[-1].pct_change

            confirmed_index_close = index_klines[-1].close
            realtime_index_price = confirmed_index_close
            realtime_index_pct = index_klines[-1].pct_change

            session_text = "盘后已收盘"

        # 1. 连续3日普通异动
        normal_3d = cls.calculate_window(
            confirmed_stock_klines=confirmed_stock,
            confirmed_index_klines=confirmed_index,
            realtime_stock_price=realtime_price,
            realtime_index_price=realtime_index_price,
            window_days=3,
            threshold=config.normal_threshold,
            price_limit_rate=config.price_limit_rate,
            is_intraday=is_intraday,
            base_mode=base_mode,
            assume_index_change=assume_index_change
        )

        # 2. 连续10日严重异动 (+100%)
        severe_10d = cls.calculate_window(
            confirmed_stock_klines=confirmed_stock,
            confirmed_index_klines=confirmed_index,
            realtime_stock_price=realtime_price,
            realtime_index_price=realtime_index_price,
            window_days=10,
            threshold=1.00,
            price_limit_rate=config.price_limit_rate,
            is_intraday=is_intraday,
            base_mode=base_mode,
            assume_index_change=assume_index_change
        )

        # 3. 连续30日严重异动 (+200%)
        severe_30d = cls.calculate_window(
            confirmed_stock_klines=confirmed_stock,
            confirmed_index_klines=confirmed_index,
            realtime_stock_price=realtime_price,
            realtime_index_price=realtime_index_price,
            window_days=30,
            threshold=2.00,
            price_limit_rate=config.price_limit_rate,
            is_intraday=is_intraday,
            base_mode=base_mode,
            assume_index_change=assume_index_change
        )

        # 4. 未来 N 天推演
        future_projections = cls.simulate_future_days(
            confirmed_stock_klines=confirmed_stock,
            confirmed_index_klines=confirmed_index,
            base_calc_price=realtime_price if is_intraday else confirmed_close_price,
            base_calc_index=realtime_index_price if is_intraday else confirmed_index_close,
            future_days=max(1, future_days),
            price_limit_rate=config.price_limit_rate,
            assume_daily_index_change=assume_index_change
        )

        # 5. 整理历史明细表 (最近15根K线走势对比)
        history_bars: List[Dict[str, Any]] = []
        recent_count = min(15, len(stock_klines))
        for i in range(-recent_count, 0):
            s_bar = stock_klines[i]
            i_bar = index_klines[i]
            is_today_in_progress = (is_intraday and i == -1)
            history_bars.append({
                "date": f"{s_bar.date} (盘中)" if is_today_in_progress else s_bar.date,
                "stock_close": s_bar.close,
                "stock_pct": s_bar.pct_change,
                "index_close": i_bar.close,
                "index_pct": i_bar.pct_change,
                "daily_dev": round(s_bar.pct_change - i_bar.pct_change, 2),
                "is_intraday": is_today_in_progress
            })

        # 6. 生成供给前端 K 线图表渲染的完整日K数据集
        kline_chart_data: List[Dict[str, Any]] = []
        for b in stock_klines:
            kline_chart_data.append({
                "date": b.date,
                "open": b.open,
                "close": b.close,
                "lowest": b.low,
                "highest": b.high,
                "volume": b.volume,
                "pct": b.pct_change
            })

        # 7. 🎮 异动推演沙盘 (主力控盘与连板推演)
        sandtable = cls.calculate_sandtable(
            confirmed_stock_klines=confirmed_stock,
            confirmed_index_klines=confirmed_index,
            confirmed_close=confirmed_close_price,
            realtime_price=realtime_price,
            confirmed_index_close=confirmed_index_close,
            realtime_index_price=realtime_index_price,
            price_limit_rate=config.price_limit_rate,
            is_intraday=is_intraday,
            base_mode=base_mode,
            assume_index_change=assume_index_change,
            assumed_today_rise_pct=assumed_today_rise_pct
        )

        return AnomalyAnalysisReport(
            symbol=symbol,
            stock_name=stock_name,
            market_name=config.market_name,
            price_limit_pct=round(config.price_limit_rate * 100, 1),
            is_intraday=is_intraday,
            market_session_text=session_text,
            confirmed_date=confirmed_close_date,
            confirmed_close=round(confirmed_close_price, 2),
            realtime_price=round(realtime_price, 2),
            realtime_pct_change=realtime_pct,
            benchmark_name=config.index_name,
            benchmark_code=config.index_code,
            confirmed_index_close=round(confirmed_index_close, 2),
            realtime_index_price=round(realtime_index_price, 2),
            realtime_index_pct_change=realtime_index_pct,
            normal_3d=normal_3d,
            severe_10d=severe_10d,
            severe_30d=severe_30d,
            future_projections=future_projections,
            history_bars=history_bars,
            kline_chart_data=kline_chart_data,
            sandtable=sandtable
        )
