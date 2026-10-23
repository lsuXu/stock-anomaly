"""
A股股票异动监控与推演系统 - 主程序入口
"""
import sys
import argparse
from cli import main as cli_main
from server import run_server

def main():
    parser = argparse.ArgumentParser(description="A股股票异动监控与未来推演测算系统")
    parser.add_argument("--server", "-s", action="store_true", help="启动可视化 Web 仪表盘服务")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Web 服务监听端口 (默认 8080)")
    parser.add_argument("--code", "-c", type=str, default=None, help="股票代码 (如 300059, 600519, 000001)")
    parser.add_argument("--days", "-d", type=int, default=5, help="未来推演天数 (默认 5 天)")
    parser.add_argument("--assume-index", "-i", type=float, default=0.0, help="假定未来基准指数日涨幅 (%, 输入 0.1 代表 +0.1%)")

    args = parser.parse_args()

    if args.server:
        run_server(args.port)
    elif args.code:
        # CLI 模式执行指定股票查询
        sys.argv = [sys.argv[0], "--code", args.code, "--days", str(args.days), "--assume-index", str(args.assume_index)]
        cli_main()
    else:
        # 默认模式: 先输出默认 300059 示例测算，并提示 Web 启动方式
        print("💡 未指定参数，为您展示创业板龙头 [东方财富 300059] 的异动测算示例：")
        sys.argv = [sys.argv[0], "--code", "300059", "--days", "5"]
        cli_main()
        print("\n 提示:")
        print("  1. 终端自定义查询: python3 main.py --code 600519 --days 3")
        print("  2. 启动图形化Web仪表盘: python3 main.py --server --port 8080")

if __name__ == "__main__":
    main()
