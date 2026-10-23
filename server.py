"""
A股异动监控系统 - 轻量级 Web 仪表盘与 REST API 服务 (原生内置库，零依赖)
"""
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datasource import DataSource
from calculator import AnomalyCalculator
from dataclasses import asdict

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A股异动监控与未来推演测算系统</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        :root {
            --bg: #0b0f19;
            --surface: #131c2e;
            --surface-hover: #1c2842;
            --border: #233354;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --red: #f43f5e;
            --green: #10b981;
            --blue: #38bdf8;
            --amber: #f59e0b;
            --purple: #a855f7;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; }
        body { background: var(--bg); color: var(--text-primary); min-height: 100vh; padding: 24px; line-height: 1.5; }
        .container { max-width: 1200px; margin: 0 auto; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
        .title-group h1 { font-size: 24px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 10px; }
        .title-group p { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
        .badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        .badge-live { background: rgba(16, 185, 129, 0.15); color: var(--green); border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-session-intraday { background: rgba(245, 158, 11, 0.15); color: var(--amber); border: 1px solid rgba(245, 158, 11, 0.4); }
        .badge-session-closed { background: rgba(56, 189, 248, 0.15); color: var(--blue); border: 1px solid rgba(56, 189, 248, 0.4); }
        
        .control-panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 24px; display: grid; grid-template-columns: 1fr 0.9fr 1fr 1.1fr 1.4fr auto; gap: 14px; align-items: end; }
        .form-group label { display: block; font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-bottom: 6px; }
        input[type="text"], input[type="number"], select { width: 100%; background: #0a1120; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; font-size: 14px; color: #fff; outline: none; transition: border-color 0.2s; }
        input[type="text"]:focus, input[type="number"]:focus, select:focus { border-color: var(--blue); }
        .btn-query { background: linear-gradient(135deg, #0284c7, #2563eb); color: white; border: none; border-radius: 8px; padding: 10px 22px; font-size: 15px; font-weight: 600; cursor: pointer; height: 42px; transition: opacity 0.2s; white-space: nowrap; }
        .btn-query:hover { opacity: 0.9; }

        .quick-tags { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: -4px; }
        .quick-tag-label { font-size: 12px; color: var(--text-secondary); }
        .tag-btn { background: #1a253c; border: 1px solid var(--border); color: #cbd5e1; font-size: 12px; padding: 3px 10px; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
        .tag-btn:hover { background: var(--border); color: #fff; }

        .meta-strip { background: rgba(56, 189, 248, 0.05); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 16px 20px; margin-bottom: 24px; display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
        .meta-item { display: flex; flex-direction: column; }
        .meta-item .m-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
        .meta-item .m-value { font-size: 16px; font-weight: 700; color: #fff; }
        .m-sub { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }

        .cards-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-bottom: 24px; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; position: relative; overflow: hidden; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .card-title { font-size: 15px; font-weight: 600; color: var(--text-secondary); }
        .rule-tag { font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 4px; background: rgba(255, 255, 255, 0.08); color: #cbd5e1; }
        .main-stat { font-size: 26px; font-weight: 800; color: #fff; margin-bottom: 10px; }
        .stat-sub { font-size: 13px; color: var(--text-secondary); margin-bottom: 8px; display: flex; justify-content: space-between; }
        .stat-highlight { background: rgba(255, 255, 255, 0.03); padding: 8px 10px; border-radius: 6px; margin-bottom: 12px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
        .card-footer { padding-top: 12px; border-top: 1px solid var(--border); font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
        
        .status-safe { color: var(--green); font-weight: 600; }
        .status-warn { color: var(--amber); font-weight: 600; }
        .status-danger { color: var(--red); font-weight: 600; }

        .section-box { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 24px; }
        .section-title { font-size: 16px; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }
        
        table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
        th { background: #0f1828; color: var(--text-secondary); font-weight: 600; padding: 12px 14px; border-bottom: 1px solid var(--border); }
        td { padding: 12px 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); color: #e2e8f0; }
        tr:hover td { background: var(--surface-hover); }
        .val-rise { color: var(--red); font-weight: 600; }
        .val-fall { color: var(--green); font-weight: 600; }
        .val-gold { color: var(--amber); font-weight: 700; }
        .badge-row-intraday { background: rgba(245, 158, 11, 0.15); color: var(--amber); padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px; font-weight: 600; }
        .streak-alert { background: rgba(244, 63, 94, 0.15); color: var(--red); border: 1px solid rgba(244, 63, 94, 0.3); padding: 2px 6px; border-radius: 4px; font-weight: 600; }

        .kline-btn-group { display: flex; gap: 8px; flex-wrap: wrap; }
        .kline-filter-btn { background: #1c2842; border: 1px solid var(--border); color: #cbd5e1; padding: 4px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
        .kline-filter-btn:hover, .kline-filter-btn.active { background: #2563eb; color: #fff; border-color: #3b82f6; }

        @media (max-width: 900px) {
            .cards-grid { grid-template-columns: 1fr; }
            .control-panel { grid-template-columns: 1fr; }
            .meta-strip { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="title-group">
                <h1>📈 A股股票异动监控与推演系统 <span id="sessionTag" class="badge badge-session-intraday">识别中...</span></h1>
                <p>严格区分【盘中实时价格】与【最新确认收盘价】 | 支持自定义未来天数与连板吃异动测算</p>
            </div>
            <div id="sourceTag" class="badge badge-live">东方财富实时数据源</div>
        </header>

        <!-- 控制栏 -->
        <div class="control-panel">
            <div class="form-group">
                <label>股票代码</label>
                <input type="text" id="symbolInput" value="300059" placeholder="如 300059, 600519">
            </div>
            <div class="form-group">
                <label>未来推演天数 (1 ~ 30 天)</label>
                <input type="number" id="daysInput" value="5" min="1" max="30">
            </div>
            <div class="form-group">
                <label>假定未来指数日涨幅</label>
                <input type="number" id="indexChgInput" value="0.0" step="0.005" placeholder="0.0为平盘">
            </div>
            <div class="form-group">
                <label>测算模式 (盘中/盘后切换)</label>
                <select id="modeSelect">
                    <option value="auto" selected>⚡ 自动识别时段 (推荐)</option>
                    <option value="intraday">☀️ 强制盘中模式 (测算今日)</option>
                    <option value="post_market">🌙 强制盘后模式 (测算明日)</option>
                </select>
            </div>
            <div class="form-group">
                <label>异动基准口径</label>
                <select id="baseModeSelect">
                    <option value="window_start" selected>🎯 炒股软件标准 (区间首日)</option>
                    <option value="pre_window">📐 窗口前一日口径 (严谨10+1日)</option>
                </select>
            </div>
            <button class="btn-query" onclick="doQuery()">开始测算</button>

            <div class="quick-tags">
                <span class="quick-tag-label">快速填充:</span>
                <button class="tag-btn" onclick="setQuick('300059')">东方财富 (创业板)</button>
                <button class="tag-btn" onclick="setQuick('300750')">宁德时代 (创业板)</button>
                <button class="tag-btn" onclick="setQuick('600519')">贵州茅台 (沪市主板)</button>
                <button class="tag-btn" onclick="setQuick('000001')">平安银行 (深市主板)</button>
                <button class="tag-btn" onclick="setQuick('002594')">比亚迪 (深市主板)</button>
                <button class="tag-btn" onclick="setQuick('688981')">中芯国际 (科创板)</button>
            </div>
        </div>

        <!-- 标的概要条 (清晰区分确认收盘价与实时价) -->
        <div class="meta-strip" id="metaStrip" style="display: none;">
            <div class="meta-item">
                <span class="m-label">标的名称 / 代码</span>
                <span class="m-value" id="mStock">--</span>
                <span class="m-sub" id="mMarket">--</span>
            </div>
            <div class="meta-item">
                <span class="m-label">最新已确认收盘价</span>
                <span class="m-value" id="mConfirmedClose">-- 元</span>
                <span class="m-sub" id="mConfirmedDate">基准日期: --</span>
            </div>
            <div class="meta-item">
                <span class="m-label">当前盘中实时现价</span>
                <span class="m-value" id="mRealtimePrice">-- 元</span>
                <span class="m-sub" id="mRealtimePct">今日涨跌: --%</span>
            </div>
            <div class="meta-item">
                <span class="m-label">法定基准指数</span>
                <span class="m-value" id="mIndexName">--</span>
                <span class="m-sub" id="mIndexPrice">收盘: -- | 现价: --</span>
            </div>
            <div class="meta-item">
                <span class="m-label">当前计算模式</span>
                <span class="m-value" id="mSessionText" style="color: var(--amber);">--</span>
                <span class="m-sub" id="mTargetDesc">--</span>
            </div>
        </div>

        <!-- 三大监管红线卡片 -->
        <div class="cards-grid" id="cardsGrid" style="display: none;">
            <!-- 3日普通异动 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" id="title3d">3日普通异动</span>
                    <span class="rule-tag" id="tag3d">红线 ±30%</span>
                </div>
                <div class="main-stat" id="crit3d">-- 元</div>
                <div class="stat-highlight">
                    <span id="labelDaily3d">目标日涨幅红线(相对昨收):</span>
                    <strong id="dailyRise3d" class="val-rise">--%</strong>
                </div>
                <div class="stat-sub">
                    <span>从当前现价还能涨: <strong id="remain3d" class="val-gold">--%</strong></span>
                    <span>当前实时偏离: <strong id="dev3d">--%</strong></span>
                </div>
                <div class="card-footer">
                    <div>
                        <div style="font-size: 11px; color: var(--text-secondary);" id="baseDesc3d">基准起点: --</div>
                    </div>
                    <span id="status3d" class="status-warn">计算中...</span>
                </div>
            </div>

            <!-- 10日严重异动 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" id="title10d">10日严重异动</span>
                    <span class="rule-tag">红线 +100%</span>
                </div>
                <div class="main-stat" id="crit10d">-- 元</div>
                <div class="stat-highlight">
                    <span id="labelDaily10d">目标日涨幅红线(相对昨收):</span>
                    <strong id="dailyRise10d" class="val-rise">--%</strong>
                </div>
                <div class="stat-sub">
                    <span>从当前现价还能涨: <strong id="remain10d" class="val-gold">--%</strong></span>
                    <span>当前累计偏离: <strong id="dev10d">--%</strong></span>
                </div>
                <div class="card-footer">
                    <div>
                        <div style="font-size: 11px; color: var(--text-secondary);" id="baseDesc10d">基准起点: --</div>
                    </div>
                    <span id="status10d" class="status-safe">计算中...</span>
                </div>
            </div>

            <!-- 30日严重异动 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title" id="title30d">30日严重异动</span>
                    <span class="rule-tag">红线 +200%</span>
                </div>
                <div class="main-stat" id="crit30d">-- 元</div>
                <div class="stat-highlight">
                    <span id="labelDaily30d">目标日涨幅红线(相对昨收):</span>
                    <strong id="dailyRise30d" class="val-rise">--%</strong>
                </div>
                <div class="stat-sub">
                    <span>从当前现价还能涨: <strong id="remain30d" class="val-gold">--%</strong></span>
                    <span>当前累计偏离: <strong id="dev30d">--%</strong></span>
                </div>
                <div class="card-footer">
                    <div>
                        <div style="font-size: 11px; color: var(--text-secondary);" id="baseDesc30d">基准起点: --</div>
                    </div>
                    <span id="status30d" class="status-safe">计算中...</span>
                </div>
            </div>
        </div>

        <!-- 日K线走势图 -->
        <div class="section-box" id="klineSection" style="display: none;">
            <div class="section-title">
                <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                    <span>📊 历史日K线走势图与均线 (含成交量及异动红线)</span>
                    <span id="klineCountLabel" style="font-size: 13px; font-weight: normal; color: var(--text-secondary);"></span>
                </div>
                <div class="kline-btn-group">
                    <button class="kline-filter-btn" onclick="setKLineZoom(30)">近30日</button>
                    <button class="kline-filter-btn active" onclick="setKLineZoom(60)">近60日</button>
                    <button class="kline-filter-btn" onclick="setKLineZoom(120)">近120日</button>
                    <button class="kline-filter-btn" onclick="setKLineZoom(250)">近250日 (年线)</button>
                    <button class="kline-filter-btn" onclick="setKLineZoom(0)">全部历史 (~320日)</button>
                </div>
            </div>
            <div id="klineChartContainer" style="width: 100%; height: 500px;"></div>
        </div>

        <!-- 未来N天推演表格 -->
        <div class="section-box" id="futureSection" style="display: none;">
            <div class="section-title">
                <span>🔮 未来自定义天数连板与异动推演 (基于10日严重异动 +100% 规则)</span>
                <span style="font-size: 13px; font-weight: normal; color: var(--text-secondary);">若连续涨停，系统自动推演哪一天将首次吃严重异动</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>未来预测周期</th>
                        <th>累计允许最大涨幅</th>
                        <th>触碰异动临界价</th>
                        <th>单日平均允许涨幅</th>
                        <th>若每日涨停价格</th>
                        <th>连板吃异动预警</th>
                    </tr>
                </thead>
                <tbody id="futureTbody"></tbody>
            </table>
        </div>

        <!-- 历史K线走势明细 -->
        <div class="section-box" id="historySection" style="display: none;">
            <div class="section-title">
                <span>📜 近期历史走势明细 (区分已确认收盘与盘中状态)</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>交易日期</th>
                        <th>股票价格</th>
                        <th>股票涨跌幅</th>
                        <th>基准指数点位</th>
                        <th>基准指数涨跌幅</th>
                        <th>当日偏离值</th>
                    </tr>
                </thead>
                <tbody id="historyTbody"></tbody>
            </table>
        </div>
    </div>

    <script>
        function setQuick(code) {
            document.getElementById('symbolInput').value = code;
            doQuery();
        }

        async function doQuery() {
            const code = document.getElementById('symbolInput').value.trim();
            const days = document.getElementById('daysInput').value.trim() || 5;
            const indexChg = document.getElementById('indexChgInput').value.trim() || 0.0;
            const mode = document.getElementById('modeSelect').value;
            const baseMode = document.getElementById('baseModeSelect').value;

            if (!code) {
                alert("请输入股票代码");
                return;
            }

            try {
                const resp = await fetch(`/api/calculate?code=${code}&days=${days}&assume_index=${indexChg}&mode=${mode}&base_mode=${baseMode}`);
                const data = await resp.json();

                if (!data.success) {
                    alert("查询失败: " + data.error);
                    return;
                }

                renderData(data);
            } catch (e) {
                alert("请求出错: " + e.message);
            }
        }

        function renderData(data) {
            const r = data.report;
            document.getElementById('sourceTag').innerText = data.is_mock ? "高仿仿真模拟源" : "东方财富实时数据源";

            // 头部时段标签
            const sessionTag = document.getElementById('sessionTag');
            if (r.is_intraday) {
                sessionTag.className = "badge badge-session-intraday";
                sessionTag.innerText = "☀️ 盘中交易中 (以昨收为基准测算今日)";
            } else {
                sessionTag.className = "badge badge-session-closed";
                sessionTag.innerText = "🌙 盘后已收盘 (以今日收盘为基准测算明日)";
            }

            // 标的概要条
            document.getElementById('mStock').innerText = `${r.stock_name} (${r.symbol})`;
            document.getElementById('mMarket').innerText = `${r.market_name} (涨跌幅限制: ±${r.price_limit_pct}%)`;

            document.getElementById('mConfirmedClose').innerText = `${r.confirmed_close.toFixed(2)} 元`;
            document.getElementById('mConfirmedDate').innerText = `${r.is_intraday ? '昨日确认收盘' : '今日确认收盘'}: ${r.confirmed_date}`;

            const rtSign = r.realtime_pct_change >= 0 ? '+' : '';
            const rtColor = r.realtime_pct_change >= 0 ? 'var(--red)' : 'var(--green)';
            document.getElementById('mRealtimePrice').innerHTML = `${r.realtime_price.toFixed(2)} 元`;
            document.getElementById('mRealtimePct').innerHTML = `实时涨跌: <span style="color: ${rtColor}; font-weight: 700;">${rtSign}${r.realtime_pct_change.toFixed(2)}%</span>`;

            document.getElementById('mIndexName').innerText = `${r.benchmark_name} (${r.benchmark_code})`;
            const idxSign = r.realtime_index_pct_change >= 0 ? '+' : '';
            document.getElementById('mIndexPrice').innerText = `昨收: ${r.confirmed_index_close.toFixed(2)} | 现价: ${r.realtime_index_price.toFixed(2)} (${idxSign}${r.realtime_index_pct_change.toFixed(2)}%)`;

            document.getElementById('mSessionText').innerText = r.market_session_text;
            document.getElementById('mTargetDesc').innerText = r.is_intraday ? "测算今日收盘异动红线" : "测算下一个交易日异动红线";

            // 卡片动态标题
            const targetPeriod = r.is_intraday ? "今日收盘" : "下一交易日";
            document.getElementById('title3d').innerText = `3日普通异动 (${targetPeriod})`;
            document.getElementById('title10d').innerText = `10日严重异动 (${targetPeriod})`;
            document.getElementById('title30d').innerText = `30日严重异动 (${targetPeriod})`;

            const labelSuffix = r.is_intraday ? "(相对昨收)" : "(相对今日收盘)";
            document.getElementById('labelDaily3d').innerText = `${targetPeriod}涨幅红线${labelSuffix}:`;
            document.getElementById('labelDaily10d').innerText = `${targetPeriod}涨幅红线${labelSuffix}:`;
            document.getElementById('labelDaily30d').innerText = `${targetPeriod}涨幅红线${labelSuffix}:`;

            // 卡片数据填充
            renderCard('3d', r.normal_3d);
            renderCard('10d', r.severe_10d);
            renderCard('30d', r.severe_30d);

            // 未来N天表格
            const fTbody = document.getElementById('futureTbody');
            fTbody.innerHTML = '';
            r.future_projections.forEach(f => {
                const tr = document.createElement('tr');
                const warnHtml = f.will_trigger_if_limit_up ? '<span class="streak-alert">⚠️ 连板首次吃严重异动!</span>' : '-';
                tr.innerHTML = `
                    <td><strong>${f.target_date_label}</strong></td>
                    <td class="val-rise">${f.allowed_cum_rise_pct >= 0 ? '+' : ''}${f.allowed_cum_rise_pct.toFixed(2)}%</td>
                    <td><strong>${f.crit_price.toFixed(2)} 元</strong></td>
                    <td>${f.allowed_daily_rise_pct >= 0 ? '+' : ''}${f.allowed_daily_rise_pct.toFixed(2)}%/天</td>
                    <td>${f.limit_up_price.toFixed(2)} 元</td>
                    <td>${warnHtml}</td>
                `;
                fTbody.appendChild(tr);
            });

            // 历史明细
            const hTbody = document.getElementById('historyTbody');
            hTbody.innerHTML = '';
            r.history_bars.slice(-10).reverse().forEach(b => {
                const tr = document.createElement('tr');
                const sColor = b.stock_pct >= 0 ? 'val-rise' : 'val-fall';
                const iColor = b.index_pct >= 0 ? 'val-rise' : 'val-fall';
                const dColor = b.daily_dev >= 0 ? 'val-rise' : 'val-fall';
                const intradayBadge = b.is_intraday ? '<span class="badge-row-intraday">盘中实时</span>' : '';
                tr.innerHTML = `
                    <td>${b.date} ${intradayBadge}</td>
                    <td><strong>${b.stock_close.toFixed(2)} 元</strong></td>
                    <td class="${sColor}">${b.stock_pct >= 0 ? '+' : ''}${b.stock_pct.toFixed(2)}%</td>
                    <td>${b.index_close.toFixed(2)}</td>
                    <td class="${iColor}">${b.index_pct >= 0 ? '+' : ''}${b.index_pct.toFixed(2)}%</td>
                    <td class="${dColor}">${b.daily_dev >= 0 ? '+' : ''}${b.daily_dev.toFixed(2)}%</td>
                `;
                hTbody.appendChild(tr);
            });

            document.getElementById('metaStrip').style.display = 'grid';
            document.getElementById('cardsGrid').style.display = 'grid';
            document.getElementById('futureSection').style.display = 'block';
            document.getElementById('historySection').style.display = 'block';

            // K线图表渲染
            if (r.kline_chart_data && r.kline_chart_data.length > 0) {
                document.getElementById('klineSection').style.display = 'block';
                document.getElementById('klineCountLabel').innerText = `已载入 ${r.kline_chart_data.length} 个交易日走势`;
                initOrUpdateKLineChart(r.kline_chart_data, r.normal_3d.crit_price, r.severe_10d.crit_price);
            }
        }

        let klineChartInstance = null;
        let currentKLineDates = [];

        function calculateMA(dayCount, ohlc) {
            let result = [];
            for (let i = 0, len = ohlc.length; i < len; i++) {
                if (i < dayCount - 1) {
                    result.push('-');
                    continue;
                }
                let sum = 0;
                for (let j = 0; j < dayCount; j++) {
                    sum += ohlc[i - j][1];
                }
                result.push((sum / dayCount).toFixed(2));
            }
            return result;
        }

        function initOrUpdateKLineChart(rawData, crit3d, crit10d) {
            const chartDom = document.getElementById('klineChartContainer');
            if (!klineChartInstance) {
                klineChartInstance = echarts.init(chartDom);
                window.addEventListener('resize', () => klineChartInstance && klineChartInstance.resize());
            }

            currentKLineDates = rawData.map(item => item.date);
            const ohlc = rawData.map(item => [item.open, item.close, item.lowest, item.highest]);
            const volumes = rawData.map(item => item.volume);

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
                axisPointer: { link: [{ xAxisIndex: 'all' }] },
                grid: [
                    { left: '4%', right: '4%', top: '8%', height: '60%' },
                    { left: '4%', right: '4%', top: '74%', height: '18%' }
                ],
                xAxis: [
                    {
                        type: 'category',
                        data: currentKLineDates,
                        boundaryGap: true,
                        axisLine: { lineStyle: { color: '#334155' } },
                        axisLabel: { color: '#94a3b8' },
                        axisTick: { show: false },
                        splitLine: { show: false }
                    },
                    {
                        type: 'category',
                        gridIndex: 1,
                        data: currentKLineDates,
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
                    { type: 'inside', xAxisIndex: [0, 1], start: 80, end: 100 },
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
                        data: calculateMA(5, ohlc),
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1.5, color: '#f59e0b' }
                    },
                    {
                        name: 'MA10',
                        type: 'line',
                        data: calculateMA(10, ohlc),
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1.5, color: '#38bdf8' }
                    },
                    {
                        name: 'MA20',
                        type: 'line',
                        data: calculateMA(20, ohlc),
                        smooth: true,
                        showSymbol: false,
                        lineStyle: { width: 1.5, color: '#a855f7' }
                    },
                    {
                        name: 'MA30',
                        type: 'line',
                        data: calculateMA(30, ohlc),
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

            klineChartInstance.setOption(option);
        }

        function setKLineZoom(days) {
            document.querySelectorAll('.kline-filter-btn').forEach(b => b.classList.remove('active'));
            if (event && event.target && event.target.classList) {
                event.target.classList.add('active');
            }

            if (!klineChartInstance || currentKLineDates.length === 0) return;
            const total = currentKLineDates.length;
            let start = 0;
            if (days > 0 && days < total) {
                start = Math.max(0, Math.floor(((total - days) / total) * 100));
            }
            klineChartInstance.dispatchAction({
                type: 'dataZoom',
                start: start,
                end: 100
            });
        }

        function renderCard(prefix, d) {
            document.getElementById(`crit${prefix}`).innerText = `${d.crit_price.toFixed(2)} 元`;
            const riseSign = d.daily_rise_threshold_pct >= 0 ? '+' : '';
            document.getElementById(`dailyRise${prefix}`).innerText = `${riseSign}${d.daily_rise_threshold_pct.toFixed(2)}%`;
            
            const remSign = d.remaining_rise_from_realtime_pct >= 0 ? '+' : '';
            document.getElementById(`remain${prefix}`).innerText = `${remSign}${d.remaining_rise_from_realtime_pct.toFixed(2)}%`;

            const devSign = d.curr_realtime_deviation_pct >= 0 ? '+' : '';
            document.getElementById(`dev${prefix}`).innerText = `${devSign}${d.curr_realtime_deviation_pct.toFixed(2)}%`;

            const baseElem = document.getElementById(`baseDesc${prefix}`);
            if (baseElem) {
                baseElem.innerText = `基准起点: ${d.start_date} (收盘${d.base_stock_price.toFixed(2)}元)`;
            }

            document.getElementById(`status${prefix}`).innerText = d.status;
            const statusElem = document.getElementById(`status${prefix}`);
            if (d.status.includes("安全")) {
                statusElem.className = "status-safe";
            } else if (d.status.includes("预警")) {
                statusElem.className = "status-warn";
            } else {
                statusElem.className = "status-danger";
            }
        }

        window.onload = () => doQuery();
    </script>
</body>
</html>
"""

class AnomalyHTTPHandler(BaseHTTPRequestHandler):
    """处理 API 请求与静态 UI"""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        elif path == "/api/calculate":
            symbol = query.get("code", ["300059"])[0]
            days_str = query.get("days", ["5"])[0]
            index_chg_str = query.get("assume_index", ["0.0"])[0]
            mode_param = query.get("mode", ["auto"])[0]
            base_mode = query.get("base_mode", ["window_start"])[0]

            force_mode = None
            if mode_param == "intraday":
                force_mode = "intraday"
            elif mode_param == "post_market":
                force_mode = "post_market"

            try:
                days = int(days_str)
            except ValueError:
                days = 5

            try:
                index_chg = float(index_chg_str)
            except ValueError:
                index_chg = 0.0

            try:
                config, name, stock_klines, index_klines, is_intraday, is_mock = DataSource.get_stock_and_index_data(
                    symbol=symbol,
                    force_mode=force_mode
                )
                report = AnomalyCalculator.generate_full_report(
                    symbol=symbol,
                    stock_name=name,
                    config=config,
                    stock_klines=stock_klines,
                    index_klines=index_klines,
                    is_intraday=is_intraday,
                    future_days=days,
                    assume_index_change=index_chg,
                    base_mode=base_mode
                )
                payload = {
                    "success": True,
                    "is_mock": is_mock,
                    "report": asdict(report)
                }
            except Exception as e:
                payload = {
                    "success": False,
                    "error": str(e)
                }

            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def run_server(port: int = 8080):
    server = HTTPServer(("0.0.0.0", port), AnomalyHTTPHandler)
    print(f" Web 仪表盘服务已启动: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
