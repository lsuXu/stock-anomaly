"""
A股异动监控系统 - 数据获取模块 (腾讯财经高可用主通道 + 东方财富备用通道)
"""
import json
import urllib.request
import urllib.error
import datetime
from typing import List, Dict, Any, Tuple, Optional
from models import MarketType, MarketConfig, KLineBar

# 市场配置映射表 (按中国证监会及沪深交易所法定异动监管规则)
MARKET_CONFIGS: Dict[MarketType, MarketConfig] = {
    MarketType.SH_MAIN: MarketConfig(
        market_type=MarketType.SH_MAIN,
        market_name="沪市主板",
        price_limit_rate=0.10,
        normal_threshold=0.20,
        index_name="上证A指",
        index_code="000002",
        index_secid="1.000002",
        stock_prefix="1.",
        tencent_market="sh",
        tencent_index="sh000002"
    ),
    MarketType.SZ_MAIN: MarketConfig(
        market_type=MarketType.SZ_MAIN,
        market_name="深市主板",
        price_limit_rate=0.10,
        normal_threshold=0.20,
        index_name="深证A指",
        index_code="399107",
        index_secid="0.399107",
        stock_prefix="0.",
        tencent_market="sz",
        tencent_index="sz399107"
    ),
    MarketType.CYB: MarketConfig(
        market_type=MarketType.CYB,
        market_name="创业板",
        price_limit_rate=0.20,
        normal_threshold=0.30,
        index_name="创业板综",
        index_code="399102",
        index_secid="0.399102",
        stock_prefix="0.",
        tencent_market="sz",
        tencent_index="sz399102"
    ),
    MarketType.STAR: MarketConfig(
        market_type=MarketType.STAR,
        market_name="科创板",
        price_limit_rate=0.20,
        normal_threshold=0.30,
        index_name="科创50",
        index_code="000688",
        index_secid="1.000688",
        stock_prefix="1.",
        tencent_market="sh",
        tencent_index="sh000688"
    ),
}

def identify_market_config(symbol: str) -> MarketConfig:
    """根据股票代码自动识别所属板块及对应监管配置"""
    sym = symbol.strip()
    if sym.startswith(("600", "601", "603", "605", "60")):
        return MARKET_CONFIGS[MarketType.SH_MAIN]
    elif sym.startswith("688"):
        return MARKET_CONFIGS[MarketType.STAR]
    elif sym.startswith(("000", "001", "002", "003", "00")):
        return MARKET_CONFIGS[MarketType.SZ_MAIN]
    elif sym.startswith(("300", "301", "30")):
        return MARKET_CONFIGS[MarketType.CYB]
    else:
        raise ValueError(f"无法识别该股票所属板块 (输入代码: {symbol})，支持沪市(60/688)、深市(00)、创业板(30)")

class DataSource:
    """多数据源自动容灾封装：优先腾讯财经极速通道，次选东财通道"""

    HTTP_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    @classmethod
    def fetch_tencent_quote(cls, tencent_code: str) -> Optional[Dict[str, Any]]:
        """从腾讯财经获取实时五档与名称快照 (极速稳定、零封禁)"""
        url = f"https://qt.gtimg.cn/q={tencent_code}"
        try:
            req = urllib.request.Request(url, headers=cls.HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode("gbk", errors="ignore")
                parts = raw.split("~")
                if len(parts) > 5:
                    return {
                        "name": parts[1].strip(),
                        "code": parts[2].strip(),
                        "realtime_price": float(parts[3]),
                        "prev_close": float(parts[4]),
                        "open": float(parts[5]),
                        "pct_change": float(parts[32]) if len(parts) > 32 and parts[32] else 0.0
                    }
        except Exception:
            pass
        return None

    @classmethod
    def fetch_tencent_klines(cls, tencent_code: str, limit: int = 320) -> List[KLineBar]:
        """从腾讯财经获取前复权日K线数据 (qfq, 支持获取长达300+个交易日)"""
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,,,{limit},qfq"
        try:
            req = urllib.request.Request(url, headers=cls.HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=6) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(content)
                stock_data = data.get("data", {}).get(tencent_code, {})
                raw_bars = stock_data.get("qfqday") or stock_data.get("day") or []
                
                bars: List[KLineBar] = []
                prev_close = None
                for b in raw_bars:
                    # 格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]
                    date = b[0]
                    open_p = float(b[1])
                    close_p = float(b[2])
                    high_p = float(b[3])
                    low_p = float(b[4])
                    vol = float(b[5]) if len(b) > 5 else 0.0
                    if prev_close and prev_close > 0:
                        pct_chg = round(((close_p / prev_close) - 1.0) * 100.0, 2)
                    else:
                        pct_chg = round(((close_p / open_p) - 1.0) * 100.0, 2)
                    prev_close = close_p
                    bars.append(KLineBar(
                        date=date,
                        open=open_p,
                        close=close_p,
                        high=high_p,
                        low=low_p,
                        pct_change=pct_chg,
                        volume=vol
                    ))
                return bars
        except Exception:
            return []

    @classmethod
    def fetch_eastmoney_klines(cls, secid: str, limit: int = 320) -> List[KLineBar]:
        """备用通道：从东方财富拉取日K线"""
        urls = [
            f"http://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&klt=101&fqt=1&beg=0&end=20500000&lmt={limit}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&klt=101&fqt=1&beg=0&end=20500000&lmt={limit}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        ]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=cls.HTTP_HEADERS)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_klines = data.get("data", {}).get("klines", [])
                    if not raw_klines:
                        continue
                    bars: List[KLineBar] = []
                    for line in raw_klines:
                        parts = line.split(",")
                        bars.append(KLineBar(
                            date=parts[0],
                            open=float(parts[1]),
                            close=float(parts[2]),
                            high=float(parts[3]),
                            low=float(parts[4]),
                            pct_change=float(parts[8]) if len(parts) > 8 else 0.0,
                            volume=float(parts[5]) if len(parts) > 5 else 0.0
                        ))
                    return bars
            except Exception:
                continue
        return []

    @classmethod
    def check_is_intraday(cls, latest_kline_date: str, force_mode: Optional[str] = None) -> bool:
        """判断是否处于盘中交易中"""
        if force_mode == "intraday":
            return True
        elif force_mode == "post_market":
            return False

        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        if now.weekday() < 5 and latest_kline_date == today_str:
            market_close_time = datetime.time(15, 0, 0)
            if now.time() < market_close_time:
                return True
        return False

    @classmethod
    def get_stock_and_index_data(
        cls, symbol: str, limit: int = 320, force_mode: Optional[str] = None
    ) -> Tuple[MarketConfig, str, List[KLineBar], List[KLineBar], bool, bool]:
        """
        获取股票与基准指数数据 (主备自动容灾: 腾讯主通道 -> 东财备用通道 -> 离线仿真)
        返回: (config, stock_name, stock_klines, index_klines, is_intraday, is_mock)
        """
        config = identify_market_config(symbol)
        tencent_stock_code = f"{config.tencent_market}{symbol}"
        tencent_index_code = config.tencent_index

        # 1. 优先尝试腾讯财经极速通道 (支持长达300+个交易日)
        try:
            quote = cls.fetch_tencent_quote(tencent_stock_code)
            stock_name = quote["name"] if quote and quote.get("name") else ""
            stock_klines = cls.fetch_tencent_klines(tencent_stock_code, limit=limit)
            index_klines = cls.fetch_tencent_klines(tencent_index_code, limit=limit)

            if stock_name and len(stock_klines) >= 20 and len(index_klines) >= 20:
                is_intraday = cls.check_is_intraday(stock_klines[-1].date, force_mode)
                return config, stock_name, stock_klines, index_klines, is_intraday, False
        except Exception:
            pass

        # 2. 备用尝试东方财富通道
        try:
            stock_secid = f"{config.stock_prefix}{symbol}"
            index_secid = config.index_secid
            stock_klines = cls.fetch_eastmoney_klines(stock_secid, limit=limit)
            index_klines = cls.fetch_eastmoney_klines(index_secid, limit=limit)

            if len(stock_klines) >= 20 and len(index_klines) >= 20:
                stock_name = f"A股({symbol})"
                is_intraday = cls.check_is_intraday(stock_klines[-1].date, force_mode)
                return config, stock_name, stock_klines, index_klines, is_intraday, False
        except Exception:
            pass

        # 3. 仅在完全离线/沙箱断网时降级到仿真数据
        stock_name, stock_klines, index_klines, is_intraday = cls._generate_mock_klines(symbol, config, limit, force_mode)
        return config, stock_name, stock_klines, index_klines, is_intraday, True

    @classmethod
    def _generate_mock_klines(
        cls, symbol: str, config: MarketConfig, limit: int, force_mode: Optional[str] = None
    ) -> Tuple[str, List[KLineBar], List[KLineBar], bool]:
        """生成符合对应板块走势的仿真K线数据 (长达300+天)"""
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        known_names = {
            "000530": "冰山冷热",
            "300059": "东方财富",
            "300750": "宁德时代",
            "600519": "贵州茅台",
            "601318": "中国平安",
            "000001": "平安银行",
            "002594": "比亚迪",
            "688981": "中芯国际",
        }
        stock_name = known_names.get(symbol, f"股票{symbol}")
        is_intraday = cls.check_is_intraday(today_str, force_mode)

        if config.market_type == MarketType.CYB:
            curr_s = 18.0
            curr_i = 3450.0
        elif config.market_type == MarketType.STAR:
            curr_s = 65.0
            curr_i = 950.0
        elif config.market_type == MarketType.SH_MAIN:
            curr_s = 28.5
            curr_i = 3900.0
        else:
            curr_s = 9.0 if symbol == "000530" else 12.8
            curr_i = 2330.0

        trading_days = []
        d = now.date()
        while len(trading_days) < limit:
            if d.weekday() < 5:
                trading_days.append(d.strftime("%Y-%m-%d"))
            d -= datetime.timedelta(days=1)
        trading_days.reverse()

        stock_bars: List[KLineBar] = []
        index_bars: List[KLineBar] = []

        import random
        rng = random.Random(int(symbol) if symbol.isdigit() else 42)

        for i, dt in enumerate(trading_days):
            s_chg = rng.uniform(-0.02, 0.03)
            i_chg = rng.uniform(-0.008, 0.008)
            
            open_s = curr_s
            close_s = round(curr_s * (1 + s_chg), 2)
            high_s = round(max(open_s, close_s) * (1 + 0.005), 2)
            low_s = round(min(open_s, close_s) * (1 - 0.005), 2)
            pct_s = round(((close_s / open_s) - 1) * 100, 2)
            vol_s = round(rng.uniform(50000, 500000))
            curr_s = close_s

            open_i = curr_i
            close_i = round(curr_i * (1 + i_chg), 2)
            high_i = round(max(open_i, close_i) * (1 + 0.002), 2)
            low_i = round(min(open_i, close_i) * (1 - 0.002), 2)
            pct_i = round(((close_i / open_i) - 1) * 100, 2)
            vol_i = round(rng.uniform(1000000, 5000000))
            curr_i = close_i

            stock_bars.append(KLineBar(date=dt, open=open_s, close=close_s, high=high_s, low=low_s, pct_change=pct_s, volume=vol_s))
            index_bars.append(KLineBar(date=dt, open=open_i, close=close_i, high=high_i, low=low_i, pct_change=pct_i, volume=vol_i))

        return stock_name, stock_bars, index_bars, is_intraday
