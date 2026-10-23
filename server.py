"""
A股异动监控系统 - 轻量级 Web 仪表盘与 REST API 服务 (原生内置库，零依赖)
"""
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datasource import DataSource
from calculator import AnomalyCalculator
from theme_sentiment import ThemeSentimentEngine
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

        /* 🗂️ 页面多板块导航系统 */
        .module-nav-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 22px; border-bottom: 1px solid var(--border); padding-bottom: 14px; flex-wrap: wrap; }
        .module-tab-btn { background: #131c2e; border: 1px solid var(--border); color: #94a3b8; padding: 10px 18px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 8px; }
        .module-tab-btn:hover { background: #1c2842; color: #fff; }
        .module-tab-btn.active { background: linear-gradient(135deg, rgba(2, 132, 199, 0.22), rgba(37, 99, 235, 0.22)); border-color: #38bdf8; color: #38bdf8; box-shadow: 0 0 15px rgba(56, 189, 248, 0.18); }
        .module-badge-plan { font-size: 10px; background: rgba(255,255,255,0.08); color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-weight: 500; }
        
        .module-pane { display: none; animation: fadeIn 0.25s ease-in-out; }
        .module-pane.active { display: block; }

        .module-placeholder-box { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 60px 30px; text-align: center; margin-top: 10px; }
        .placeholder-icon { font-size: 46px; margin-bottom: 16px; display: inline-block; }
        .placeholder-title { font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 10px; }
        .placeholder-desc { font-size: 14px; color: var(--text-secondary); max-width: 560px; margin: 0 auto 24px auto; line-height: 1.6; }

        /* 🔥 题材梯队与连板效应、断板亏钱效应样式 */
        .sentiment-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .sentiment-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; transition: all 0.2s; position: relative; overflow: hidden; }
        .sentiment-card:hover { border-color: rgba(56, 189, 248, 0.4); box-shadow: 0 4px 16px rgba(0,0,0,0.3); }
        .sentiment-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .sentiment-card-title { font-size: 13px; color: var(--text-secondary); font-weight: 600; display: flex; align-items: center; gap: 6px; }
        .sentiment-val-main { font-size: 26px; font-weight: 800; color: #fff; line-height: 1.1; margin-bottom: 6px; }
        .sentiment-sub-items { display: flex; gap: 14px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }
        .sentiment-sub-items b { color: #f8fafc; font-weight: 600; }

        .sentiment-compass-box { background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9)); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 20px 24px; margin-bottom: 24px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 20px; }
        .compass-score-wrapper { display: flex; align-items: center; gap: 18px; }
        .compass-score-circle { width: 72px; height: 72px; border-radius: 50%; background: radial-gradient(circle, rgba(56, 189, 248, 0.2) 0%, rgba(15, 23, 42, 0.8) 100%); border: 3px solid #38bdf8; display: flex; flex-direction: column; align-items: center; justify-content: center; font-weight: 800; color: #38bdf8; }
        .compass-score-val { font-size: 22px; line-height: 1; }
        .compass-score-unit { font-size: 10px; color: var(--text-secondary); margin-top: 2px; }
        .compass-cycle-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: 700; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); margin-bottom: 6px; }
        .compass-advice-text { font-size: 13px; color: #cbd5e1; max-width: 720px; line-height: 1.6; }

        .loss-summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-bottom: 20px; }
        .loss-summary-card { background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
        .loss-summary-title { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
        .loss-summary-val { font-size: 20px; font-weight: 800; }

        .ladder-pyramid { display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px; }
        .ladder-tier { background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
        .ladder-tier-label { min-width: 90px; font-size: 13px; font-weight: 700; color: #fbbf24; display: flex; align-items: center; gap: 6px; }
        .ladder-tier-stocks { display: flex; gap: 10px; flex-wrap: wrap; flex: 1; }
        .ladder-stock-pill { background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 8px; cursor: pointer; transition: all 0.15s; }
        .ladder-stock-pill:hover { border-color: #38bdf8; background: #24344d; transform: translateY(-1px); }

        .themes-matrix-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin-bottom: 24px; }
        .theme-cluster-card { background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
        .theme-cluster-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 8px; }
        .theme-cluster-title { font-size: 14px; font-weight: 700; color: #fff; }
        .theme-cluster-leader { font-size: 12px; color: #fbbf24; }
        .theme-stock-tags { display: flex; gap: 6px; flex-wrap: wrap; }
        .theme-mini-tag { font-size: 11px; padding: 3px 8px; border-radius: 4px; background: rgba(255,255,255,0.05); color: #cbd5e1; cursor: pointer; }
        .theme-mini-tag:hover { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }

        .badge-tag-slump { background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .badge-tag-rebound { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .badge-tag-neutral { background: rgba(148, 163, 184, 0.12); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.25); padding: 3px 8px; border-radius: 4px; font-size: 11px; }

        /* 弹窗：断板个股前后走势K线图 */
        .kline-modal-backdrop { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.78); backdrop-filter: blur(4px); z-index: 2000; align-items: center; justify-content: center; }
        .kline-modal-content { background: #131c2e; border: 1px solid #38bdf8; border-radius: 12px; width: 92%; max-width: 800px; box-shadow: 0 20px 50px rgba(0,0,0,0.85); padding: 22px 26px; animation: fadeIn 0.2s ease-in-out; }
        .kline-modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 14px; }

        /* 🎮 沙盘推演样式 */
        .sandtable-box { background: linear-gradient(180deg, #131c2e 0%, #0d1525 100%); border: 1px solid #293d66; border-radius: 12px; padding: 22px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.35); }
        .sandtable-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; border-bottom: 1px solid var(--border); padding-bottom: 14px; }
        .sandtable-title { font-size: 18px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }
        .sandtable-subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
        
        .sandtable-subpanel { background: rgba(10, 16, 29, 0.7); border: 1px solid var(--border); border-radius: 10px; padding: 18px; margin-bottom: 18px; }
        .subpanel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
        .subpanel-title { font-size: 15px; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 6px; }
        
        /* 🎮 沙盘精细输入与一键脱离推荐按钮 */
        .sand-control-container { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 14px 16px; margin-bottom: 16px; }
        .sand-inputs-bar { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; }
        .sand-input-group { display: flex; align-items: center; gap: 8px; }
        .sand-input-label { font-size: 13px; color: var(--text-secondary); font-weight: 500; white-space: nowrap; }
        .sand-input-unit-wrap { position: relative; display: flex; align-items: center; }
        .sand-input-unit-wrap input[type="number"] { width: 95px; background: #0c1424; border: 1px solid #334155; border-radius: 6px; padding: 7px 24px 7px 10px; font-size: 15px; font-weight: 700; color: #fff; outline: none; transition: border-color 0.2s; }
        .sand-input-unit-wrap input[type="number"]:focus { border-color: #38bdf8; }
        #simPriceInput { color: #fbbf24; }
        .sand-input-unit-wrap .unit-text { position: absolute; right: 8px; font-size: 12px; color: var(--text-secondary); pointer-events: none; }
        
        .sand-slider-group { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 140px; }
        .sand-slider-group input[type="range"] { flex: 1; accent-color: #38bdf8; cursor: pointer; }

        .btn-rec-safe { background: linear-gradient(135deg, #059669 0%, #0284c7 100%); color: #fff; border: none; border-radius: 6px; padding: 8px 16px; font-size: 13px; font-weight: 700; cursor: pointer; transition: all 0.2s; white-space: nowrap; box-shadow: 0 2px 8px rgba(2, 132, 199, 0.35); }
        .btn-rec-safe:hover { opacity: 0.92; transform: translateY(-1px); }

        .sand-quick-row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); }

        .rec-advice-card { background: rgba(56, 189, 248, 0.06); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 12px 14px; margin-top: 12px; animation: fadeIn 0.2s ease-in-out; }
        .rec-advice-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
        .rec-advice-content { font-size: 13px; color: #e2e8f0; line-height: 1.5; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

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

        <!-- 🗂️ 页面业务板块导航栏 (支持后续无缝扩展新业务模块) -->
        <nav class="module-nav-bar" id="moduleNavBar">
            <button class="module-tab-btn active" id="tab-anomaly" onclick="switchModule('anomaly')">
                <span>📈 异动监控与推演沙盘</span>
            </button>
            <button class="module-tab-btn" id="tab-chips" onclick="switchModule('chips')">
                <span>💼 主力筹码与盘口监测</span>
                <span class="module-badge-plan">规划中</span>
            </button>
            <button class="module-tab-btn" id="tab-themes" onclick="switchModule('themes')">
                <span>🔥 题材梯队与连板效应</span>
                <span style="font-size: 10px; background: rgba(244, 63, 94, 0.2); color: #f43f5e; padding: 2px 6px; border-radius: 4px; font-weight: 600;">NEW 连板断板回测</span>
            </button>
            <button class="module-tab-btn" id="tab-backtest" onclick="switchModule('backtest')">
                <span>⚙️ 策略回测与预警中心</span>
                <span class="module-badge-plan">规划中</span>
            </button>
        </nav>

        <!-- ==================== 板块1: 异动监控与推演沙盘 (当前独立业务板块) ==================== -->
        <div class="module-pane active" id="module-anomaly">

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
                <label>假定未来指数日涨幅 (%) <span style="font-size: 11px; color: var(--text-secondary); font-weight: normal;">(输入0.1即+0.1%)</span></label>
                <div style="position: relative; display: flex; align-items: center;">
                    <input type="number" id="indexChgInput" value="0.0" step="0.1" placeholder="如 0.1 代表 +0.1%" onchange="doQuery()" style="padding-right: 28px;">
                    <span style="position: absolute; right: 10px; font-size: 13px; color: var(--text-secondary); pointer-events: none;">%</span>
                </div>
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
                    <span class="subpanel-title">🎯 推演 A: 假设收盘涨幅与价格 (What-If 控盘空间推演)</span>
                    <span style="font-size: 12px; color: var(--text-secondary);" id="sandTargetDayLabel">假设今日收盘走势:</span>
                </div>

                <!-- 精细输入与一键脱离异动推荐区 -->
                <div class="sand-control-container">
                    <div class="sand-inputs-bar">
                        <!-- 直接输入价格 -->
                        <div class="sand-input-group">
                            <label class="sand-input-label" id="labelPriceInput">💰 直接输入价格:</label>
                            <div class="sand-input-unit-wrap">
                                <input type="number" id="simPriceInput" step="0.01" placeholder="如 9.80" oninput="onDirectPriceInput(this.value)">
                                <span class="unit-text">元</span>
                            </div>
                        </div>

                        <!-- 直接输入涨跌幅 -->
                        <div class="sand-input-group">
                            <label class="sand-input-label" id="labelPctInput">📈 对应涨跌幅:</label>
                            <div class="sand-input-unit-wrap">
                                <input type="number" id="simPctInput" step="0.01" placeholder="如 3.25" oninput="onDirectPctInput(this.value)">
                                <span class="unit-text">%</span>
                            </div>
                        </div>

                        <!-- 辅助滑块微调 -->
                        <div class="sand-slider-group">
                            <label class="sand-input-label">微调:</label>
                            <input type="range" id="simSlider" min="-10.0" max="10.0" step="0.1" value="0.0" oninput="onSimSliderInput(this.value)">
                        </div>

                        <!-- ⚡ 一键测算下一日脱离异动按钮 -->
                        <button class="btn-rec-safe" onclick="calculateNextDaySafePrice()" title="一键计算明日拉板或脱离异动的推荐价格">
                            ⚡ 一键测算：下一日脱离异动推荐价
                        </button>
                    </div>

                    <!-- 快速定盘快捷按钮 -->
                    <div class="sand-quick-row">
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

                    <!-- 推荐脱离异动控盘分析卡片 -->
                    <div class="rec-advice-card" id="recAdviceCard" style="display: none;">
                        <div class="rec-advice-header">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-size: 14px; font-weight: 700; color: #38bdf8;">🎯 下一日脱离异动·推荐控盘参考</span>
                                <span id="recAdviceBadge" class="badge badge-status-safe">脱离异动安全区</span>
                            </div>
                            <span style="font-size: 11px; color: var(--text-secondary);">*已自动为您填入并刷新下方推演表</span>
                        </div>
                        <div class="rec-advice-content" id="recAdviceContent"></div>
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
        </div><!-- ==================== /板块1: 异动监控与推演沙盘 ==================== -->

        <!-- ==================== 板块2: 主力筹码与盘口监测 (预留扩展位) ==================== -->
        <div class="module-pane" id="module-chips">
            <div class="module-placeholder-box">
                <div class="placeholder-icon">💼</div>
                <div class="placeholder-title">主力筹码与盘口监测板块</div>
                <div class="placeholder-desc">该板块已预留扩展接口。未来将提供筹码分布峰值、主力大单净流入追踪、分时量比突异、盘口挂单博弈等全维度盘口监控功能。</div>
                <button class="btn btn-secondary" onclick="switchModule('anomaly')" style="display: inline-flex; margin: 0 auto;">← 返回异动推演沙盘</button>
            </div>
        </div>

        <!-- ==================== 板块3: 题材梯队与连板效应 (连板统计 & 断板亏钱效应回测) ==================== -->
        <div class="module-pane" id="module-themes">
            <!-- 顶部控制栏与回测条件配置 -->
            <div class="sandtable-box" style="margin-bottom: 20px;">
                <div class="sandtable-header">
                    <div>
                        <div class="sandtable-title">🔥 题材梯队与连板效应 · 断板亏钱效应回测罗盘</div>
                        <div class="sandtable-subtitle">连板天梯分布 | 题材热度扩散 | 连板断板亏钱效应量化回测 (T日大面、T+1竞价溢价与次日修复) | 超短六大核心情绪周期</div>
                    </div>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <button class="btn btn-primary" onclick="doQueryThemeSentiment()" id="btnQueryTheme">⚡ 刷新/开始回测</button>
                    </div>
                </div>

                <div class="control-panel" style="margin-bottom: 0;">
                    <div class="form-group">
                        <label>基准复盘交易日 (支持历史穿梭复盘)</label>
                        <select id="themeDateSelect" onchange="doQueryThemeSentiment()">
                            <option value="">载入交易日历中...</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>断板回测时间跨度 (交易日天数)</label>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <input type="number" id="themeDaysInput" value="5" min="1" max="30" style="flex: 1;" onchange="doQueryThemeSentiment()">
                            <button type="button" class="kline-filter-btn active" id="btnDays5" onclick="setThemeDays(5)">近5日(1周)</button>
                            <button type="button" class="kline-filter-btn" id="btnDays10" onclick="setThemeDays(10)">近10日(2周)</button>
                            <button type="button" class="kline-filter-btn" id="btnDays20" onclick="setThemeDays(20)">近20日(1月)</button>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>断板高度筛选 (晋级失败阶段)</label>
                        <select id="themeHeightSelect" onchange="doQueryThemeSentiment()">
                            <option value="all">⚡ 全部连板断板 (2板及以上)</option>
                            <option value="2_to_3">2进3 断板 (二板接力分水岭)</option>
                            <option value="3_to_4" selected>🎯 3进4 断板 (中位股分歧核心)</option>
                            <option value="4_to_5">4进5 断板 (中高标拓展期)</option>
                            <option value="high_5_plus">5板及以上断板 (高标特停/核按钮)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>断板走势日K范围设置 (统一设置前后跨度)</label>
                        <div style="display: flex; gap: 6px; align-items: center;">
                            <span style="font-size: 12px; color: var(--text-secondary); white-space: nowrap;">前:</span>
                            <select id="themePreDaysSelect" onchange="doQueryThemeSentiment()" style="flex: 1;">
                                <option value="3">前 3 天</option>
                                <option value="4" selected>前 4 天 (默认)</option>
                                <option value="5">前 5 天</option>
                                <option value="7">前 7 天</option>
                            </select>
                            <span style="font-size: 12px; color: var(--text-secondary); white-space: nowrap;">至 后:</span>
                            <select id="themePostDaysSelect" onchange="doQueryThemeSentiment()" style="flex: 1;">
                                <option value="3">后 3 天</option>
                                <option value="5" selected>后 5 天 (默认)</option>
                                <option value="7">后 7 天</option>
                                <option value="10">后 10 天</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 超短情绪罗盘与情绪周期定性 -->
            <div class="sentiment-compass-box" id="sentimentCompassBox">
                <div class="compass-score-wrapper">
                    <div class="compass-score-circle">
                        <div class="compass-score-val" id="smScore">--</div>
                        <div class="compass-score-unit">情绪分值</div>
                    </div>
                    <div>
                        <div class="compass-cycle-badge" id="smCycleBadge">
                            <span>🧭</span> <span id="smCycle">计算中...</span>
                        </div>
                        <div class="compass-advice-text" id="smAdvice">正在获取全市场超短打板情绪、梯队与亏钱效应数据...</div>
                    </div>
                </div>
                <div style="text-align: right; font-size: 12px; color: var(--text-secondary);">
                    <div>市场空间板: <b style="color: #fbbf24; font-size: 15px;" id="smMaxHeightStock">--</b></div>
                    <div style="margin-top: 4px;">连板家数: <b style="color: #38bdf8;" id="smLadderCount">--</b> 家 / 首板: <b style="color: #cbd5e1;" id="smFirstCount">--</b> 家</div>
                </div>
            </div>

            <!-- 超短线六大核心专业情绪指标卡片 -->
            <div class="sentiment-grid">
                <div class="sentiment-card">
                    <div class="sentiment-card-header">
                        <div class="sentiment-card-title">🏆 空间高度与梯队广度</div>
                        <span class="badge" style="background: rgba(251, 191, 36, 0.15); color: #fbbf24;">高度压制</span>
                    </div>
                    <div class="sentiment-val-main" id="cardMaxHeight">-- 板</div>
                    <div class="sentiment-sub-items">
                        <span>最高龙头: <b id="cardMaxLeader" style="color: #fbbf24;">--</b></span>
                        <span>连板家数: <b id="cardLadderTotal">--</b></span>
                        <span>涨停总数: <b id="cardZtTotal">--</b></span>
                    </div>
                </div>

                <div class="sentiment-card">
                    <div class="sentiment-card-header">
                        <div class="sentiment-card-title">🪜 梯队晋级率矩阵</div>
                        <span class="badge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8;">接力意愿</span>
                    </div>
                    <div class="sentiment-val-main" id="cardPromSummary">--%</div>
                    <div class="sentiment-sub-items">
                        <span>1进2: <b id="cardProm12">--%</b></span>
                        <span>2进3: <b id="cardProm23">--%</b></span>
                        <span>3进4: <b id="cardProm34">--%</b></span>
                        <span>高位(4+): <b id="cardPromHigh">--%</b></span>
                    </div>
                </div>

                <div class="sentiment-card">
                    <div class="sentiment-card-header">
                        <div class="sentiment-card-title">⚠️ 炸板率与分歧警报</div>
                        <span class="badge" id="cardBreakBadge" style="background: rgba(244, 63, 94, 0.15); color: #f43f5e;">分歧监测</span>
                    </div>
                    <div class="sentiment-val-main" id="cardBreakRate">--%</div>
                    <div class="sentiment-sub-items">
                        <span>封死涨停: <b id="cardZtCount" style="color: #10b981;">--</b> 家</span>
                        <span>触板炸板: <b id="cardZbCount" style="color: #f43f5e;">--</b> 家</span>
                        <span>炸板风险: <b id="cardBreakLevel">正常</b></span>
                    </div>
                </div>

                <div class="sentiment-card">
                    <div class="sentiment-card-header">
                        <div class="sentiment-card-title">💰 昨涨停今日赚钱效应</div>
                        <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981;">打板收益</span>
                    </div>
                    <div class="sentiment-val-main" id="cardYztReturn">--%</div>
                    <div class="sentiment-sub-items">
                        <span>昨涨停平均涨幅: <b id="cardYztAvg">--%</b></span>
                        <span>今日上涨胜率: <b id="cardYztUpRate">--%</b></span>
                    </div>
                </div>

                <div class="sentiment-card">
                    <div class="sentiment-card-header">
                        <div class="sentiment-card-title">🩸 跌停家数与极端亏钱</div>
                        <span class="badge" style="background: rgba(244, 63, 94, 0.15); color: #f43f5e;">恐慌指数</span>
                    </div>
                    <div class="sentiment-val-main" id="cardDtCount">-- 家</div>
                    <div class="sentiment-sub-items">
                        <span>跌停数量: <b id="cardDtNum" style="color: #f43f5e;">--</b> 家</span>
                        <span>核按钮风偏: <b id="cardDtDesc">--</b></span>
                    </div>
                </div>

                <div class="sentiment-card">
                    <div class="sentiment-card-header">
                        <div class="sentiment-card-title">🧭 超短综合情绪评分</div>
                        <span class="badge" style="background: rgba(168, 85, 247, 0.15); color: #a855f7;">多因子加权</span>
                    </div>
                    <div class="sentiment-val-main" id="cardScore">-- / 100</div>
                    <div class="sentiment-sub-items">
                        <span>所处周期: <b id="cardCycleText" style="color: #38bdf8;">--</b></span>
                        <span>短线做多安全度: <b id="cardSafetyText">--</b></span>
                    </div>
                </div>
            </div>

            <!-- 💥 连板断板亏钱效应量化回测分析区 (核心诉求) -->
            <div class="section-box" id="lossEffectSection">
                <div class="section-title">
                    <span>💥 连板断板亏钱效应量化回测分析 (<span id="lossFilterTitle">近5日 3进4断板</span>)</span>
                    <span style="font-size: 12px; color: var(--text-secondary); font-weight: normal;">统计连板冲击失败当日回撤幅度、次日(T+1)竞价溢价、次日收盘涨跌及隔日(T+2)修复表现</span>
                </div>

                <!-- 亏钱效应汇总指标 -->
                <div class="loss-summary-grid">
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">🎯 断板样本总数</div>
                        <div class="loss-summary-val" id="lossTotalSamples">0 <span style="font-size: 13px; font-weight: normal;">只</span></div>
                    </div>
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">📉 断板日(T日)平均涨跌幅</div>
                        <div class="loss-summary-val" id="lossT0AvgPct">0.00%</div>
                    </div>
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">💥 断板日炸板大面均值</div>
                        <div class="loss-summary-val" id="lossT0AvgDrop" style="color: #f43f5e;">0.00%</div>
                    </div>
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">🩸 断板日收阴率 / 跌停率</div>
                        <div class="loss-summary-val" id="lossT0NegRate">0.0% / 0.0%</div>
                    </div>
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">🌅 次日(T+1)竞价平均溢价</div>
                        <div class="loss-summary-val" id="lossT1AvgGap">0.00%</div>
                    </div>
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">💔 次日(T+1)收盘平均涨跌</div>
                        <div class="loss-summary-val" id="lossT1AvgClose">0.00%</div>
                    </div>
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">🩹 次日大面率 vs 反包率</div>
                        <div class="loss-summary-val" id="lossT1SlumpVsRebound">0.0% vs 0.0%</div>
                    </div>
                    <div class="loss-summary-card">
                        <div class="loss-summary-title">📊 断板后2日累积收益率</div>
                        <div class="loss-summary-val" id="lossCum2dAvg">0.00%</div>
                    </div>
                </div>

                <!-- 断板明细流水表 -->
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>股票代码 / 名称</th>
                                <th>所属题材概念</th>
                                <th>断板阶段</th>
                                <th>断板交易日 (T日)</th>
                                <th>断板日收盘涨跌</th>
                                <th>断板日大面幅(%)</th>
                                <th>断板日前后日K走势 (点击放大)</th>
                                <th>断板日振幅</th>
                                <th>T+1日竞价溢价</th>
                                <th>T+1日收盘涨跌</th>
                                <th>T+2日累积表现</th>
                                <th>情绪分类标签</th>
                                <th>快捷联动</th>
                            </tr>
                        </thead>
                        <tbody id="brokenBoardTbody">
                            <tr>
                                <td colspan="12" style="text-align: center; color: var(--text-secondary); padding: 24px;">点击「⚡ 刷新/开始回测」载入断板亏钱效应数据</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- 🪜 连板梯队天梯榜 (Ladder Pyramid) -->
            <div class="section-box">
                <div class="section-title">
                    <span>🪜 当日连板梯队天梯分布图 (<span id="ladderDateTitle">最新交易日</span>)</span>
                    <span style="font-size: 12px; color: var(--text-secondary); font-weight: normal;">按连板高度从高到低排列，清晰定位空间龙与梯队接力</span>
                </div>
                <div class="ladder-pyramid" id="ladderPyramidContainer">
                    <div style="text-align: center; color: var(--text-secondary); padding: 20px;">载入梯队数据中...</div>
                </div>
            </div>

            <!-- 🔥 题材主线热度分布 (Hot Themes Breakdown) -->
            <div class="section-box">
                <div class="section-title">
                    <span>🔥 题材板块主线热度扩散矩阵</span>
                    <span style="font-size: 12px; color: var(--text-secondary); font-weight: normal;">按涨停梯队与涨停家数智能聚类，锁定全市场最具赚钱效应的做多主线</span>
                </div>
                <div class="themes-matrix-grid" id="themesMatrixContainer">
                    <div style="text-align: center; color: var(--text-secondary); padding: 20px;">载入题材数据中...</div>
                </div>
            </div>

            <!-- 弹窗：断板个股前后日K走势高清大图与明细 -->
            <div id="klineModal" class="kline-modal-backdrop" onclick="closeKLineModal()">
                <div class="kline-modal-content" onclick="event.stopPropagation()">
                    <div class="kline-modal-header">
                        <div>
                            <div style="font-size: 16px; font-weight: 700; color: #fff;" id="modalStockTitle">断板前后日K走势明细</div>
                            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;" id="modalStockSubtitle">金黄色高亮蜡烛为断板日，不足5日交易日已自然截止</div>
                        </div>
                        <button class="kline-filter-btn" onclick="closeKLineModal()" style="font-size: 12px; padding: 4px 10px;">✖ 关闭</button>
                    </div>
                    <div id="modalSvgContainer" style="padding: 10px 0; text-align: center;"></div>
                    <div style="overflow-x: auto; max-height: 220px; border: 1px solid var(--border); border-radius: 8px;">
                        <table style="font-size: 12px; margin-bottom: 0;">
                            <thead>
                                <tr>
                                    <th>交易日期</th>
                                    <th>定位阶段</th>
                                    <th>开盘价</th>
                                    <th>收盘价</th>
                                    <th>最高价</th>
                                    <th>最低价</th>
                                    <th>当日涨跌幅</th>
                                </tr>
                            </thead>
                            <tbody id="modalKLineTbody"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div><!-- ==================== /板块3: 题材梯队与连板效应 ==================== -->

        <!-- ==================== 板块4: 策略回测与预警中心 (预留扩展位) ==================== -->
        <div class="module-pane" id="module-backtest">
            <div class="module-placeholder-box">
                <div class="placeholder-icon">⚙️</div>
                <div class="placeholder-title">策略回测与预警中心板块</div>
                <div class="placeholder-desc">该板块已预留扩展接口。未来将支持基于异动卡位规则的历史战法回测、全市场实时异动触发声光预警推送及自定义飞书/微信机器人Webhook对接。</div>
                <button class="btn btn-secondary" onclick="switchModule('anomaly')" style="display: inline-flex; margin: 0 auto;">← 返回异动推演沙盘</button>
            </div>
        </div>
    </div>

    <script>
        // 🗂️ 页面多板块切换控制与视图自适应
        function switchModule(moduleId) {
            const modules = ['anomaly', 'chips', 'themes', 'backtest'];
            if (!modules.includes(moduleId)) {
                moduleId = 'anomaly';
            }
            
            modules.forEach(m => {
                const tabBtn = document.getElementById(`tab-${m}`);
                const pane = document.getElementById(`module-${m}`);
                if (tabBtn) {
                    if (m === moduleId) {
                        tabBtn.classList.add('active');
                    } else {
                        tabBtn.classList.remove('active');
                    }
                }
                if (pane) {
                    if (m === moduleId) {
                        pane.classList.add('active');
                    } else {
                        pane.classList.remove('active');
                    }
                }
            });

            try {
                localStorage.setItem('stock_active_module', moduleId);
            } catch (e) {}

            // 若切回异动监控与沙盘推演板块，且K线图表已初始化，触发resize避免容器宽度折叠
            if (moduleId === 'anomaly' && klineChartInstance) {
                setTimeout(() => {
                    if (klineChartInstance) {
                        klineChartInstance.resize();
                    }
                }, 80);
            }

            // 若切换到题材梯队与连板效应板块，且尚未载入数据，自动触发查询
            if (moduleId === 'themes' && !window._themeSentimentLoaded) {
                doQueryThemeSentiment();
            }
        }

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
            if (!/^[0-9]{6}$/.test(code)) {
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
            if (document.getElementById('labelPriceInput')) {
                document.getElementById('labelPriceInput').innerText = `💰 设定${targetLabel}收盘价:`;
            }
            if (document.getElementById('labelPctInput')) {
                document.getElementById('labelPctInput').innerText = `📈 对应${targetLabel}涨幅:`;
            }

            const limit = r.price_limit_pct;
            const slider = document.getElementById('simSlider');
            if (slider) {
                slider.min = (-limit).toFixed(1);
                slider.max = limit.toFixed(1);
                slider.value = st.assumed_today_rise_pct;
            }

            updateSimInputs(st.assumed_today_rise_pct, st.assumed_today_price);
            renderWhatIfTable(st.what_if_steps);
            renderReverseMatrix(st.reverse_plans, targetLabel);

            const summaryElem = document.getElementById('streakSummaryText');
            if (st.max_sustainable_streak_days > 0) {
                summaryElem.innerHTML = `💡 <strong>控盘推演结论:</strong> 在跌停板(-${limit}%)以内极限控盘下，未来最多可维持【<strong>连续 ${st.max_sustainable_streak_days} 天涨停</strong>】；若想实现连续 ${st.max_sustainable_streak_days + 1} 连板在数学上不可能！`;
            } else {
                summaryElem.innerHTML = `💡 <strong>控盘推演结论:</strong> 即使${targetLabel}直接死死封死跌停(-${limit}%)，未来第 1 天涨停也无法避免严重异动！`;
            }
        }

        function updateSimInputs(pct, price) {
            const pInput = document.getElementById('simPriceInput');
            const rInput = document.getElementById('simPctInput');
            const slider = document.getElementById('simSlider');

            if (pInput && document.activeElement !== pInput) {
                pInput.value = Number(price).toFixed(2);
            }
            if (rInput && document.activeElement !== rInput) {
                const numPct = Number(pct);
                rInput.value = numPct.toFixed(2);
                rInput.style.color = numPct >= 0 ? 'var(--red)' : 'var(--green)';
            }
            if (slider) slider.value = Number(pct).toFixed(1);
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

        function onDirectPriceInput(val) {
            if (!currentReportData) return;
            const price = parseFloat(val);
            if (isNaN(price) || price <= 0) return;

            const pPrev = currentReportData.confirmed_close;
            const pct = ((price / pPrev) - 1.0) * 100.0;

            const rInput = document.getElementById('simPctInput');
            if (rInput && document.activeElement !== rInput) {
                rInput.value = pct.toFixed(2);
                rInput.style.color = pct >= 0 ? 'var(--red)' : 'var(--green)';
            }
            const slider = document.getElementById('simSlider');
            if (slider) slider.value = pct.toFixed(1);

            clearTimeout(simDebounceTimer);
            simDebounceTimer = setTimeout(() => {
                fetchSimRise(pct);
            }, 180);
        }

        function onDirectPctInput(val) {
            if (!currentReportData) return;
            const pct = parseFloat(val);
            if (isNaN(pct)) return;

            const pPrev = currentReportData.confirmed_close;
            const price = pPrev * (1.0 + pct / 100.0);

            const pInput = document.getElementById('simPriceInput');
            if (pInput && document.activeElement !== pInput) {
                pInput.value = price.toFixed(2);
            }
            const rInput = document.getElementById('simPctInput');
            if (rInput) {
                rInput.style.color = pct >= 0 ? 'var(--red)' : 'var(--green)';
            }
            const slider = document.getElementById('simSlider');
            if (slider) slider.value = pct.toFixed(1);

            clearTimeout(simDebounceTimer);
            simDebounceTimer = setTimeout(() => {
                fetchSimRise(pct);
            }, 180);
        }

        function onSimSliderInput(val) {
            if (!currentReportData) return;
            const pct = parseFloat(val);
            const pPrev = currentReportData.confirmed_close;
            const price = pPrev * (1.0 + pct / 100.0);
            updateSimInputs(pct, price);

            clearTimeout(simDebounceTimer);
            simDebounceTimer = setTimeout(() => {
                fetchSimRise(pct);
            }, 180);
        }

        function applySimRise(val) {
            if (!currentReportData) return;
            let targetVal = val;
            const limit = currentReportData.price_limit_pct;
            if (val === 'limit_up') targetVal = limit;
            else if (val === 'limit_down') targetVal = -limit;

            const pPrev = currentReportData.confirmed_close;
            const price = pPrev * (1.0 + parseFloat(targetVal) / 100.0);
            updateSimInputs(targetVal, price);
            fetchSimRise(targetVal);
        }

        function calculateNextDaySafePrice() {
            if (!currentReportData || !currentReportData.sandtable) return;
            const r = currentReportData;
            const st = r.sandtable;
            const pPrev = r.confirmed_close;
            const limitRate = r.price_limit_pct / 100.0;
            const targetLabel = r.is_intraday ? "今日" : "下一交易日";
            const nextDayLabel = r.is_intraday ? "明日 (T+1)" : "下下交易日 (T+2)";

            const plan1 = st.reverse_plans && st.reverse_plans.length > 0 ? st.reverse_plans[0] : null;
            const step1 = st.what_if_steps && st.what_if_steps.length > 0 ? st.what_if_steps[0] : null;
            if (!plan1 || !step1) return;

            const pRec = plan1.max_today_price;
            const rRec = plan1.max_today_rise_pct;
            const critToday = r.severe_10d.crit_price;
            const critTomorrow = step1.crit_price;
            const streakTomorrow = Number((pRec * (1.0 + limitRate)).toFixed(2));
            const bufferMargin = Number((critTomorrow - streakTomorrow).toFixed(2));
            const bufferPct = Number(((bufferMargin / pRec) * 100.0).toFixed(2));

            updateSimInputs(rRec, pRec);
            fetchSimRise(rRec);

            const card = document.getElementById('recAdviceCard');
            const badge = document.getElementById('recAdviceBadge');
            const content = document.getElementById('recAdviceContent');

            if (card && badge && content) {
                card.style.display = 'block';

                if (plan1.level_type === 'safe') {
                    badge.className = 'badge badge-status-safe';
                    badge.innerText = '毫无法定压力';
                } else if (plan1.level_type === 'control_green') {
                    badge.className = 'badge badge-status-control';
                    badge.innerText = '可达成 (红盘控涨)';
                } else if (plan1.level_type === 'pressure_red') {
                    badge.className = 'badge badge-status-pressure';
                    badge.innerText = '须压盘收跌';
                } else {
                    badge.className = 'badge badge-status-impossible';
                    badge.innerText = '无法达成';
                }

                const riseColor = rRec >= 0 ? 'var(--red)' : 'var(--green)';
                const sign = rRec >= 0 ? '+' : '';

                let adviceDetails = '';
                if (plan1.is_achievable) {
                    adviceDetails = `
                        💡 <strong>测算逻辑与参考：</strong>
                        若${targetLabel}收盘控制在 <strong>${pRec.toFixed(2)} 元</strong>（涨跌幅 <strong>${sign}${rRec.toFixed(2)}%</strong>）以内：
                        <br/>
                        1. ${targetLabel}收盘严格处于 10 日异动红线（${critToday.toFixed(2)} 元）下方，${targetLabel}不吃异动；
                        <br/>
                        2. ${nextDayLabel}即便封死涨停（涨停价 <strong>${streakTomorrow.toFixed(2)} 元</strong>），依然低于${nextDayLabel} 10 日异动红线（<strong>${critTomorrow.toFixed(2)} 元</strong>），留有 <strong>${bufferMargin.toFixed(2)} 元 (+${bufferPct.toFixed(2)}%)</strong> 的安全边际空间，可确保完全脱离严重异动风险！
                    `;
                } else {
                    adviceDetails = `
                        ⚠️ <strong>测算结论：</strong> 当前个股前期累计涨幅过大，即使${targetLabel}封死跌停板，${nextDayLabel}也无法脱离异动。建议等待后续交易日基期抬升后再寻找开盘机会。
                    `;
                }

                content.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
                        <div>
                            ${targetLabel}脱离异动推荐收盘价: <strong style="color: #fbbf24; font-size: 19px;">${pRec.toFixed(2)} 元</strong>
                            &nbsp;&nbsp;对应涨跌幅: <strong style="color: ${riseColor}; font-size: 16px;">${sign}${rRec.toFixed(2)}%</strong>
                        </div>
                    </div>
                    <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 6px;">
                        ${adviceDetails}
                    </div>
                `;
            }
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

        // ==================== 🔥 题材梯队与连板效应、断板亏钱效应回测前端逻辑 ====================
        function setThemeDays(d) {
            const input = document.getElementById('themeDaysInput');
            if (input) input.value = d;
            [5, 10, 20].forEach(n => {
                const btn = document.getElementById(`btnDays${n}`);
                if (btn) {
                    if (n === d) btn.classList.add('active');
                    else btn.classList.remove('active');
                }
            });
            doQueryThemeSentiment();
        }

        function jumpToAnomaly(code) {
            if (!code) return;
            switchModule('anomaly');
            const input = document.getElementById('symbolInput');
            if (input) {
                input.value = code;
                hideDropdown();
                doQuery();
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }

        async function doQueryThemeSentiment() {
            const btn = document.getElementById('btnQueryTheme');
            const originalText = btn ? btn.innerText : '';
            if (btn) {
                btn.innerText = '⚡ 回测测算中...';
                btn.disabled = true;
            }

            const dateSel = document.getElementById('themeDateSelect');
            const date = dateSel ? dateSel.value : '';
            const daysInput = document.getElementById('themeDaysInput');
            const days = daysInput ? daysInput.value : 5;
            const heightSel = document.getElementById('themeHeightSelect');
            const height = heightSel ? heightSel.value : 'all';
            const preDaysSel = document.getElementById('themePreDaysSelect');
            const preDays = preDaysSel ? preDaysSel.value : 4;
            const postDaysSel = document.getElementById('themePostDaysSelect');
            const postDays = postDaysSel ? postDaysSel.value : 5;

            try {
                const resp = await fetch(`/api/theme_sentiment?date=${encodeURIComponent(date)}&days=${days}&height=${height}&pre_days=${preDays}&post_days=${postDays}`);
                const data = await resp.json();
                if (data.success) {
                    window._themeSentimentLoaded = true;

                    // 填充交易日选择列表 (若未初始化)
                    if (dateSel && data.dates_list && dateSel.options.length <= 1) {
                        dateSel.innerHTML = '';
                        data.dates_list.forEach((d, idx) => {
                            const opt = document.createElement('option');
                            opt.value = d;
                            const fmt = `${d.substring(0,4)}-${d.substring(4,6)}-${d.substring(6,8)}`;
                            opt.innerText = idx === 0 ? `📅 ${fmt} (最新交易日)` : `📅 ${fmt}`;
                            if (d === data.date) opt.selected = true;
                            dateSel.appendChild(opt);
                        });
                    }

                    renderSentimentDashboard(data.metrics, data.date);
                    renderBrokenBoardTable(data.backtest, days, heightSel ? heightSel.options[heightSel.selectedIndex].text : '');
                    renderLadderAndThemes(data.ladder, data.themes, data.date);
                } else {
                    alert('获取题材梯队与情绪数据失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                console.error('doQueryThemeSentiment error:', e);
            } finally {
                if (btn) {
                    btn.innerText = originalText || '⚡ 刷新/开始回测';
                    btn.disabled = false;
                }
            }
        }

        function renderSentimentDashboard(m, date) {
            if (!m) return;
            document.getElementById('smScore').innerText = m.score;
            document.getElementById('smCycle').innerText = m.cycle_phase;
            document.getElementById('smAdvice').innerText = m.action_advice;
            document.getElementById('smMaxHeightStock').innerText = m.max_height_stock;
            document.getElementById('smLadderCount').innerText = m.ladder_total_count;
            document.getElementById('smFirstCount').innerText = m.first_board_count;

            const badge = document.getElementById('smCycleBadge');
            if (badge) {
                if (m.cycle_phase.includes('冰点')) {
                    badge.style.borderColor = '#38bdf8';
                    badge.style.background = 'rgba(56, 189, 248, 0.15)';
                    badge.style.color = '#38bdf8';
                } else if (m.cycle_phase.includes('启动')) {
                    badge.style.borderColor = '#fbbf24';
                    badge.style.background = 'rgba(251, 191, 36, 0.15)';
                    badge.style.color = '#fbbf24';
                } else if (m.cycle_phase.includes('主升')) {
                    badge.style.borderColor = '#10b981';
                    badge.style.background = 'rgba(16, 185, 129, 0.15)';
                    badge.style.color = '#10b981';
                } else if (m.cycle_phase.includes('高潮')) {
                    badge.style.borderColor = '#a855f7';
                    badge.style.background = 'rgba(168, 85, 247, 0.15)';
                    badge.style.color = '#a855f7';
                } else {
                    badge.style.borderColor = '#f43f5e';
                    badge.style.background = 'rgba(244, 63, 94, 0.15)';
                    badge.style.color = '#f43f5e';
                }
            }

            // 6大卡片
            document.getElementById('cardMaxHeight').innerText = `${m.max_height} 板`;
            document.getElementById('cardMaxLeader').innerText = m.max_height_stock;
            document.getElementById('cardLadderTotal').innerText = `${m.ladder_total_count} 只`;
            document.getElementById('cardZtTotal').innerText = `${m.limit_up_count} 只`;

            document.getElementById('cardPromSummary').innerText = `${m.promotion_1_to_2}%`;
            document.getElementById('cardProm12').innerText = `${m.promotion_1_to_2}%`;
            document.getElementById('cardProm23').innerText = `${m.promotion_2_to_3}%`;
            document.getElementById('cardProm34').innerText = `${m.promotion_3_to_4}%`;
            document.getElementById('cardPromHigh').innerText = `${m.promotion_high}%`;

            document.getElementById('cardBreakRate').innerText = `${m.break_rate}%`;
            document.getElementById('cardZtCount').innerText = m.limit_up_count;
            document.getElementById('cardZbCount').innerText = m.break_count;

            const breakLevel = m.break_rate > 28 ? '高风险退潮 ⚠️' : (m.break_rate > 18 ? '分歧震荡 ⚖️' : '良性强势 🛡️');
            document.getElementById('cardBreakLevel').innerText = breakLevel;

            const sign = m.yzt_avg_return >= 0 ? '+' : '';
            const yztColor = m.yzt_avg_return >= 0 ? 'var(--red)' : 'var(--green)';
            const yztElem = document.getElementById('cardYztReturn');
            yztElem.innerText = `${sign}${m.yzt_avg_return}%`;
            yztElem.style.color = yztColor;
            document.getElementById('cardYztAvg').innerText = `${sign}${m.yzt_avg_return}%`;
            document.getElementById('cardYztUpRate').innerText = `${m.yzt_up_rate}%`;

            document.getElementById('cardDtCount').innerText = `${m.limit_down_count} 家`;
            document.getElementById('cardDtNum').innerText = m.limit_down_count;
            document.getElementById('cardDtDesc').innerText = m.limit_down_count > 10 ? '恐慌核按钮蔓延' : (m.limit_down_count > 3 ? '局部个股补跌' : '情绪可控');

            document.getElementById('cardScore').innerText = `${m.score} / 100`;
            document.getElementById('cardCycleText').innerText = m.cycle_phase;
            document.getElementById('cardSafetyText').innerText = m.score >= 50 ? '做多窗口期' : '防守防核期';
        }

        function renderBrokenBoardTable(backtest, days, heightText) {
            const filterTitle = document.getElementById('lossFilterTitle');
            if (filterTitle) {
                filterTitle.innerText = `近 ${days} 个交易日 · ${heightText}`;
            }

            const s = backtest.summary || {};
            document.getElementById('lossTotalSamples').innerHTML = `${s.total_samples || 0} <span style="font-size:13px; font-weight:normal;">只</span>`;

            const t0AvgElem = document.getElementById('lossT0AvgPct');
            const t0Sign = (s.t0_avg_pct || 0) >= 0 ? '+' : '';
            t0AvgElem.innerText = `${t0Sign}${(s.t0_avg_pct || 0).toFixed(2)}%`;
            t0AvgElem.style.color = (s.t0_avg_pct || 0) >= 0 ? 'var(--red)' : 'var(--green)';

            document.getElementById('lossT0AvgDrop').innerText = `${(s.t0_avg_drop_from_high || 0).toFixed(2)}%`;
            document.getElementById('lossT0NegRate').innerText = `${(s.t0_negative_rate || 0).toFixed(1)}% / ${(s.t0_limit_down_rate || 0).toFixed(1)}%`;

            const t1GapElem = document.getElementById('lossT1AvgGap');
            const t1GapSign = (s.t1_avg_open_gap || 0) >= 0 ? '+' : '';
            t1GapElem.innerText = `${t1GapSign}${(s.t1_avg_open_gap || 0).toFixed(2)}%`;
            t1GapElem.style.color = (s.t1_avg_open_gap || 0) >= 0 ? 'var(--red)' : 'var(--green)';

            const t1CloseElem = document.getElementById('lossT1AvgClose');
            const t1CloseSign = (s.t1_avg_close_pct || 0) >= 0 ? '+' : '';
            t1CloseElem.innerText = `${t1CloseSign}${(s.t1_avg_close_pct || 0).toFixed(2)}%`;
            t1CloseElem.style.color = (s.t1_avg_close_pct || 0) >= 0 ? 'var(--red)' : 'var(--green)';

            document.getElementById('lossT1SlumpVsRebound').innerHTML = `<b style="color:var(--red);">${(s.t1_slump_rate || 0).toFixed(1)}%</b> vs <b style="color:var(--green);">${(s.t1_rebound_rate || 0).toFixed(1)}%</b>`;

            const cumElem = document.getElementById('lossCum2dAvg');
            const cumSign = (s.cum_2d_avg_return || 0) >= 0 ? '+' : '';
            cumElem.innerText = `${cumSign}${(s.cum_2d_avg_return || 0).toFixed(2)}%`;
            cumElem.style.color = (s.cum_2d_avg_return || 0) >= 0 ? 'var(--red)' : 'var(--green)';

            // 渲染表格
            const tbody = document.getElementById('brokenBoardTbody');
            if (!tbody) return;

            const list = backtest.details || [];
            if (list.length === 0) {
                tbody.innerHTML = `<tr><td colspan="13" style="text-align: center; color: var(--text-secondary); padding: 24px;">所选时间范围和高度下暂无断板样本</td></tr>`;
                return;
            }

            tbody.innerHTML = list.map(item => {
                const t0Color = item.t0_pct_change >= 0 ? 'var(--red)' : 'var(--green)';
                const t0Sign = item.t0_pct_change >= 0 ? '+' : '';

                const t1GapColor = item.t1_open_gap !== null ? (item.t1_open_gap >= 0 ? 'var(--red)' : 'var(--green)') : 'inherit';
                const t1GapStr = item.t1_open_gap !== null ? `${item.t1_open_gap >= 0 ? '+' : ''}${item.t1_open_gap.toFixed(2)}%` : '<span style="color:#64748b;">待开盘</span>';

                const t1CloseColor = item.t1_close_pct !== null ? (item.t1_close_pct >= 0 ? 'var(--red)' : 'var(--green)') : 'inherit';
                const t1CloseStr = item.t1_close_pct !== null ? `${item.t1_close_pct >= 0 ? '+' : ''}${item.t1_close_pct.toFixed(2)}%` : '<span style="color:#64748b;">待确认</span>';

                const cumColor = item.cum_return_2d !== null ? (item.cum_return_2d >= 0 ? 'var(--red)' : 'var(--green)') : 'inherit';
                const cumStr = item.cum_return_2d !== null ? `${item.cum_return_2d >= 0 ? '+' : ''}${item.cum_return_2d.toFixed(2)}%` : '<span style="color:#64748b;">-</span>';

                let tagClass = 'badge-tag-neutral';
                if (item.sentiment_tag.includes('反包')) tagClass = 'badge-tag-rebound';
                else if (item.sentiment_tag.includes('核按钮') || item.sentiment_tag.includes('大面')) tagClass = 'badge-tag-slump';

                const fmtDate = `${item.break_date.substring(0,4)}-${item.break_date.substring(4,6)}-${item.break_date.substring(6,8)}`;
                const miniKLineHtml = renderMiniKLineSvg(item.mini_kline, item.code, item.name, item.stage);

                return `
                    <tr>
                        <td>
                            <strong style="color: #38bdf8; cursor: pointer;" onclick="jumpToAnomaly('${item.code}')">${item.name}</strong>
                            <div style="font-size: 11px; color: var(--text-secondary);">${item.code}</div>
                        </td>
                        <td><span style="color: #cbd5e1;">${item.theme}</span></td>
                        <td><span class="badge" style="background: rgba(251, 191, 36, 0.15); color: #fbbf24; font-weight: 600;">${item.stage}</span></td>
                        <td>${fmtDate}</td>
                        <td style="color: ${t0Color}; font-weight: 700;">${t0Sign}${item.t0_pct_change.toFixed(2)}%</td>
                        <td style="color: #f43f5e; font-weight: 700;">${item.t0_drop_from_high.toFixed(2)}%</td>
                        <td>${miniKLineHtml}</td>
                        <td>${item.t0_amplitude.toFixed(2)}%</td>
                        <td style="color: ${t1GapColor}; font-weight: 600;">${t1GapStr}</td>
                        <td style="color: ${t1CloseColor}; font-weight: 700;">${t1CloseStr}</td>
                        <td style="color: ${cumColor}; font-weight: 600;">${cumStr}</td>
                        <td><span class="${tagClass}">${item.sentiment_tag}</span></td>
                        <td>
                            <button class="kline-filter-btn" style="font-size: 11px; padding: 2px 8px;" onclick="jumpToAnomaly('${item.code}')">⚡ 测算异动</button>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        function renderMiniKLineSvg(bars, stockCode, stockName, stage) {
            if (!bars || bars.length === 0) {
                return '<span style="color:#64748b; font-size:11px;">无K线数据</span>';
            }
            const width = 150;
            const height = 40;
            const padY = 3;
            const minP = Math.min(...bars.map(b => b.low));
            const maxP = Math.max(...bars.map(b => b.high));
            const rangeP = (maxP - minP) > 0 ? (maxP - minP) : 1;
            const toY = (p) => height - padY - ((p - minP) / rangeP) * (height - padY * 2);

            const count = bars.length;
            const candleW = Math.max(3, Math.min(8, Math.floor((width - 12) / count) - 2));
            const stepX = (width - 12) / count;

            let svg = `<svg width="${width}" height="${height}" style="background:rgba(10,16,29,0.8); border:1px solid rgba(255,255,255,0.06); border-radius:4px; vertical-align:middle;">`;
            svg += `<line x1="0" y1="${height/2}" x2="${width}" y2="${height/2}" stroke="rgba(255,255,255,0.05)" stroke-dasharray="2,2" />`;

            bars.forEach((b, idx) => {
                const cx = 6 + idx * stepX + stepX / 2;
                const openY = toY(b.open);
                const closeY = toY(b.close);
                const highY = toY(b.high);
                const lowY = toY(b.low);
                const isRed = b.close >= b.open;
                const color = isRed ? '#f43f5e' : '#10b981';
                const rectTop = Math.min(openY, closeY);
                const rectHeight = Math.max(1.5, Math.abs(openY - closeY));

                svg += `<line x1="${cx}" y1="${highY}" x2="${cx}" y2="${lowY}" stroke="${color}" stroke-width="1" />`;

                if (b.is_break_day) {
                    svg += `<rect x="${cx - candleW/2}" y="${rectTop}" width="${candleW}" height="${rectHeight}" fill="${color}" stroke="#fbbf24" stroke-width="1.5" />`;
                    svg += `<circle cx="${cx}" cy="${Math.max(2, highY - 2)}" r="1.8" fill="#fbbf24" />`;
                } else {
                    svg += `<rect x="${cx - candleW/2}" y="${rectTop}" width="${candleW}" height="${rectHeight}" fill="${color}" />`;
                }
            });
            svg += `</svg>`;

            const safeJson = encodeURIComponent(JSON.stringify(bars));
            return `
                <div style="cursor: pointer; display: inline-flex; align-items: center; gap: 6px;" onclick="openKLineModal('${stockCode}', '${stockName}', '${stage}', '${safeJson}')" title="点击放大查看断板走势明细">
                    ${svg}
                    <span style="font-size: 10px; color: #64748b; white-space: nowrap;">${bars.length}天</span>
                </div>
            `;
        }

        function openKLineModal(code, name, stage, encodedBars) {
            const bars = JSON.parse(decodeURIComponent(encodedBars));
            const modal = document.getElementById('klineModal');
            if (!modal) return;

            document.getElementById('modalStockTitle').innerText = `${name} (${code}) · ${stage} 前后走势追踪`;
            document.getElementById('modalStockSubtitle').innerText = `共显示 ${bars.length} 个交易日日K (金黄色且带黄标蜡烛为断板日，不足5日交易日已自然截止)`;

            const width = 680;
            const height = 150;
            const padY = 12;
            const minP = Math.min(...bars.map(b => b.low));
            const maxP = Math.max(...bars.map(b => b.high));
            const rangeP = (maxP - minP) > 0 ? (maxP - minP) : 1;
            const toY = (p) => height - padY - ((p - minP) / rangeP) * (height - padY * 2);

            const count = bars.length;
            const candleW = Math.max(10, Math.min(22, Math.floor((width - 40) / count) - 6));
            const stepX = (width - 40) / count;

            let svg = `<svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" style="background:#0a1120; border:1px solid #233354; border-radius:8px;">`;
            svg += `<line x1="0" y1="${height/2}" x2="${width}" y2="${height/2}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="3,3" />`;

            bars.forEach((b, idx) => {
                const cx = 20 + idx * stepX + stepX / 2;
                const openY = toY(b.open);
                const closeY = toY(b.close);
                const highY = toY(b.high);
                const lowY = toY(b.low);
                const isRed = b.close >= b.open;
                const color = isRed ? '#f43f5e' : '#10b981';
                const rectTop = Math.min(openY, closeY);
                const rectHeight = Math.max(2, Math.abs(openY - closeY));

                svg += `<line x1="${cx}" y1="${highY}" x2="${cx}" y2="${lowY}" stroke="${color}" stroke-width="1.5" />`;

                if (b.is_break_day) {
                    svg += `<rect x="${cx - candleW/2}" y="${rectTop}" width="${candleW}" height="${rectHeight}" fill="${color}" stroke="#fbbf24" stroke-width="2" />`;
                    svg += `<polygon points="${cx},${Math.max(4, highY - 10)} ${cx-4},${Math.max(0, highY - 16)} ${cx+4},${Math.max(0, highY - 16)}" fill="#fbbf24" />`;
                    svg += `<text x="${cx}" y="${height - 2}" text-anchor="middle" fill="#fbbf24" font-size="10" font-weight="700">断板日</text>`;
                } else {
                    svg += `<rect x="${cx - candleW/2}" y="${rectTop}" width="${candleW}" height="${rectHeight}" fill="${color}" />`;
                    const offsetLabel = b.offset > 0 ? `+${b.offset}` : `${b.offset}`;
                    svg += `<text x="${cx}" y="${height - 2}" text-anchor="middle" fill="#64748b" font-size="9">${offsetLabel}</text>`;
                }
            });
            svg += `</svg>`;

            document.getElementById('modalSvgContainer').innerHTML = svg;

            const tbody = document.getElementById('modalKLineTbody');
            if (tbody) {
                tbody.innerHTML = bars.map(b => {
                    const isRed = b.close >= b.open;
                    const color = isRed ? 'var(--red)' : 'var(--green)';
                    const sign = b.pct >= 0 ? '+' : '';
                    let label = b.offset === 0 ? '<span style="color:#fbbf24; font-weight:700;">🎯 T0 (断板日)</span>' : (b.offset > 0 ? `<span style="color:#38bdf8;">T+${b.offset} 日</span>` : `<span style="color:#94a3b8;">T${b.offset} 日</span>`);
                    return `
                        <tr style="${b.is_break_day ? 'background:rgba(251,191,36,0.08);' : ''}">
                            <td>${b.date}</td>
                            <td>${label}</td>
                            <td>${b.open.toFixed(2)}</td>
                            <td style="color:${color}; font-weight:700;">${b.close.toFixed(2)}</td>
                            <td>${b.high.toFixed(2)}</td>
                            <td>${b.low.toFixed(2)}</td>
                            <td style="color:${color}; font-weight:700;">${sign}${b.pct.toFixed(2)}%</td>
                        </tr>
                    `;
                }).join('');
            }

            modal.style.display = 'flex';
        }

        function closeKLineModal() {
            const modal = document.getElementById('klineModal');
            if (modal) modal.style.display = 'none';
        }

        function renderLadderAndThemes(ladder, themes, date) {
            const dateTitle = document.getElementById('ladderDateTitle');
            if (dateTitle && date) {
                const fmt = `${date.substring(0,4)}-${date.substring(4,6)}-${date.substring(6,8)}`;
                dateTitle.innerText = fmt;
            }

            // 渲染连板天梯
            const ladderContainer = document.getElementById('ladderPyramidContainer');
            if (ladderContainer) {
                const keys = Object.keys(ladder || {}).map(k => parseInt(k)).sort((a, b) => b - a);
                if (keys.length === 0) {
                    ladderContainer.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 20px;">当日暂无连板股票</div>';
                } else {
                    ladderContainer.innerHTML = keys.map(level => {
                        const stocks = ladder[level] || [];
                        let levelIcon = '📦';
                        let levelColor = '#cbd5e1';
                        if (level >= 5) { levelIcon = '👑'; levelColor = '#fbbf24'; }
                        else if (level >= 3) { levelIcon = '🔥'; levelColor = '#f43f5e'; }
                        else if (level === 2) { levelIcon = '🌱'; levelColor = '#38bdf8'; }

                        const pills = stocks.map(s => `
                            <div class="ladder-stock-pill" onclick="jumpToAnomaly('${s.code}')" title="点击立即跳转测算 ${s.name} 异动沙盘">
                                <b>${s.name}</b>
                                <span style="color: #64748b; font-size: 11px;">${s.code}</span>
                                <span style="color: #38bdf8; font-size: 11px;">${s.theme}</span>
                                <span style="color: #10b981; font-size: 11px;">封${s.fund}万</span>
                                <span style="color: #cbd5e1; font-size: 11px;">换${s.turnover_rate}%</span>
                            </div>
                        `).join('');

                        return `
                            <div class="ladder-tier">
                                <div class="ladder-tier-label" style="color: ${levelColor};">
                                    <span>${levelIcon}</span>
                                    <span>${level === 1 ? '首板' : `${level} 连板`} (${stocks.length}只)</span>
                                </div>
                                <div class="ladder-tier-stocks">${pills}</div>
                            </div>
                        `;
                    }).join('');
                }
            }

            // 渲染题材主线矩阵
            const themesContainer = document.getElementById('themesMatrixContainer');
            if (themesContainer) {
                const list = (themes || []).slice(0, 12);
                if (list.length === 0) {
                    themesContainer.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 20px;">暂无主线题材数据</div>';
                } else {
                    themesContainer.innerHTML = list.map(t => {
                        const tags = (t.stocks || []).map(s => `
                            <span class="theme-mini-tag" onclick="jumpToAnomaly('${s.code}')" title="点击立即跳转测算异动">
                                ${s.name} ${s.lbc > 1 ? `(${s.lbc}板)` : ''}
                            </span>
                        `).join('');

                        return `
                            <div class="theme-cluster-card">
                                <div class="theme-cluster-header">
                                    <div class="theme-cluster-title">${t.theme_name} <span style="color: #38bdf8; font-size: 12px;">(${t.count}只涨停)</span></div>
                                    <div class="theme-cluster-leader">龙头: <b>${t.leader_name}</b> (${t.leader_lbc}板)</div>
                                </div>
                                <div class="theme-stock-tags">${tags}</div>
                            </div>
                        `;
                    }).join('');
                }
            }
        }

        window.onload = () => {
            // 恢复上次浏览的业务板块 (默认异动推演沙盘板块)
            try {
                const savedModule = localStorage.getItem('stock_active_module') || 'anomaly';
                switchModule(savedModule);
            } catch (e) {
                switchModule('anomaly');
            }

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
                # 前端按百分比传入 (例如输入 0.1 代表 +0.1%)
                index_chg_pct = float(index_chg_str)
            except ValueError:
                index_chg_pct = 0.0

            index_chg_ratio = index_chg_pct / 100.0

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
                    assume_index_change=index_chg_ratio,
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

        elif path == "/api/theme_sentiment":
            date_param = query.get("date", [""])[0].strip()
            days_str = query.get("days", ["5"])[0].strip()
            height_param = query.get("height", ["all"])[0].strip()
            pre_days_str = query.get("pre_days", ["4"])[0].strip()
            post_days_str = query.get("post_days", ["5"])[0].strip()

            try:
                days = int(days_str)
            except ValueError:
                days = 5
            days = max(1, min(30, days))

            try:
                pre_days = int(pre_days_str)
            except ValueError:
                pre_days = 4
            pre_days = max(1, min(15, pre_days))

            try:
                post_days = int(post_days_str)
            except ValueError:
                post_days = 5
            post_days = max(1, min(15, post_days))

            try:
                trading_dates = ThemeSentimentEngine.get_trading_dates(30)
                selected_date = date_param if (date_param and date_param in trading_dates) else (trading_dates[0] if trading_dates else "20261023")

                metrics = ThemeSentimentEngine.get_sentiment_metrics(selected_date)
                ladder_groups, theme_clusters = ThemeSentimentEngine.get_ladder_and_themes(selected_date)
                backtest_data = ThemeSentimentEngine.get_broken_board_backtest(
                    days=days,
                    target_height=height_param,
                    ref_date=selected_date,
                    pre_days=pre_days,
                    post_days=post_days
                )

                payload = {
                    "success": True,
                    "date": selected_date,
                    "dates_list": trading_dates,
                    "metrics": metrics,
                    "ladder": ladder_groups,
                    "themes": theme_clusters,
                    "backtest": backtest_data
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
