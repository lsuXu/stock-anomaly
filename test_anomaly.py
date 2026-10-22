"""
单元测试用例 - 异动计算与推演数学正确性验证 (支持盘中/盘后区分)
"""
import unittest
from models import MarketType, KLineBar
from calculator import AnomalyCalculator
from datasource import identify_market_config

class TestAnomalyLogic(unittest.TestCase):

    def test_market_identification(self):
        """测试各板块代码识别与基准指数匹配"""
        cfg_cyb = identify_market_config("300059")
        self.assertEqual(cfg_cyb.market_type, MarketType.CYB)
        self.assertEqual(cfg_cyb.index_name, "创业板综")
        self.assertEqual(cfg_cyb.index_code, "399102")
        self.assertEqual(cfg_cyb.normal_threshold, 0.30)
        self.assertEqual(cfg_cyb.price_limit_rate, 0.20)

        cfg_sh = identify_market_config("600519")
        self.assertEqual(cfg_sh.market_type, MarketType.SH_MAIN)
        self.assertEqual(cfg_sh.index_name, "上证A指")
        self.assertEqual(cfg_sh.index_code, "000002")

    def test_intraday_deviation_math(self):
        """
        测试盘中模式下的计算:
        已确认K线(截止昨日):
        - T-3 (基期): 股票 10.00元, 指数 3000点
        - T-2: 股票 10.50元, 指数 3000点
        - T-1 (昨收): 股票 11.00元, 指数 3000点
        今日盘中实时 (T):
        - 股票实时现价: 11.50元
        - 指数实时点位: 3000点 (平盘)
        阈值: 主板 0.20 (+20%)
        反解临界价: P_crit = 10.00 * (0.20 + 3000/3000) = 12.00元
        今日涨幅阈值 (相对昨收 11.00元): (12.00 / 11.00 - 1) * 100% = +9.09%
        现价还能再涨 (相对现价 11.50元): (12.00 / 11.50 - 1) * 100% = +4.35%
        当前盘中实时偏离: (11.50/10 - 1) - 0 = +15.0%
        """
        confirmed_stock = [
            KLineBar("2026-10-10", 10.0, 10.0, 10.0, 10.0), # T-3 基期
            KLineBar("2026-10-11", 10.0, 10.5, 10.5, 10.0), # T-2
            KLineBar("2026-10-12", 10.5, 11.0, 11.0, 10.5), # T-1 昨收
        ]
        confirmed_index = [
            KLineBar("2026-10-10", 3000.0, 3000.0, 3000.0, 3000.0),
            KLineBar("2026-10-11", 3000.0, 3000.0, 3000.0, 3000.0),
            KLineBar("2026-10-12", 3000.0, 3000.0, 3000.0, 3000.0),
        ]

        result = AnomalyCalculator.calculate_window(
            confirmed_stock_klines=confirmed_stock,
            confirmed_index_klines=confirmed_index,
            realtime_stock_price=11.50,
            realtime_index_price=3000.0,
            window_days=3,
            threshold=0.20,
            price_limit_rate=0.10,
            is_intraday=True,
            assume_index_change=0.0
        )

        self.assertEqual(result.base_stock_price, 10.0)
        self.assertEqual(result.crit_price, 12.0)
        self.assertEqual(result.daily_rise_threshold_pct, 9.09)
        self.assertEqual(result.remaining_rise_from_realtime_pct, 4.35)
        self.assertEqual(result.curr_realtime_deviation_pct, 15.0)

    def test_post_market_deviation_math(self):
        """
        测试盘后模式下的计算:
        今日收盘后，已确认K线截止到今日:
        - T-2 (基期，相对于明日): 股票 10.00元, 指数 3000点
        - T-1: 股票 11.00元, 指数 3000点
        - T (今日已收盘): 股票 12.00元, 指数 3000点
        测算明日(T+1):
        反解临界价: P_crit = 10.00 * (0.20 + 3000/3000) = 12.00元
        明日涨幅红线 (相对今日收盘 12.00元): (12.00 / 12.00 - 1) * 100% = 0.0%
        """
        confirmed_stock = [
            KLineBar("2026-10-10", 10.0, 10.0, 10.0, 10.0), # T-2 基期
            KLineBar("2026-10-11", 10.0, 11.0, 11.0, 10.0), # T-1
            KLineBar("2026-10-12", 11.0, 12.0, 12.0, 11.0), # T 今日收盘
        ]
        confirmed_index = [
            KLineBar("2026-10-10", 3000.0, 3000.0, 3000.0, 3000.0),
            KLineBar("2026-10-11", 3000.0, 3000.0, 3000.0, 3000.0),
            KLineBar("2026-10-12", 3000.0, 3000.0, 3000.0, 3000.0),
        ]

        result = AnomalyCalculator.calculate_window(
            confirmed_stock_klines=confirmed_stock,
            confirmed_index_klines=confirmed_index,
            realtime_stock_price=12.0,
            realtime_index_price=3000.0,
            window_days=3,
            threshold=0.20,
            price_limit_rate=0.10,
            is_intraday=False,
            assume_index_change=0.0
        )

        self.assertEqual(result.base_stock_price, 10.0)
        self.assertEqual(result.crit_price, 12.0)
        self.assertEqual(result.daily_rise_threshold_pct, 0.0)

if __name__ == "__main__":
    unittest.main()
