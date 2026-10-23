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

        /* 🎮 沙盘推演样式 */
        .sandtable-box { background: linear-gradient(180deg, #131c2e 0%, #0d1525 100%); border: 1px solid #293d66; border-radius: 12px; padding: 22px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.35); }
        .sandtable-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; border-bottom: 1px solid var(--border); padding-bottom: 14px; }
        .sandtable-title { font-size: 18px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }
        .sandtable-subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
        
        .sandtable-subpanel { background: rgba(10, 16, 29, 0.7); border: 1px solid var(--border); border-radius: 10px; padding: 18px; margin-bottom: 18px; }
        .subpanel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
        .subpanel-title { font-size: 15px; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 6px; }
        
        .sim-slider-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; background: rgba(255,255,255,0.02); padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.06); }
        .sim-slider-row label { font-size: 13px; color: var(--text-secondary); font-weight: 500; white-space: nowrap; }
        .sim-slider-row input[type="range"] { flex: 1; min-width: 140px; accent-color: #38bdf8; cursor: pointer; }
        .sim-val-display { font-size: 15px; font-weight: 700; color: #fff; background: #1a253c; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--border); min-width: 86px; text-align: center; }
        .sim-price-display { font-size: 14px; color: var(--amber); font-weight: 600; margin-left: 6px; }

        .sand-quick-btns { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
        .sand-quick-btn { background: #1a253c; border: 1px solid var(--border); color: #cbd5e1; font-size: 11px; padding: 3px 8px; border-radius: 4px; cursor: pointer; transition: all 0.15s; }
        .sand-quick-btn:hover { background: #2563eb; color: #fff; border-color: #3b82f6; }

        .reverse-matrix-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 12px; }
        .reverse-card { background: #0c1424; border: 1px solid var(--border); border-radius: 10px; padding: 14px; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.2s, border-color 0.2s; }
        .reverse-card:hover { transform: translateY(-2px); border-color: #38bdf8; }
        .reverse-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .reverse-card-title { font-size: 14px; font-weight: 700; color: #f8fafc; }
        .reverse-price-stat { font-size: 19px; font-weight: 800; color: #fff; margin-bottom: 2px; }
        .reverse-rise-stat { font-size: 13px; font-weight: 700; margin-bottom: 8px; }
        .reverse-desc { font-size: 11px; color: var(--text-secondary); line-height: 1.4; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px; }

        .badge-status-safe { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-status-control { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
        .badge-status-pressure { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }
        .badge-status-impossible { background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); }

        .streak-summary-banner { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 12px 16px; margin-top: 14px; font-size: 13px; display: flex; align-items: center; justify-content: space-between; }

        /* 🔍 股票输入下拉推荐面板与历史记录 */
        .stock-input-wrapper { position: relative; }
        .stock-dropdown {
            position: absolute;
            top: calc(100% + 6px);
            left: 0;
            right: 0;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.6);
            z-index: 1000;
            max-height: 280px;
            overflow-y: auto;
            display: none;
        }
        .dropdown-header {
            font-size: 11px;
            color: var(--text-secondary);
            padding: 8px 12px;
            background: #0a1120;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .dropdown-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 9px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            cursor: pointer;
            transition: background 0.15s;
        }
        .dropdown-item:hover {
            background: #1e293b;
        }
        .dropdown-item:last-child {
            border-bottom: none;
        }
        .dropdown-del-btn {
            color: #64748b;
            font-size: 12px;
            padding: 2px 6px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .dropdown-del-btn:hover {
            color: #f43f5e;
            background: rgba(244, 63, 94, 0.15);
        }

        @media (max-width: 900px) {
            .cards-grid { grid-template-columns: 1fr; }
            .control-panel { grid-template-columns: 1fr; }
            .meta-strip { grid-template-columns: 1fr 1fr; }
            .reverse-matrix-grid { grid-template-columns: 1fr; }
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
            <div class="form-group stock-input-wrapper">
                <label>股票代码 (记忆上次 & 智能推荐)</label>
                <input type="text" id="symbolInput" placeholder="输入代码或名称 如 000530, 冰山冷热" autocomplete="off" onfocus="showDropdown(this.value)" oninput="showDropdown(this.value)">
                <div id="stockDropdown" class="stock-dropdown"></div>
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
                <label>10日异动基准口径 (市场通行双口径)</label>
                <select id="baseModeSelect" onchange="onBaseModeChange(this.value)">
                    <option value="window_start" selected>🎯 炒股软件口径 (倒数第10天/区间首日，000530对应+4.85%)</option>
                    <option value="pre_window">📐 交易所严谨口径 (倒数第11天/前一日T-10，000530对应+7.48%)</option>
                </select>
            </div>
            <button class="btn-query" onclick="doQuery()">开始测算</button>

            <!-- 历史测算记录标签栏 -->
            <div class="quick-tags" id="historyTagsRow" style="display: none; margin-bottom: 2px;">
                <span class="quick-tag-label" style="color: #38bdf8; font-weight: 600;">🕒 历史测算:</span>
                <div id="historyTagsList" style="display: flex; gap: 6px; flex-wrap: wrap;"></div>
                <button class="tag-btn" onclick="clearAllHistory()" style="color: #94a3b8; font-size: 11px; padding: 2px 6px;">清空历史</button>
            </div>

            <!-- 快速填充常用股票标签 -->
            <div class="quick-tags">
                <span class="quick-tag-label">常用示例:</span>
                <button class="tag-btn" onclick="setQuick('000530')">冰山冷热 (000530)</button>
                <button class="tag-btn" onclick="setQuick('300059')">东方财富 (300059)</button>
                <button class="tag-btn" onclick="setQuick('300750')">宁德时代 (300750)</button>
                <button class="tag-btn" onclick="setQuick('600519')">贵州茅台 (600519)</button>
                <button class="tag-btn" onclick="setQuick('000001')">平安银行 (000001)</button>
                <button class="tag-btn" onclick="setQuick('002594')">比亚迪 (002594)</button>
                <button class="tag-btn" onclick="setQuick('688981')">中芯国际 (688981)</button>
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

        <!-- 🎮 异动推演沙盘 (主力控盘与连板推演) -->
        <div class="sandtable-box" id="sandtableSection" style="display: none;">
            <div class="sandtable-header">
                <div>
                    <div class="sandtable-title">
                        <span>🎮 异动推演沙盘 (主力控盘与连板空间推演)</span>
                        <span class="badge badge-live" style="background: rgba(168, 85, 247, 0.15); color: #c084fc; border-color: rgba(168, 85, 247, 0.3);">量化沙盘</span>
                    </div>
                    <div class="sandtable-subtitle">模拟设定控盘涨跌幅对未来连板空间的影响，并倒推若想未来连续涨停，今日允许的最高涨幅红线</div>
                </div>
                <div style="font-size: 12px; color: var(--text-secondary);">基于 10 日严重异动 (+100%) 监管红线</div>
            </div>

            <!-- 推演 A: 假设控盘逐日推演 -->
            <div class="sandtable-subpanel">
                <div class="subpanel-header">
                    <span class="subpanel-title">🎯 推演 A: 假设收盘涨幅 (What-If 控盘空间推演)</span>
                    <span style="font-size: 12px; color: var(--text-secondary);" id="sandTargetDayLabel">假设今日收盘走势:</span>
                </div>

                <div class="sim-slider-row">
                    <label id="simSliderLabel">设定今日收盘涨幅:</label>
                    <input type="range" id="simSlider" min="-10.0" max="10.0" step="0.1" value="0.0" oninput="onSimSliderInput(this.value)">
                    <div class="sim-val-display" id="simValDisplay">+0.00%</div>
                    <div class="sim-price-display">对应模拟收盘价: <strong id="simPriceDisplay">-- 元</strong></div>
                    <div class="sand-quick-btns">
                        <span style="font-size: 11px; color: var(--text-secondary);">快速定盘:</span>
                        <button class="sand-quick-btn" onclick="applySimRise('limit_down')">跌停板</button>
                        <button class="sand-quick-btn" onclick="applySimRise(-5.0)">-5.0%</button>
                        <button class="sand-quick-btn" onclick="applySimRise(-2.0)">-2.0%</button>
                        <button class="sand-quick-btn" onclick="applySimRise(0.0)">平盘 0.0%</button>
                        <button class="sand-quick-btn" onclick="applySimRise(2.0)">+2.0%</button>
                        <button class="sand-quick-btn" onclick="applySimRise(3.0)">+3.0%</button>
                        <button class="sand-quick-btn" onclick="applySimRise(4.0)">+4.0%</button>
                        <button class="sand-quick-btn" onclick="applySimRise('limit_up')">涨停板</button>
                    </div>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>预测交易日</th>
                            <th id="sandBaseHeader">基准基期</th>
                            <th>10日异动临界价</th>
                            <th>若天天涨停价格</th>
                            <th>能否连续涨停</th>
                            <th>单日最大允许涨幅</th>
                            <th>涨停安全边际空间</th>
                        </tr>
                    </thead>
                    <tbody id="sandWhatIfTbody"></tbody>
                </table>
            </div>

            <!-- 推演 B: 目标连板倒推矩阵 -->
            <div class="sandtable-subpanel">
                <div class="subpanel-header">
                    <span class="subpanel-title">🧮 推演 B: 目标连续涨停倒推矩阵 (主力控盘红线)</span>
                    <span style="font-size: 12px; color: var(--text-secondary);">倒推若想未来连续涨停，今日最高允许涨多少</span>
                </div>

                <div class="reverse-matrix-grid" id="reverseMatrixGrid">
                    <!-- 动态生成 1~5 连板卡片 -->
                </div>

                <div class="streak-summary-banner" id="streakSummaryBanner">
                    <span id="streakSummaryText">💡 极限控盘推演加载中...</span>
                    <span style="font-size: 12px; color: var(--text-secondary);">*根据交易所偏离度累计规则，跌停板以外的价格在A股无法撮合成交</span>
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
        const BUILTIN_STOCKS = [
            { symbol: "000530", name: "冰山冷热", market: "深市主板" },
            { symbol: "300059", name: "东方财富", market: "创业板" },
            { symbol: "300750", name: "宁德时代", market: "创业板" },
            { symbol: "600519", name: "贵州茅台", market: "沪市主板" },
            { symbol: "000001", name: "平安银行", market: "深市主板" },
            { symbol: "002594", name: "比亚迪", market: "深市主板" },
            { symbol: "688981", name: "中芯国际", market: "科创板" }
        ];

        function getHistoryList() {
            try {
                const raw = localStorage.getItem('stock_history_records');
                return raw ? JSON.parse(raw) : [];
            } catch (e) {
                return [];
            }
        }

        function saveToHistory(symbol, name, market) {
            if (!symbol) return;
            try {
                let list = getHistoryList();
                list = list.filter(item => item.symbol !== symbol);
                list.unshift({
                    symbol: symbol,
                    name: name || symbol,
                    market: market || "",
                    timestamp: Date.now()
                });
                if (list.length > 20) list = list.slice(0, 20);
                localStorage.setItem('stock_history_records', JSON.stringify(list));
                localStorage.setItem('stock_last_symbol', symbol);
                renderHistoryTags();
            } catch (e) {
                console.error("saveToHistory error:", e);
            }
        }

        function deleteHistory(event, symbol) {
            if (event) event.stopPropagation();
            try {
                let list = getHistoryList();
                list = list.filter(item => item.symbol !== symbol);
                localStorage.setItem('stock_history_records', JSON.stringify(list));
                
                const lastSym = localStorage.getItem('stock_last_symbol');
                if (lastSym === symbol) {
                    localStorage.setItem('stock_last_symbol', list.length > 0 ? list[0].symbol : '000530');
                }
                renderHistoryTags();
                showDropdown(document.getElementById('symbolInput').value);
            } catch (e) {
                console.error("deleteHistory error:", e);
            }
        }

        function clearAllHistory() {
            if (confirm("确定清空所有测算历史记录吗？")) {
                localStorage.removeItem('stock_history_records');
                renderHistoryTags();
                hideDropdown();
            }
        }

        function renderHistoryTags() {
            const list = getHistoryList();
            const row = document.getElementById('historyTagsRow');
            const container = document.getElementById('historyTagsList');
            if (!row || !container) return;

            if (list.length === 0) {
                row.style.display = 'none';
                container.innerHTML = '';
                return;
            }

            row.style.display = 'flex';
            container.innerHTML = '';
            list.slice(0, 8).forEach(item => {
                const btn = document.createElement('button');
                btn.className = 'tag-btn';
                btn.style.borderColor = 'rgba(56, 189, 248, 0.4)';
                btn.style.color = '#e0f2fe';
                btn.innerText = `${item.name} (${item.symbol})`;
                btn.onclick = () => setQuick(item.symbol);
                container.appendChild(btn);
            });
        }

        function hideDropdown() {
            const dd = document.getElementById('stockDropdown');
            if (dd) dd.style.display = 'none';
        }

        function showDropdown(filterVal) {
            const dd = document.getElementById('stockDropdown');
            if (!dd) return;

            const q = (filterVal || '').trim().toLowerCase();
            const historyList = getHistoryList();
            
            const seen = new Set();
            const merged = [];
            
            historyList.forEach(item => {
                seen.add(item.symbol);
                merged.push({ ...item, isHistory: true });
            });
            
            BUILTIN_STOCKS.forEach(item => {
                if (!seen.has(item.symbol)) {
                    seen.add(item.symbol);
                    merged.push({ ...item, isHistory: false });
                }
            });

            let matched = merged;
            if (q) {
                matched = merged.filter(item => 
                    item.symbol.toLowerCase().includes(q) || 
                    item.name.toLowerCase().includes(q)
                );
            }

            if (matched.length === 0) {
                dd.innerHTML = `<div style="padding: 12px; font-size: 13px; color: var(--text-secondary); text-align: center;">未找到匹配股票，输入 6 位代码直接测算</div>`;
                dd.style.display = 'block';
                return;
            }

            let html = `<div class="dropdown-header">
                <span>🕒 历史记录与推荐股票 (${matched.length})</span>
                <span style="font-size: 10px; color: #64748b;">支持代码/中文过滤</span>
            </div>`;

            matched.slice(0, 10).forEach(item => {
                const histTag = item.isHistory ? '<span style="font-size: 10px; color: #38bdf8; background: rgba(56,189,248,0.1); padding: 1px 4px; border-radius: 3px;">历史</span>' : '';
                const marketTag = item.market ? `<span class="rule-tag" style="font-size: 10px; padding: 1px 5px;">${item.market}</span>` : '';
                const delBtn = item.isHistory 
                    ? `<span class="dropdown-del-btn" onclick="deleteHistory(event, '${item.symbol}')" title="删除历史记录">✕</span>` 
                    : '';

                html += `
                    <div class="dropdown-item" onclick="selectStock('${item.symbol}')">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <strong style="color: #38bdf8; font-size: 13px;">${item.symbol}</strong>
                            <span style="color: #fff; font-size: 13px; font-weight: 500;">${item.name}</span>
                            ${marketTag}
                            ${histTag}
                        </div>
                        ${delBtn}
                    </div>
                `;
            });

            dd.innerHTML = html;
            dd.style.display = 'block';
        }

        function selectStock(code) {
            document.getElementById('symbolInput').value = code;
            hideDropdown();
            doQuery();
        }

        function setQuick(code) {
            document.getElementById('symbolInput').value = code;
            hideDropdown();
            doQuery();
        }

        async function doQuery() {
            hideDropdown();
            let code = document.getElementById('symbolInput').value.trim();
            if (!code) {
                code = localStorage.getItem('stock_last_symbol') || '000530';
                document.getElementById('symbolInput').value = code;
            }

            // 若用户输入中文名称，尝试自动匹配对应代码
            if (!/^\d{6}$/.test(code)) {
                const allList = [...getHistoryList(), ...BUILTIN_STOCKS];
                const found = allList.find(s => s.name === code || s.name.includes(code));
                if (found) {
                    code = found.symbol;
                    document.getElementById('symbolInput').value = code;
                }
            }

            const days = document.getElementById('daysInput').value.trim() || 5;
            const indexChg = document.getElementById('indexChgInput').value.trim() || 0.0;
            const mode = document.getElementById('modeSelect').value;
            const baseMode = document.getElementById('baseModeSelect').value;

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
            if (r && r.symbol) {
                saveToHistory(r.symbol, r.stock_name, r.market_name);
            }
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

            currentReportData = r;
            if (r.sandtable) {
                renderSandtable(r.sandtable, r);
            }

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
                const baseMode = document.getElementById('baseModeSelect').value;
                const modeLabel = baseMode === 'pre_window' ? '倒数第11天/前一日T-10' : '倒数第10天/区间首日';
                baseElem.innerText = `基准起点: ${d.start_date} (${modeLabel}, 收盘${d.base_stock_price.toFixed(2)}元)`;
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

        let currentReportData = null;
        let simDebounceTimer = null;

        function renderSandtable(st, r) {
            if (!st) return;
            document.getElementById('sandtableSection').style.display = 'block';

            const baseMode = document.getElementById('baseModeSelect').value;
            const thElem = document.getElementById('sandBaseHeader');
            if (thElem) {
                thElem.innerText = baseMode === 'pre_window' ? '基准日 (倒数第11天/前一日T-10)' : '基准日 (倒数第10天/区间首日)';
            }

            const targetLabel = r.is_intraday ? "今日" : "下一交易日";
            document.getElementById('sandTargetDayLabel').innerText = `假设${targetLabel}收盘走势推演:`;
            document.getElementById('simSliderLabel').innerText = `设定${targetLabel}收盘涨幅:`;

            const limit = r.price_limit_pct;
            const slider = document.getElementById('simSlider');
            slider.min = (-limit).toFixed(1);
            slider.max = limit.toFixed(1);
            slider.value = st.assumed_today_rise_pct;

            updateSimDisplay(st.assumed_today_rise_pct, st.assumed_today_price);
            renderWhatIfTable(st.what_if_steps);
            renderReverseMatrix(st.reverse_plans, targetLabel);

            const summaryElem = document.getElementById('streakSummaryText');
            if (st.max_sustainable_streak_days > 0) {
                summaryElem.innerHTML = `💡 <strong>控盘推演结论:</strong> 在跌停板(-${limit}%)以内极限控盘下，未来最多可维持【<strong>连续 ${st.max_sustainable_streak_days} 天涨停</strong>】；若想实现连续 ${st.max_sustainable_streak_days + 1} 连板在数学上不可能！`;
            } else {
                summaryElem.innerHTML = `💡 <strong>控盘推演结论:</strong> 即使${targetLabel}直接死死封死跌停(-${limit}%)，未来第 1 天涨停也无法避免严重异动！`;
            }
        }

        function updateSimDisplay(pct, price) {
            const sign = pct >= 0 ? '+' : '';
            const color = pct >= 0 ? 'var(--red)' : 'var(--green)';
            const valElem = document.getElementById('simValDisplay');
            valElem.style.color = color;
            valElem.innerText = `${sign}${Number(pct).toFixed(2)}%`;
            document.getElementById('simPriceDisplay').innerText = `${Number(price).toFixed(2)} 元`;
        }

        function renderWhatIfTable(steps) {
            const tbody = document.getElementById('sandWhatIfTbody');
            tbody.innerHTML = '';
            steps.forEach(s => {
                const tr = document.createElement('tr');
                const canUpBadge = s.can_limit_up 
                    ? `<span class="badge" style="background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3);">✅ 可以涨停</span>`
                    : `<span class="badge" style="background: rgba(244,63,94,0.15); color: #f43f5e; border: 1px solid rgba(244,63,94,0.3);">❌ 触碰异动</span>`;
                
                const bufColor = s.buffer_margin_pct >= 0 ? 'var(--green)' : 'var(--red)';
                const bufSign = s.buffer_margin_pct >= 0 ? '+' : '';

                tr.innerHTML = `
                    <td><strong>${s.date_label}</strong></td>
                    <td style="color: var(--text-secondary);">${s.base_date} (${s.base_price.toFixed(2)}元)</td>
                    <td><strong style="color: var(--amber);">${s.crit_price.toFixed(2)} 元</strong></td>
                    <td><strong>${s.streak_limit_up_price.toFixed(2)} 元</strong></td>
                    <td>${canUpBadge}</td>
                    <td class="val-rise">${s.max_allowed_rise_pct >= 0 ? '+' : ''}${s.max_allowed_rise_pct.toFixed(2)}%</td>
                    <td style="color: ${bufColor}; font-weight: 700;">${bufSign}${s.buffer_margin_pct.toFixed(2)}%</td>
                `;
                tbody.appendChild(tr);
            });
        }

        function renderReverseMatrix(plans, targetLabel) {
            const container = document.getElementById('reverseMatrixGrid');
            container.innerHTML = '';
            plans.forEach(p => {
                let badgeClass = 'badge-status-safe';
                let badgeText = '毫无法定压力';
                let riseColor = 'var(--green)';

                if (p.level_type === 'safe') {
                    badgeClass = 'badge-status-safe';
                    badgeText = '毫无压力 (涨停亦可)';
                    riseColor = 'var(--green)';
                } else if (p.level_type === 'control_green') {
                    badgeClass = 'badge-status-control';
                    badgeText = '可达成 (红盘控涨)';
                    riseColor = 'var(--blue)';
                } else if (p.level_type === 'pressure_red') {
                    badgeClass = 'badge-status-pressure';
                    badgeText = '须压盘收跌';
                    riseColor = 'var(--amber)';
                } else {
                    badgeClass = 'badge-status-impossible';
                    badgeText = '无法达成';
                    riseColor = 'var(--red)';
                }

                const card = document.createElement('div');
                card.className = 'reverse-card';
                card.innerHTML = `
                    <div>
                        <div class="reverse-card-head">
                            <span class="reverse-card-title">🎯 目标 ${p.target_streak_days} 连板</span>
                            <span class="badge ${badgeClass}">${badgeText}</span>
                        </div>
                        <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 2px;">${targetLabel}最高允许价:</div>
                        <div class="reverse-price-stat">≤ ${p.max_today_price.toFixed(2)} 元</div>
                        <div class="reverse-rise-stat" style="color: ${riseColor};">
                            ${targetLabel}允许涨幅: ≤ ${p.max_today_rise_pct >= 0 ? '+' : ''}${p.max_today_rise_pct.toFixed(2)}%
                        </div>
                        <div style="font-size: 12px; color: #cbd5e1; line-height: 1.4;">${p.action_advice}</div>
                    </div>
                    <div class="reverse-desc">
                        ⚠️ 瓶颈说明: ${p.bottleneck_desc}
                    </div>
                `;
                container.appendChild(card);
            });
        }

        function onSimSliderInput(val) {
            if (!currentReportData) return;
            const pPrev = currentReportData.confirmed_close;
            const price = pPrev * (1.0 + parseFloat(val) / 100.0);
            updateSimDisplay(val, price);

            clearTimeout(simDebounceTimer);
            simDebounceTimer = setTimeout(() => {
                fetchSimRise(val);
            }, 180);
        }

        function applySimRise(val) {
            if (!currentReportData) return;
            let targetVal = val;
            const limit = currentReportData.price_limit_pct;
            if (val === 'limit_up') targetVal = limit;
            else if (val === 'limit_down') targetVal = -limit;

            document.getElementById('simSlider').value = targetVal;
            const pPrev = currentReportData.confirmed_close;
            const price = pPrev * (1.0 + parseFloat(targetVal) / 100.0);
            updateSimDisplay(targetVal, price);
            fetchSimRise(targetVal);
        }

        async function fetchSimRise(val) {
            const code = document.getElementById('symbolInput').value.trim();
            const days = document.getElementById('daysInput').value.trim() || 5;
            const indexChg = document.getElementById('indexChgInput').value.trim() || 0.0;
            const mode = document.getElementById('modeSelect').value;
            const baseMode = document.getElementById('baseModeSelect').value;

            try {
                const resp = await fetch(`/api/calculate?code=${code}&days=${days}&assume_index=${indexChg}&mode=${mode}&base_mode=${baseMode}&sim_rise=${val}`);
                const data = await resp.json();
                if (data.success && data.report && data.report.sandtable) {
                    renderWhatIfTable(data.report.sandtable.what_if_steps);
                }
            } catch (e) {
                console.error("fetchSimRise failed:", e);
            }
        }

        function onBaseModeChange(val) {
            try {
                localStorage.setItem('stock_base_mode', val);
            } catch (e) {}
            doQuery();
        }

        window.onload = () => {
            // 恢复上次选择的基准口径 (默认炒股软件口径)
            try {
                const savedMode = localStorage.getItem('stock_base_mode');
                if (savedMode && document.getElementById('baseModeSelect')) {
                    document.getElementById('baseModeSelect').value = savedMode;
                }
            } catch (e) {}

            // 优先恢复上次测算的股票代码，无记录时默认 000530
            const lastCode = localStorage.getItem('stock_last_symbol') || '000530';
            const input = document.getElementById('symbolInput');
            if (input) {
                input.value = lastCode;
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        hideDropdown();
                        doQuery();
                    }
                });
            }

            // 点击页面外部区域时自动收起推荐下拉框
            document.addEventListener('click', (e) => {
                const dd = document.getElementById('stockDropdown');
                if (dd && !dd.contains(e.target) && e.target !== input) {
                    hideDropdown();
                }
            });

            // 渲染历史测算快捷标签
            renderHistoryTags();

            // 自动测算上次保存的代码
            doQuery();
        };
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
            sim_rise_param = query.get("sim_rise", [None])[0]
            sim_rise = None
            if sim_rise_param is not None and sim_rise_param != "":
                try:
                    sim_rise = float(sim_rise_param)
                except ValueError:
                    sim_rise = None

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
                    base_mode=base_mode,
                    assumed_today_rise_pct=sim_rise
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
