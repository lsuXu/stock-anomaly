"""
A股异动监控系统 - 命令行交互工具 (CLI)
"""
import sys
import argparse
from datasource import DataSource
from calculator import AnomalyCalculator
from models import AnomalyAnalysisReport

def print_separator(char: str = "=", length: int = 96):
    print(char * length)

def render_report_cli(report: AnomalyAnalysisReport, is_mock: bool):
    print_separator("=")
    status_tag = f"【{report.market_session_text}】"
    source_tag = "[高仿模拟数据源]" if is_mock else "[东方财富实时数据源]"
    print(f" 🚀 A股股票异动监控与未来推演测算报告 {status_tag} {source_tag}")
    print_separator("=")
    
    # 头部基础信息
    print(f" 标的股票: {report.stock_name} ({report.symbol})  | 所属板块: {report.market_name} (涨跌幅限制: ±{report.price_limit_pct}%)")
    if report.is_intraday:
        print(f" 最新确认收盘(昨收): {report.confirmed_close:.2f} 元 ({report.confirmed_date})  | 盘中实时现价: {report.realtime_price:.2f} 元 (今日已涨跌: {report.realtime_pct_change:+.2f}%)")
        print(f" 法定基准指数: {report.benchmark_name} ({report.benchmark_code})  | 昨收: {report.confirmed_index_close:.2f} -> 实时点位: {report.realtime_index_price:.2f} ({report.realtime_index_pct_change:+.2f}%)")
    else:
        print(f" 最新确认收盘(今日终盘): {report.confirmed_close:.2f} 元 ({report.confirmed_date})")
        print(f" 法定基准指数: {report.benchmark_name} ({report.benchmark_code})  | 今日终盘点位: {report.confirmed_index_close:.2f}")
    print_separator("-")

    # 1. 异动监管核心窗口监控
    target_period = "今日收盘" if report.is_intraday else "下一交易日"
    print(f" 【一、三大监管窗口偏离值与异动临界测算 (测算目标期: {target_period})】")
    header_fmt = "{:<12} {:<8} {:<12} {:<12} {:<18} {:<16} {:<16}"
    base_ref = "相对昨收" if report.is_intraday else "相对今收"
    print(header_fmt.format("监管窗口", "官方红线", "触碰临界价", f"{target_period}红线({base_ref})", "现价还能涨", "当前累计偏离", "状态判定"))
    print("-" * 96)
    
    row_fmt = "{:<12} {:<8} {:<12} {:<18} {:<16} {:<16} {:<16}"
    for w_name, w in [
        (f"3日普通异动", report.normal_3d),
        (f"10日严重异动", report.severe_10d),
        (f"30日严重异动", report.severe_30d),
    ]:
        dev_str = f"{w.curr_realtime_deviation_pct:+.2f}%"
        limit_str = f"+{w.threshold_pct:.0f}%"
        crit_str = f"{w.crit_price:.2f}元"
        daily_rise_str = f"{w.daily_rise_threshold_pct:+.2f}%"
        remain_str = f"{w.remaining_rise_from_realtime_pct:+.2f}%"
        print(row_fmt.format(w_name, limit_str, crit_str, daily_rise_str, remain_str, dev_str, w.status))

    print_separator("-")

    # 2. 未来 N 天自定义推演表
    print(f" 【二、未来 {len(report.future_projections)} 天推演及连板吃异动测算 (10日严重异动红线)】")
    fut_header = "{:<12} {:<16} {:<16} {:<18} {:<16} {:<14}"
    print(fut_header.format("未来周期", "累计允许涨幅", "临界收盘价", "单日平均允许涨幅", "若天天涨停价", "连板首吃异动"))
    print("-" * 96)

    fut_row = "{:<12} {:<16} {:<16} {:<18} {:<16} {:<14}"
    for f in report.future_projections:
        alert_flag = "⚠️ 首次触发异动!" if f.will_trigger_if_limit_up else "-"
        print(fut_row.format(
            f.target_date_label,
            f"{f.allowed_cum_rise_pct:+.2f}%",
            f"{f.crit_price:.2f}元",
            f"{f.allowed_daily_rise_pct:+.2f}%/天",
            f"{f.limit_up_price:.2f}元",
            alert_flag
        ))

    print_separator("-")

    # 3. 最近交易日走势与基准偏离明细
    print(" 【三、近期历史走势与基准偏离明细】")
    hist_header = "{:<16} {:<12} {:<12} {:<14} {:<14} {:<12}"
    print(hist_header.format("交易日期", "股票价格", "股票涨跌幅", f"{report.benchmark_name}点位", "基准涨跌幅", "单日偏离值"))
    print("-" * 96)
    for b in report.history_bars[-8:]:
        print(hist_header.format(
            b["date"],
            f"{b['stock_close']:.2f}元",
            f"{b['stock_pct']:+.2f}%",
            f"{b['index_close']:.2f}",
            f"{b['index_pct']:+.2f}%",
            f"{b['daily_dev']:+.2f}%"
        ))
    print_separator("=")

def main():
    parser = argparse.ArgumentParser(description="A股股票异动监控与未来推演测算工具")
    parser.add_argument("--code", "-c", type=str, default="300059", help="股票代码")
    parser.add_argument("--days", "-d", type=int, default=5, help="未来推演天数 (默认 5 天)")
    parser.add_argument("--assume-index", "-i", type=float, default=0.0, help="假定未来基准指数涨跌幅")
    parser.add_argument("--mode", "-m", type=str, default="auto", choices=["auto", "intraday", "post_market"], help="测算模式: auto, intraday, post_market")
    parser.add_argument("--base-mode", "-b", type=str, default="window_start", choices=["window_start", "pre_window"], help="基准口径: window_start (炒股软件口径，区间首日), pre_window (窗口前一日)")

    args = parser.parse_args()

    force_mode = None
    if args.mode in ["intraday", "post_market"]:
        force_mode = args.mode

    try:
        config, name, stock_klines, index_klines, is_intraday, is_mock = DataSource.get_stock_and_index_data(
            symbol=args.code,
            force_mode=force_mode
        )
        report = AnomalyCalculator.generate_full_report(
            symbol=args.code,
            stock_name=name,
            config=config,
            stock_klines=stock_klines,
            index_klines=index_klines,
            is_intraday=is_intraday,
            future_days=args.days,
            assume_index_change=args.assume_index,
            base_mode=args.base_mode
        )
        render_report_cli(report, is_mock)
    except Exception as e:
        print(f"❌ 计算发生错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
