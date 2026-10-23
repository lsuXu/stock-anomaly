"""
A股股票日K线图绘制与可视化工具 (支持自由指定股票与天数，如 60天 / 120天 / 300天)
"""
import sys
import os
import json
import argparse
import webbrowser
from datasource import DataSource
from calculator import AnomalyCalculator

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{STOCK_NAME}} ({{SYMBOL}}) - 日K线图与异动警戒线</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        :root {
            --bg: #0b0f19;
            --surface: #131c2e;
            --border: #233354;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --red: #f43f5e;
            --green: #10b981;
            --blue: #38bdf8;
            --amber: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; }
        body { background: var(--bg); color: var(--text-primary); padding: 20px; min-height: 100vh; }
        .container { max-width: 1300px; margin: 0 auto; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; box-shadow: 0 8px 30px rgba(0,0,0,0.4); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--border); flex-wrap: wrap; gap: 12px; }
        .title h1 { font-size: 24px; font-weight: 700; display: flex; align-items: center; gap: 10px; }
        .subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
        .btn-group { display: flex; gap: 8px; }
        .filter-btn { background: #1c2842; border: 1px solid var(--border); color: #cbd5e1; padding: 6px 14px; border-radius: 6px; font-size: 13px; cursor: pointer; transition: all 0.2s; }
        .filter-btn:hover, .filter-btn.active { background: #2563eb; color: #fff; border-color: #3b82f6; }
        .meta-tags { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
        .tag { background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.25); color: #e2e8f0; padding: 6px 12px; border-radius: 6px; font-size: 13px; }
        .tag strong { color: #fff; }
        #chart { width: 100%; height: 600px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">
                <h1>📈 {{STOCK_NAME}} ({{SYMBOL}}) 日K线图</h1>
                <div class="subtitle">所属板块: {{MARKET_NAME}} | 法定基准: {{BENCHMARK_NAME}} | 数据来源: 腾讯财经实时前复权通道</div>
            </div>
            <div class="btn-group">
                <button class="filter-btn" onclick="setRange(30)">近30日</button>
                <button class="filter-btn active" onclick="setRange(60)">近60日</button>
                <button class="filter-btn" onclick="setRange(120)">近120日</button>
                <button class="filter-btn" onclick="setRange(250)">近250日 (年线)</button>
                <button class="filter-btn" onclick="setRange(0)">全部历史 (~320日)</button>
            </div>
        </div>

        <div class="meta-tags">
            <div class="tag">最新收盘: <strong>{{LATEST_PRICE}} 元</strong> ({{LATEST_PCT}}%)</div>
            <div class="tag">最新日期: <strong>{{LATEST_DATE}}</strong></div>
            <div class="tag">3日异动临界价: <strong style="color: var(--amber);">{{CRIT_3D}} 元</strong></div>
            <div class="tag">10日严重异动临界价: <strong style="color: var(--red);">{{CRIT_10D}} 元</strong></div>
        </div>

        <div id="chart"></div>
    </div>

    <script>
        const rawData = {{KLINE_JSON}};
        const crit3d = {{CRIT_3D_VAL}};
        const crit10d = {{CRIT_10D_VAL}};

        const dates = rawData.map(item => item.date);
        const ohlc = rawData.map(item => [item.open, item.close, item.lowest, item.highest]);
        const volumes = rawData.map(item => item.volume);

        function calculateMA(dayCount) {
            let result = [];
            for (let i = 0, len = ohlc.length; i < len; i++) {
                if (i < dayCount - 1) {
                    result.push('-');
                    continue;
                }
                let sum = 0;
                for (let j = 0; j < dayCount; j++) {
                    sum += ohlc[i - j][1]; // close
                }
                result.push((sum / dayCount).toFixed(2));
            }
            return result;
        }

        const chart = echarts.init(document.getElementById('chart'));

        const option = {
            animation: true,
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                backgroundColor: 'rgba(19, 28, 46, 0.95)',
                borderColor: '#233354',
                textStyle: { color: '#f8fafc' },
                formatter: function (params) {
                    const kParam = params.find(p => p.seriesName === '日K');
                    const vParam = params.find(p => p.seriesName === '成交量');
                    if (!kParam) return '';
                    const d = kParam.data;
                    const date = kParam.axisValue;
                    const open = d[1], close = d[2], lowest = d[3], highest = d[4];
                    const chgPct = (((close - open) / open) * 100).toFixed(2);
                    const chgColor = close >= open ? '#f43f5e' : '#10b981';
                    
                    let html = `<div style="font-weight:700;margin-bottom:4px;border-bottom:1px solid #334155;padding-bottom:4px;">${date}</div>`;
                    html += `开盘: <b>${open}</b> 元<br/>`;
                    html += `收盘: <b style="color:${chgColor}">${close}</b> 元 (${chgPct >= 0 ? '+' : ''}${chgPct}%)<br/>`;
                    html += `最高: <b>${highest}</b> 元<br/>`;
                    html += `最低: <b>${lowest}</b> 元<br/>`;
                    if (vParam) {
                        html += `成交量: <b>${(vParam.value / 100).toFixed(0)}</b> 手<br/>`;
                    }
                    params.forEach(p => {
                        if (p.seriesName.startsWith('MA')) {
                            html += `<span style="color:${p.color}">${p.seriesName}: ${p.value}</span> `;
                        }
                    });
                    return html;
                }
            },
            legend: {
                data: ['日K', 'MA5', 'MA10', 'MA20', 'MA30'],
                textStyle: { color: '#94a3b8' },
                top: 0
            },
            axisPointer: {
                link: [{ xAxisIndex: 'all' }]
            },
            grid: [
                { left: '4%', right: '4%', top: '8%', height: '60%' },
                { left: '4%', right: '4%', top: '74%', height: '18%' }
            ],
            xAxis: [
                {
                    type: 'category',
                    data: dates,
                    boundaryGap: true,
                    axisLine: { lineStyle: { color: '#334155' } },
                    axisLabel: { color: '#94a3b8' },
                    axisTick: { show: false },
                    splitLine: { show: false }
                },
                {
                    type: 'category',
                    gridIndex: 1,
                    data: dates,
                    boundaryGap: true,
                    axisLine: { lineStyle: { color: '#334155' } },
                    axisLabel: { show: false },
                    axisTick: { show: false },
                    splitLine: { show: false }
                }
            ],
            yAxis: [
                {
                    scale: true,
                    axisLine: { show: false },
                    axisLabel: { color: '#94a3b8' },
                    splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } }
                },
                {
                    scale: true,
                    gridIndex: 1,
                    splitNumber: 2,
                    axisLabel: { show: false },
                    axisLine: { show: false },
                    axisTick: { show: false },
                    splitLine: { show: false }
                }
            ],
            dataZoom: [
                {
                    type: 'inside',
                    xAxisIndex: [0, 1],
                    start: 80,
                    end: 100
                },
                {
                    show: true,
                    xAxisIndex: [0, 1],
                    type: 'slider',
                    bottom: '2%',
                    start: 80,
                    end: 100,
                    textStyle: { color: '#94a3b8' },
                    borderColor: '#233354',
                    fillerColor: 'rgba(37, 99, 235, 0.2)'
                }
            ],
            series: [
                {
                    name: '日K',
                    type: 'candlestick',
                    data: ohlc,
                    itemStyle: {
                        color: '#f43f5e',
                        color0: '#10b981',
                        borderColor: '#f43f5e',
                        borderColor0: '#10b981'
                    },
                    markLine: {
                        symbol: ['none', 'none'],
                        data: [
                            crit3d > 0 ? {
                                yAxis: crit3d,
                                name: '3日异动线',
                                lineStyle: { color: '#f59e0b', type: 'dashed', width: 2 },
                                label: { formatter: '3日异动: {c}元', position: 'end', color: '#f59e0b' }
                            } : null,
                            crit10d > 0 ? {
                                yAxis: crit10d,
                                name: '10日严重异动线',
                                lineStyle: { color: '#ef4444', type: 'dotted', width: 2 },
                                label: { formatter: '10日红线: {c}元', position: 'end', color: '#ef4444' }
                            } : null
                        ].filter(Boolean)
                    }
                },
                {
                    name: 'MA5',
                    type: 'line',
                    data: calculateMA(5),
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 1.5, color: '#f59e0b' }
                },
                {
                    name: 'MA10',
                    type: 'line',
                    data: calculateMA(10),
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 1.5, color: '#38bdf8' }
                },
                {
                    name: 'MA20',
                    type: 'line',
                    data: calculateMA(20),
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 1.5, color: '#a855f7' }
                },
                {
                    name: 'MA30',
                    type: 'line',
                    data: calculateMA(30),
                    smooth: true,
                    showSymbol: false,
                    lineStyle: { width: 1.5, color: '#ec4899' }
                },
                {
                    name: '成交量',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: volumes,
                    itemStyle: {
                        color: function (params) {
                            const i = params.dataIndex;
                            return ohlc[i][1] >= ohlc[i][0] ? 'rgba(244, 63, 94, 0.7)' : 'rgba(16, 185, 129, 0.7)';
                        }
                    }
                }
            ]
        };

        chart.setOption(option);
        window.addEventListener('resize', () => chart.resize());

        function setRange(days) {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            const total = dates.length;
            let start = 0;
            if (days > 0 && days < total) {
                start = Math.max(0, Math.floor(((total - days) / total) * 100));
            }
            chart.dispatchAction({
                type: 'dataZoom',
                start: start,
                end: 100
            });
        }

        // 默认定位到最近 60 天
        setRange(60);
    </script>
</body>
</html>
"""

def generate_kline_html(symbol: str, days_limit: int = 320, auto_open: bool = True) -> str:
    """获取数据并生成交互式K线图 HTML 文件"""
    config, stock_name, stock_klines, index_klines, is_intraday, is_mock = DataSource.get_stock_and_index_data(
        symbol=symbol,
        limit=days_limit
    )
    report = AnomalyCalculator.generate_full_report(
        symbol=symbol,
        stock_name=stock_name,
        config=config,
        stock_klines=stock_klines,
        index_klines=index_klines,
        is_intraday=is_intraday
    )

    kline_list = report.kline_chart_data
    latest = kline_list[-1]
    latest_pct_sign = '+' if latest['pct'] >= 0 else ''
    
    html = HTML_TEMPLATE
    html = html.replace("{{STOCK_NAME}}", report.stock_name)
    html = html.replace("{{SYMBOL}}", report.symbol)
    html = html.replace("{{MARKET_NAME}}", report.market_name)
    html = html.replace("{{BENCHMARK_NAME}}", report.benchmark_name)
    html = html.replace("{{LATEST_PRICE}}", str(report.realtime_price))
    html = html.replace("{{LATEST_PCT}}", f"{latest_pct_sign}{report.realtime_pct_change:.2f}")
    html = html.replace("{{LATEST_DATE}}", latest["date"])
    html = html.replace("{{CRIT_3D}}", str(report.normal_3d.crit_price))
    html = html.replace("{{CRIT_3D_VAL}}", str(report.normal_3d.crit_price))
    html = html.replace("{{CRIT_10D}}", str(report.severe_10d.crit_price))
    html = html.replace("{{CRIT_10D_VAL}}", str(report.severe_10d.crit_price))
    html = html.replace("{{KLINE_JSON}}", json.dumps(kline_list, ensure_ascii=False))

    output_filename = f"kline_{symbol}.html"
    output_path = os.path.abspath(output_filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 日K线图已生成: {output_path} (共包含 {len(kline_list)} 个交易日数据)")
    if auto_open:
        print(f"🌐 正在自动为您在浏览器中打开 K 线图...")
        webbrowser.open(f"file://{output_path}")

    return output_path

def main():
    parser = argparse.ArgumentParser(description="A股股票日K线图获取与绘制工具")
    parser.add_argument("--code", "-c", type=str, default="000530", help="股票代码 (如 000530 冰山冷热, 300059 东方财富)")
    parser.add_argument("--days", "-d", type=int, default=320, help="获取的最大交易日数量 (默认 320 天，约 1.3 年)")
    parser.add_argument("--no-open", action="store_true", help="生成后不自动唤起浏览器")

    args = parser.parse_args()
    generate_kline_html(args.code, args.days, auto_open=not args.no_open)

if __name__ == "__main__":
    main()
