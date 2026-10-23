"""
单元测试用例 - 异动计算与推演数学正确性验证 (支持两种基准口径验证)
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

        cfg_sz = identify_market_config("000530")
        self.assertEqual(cfg_sz.market_type, MarketType.SZ_MAIN)
        self.assertEqual(cfg_sz.index_name, "深证A指")

    def test_window_start_mode(self):
        """测试主流专业炒股软件口径 (window_start: 区间首日为基准)"""
        # 3日窗口: Day 1 (10.50), Day 2 (昨收 11.00), Day 3 (今日实时 11.50)
        # 基期为 Day 1 的 10.50 元
        confirmed_stock = [
            KLineBar("2026-10-10", 10.0, 10.0, 10.0, 10.0),
            KLineBar("2026-10-11", 10.0, 10.5, 10.5, 10.0), # Day 1
            KLineBar("2026-10-12", 10.5, 11.0, 11.0, 10.5), # Day 2 (昨收)
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
            base_mode="window_start"
        )

        self.assertEqual(result.base_stock_price, 10.50)
        # P_crit = 10.50 * (0.20 + 1) = 12.60
        self.assertEqual(result.crit_price, 12.60)

    def test_pre_window_mode(self):
        """测试窗口前一日收盘口径 (pre_window)"""
        confirmed_stock = [
            KLineBar("2026-10-10", 10.0, 10.0, 10.0, 10.0), # T-3 基期
            KLineBar("2026-10-11", 10.0, 10.5, 10.5, 10.0),
            KLineBar("2026-10-12", 10.5, 11.0, 11.0, 10.5), # 昨收
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
            base_mode="pre_window"
        )

        self.assertEqual(result.base_stock_price, 10.0)
        self.assertEqual(result.crit_price, 12.0)

    def test_sandtable_simulation(self):
        """测试沙盘推演 (What-If 与 目标连板倒推矩阵)"""
        # 构造15天平稳数据，基准收盘价均为 10.0
        stock_klines = [KLineBar(f"2026-10-{i:02d}", 10.0, 10.0, 10.0, 10.0) for i in range(1, 20)]
        index_klines = [KLineBar(f"2026-10-{i:02d}", 3000.0, 3000.0, 3000.0, 3000.0) for i in range(1, 20)]

        st = AnomalyCalculator.calculate_sandtable(
            confirmed_stock_klines=stock_klines,
            confirmed_index_klines=index_klines,
            confirmed_close=10.0,
            realtime_price=10.3,
            confirmed_index_close=3000.0,
            realtime_index_price=3000.0,
            price_limit_rate=0.10,
            is_intraday=True,
            base_mode="window_start",
            assumed_today_rise_pct=3.0
        )

        self.assertEqual(st.assumed_today_rise_pct, 3.0)
        self.assertEqual(st.assumed_today_price, 10.30)
        self.assertEqual(len(st.what_if_steps), 5)
        self.assertEqual(len(st.reverse_plans), 5)
        self.assertTrue(st.max_sustainable_streak_days >= 1)

        # 验证目标连板计划倒推属性
        plan_1 = st.reverse_plans[0]
        self.assertEqual(plan_1.target_streak_days, 1)
        self.assertTrue(plan_1.is_achievable)
        self.assertIsNotNone(plan_1.action_advice)

if __name__ == "__main__":
    unittest.main()
