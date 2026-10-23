"""
题材梯队与连板效应、断板亏钱效应模块单元测试
"""
import unittest
from theme_sentiment import ThemeSentimentEngine

class TestThemeSentimentEngine(unittest.TestCase):

    def test_trading_dates(self):
        dates = ThemeSentimentEngine.get_trading_dates(10)
        self.assertIsInstance(dates, list)
        self.assertGreaterEqual(len(dates), 5)
        # 验证降序排列且为8位数字
        self.assertEqual(len(dates[0]), 8)
        self.assertTrue(dates[0] >= dates[1])

    def test_sentiment_metrics(self):
        dates = ThemeSentimentEngine.get_trading_dates(5)
        latest_date = dates[0]
        metrics = ThemeSentimentEngine.get_sentiment_metrics(latest_date)

        self.assertIn("score", metrics)
        self.assertIn("cycle_phase", metrics)
        self.assertIn("max_height", metrics)
        self.assertIn("break_rate", metrics)
        self.assertIn("promotion_1_to_2", metrics)
        self.assertIn("promotion_2_to_3", metrics)
        self.assertIn("promotion_3_to_4", metrics)

        self.assertGreaterEqual(metrics["score"], 0)
        self.assertLessEqual(metrics["score"], 100)
        self.assertGreaterEqual(metrics["max_height"], 1)

    def test_ladder_and_themes(self):
        dates = ThemeSentimentEngine.get_trading_dates(5)
        latest_date = dates[0]
        ladder, themes = ThemeSentimentEngine.get_ladder_and_themes(latest_date)

        self.assertIsInstance(ladder, dict)
        self.assertIsInstance(themes, list)
        # 至少有首板
        self.assertTrue(1 in ladder or len(ladder) > 0)
        if themes:
            top_theme = themes[0]
            self.assertIn("theme_name", top_theme)
            self.assertIn("count", top_theme)
            self.assertIn("leader_name", top_theme)

    def test_broken_board_backtest(self):
        dates = ThemeSentimentEngine.get_trading_dates(5)
        res = ThemeSentimentEngine.get_broken_board_backtest(days=5, target_height="all", ref_date=dates[0])
        self.assertIn("summary", res)
        self.assertIn("details", res)
        s = res["summary"]
        self.assertIn("total_samples", s)
        self.assertIn("t0_avg_pct", s)
        self.assertIn("t0_avg_drop_from_high", s)
        self.assertIn("t1_avg_open_gap", s)
        self.assertIn("t1_avg_close_pct", s)

        # 测试高度筛选 3进4
        res_3_4 = ThemeSentimentEngine.get_broken_board_backtest(days=5, target_height="3_to_4", ref_date=dates[0], pre_days=3, post_days=5)
        for item in res_3_4["details"]:
            self.assertEqual(item["stage"], "3进4断板")
            self.assertIn("mini_kline", item)
            # 验证切片天数符合范围
            self.assertLessEqual(len(item["mini_kline"]), 3 + 5 + 1)
            # 验证断板日标记存在
            self.assertTrue(any(b["is_break_day"] for b in item["mini_kline"]))

if __name__ == "__main__":
    unittest.main()
