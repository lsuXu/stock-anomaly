"""
A股异动监控系统 - 核心计算引擎 (严谨区分盘中实时现价与已确认收盘价)
"""
from typing import List, Dict, Any
from models import (
    MarketConfig,
    KLineBar,
    WindowDeviationDetail,
    FutureDayProjection,
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
        assume_index_change: float = 0.0
    ) -> WindowDeviationDetail:
        """
        计算指定窗口 (3天、10天、30天) 的异动指标:
        - 盘中: 目标期为"今日收盘"，以昨日收盘价(confirmed_close)为日涨幅基准，计算今日收盘涨幅阈值与现价剩余空间
        - 盘后: 目标期为"下一交易日"，以今日收盘价为基准，计算下一交易日涨幅阈值
        """
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
    def generate_full_report(
        cls,
        symbol: str,
        stock_name: str,
        config: MarketConfig,
        stock_klines: List[KLineBar],
        index_klines: List[KLineBar],
        is_intraday: bool,
        future_days: int = 5,
        assume_index_change: float = 0.0
    ) -> AnomalyAnalysisReport:
        """生成全面的异动分析报告 (含长周期日K线序列)"""

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

        # 6. 生成供给前端 K 线图表渲染的完整日K数据集 (可达300+天)
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
            kline_chart_data=kline_chart_data
        )
