"""
题材梯队与连板效应分析引擎 (Theme Ladder & Broken Board Sentiment Engine)
包含：
1. 全市场连板梯队天梯榜 (Ladder Groups)
2. 题材板块横向聚类归纳 (Themes Clustering)
3. 连板断板亏钱效应回测分析 (Broken Board Loss Effect Analysis)
4. 超短线六大核心专业情绪指标与情绪周期罗盘 (Sentiment Metrics & Emotion Cycle)
"""
import os
import json
import time
import urllib.request
import urllib.error
import concurrent.futures
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from datasource import DataSource, identify_market_config

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache_sentiment")
os.makedirs(CACHE_DIR, exist_ok=True)

EASTMONEY_UT = "7eea3edcaed734bea9cbfc24409ed989"
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*"
}

@dataclass
class LadderItem:
    code: str
    name: str
    lbc: int
    theme: str
    price: float
    pct_change: float
    turnover_rate: float
    amount: float
    first_time: str
    last_time: str
    break_count: int
    fund: float

@dataclass
class ThemeCluster:
    theme_name: str
    count: int
    leader_code: str
    leader_name: str
    leader_lbc: int
    stocks: List[Dict[str, Any]]

@dataclass
class BrokenBoardDetail:
    break_date: str
    code: str
    name: str
    theme: str
    prev_lbc: int
    stage: str
    t0_close: float
    t0_pct_change: float
    t0_drop_from_high: float
    t0_amplitude: float
    t1_date: str
    t1_open_gap: Optional[float]
    t1_close_pct: Optional[float]
    t2_date: str
    t2_close_pct: Optional[float]
    cum_return_2d: Optional[float]
    sentiment_tag: str

@dataclass
class BrokenBoardSummary:
    total_samples: int
    t0_avg_pct: float
    t0_avg_drop_from_high: float
    t0_negative_rate: float
    t0_limit_down_rate: float
    t1_avg_open_gap: float
    t1_avg_close_pct: float
    t1_slump_rate: float
    t1_rebound_rate: float
    cum_2d_avg_return: float

@dataclass
class SentimentMetrics:
    date: str
    max_height: int
    max_height_stock: str
    ladder_total_count: int
    limit_up_count: int
    first_board_count: int
    limit_down_count: int
    break_count: int
    break_rate: float
    promotion_1_to_2: float
    promotion_2_to_3: float
    promotion_3_to_4: float
    promotion_high: float
    yzt_avg_return: float
    yzt_up_rate: float
    score: int
    cycle_phase: str
    action_advice: str

class ThemeSentimentEngine:
    _memory_cache: Dict[str, Any] = {}

    @classmethod
    def get_trading_dates(cls, count: int = 30) -> List[str]:
        """获取最近有效交易日历列表 (降序排列，最新在最前)"""
        cache_key = f"trading_dates_{count}"
        if cache_key in cls._memory_cache:
            return cls._memory_cache[cache_key]

        try:
            bars = DataSource.fetch_tencent_klines("sh000001", limit=count + 10)
            if bars and len(bars) >= 5:
                dates = [b.date.replace("-", "") for b in bars][-count:]
                dates.reverse()
                cls._memory_cache[cache_key] = dates
                return dates
        except Exception:
            pass

        # 离线保底交易日历
        today_date = "20261023"
        mock_dates = [
            "20261023", "20261022", "20261021", "20261020", "20261019",
            "20261016", "20261015", "20261014", "20261013", "20261012",
            "20261009", "20261008", "20260930", "20260929", "20260928"
        ]
        return mock_dates[:count]

    @classmethod
    def _fetch_pool_raw(cls, endpoint: str, date: str, sort: str = "zdp:desc", pagesize: int = 150) -> List[Dict[str, Any]]:
        """从东财接口抓取或从本地磁盘缓存读取特色板块池数据"""
        cache_file = os.path.join(CACHE_DIR, f"{endpoint}_{date}_{sort.split(':')[0]}.json")
        is_today = (date == cls.get_trading_dates(1)[0])

        if not is_today and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        url = f"http://push2ex.eastmoney.com/{endpoint}?ut={EASTMONEY_UT}&dpt=wz.ztzt&Pageindex=0&pagesize={pagesize}&sort={sort}&date={date}"
        try:
            req = urllib.request.Request(url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pool = data.get("data", {}).get("pool", []) if data.get("data") else []
                if pool and not is_today:
                    try:
                        with open(cache_file, "w", encoding="utf-8") as f:
                            json.dump(pool, f, ensure_ascii=False)
                    except Exception:
                        pass
                return pool
        except Exception:
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return []

    @classmethod
    def get_zt_pool(cls, date: str) -> List[Dict[str, Any]]:
        return cls._fetch_pool_raw("getTopicZTPool", date, sort="lbc:desc", pagesize=150)

    @classmethod
    def get_yzt_pool(cls, date: str) -> List[Dict[str, Any]]:
        return cls._fetch_pool_raw("getYesterdayZTPool", date, sort="zdp:desc", pagesize=150)

    @classmethod
    def get_zb_pool(cls, date: str) -> List[Dict[str, Any]]:
        return cls._fetch_pool_raw("getTopicZBPool", date, sort="zdp:asc", pagesize=100)

    @classmethod
    def get_dt_pool(cls, date: str) -> List[Dict[str, Any]]:
        return cls._fetch_pool_raw("getTopicDTPool", date, sort="zdp:asc", pagesize=100)

    @classmethod
    def _format_time(cls, t_val: Any) -> str:
        s = str(t_val)
        if len(s) == 5:
            return f"0{s[0]}:{s[1:3]}:{s[3:]}"
        elif len(s) == 6:
            return f"{s[:2]}:{s[2:4]}:{s[4:]}"
        return "-"

    @classmethod
    def get_ladder_and_themes(cls, date: str) -> Tuple[Dict[int, List[Dict[str, Any]]], List[Dict[str, Any]]]:
        """按连板高度分组连板天梯，并按行业题材聚类"""
        zt_pool = cls.get_zt_pool(date)
        if not zt_pool:
            zt_pool = cls._get_mock_zt_pool(date)

        ladder_groups: Dict[int, List[Dict[str, Any]]] = {}
        theme_map: Dict[str, List[Dict[str, Any]]] = {}

        for item in zt_pool:
            lbc = int(item.get("lbc", 1) or 1)
            raw_p = float(item.get("p", 0) or 0)
            price = round(raw_p / 1000.0, 2) if raw_p > 1000 else round(raw_p, 2)
            pct = round(float(item.get("zdp", 0) or 0), 2)
            amount_yi = round(float(item.get("amount", 0) or 0) / 100000000.0, 2)
            fund_wan = round(float(item.get("fund", 0) or 0) / 10000.0, 2)
            hs = round(float(item.get("hs", 0) or 0), 2)
            hy = str(item.get("hybk", "其他") or "其他").strip()

            ladder_entry = {
                "code": item.get("c", ""),
                "name": item.get("n", ""),
                "lbc": lbc,
                "theme": hy,
                "price": price,
                "pct_change": pct,
                "turnover_rate": hs,
                "amount": amount_yi,
                "first_time": cls._format_time(item.get("fbt", "")),
                "last_time": cls._format_time(item.get("lbt", "")),
                "break_count": int(item.get("zbc", 0) or 0),
                "fund": fund_wan
            }

            if lbc not in ladder_groups:
                ladder_groups[lbc] = []
            ladder_groups[lbc].append(ladder_entry)

            if hy not in theme_map:
                theme_map[hy] = []
            theme_map[hy].append(ladder_entry)

        # 题材聚类统计与排序
        theme_clusters: List[Dict[str, Any]] = []
        for theme_name, stocks in theme_map.items():
            stocks_sorted = sorted(stocks, key=lambda x: (x["lbc"], x["amount"]), reverse=True)
            leader = stocks_sorted[0]
            theme_clusters.append({
                "theme_name": theme_name,
                "count": len(stocks),
                "leader_code": leader["code"],
                "leader_name": leader["name"],
                "leader_lbc": leader["lbc"],
                "stocks": stocks_sorted
            })

        theme_clusters.sort(key=lambda t: (t["leader_lbc"], t["count"]), reverse=True)
        return ladder_groups, theme_clusters

    @classmethod
    def get_sentiment_metrics(cls, date: str) -> Dict[str, Any]:
        """计算全市场超短线六大核心专业情绪指标"""
        zt_pool = cls.get_zt_pool(date)
        yzt_pool = cls.get_yzt_pool(date)
        zb_pool = cls.get_zb_pool(date)
        dt_pool = cls.get_dt_pool(date)

        if not zt_pool:
            zt_pool = cls._get_mock_zt_pool(date)
        if not yzt_pool:
            yzt_pool = cls._get_mock_yzt_pool(date)

        # 1. 连板高度与家数
        ladder_counts: Dict[int, int] = {}
        max_height = 0
        max_height_stock = "-"

        for item in zt_pool:
            l = int(item.get("lbc", 1) or 1)
            ladder_counts[l] = ladder_counts.get(l, 0) + 1
            if l > max_height:
                max_height = l
                max_height_stock = f"{item.get('n', '')} ({l}板)"

        limit_up_count = len(zt_pool)
        first_board_count = ladder_counts.get(1, 0)
        ladder_total_count = sum(v for k, v in ladder_counts.items() if k >= 2)
        limit_down_count = len(dt_pool)
        break_count = len(zb_pool)

        # 2. 炸板率
        total_touch_zt = limit_up_count + break_count
        break_rate = round((break_count / total_touch_zt * 100.0), 2) if total_touch_zt > 0 else 0.0

        # 3. 昨涨停今日表现 (昨涨停收益与胜率)
        yzt_returns = [float(x.get("zdp", 0) or 0) for x in yzt_pool]
        yzt_avg_return = round(sum(yzt_returns) / len(yzt_returns), 2) if yzt_returns else 0.0
        yzt_up_count = sum(1 for r in yzt_returns if r > 0)
        yzt_up_rate = round((yzt_up_count / len(yzt_returns) * 100.0), 2) if yzt_returns else 0.0

        # 4. 梯队晋级率矩阵
        trading_dates = cls.get_trading_dates(10)
        prev_date = None
        for i, d in enumerate(trading_dates):
            if d == date and i + 1 < len(trading_dates):
                prev_date = trading_dates[i + 1]
                break

        prev_ladder_counts: Dict[int, int] = {}
        if prev_date:
            prev_zt = cls.get_zt_pool(prev_date)
            for item in prev_zt:
                l = int(item.get("lbc", 1) or 1)
                prev_ladder_counts[l] = prev_ladder_counts.get(l, 0) + 1

        prom_1_2 = round(ladder_counts.get(2, 0) / prev_ladder_counts.get(1, 1) * 100.0, 1) if prev_ladder_counts.get(1, 0) else 0.0
        prom_2_3 = round(ladder_counts.get(3, 0) / prev_ladder_counts.get(2, 1) * 100.0, 1) if prev_ladder_counts.get(2, 0) else 0.0
        prom_3_4 = round(ladder_counts.get(4, 0) / prev_ladder_counts.get(3, 1) * 100.0, 1) if prev_ladder_counts.get(3, 0) else 0.0

        prev_high = sum(v for k, v in prev_ladder_counts.items() if k >= 4)
        curr_high = sum(v for k, v in ladder_counts.items() if k >= 5)
        prom_high = round(curr_high / prev_high * 100.0, 1) if prev_high > 0 else (100.0 if curr_high > 0 else 0.0)

        # 5. 超短情绪综合评分与周期定性
        score = 50
        # 连板高度加分
        score += min(20, max_height * 3)
        # 昨涨停溢价加减分
        score += int(yzt_avg_return * 3.5)
        # 炸板率扣分
        if break_rate > 35:
            score -= 18
        elif break_rate > 25:
            score -= 10
        elif break_rate < 15:
            score += 10
        # 跌停数扣分
        score -= min(25, limit_down_count * 2)
        # 晋级率加分
        if prom_1_2 > 25:
            score += 8
        if prom_2_3 > 25:
            score += 8

        score = max(5, min(98, score))

        # 情绪周期定性
        if score <= 28 or (limit_down_count >= 15 and max_height <= 2):
            cycle_phase = "冰点期"
            action_advice = "市场处于冰点冰冻期，接力亏钱效应扩散，高标易遭核按钮，建议严控仓位或轻仓试错首板新题材。"
        elif score <= 48:
            cycle_phase = "启动/试错期"
            action_advice = "冰点企稳信号初现，首板放量承接，新题材萌芽扩散，可积极寻找首板与1进2高性价比换手标的。"
        elif score <= 75:
            cycle_phase = "发酵/主升期"
            action_advice = "连板梯队健全，中高位晋级顺畅，赚钱效应充裕，建议紧跟主线题材核心龙头，拥抱高标确定性溢价。"
        elif score <= 88:
            cycle_phase = "高潮加速期"
            action_advice = "情绪高度一致，一字板与缩量加速密集，随时防范由盛转衰分歧大面，切勿盲目接力后排杂毛。"
        else:
            cycle_phase = "分歧/退潮期"
            action_advice = "高位筹码剧烈松动，天地板与核按钮频发，断板亏钱效应极度恶劣，坚决空仓防守，保住利润。"

        return {
            "date": date,
            "max_height": max_height,
            "max_height_stock": max_height_stock,
            "ladder_total_count": ladder_total_count,
            "limit_up_count": limit_up_count,
            "first_board_count": first_board_count,
            "limit_down_count": limit_down_count,
            "break_count": break_count,
            "break_rate": break_rate,
            "promotion_1_to_2": prom_1_2,
            "promotion_2_to_3": prom_2_3,
            "promotion_3_to_4": prom_3_4,
            "promotion_high": prom_high,
            "yzt_avg_return": yzt_avg_return,
            "yzt_up_rate": yzt_up_rate,
            "score": score,
            "cycle_phase": cycle_phase,
            "action_advice": action_advice
        }

    @classmethod
    def get_broken_board_backtest(
        cls, days: int = 5, target_height: str = "all", ref_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        断板亏钱效应回测：
        统计过去指定交易日内，达到指定高度的股票断板时的当日表现及次日(T+1)、隔日(T+2)亏钱与修复表现。
        """
        all_dates = cls.get_trading_dates(days + 15)
        if not all_dates:
            return {"summary": {}, "details": []}

        start_idx = 0
        if ref_date and ref_date in all_dates:
            start_idx = all_dates.index(ref_date)

        test_dates = all_dates[start_idx : start_idx + days]
        broken_records: List[Dict[str, Any]] = []

        # 1. 扫描各交易日断板个股
        for dt in test_dates:
            yzt = cls.get_yzt_pool(dt)
            if not yzt:
                continue

            for item in yzt:
                ylbc = int(item.get("ylbc", 1) or 1)
                zdp = float(item.get("zdp", 0) or 0)

                # 仅针对连板冲击下一板失败 (断板标准: 当日未涨停，涨幅<9.3%)
                if ylbc >= 2 and zdp < 9.3:
                    # 高度筛选
                    if target_height == "2_to_3" and ylbc != 2:
                        continue
                    elif target_height == "3_to_4" and ylbc != 3:
                        continue
                    elif target_height == "4_to_5" and ylbc != 4:
                        continue
                    elif target_height == "high_5_plus" and ylbc < 5:
                        continue

                    raw_p = float(item.get("p", 0) or 0)
                    close_p = round(raw_p / 1000.0, 2) if raw_p > 1000 else round(raw_p, 2)
                    zf = round(float(item.get("zf", 0) or 0), 2)
                    hy = str(item.get("hybk", "其他") or "其他").strip()

                    # 炸板大面回落估算 (若涨停为+10%，收盘为zdp，则大面幅度约为 zdp - 10.0%)
                    drop_from_high = round(zdp - (20.0 if item.get("c", "").startswith(("30", "68")) else 10.0), 2)

                    broken_records.append({
                        "break_date": dt,
                        "code": item.get("c", ""),
                        "name": item.get("n", ""),
                        "theme": hy,
                        "prev_lbc": ylbc,
                        "stage": f"{ylbc}进{ylbc + 1}断板",
                        "t0_close": close_p,
                        "t0_pct_change": round(zdp, 2),
                        "t0_drop_from_high": drop_from_high,
                        "t0_amplitude": zf,
                        "t1_date": "-",
                        "t1_open_gap": None,
                        "t1_close_pct": None,
                        "t2_date": "-",
                        "t2_close_pct": None,
                        "cum_return_2d": None,
                        "sentiment_tag": "分歧断板"
                    })

        # 2. 并发拉取个股日K线计算 T+1, T+2 表现
        unique_codes = list({r["code"] for r in broken_records})
        code_klines_map: Dict[str, List[Any]] = {}

        def fetch_stock_kline(c: str):
            try:
                cfg = identify_market_config(c)
                bars = DataSource.fetch_tencent_klines(f"{cfg.tencent_market}{c}", limit=40)
                return c, bars
            except Exception:
                return c, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            for c, bars in ex.map(fetch_stock_kline, unique_codes):
                code_klines_map[c] = bars

        # 3. 计算每只股票的 T+1, T+2 亏钱指标
        for r in broken_records:
            code = r["code"]
            b_date_str = r["break_date"]
            b_date_fmt = f"{b_date_str[:4]}-{b_date_str[4:6]}-{b_date_str[6:8]}"
            bars = code_klines_map.get(code, [])

            b_idx = None
            for i, b in enumerate(bars):
                if b.date == b_date_fmt:
                    b_idx = i
                    break

            if b_idx is not None:
                b0 = bars[b_idx]
                # T+1 日
                if b_idx + 1 < len(bars):
                    b1 = bars[b_idx + 1]
                    r["t1_date"] = b1.date.replace("-", "")
                    r["t1_open_gap"] = round(((b1.open - b0.close) / b0.close) * 100.0, 2)
                    r["t1_close_pct"] = round(((b1.close - b0.close) / b0.close) * 100.0, 2)

                # T+2 日
                if b_idx + 2 < len(bars):
                    b2 = bars[b_idx + 2]
                    r["t2_date"] = b2.date.replace("-", "")
                    r["t2_close_pct"] = round(b2.pct_change, 2)
                    r["cum_return_2d"] = round(((b2.close - b0.close) / b0.close) * 100.0, 2)

            # 打标分类
            t0_pct = r["t0_pct_change"]
            t1_pct = r["t1_close_pct"]
            t1_gap = r["t1_open_gap"]

            if t1_pct is not None and t1_pct >= 5.0:
                r["sentiment_tag"] = "弱转强反包 🚀"
            elif t1_gap is not None and t1_gap <= -6.0:
                r["sentiment_tag"] = "深度核按钮 💥"
            elif t0_pct <= -8.0 or (t1_pct is not None and t1_pct <= -6.0):
                r["sentiment_tag"] = "恶性大面 🩸"
            elif t0_pct > 0 and (t1_pct is None or t1_pct >= -2.0):
                r["sentiment_tag"] = "良性换手 🛡️"
            else:
                r["sentiment_tag"] = "大幅补跌 📉"

        # 4. 汇总统计断板亏钱效应数据
        total_samples = len(broken_records)
        if total_samples == 0:
            return {
                "summary": {
                    "total_samples": 0,
                    "t0_avg_pct": 0.0,
                    "t0_avg_drop_from_high": 0.0,
                    "t0_negative_rate": 0.0,
                    "t0_limit_down_rate": 0.0,
                    "t1_avg_open_gap": 0.0,
                    "t1_avg_close_pct": 0.0,
                    "t1_slump_rate": 0.0,
                    "t1_rebound_rate": 0.0,
                    "cum_2d_avg_return": 0.0
                },
                "details": []
            }

        t0_pcts = [r["t0_pct_change"] for r in broken_records]
        t0_drops = [r["t0_drop_from_high"] for r in broken_records]
        t0_neg_count = sum(1 for p in t0_pcts if p < 0)
        t0_down_limit = sum(1 for p in t0_pcts if p <= -9.0)

        t1_gaps = [r["t1_open_gap"] for r in broken_records if r["t1_open_gap"] is not None]
        t1_pcts = [r["t1_close_pct"] for r in broken_records if r["t1_close_pct"] is not None]
        t1_slumps = sum(1 for p in t1_pcts if p <= -5.0)
        t1_rebounds = sum(1 for p in t1_pcts if p >= 5.0)

        cum_2ds = [r["cum_return_2d"] for r in broken_records if r["cum_return_2d"] is not None]

        summary = {
            "total_samples": total_samples,
            "t0_avg_pct": round(sum(t0_pcts) / total_samples, 2),
            "t0_avg_drop_from_high": round(sum(t0_drops) / total_samples, 2),
            "t0_negative_rate": round(t0_neg_count / total_samples * 100.0, 1),
            "t0_limit_down_rate": round(t0_down_limit / total_samples * 100.0, 1),
            "t1_avg_open_gap": round(sum(t1_gaps) / len(t1_gaps), 2) if t1_gaps else 0.0,
            "t1_avg_close_pct": round(sum(t1_pcts) / len(t1_pcts), 2) if t1_pcts else 0.0,
            "t1_slump_rate": round(t1_slumps / len(t1_pcts) * 100.0, 1) if t1_pcts else 0.0,
            "t1_rebound_rate": round(t1_rebounds / len(t1_pcts) * 100.0, 1) if t1_pcts else 0.0,
            "cum_2d_avg_return": round(sum(cum_2ds) / len(cum_2ds), 2) if cum_2ds else 0.0
        }

        # 排序：按断板日期倒序，再按大面程度排序
        broken_records.sort(key=lambda r: (r["break_date"], -r["t0_drop_from_high"]), reverse=True)

        return {
            "summary": summary,
            "details": broken_records
        }

    @classmethod
    def _get_mock_zt_pool(cls, date: str) -> List[Dict[str, Any]]:
        """离线仿真涨停池数据"""
        return [
            {"c": "002724", "n": "海洋王", "p": 12330, "zdp": 9.99, "amount": 1727203728, "lbc": 6, "fbt": 95351, "lbt": 145406, "fund": 3452400, "hs": 28.1, "hybk": "照明设备", "zbc": 3},
            {"c": "603278", "n": "大业股份", "p": 15960, "zdp": 9.99, "amount": 1245000000, "lbc": 6, "fbt": 94000, "lbt": 142000, "fund": 5100000, "hs": 22.4, "hybk": "通用设备", "zbc": 1},
            {"c": "600838", "n": "上海九百", "p": 11000, "zdp": 10.0, "amount": 890000000, "lbc": 3, "fbt": 93015, "lbt": 93015, "fund": 18000000, "hs": 8.5, "hybk": "商业百货", "zbc": 0},
            {"c": "002982", "n": "湘佳股份", "p": 24500, "zdp": 10.02, "amount": 450000000, "lbc": 2, "fbt": 94500, "lbt": 95500, "fund": 6200000, "hs": 14.2, "hybk": "养殖业", "zbc": 2},
            {"c": "000530", "n": "冰山冷热", "p": 9530, "zdp": 0.42, "amount": 1150000000, "lbc": 1, "fbt": 101500, "lbt": 145000, "fund": 2100000, "hs": 19.8, "hybk": "通用设备", "zbc": 4}
        ]

    @classmethod
    def _get_mock_yzt_pool(cls, date: str) -> List[Dict[str, Any]]:
        """离线仿真昨日涨停池数据"""
        return [
            {"c": "600293", "n": "三峡新材", "p": 4910, "zdp": -6.12, "ylbc": 3, "zf": 19.89, "amount": 680000000, "hs": 21.5, "hybk": "玻璃玻纤"},
            {"c": "002076", "n": "星光股份", "p": 2490, "zdp": -7.78, "ylbc": 3, "zf": 12.22, "amount": 540000000, "hs": 18.2, "hybk": "照明设备"},
            {"c": "603330", "n": "天洋新材", "p": 10400, "zdp": -6.31, "ylbc": 2, "zf": 14.86, "amount": 320000000, "hs": 16.1, "hybk": "塑料制品"},
            {"c": "600202", "n": "哈空调", "p": 5520, "zdp": -9.95, "ylbc": 2, "zf": 8.97, "amount": 410000000, "hs": 19.4, "hybk": "通用设备"}
        ]
