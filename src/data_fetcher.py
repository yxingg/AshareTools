# data_fetcher.py - 数据获取模块
"""
数据获取模块
- 实时报价获取（新浪接口）
- K线数据获取（多数据源：东方财富、腾讯、新浪）
"""

import dataclasses
import logging
import time
import contextlib
from typing import List, Optional, Sequence, Dict, Any

import requests
import pandas as pd
from requests.exceptions import RequestException, SSLError

from .utils import normalize_stock_code, split_text, get_market_prefix


@contextlib.contextmanager
def suppress_tqdm():
    """
    临时抑制 tqdm 进度条输出
    通过 monkey patch akshare.utils.tqdm.get_tqdm 来禁用进度条
    """
    try:
        from akshare.utils import tqdm as ak_tqdm
        original_get_tqdm = ak_tqdm.get_tqdm
        
        # 替换为返回透传迭代器的函数
        ak_tqdm.get_tqdm = lambda enable=True: (lambda iterable, *args, **kwargs: iterable)
        
        yield
    except ImportError:
        yield
    finally:
        try:
            ak_tqdm.get_tqdm = original_get_tqdm
        except (NameError, UnboundLocalError):
            pass

logger = logging.getLogger(__name__)


# ==========================================
# 代理屏蔽补丁
# ==========================================
_old_session_init = requests.Session.__init__

def _new_session_init(self, *args, **kwargs):
    _old_session_init(self, *args, **kwargs)
    self.trust_env = False

requests.Session.__init__ = _new_session_init


def _trim_formatted(text: str, suffix: str = "") -> str:
    """格式化数字字符串"""
    if suffix and text.endswith(suffix):
        core = text[: -len(suffix)]
    else:
        core = text
        suffix = ""
    sign = ""
    if core.startswith(("+", "-")):
        sign = core[0]
        core = core[1:]
    if "." in core:
        core = core.rstrip("0").rstrip(".")
    if not core:
        core = "0"
        sign = ""
    return f"{sign}{core}{suffix}"


# ==========================================
# 实时报价数据类
# ==========================================
@dataclasses.dataclass(slots=True)
class StockQuote:
    """股票实时报价"""
    code: str
    name: str
    last_price: float
    prev_close: float
    is_fund: bool = False
    bid1_volume: float = 0.0
    ask1_volume: float = 0.0

    @property
    def change(self) -> float:
        return self.last_price - self.prev_close

    @property
    def change_percent(self) -> float:
        if self.prev_close == 0:
            return 0.0
        return (self.change / self.prev_close) * 100.0

    def as_row(self) -> List[str]:
        price_precision = 3 if self.is_fund else 2
        price_text = _trim_formatted(f"{self.last_price:.{price_precision}f}")
        change_value = _trim_formatted(f"{self.change:+.{price_precision}f}")
        change_pct = _trim_formatted(f"{self.change_percent:+.2f}%", "%")
        return [
            self.name,
            self.code,
            price_text,
            change_value,
            change_pct,
        ]


# ==========================================
# 实时报价获取器（新浪接口）
# ==========================================
try:
    import ssl
    _SSL_AVAILABLE = True
except Exception:
    _SSL_AVAILABLE = False


class QuoteFetcher:
    """实时报价获取器"""
    
    _BASE_URL_HTTPS = "https://hq.sinajs.cn/list="
    _BASE_URL_HTTP = "http://hq.sinajs.cn/list="
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.sina.com.cn",
    }

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(self._HEADERS)
        self._session.trust_env = False
        self._use_https = _SSL_AVAILABLE
        if not self._use_https:
            logger.warning("SSL 模块不可用，行情接口将改用 HTTP。")

    def fetch(self, raw_codes: Sequence[str]) -> List[StockQuote]:
        """获取多个股票的实时报价"""
        normalized_order: List[str] = []
        normalized_seen = set()
        alias_map: dict[str, str] = {}
        query_codes: List[str] = []
        query_seen = set()
        fund_flags: dict[str, bool] = {}

        for code in raw_codes:
            normalized = normalize_stock_code(code)
            if not normalized:
                continue
            if normalized not in normalized_seen:
                normalized_seen.add(normalized)
                normalized_order.append(normalized)

            variants = self._code_variants(normalized)
            if self._is_likely_fund(normalized):
                fund_flags[normalized] = True
            for variant in variants:
                if variant not in query_seen:
                    query_seen.add(variant)
                    query_codes.append(variant)
                alias_map.setdefault(variant, normalized)
                if self._is_likely_fund(variant):
                    fund_flags[normalized] = True

        if not query_codes:
            return []

        suffix = ",".join(query_codes)
        response = None

        if self._use_https:
            try:
                response = self._session.get(self._BASE_URL_HTTPS + suffix, timeout=5)
                response.raise_for_status()
            except SSLError as exc:
                logger.warning("HTTPS 请求失败，自动切换为 HTTP：%s", exc)
                self._use_https = False
                response = None
            except RequestException as exc:
                logger.warning("fetch quotes failed: %s", exc)
                raise

        if response is None:
            try:
                response = self._session.get(self._BASE_URL_HTTP + suffix, timeout=5)
                response.raise_for_status()
            except RequestException as exc:
                logger.warning("fetch quotes failed: %s", exc)
                raise

        payload = response.text
        raw_quotes = self._parse_payload(payload)

        mapped: dict[str, StockQuote] = {}
        for quote in raw_quotes:
            normalized_code = alias_map.get(quote.code, quote.code)
            adjusted = dataclasses.replace(
                quote,
                code=normalized_code,
                is_fund=quote.is_fund or fund_flags.get(normalized_code, False),
            )
            if normalized_code not in mapped:
                mapped[normalized_code] = adjusted

        return [mapped[code] for code in normalized_order if code in mapped]

    def _code_variants(self, normalized: str) -> List[str]:
        """生成代码变体（用于查询）"""
        variants = []
        if normalized.startswith("hk"):
            variants.append(f"rt_{normalized}")
        variants.append(normalized)

        if normalized.startswith(("sh", "sz")) and len(normalized) == 8 and normalized[2:].isdigit():
            digits = normalized[2:]
            variants.extend([f"f_{digits}", f"of{digits}"])
        elif normalized.startswith("f_") and len(normalized) == 8 and normalized[2:].isdigit():
            digits = normalized[2:]
            variants.append(f"of{digits}")
            if digits.startswith("6"):
                variants.append(f"sh{digits}")
            else:
                variants.append(f"sz{digits}")
        elif normalized.startswith("of") and len(normalized) == 8 and normalized[2:].isdigit():
            digits = normalized[2:]
            variants.append(f"f_{digits}")
            if digits.startswith("6"):
                variants.append(f"sh{digits}")
            else:
                variants.append(f"sz{digits}")

        return variants

    def _is_likely_fund(self, code: str) -> bool:
        """判断是否为基金代码"""
        code = code.lower()
        if code.startswith(("f_", "of")):
            return True
        if code.startswith(("sh", "sz")) and len(code) == 8 and code[2:].isdigit():
            digits = code[2:]
            return digits.startswith(("15", "16", "50", "51", "56"))
        return False

    def _parse_payload(self, text: str) -> List[StockQuote]:
        """解析新浪接口返回数据"""
        quotes: List[StockQuote] = []
        for block in split_text(text, "var hq_str_"):
            if not block:
                continue
            key, _, data = block.partition("=")
            key = key.strip()
            data = data.strip().strip('"').strip(";").strip('"')
            if not data:
                continue

            parts = data.split(",")
            quote = self._parse_parts(key, parts)
            if quote:
                quotes.append(quote)

        return quotes

    def _parse_parts(self, key: str, parts: List[str]) -> Optional[StockQuote]:
        """解析单条数据"""
        try:
            if key.startswith(("sh", "sz", "bj")):
                # A股格式
                if len(parts) < 32:
                    return None
                return StockQuote(
                    code=key,
                    name=parts[0],
                    last_price=float(parts[3]) if parts[3] else 0.0,
                    prev_close=float(parts[2]) if parts[2] else 0.0,
                    bid1_volume=float(parts[10]) if parts[10] else 0.0,
                    ask1_volume=float(parts[20]) if parts[20] else 0.0,
                )
            elif key.startswith("rt_hk"):
                # 港股实时
                if len(parts) < 18:
                    return None
                return StockQuote(
                    code=key.replace("rt_", ""),
                    name=parts[1],
                    last_price=float(parts[6]) if parts[6] else 0.0,
                    prev_close=float(parts[3]) if parts[3] else 0.0,
                )
            elif key.startswith("hk"):
                # 港股延迟
                if len(parts) < 18:
                    return None
                return StockQuote(
                    code=key,
                    name=parts[1],
                    last_price=float(parts[6]) if parts[6] else 0.0,
                    prev_close=float(parts[3]) if parts[3] else 0.0,
                )
            elif key.startswith(("f_", "of")):
                # 基金
                if len(parts) < 5:
                    return None
                return StockQuote(
                    code=key,
                    name=parts[0],
                    last_price=float(parts[1]) if parts[1] else 0.0,
                    prev_close=float(parts[2]) if parts[2] else 0.0,
                    is_fund=True,
                )
            else:
                # 美股等
                if len(parts) < 4:
                    return None
                return StockQuote(
                    code=key,
                    name=parts[0],
                    last_price=float(parts[1]) if parts[1] else 0.0,
                    prev_close=float(parts[26]) if len(parts) > 26 and parts[26] else 0.0,
                )
        except (ValueError, IndexError) as e:
            logger.debug(f"解析报价失败 {key}: {e}")
            return None


# ==========================================
# K线数据获取器（多数据源）
# ==========================================
class KLineFetcher:
    """K线数据获取器"""
    
    def __init__(self, symbol: str, period: str = "1", preferred_source: str = 'em'):
        self.symbol = symbol
        self.period = period
        self.preferred_source = preferred_source
        self.sources = ['em', 'tx', 'sina']
        
        # 判断证券类型
        from .utils import get_security_type
        self.security_type = get_security_type(symbol)  # 股、基、债

    def fetch_latest(self) -> Optional[pd.DataFrame]:
        """获取最新K线数据"""
        try_order = [self.preferred_source] + [s for s in self.sources if s != self.preferred_source]
        
        last_error = None
        for source in try_order:
            try:
                df = None
                if source == 'tx':
                    df = self._fetch_from_tx()
                elif source == 'sina':
                    df = self._fetch_from_sina()
                else:
                    df = self._fetch_from_em()
                    
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                last_error = e
                continue
        
        if last_error:
            logger.warning(f"获取K线数据失败 {self.symbol}: {last_error}")
            
        return None

    def fetch_snapshot(self) -> Optional[Dict[str, Any]]:
        """获取实时快照数据"""
        try:
            return self._fetch_snapshot_from_em()
        except Exception as e:
            logger.debug(f"获取快照失败 {self.symbol}: {e}")
            return None

    def _get_market_code(self) -> tuple:
        """获取市场代码"""
        return get_market_prefix(self.symbol)

    def _fetch_from_sina(self) -> Optional[pd.DataFrame]:
        """从新浪获取K线数据"""
        market_prefix, code = self._get_market_code()
        full_code = f"{market_prefix}{code}" if market_prefix else code
        
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={full_code}&scale={self.period}&ma=no&datalen=500"
        
        for i in range(3):
            try:
                session = requests.Session()
                session.trust_env = False
                resp = session.get(url, timeout=5)
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                if not data:
                    return None
                
                rows = []
                for line in data:
                    rows.append({
                        'time': pd.to_datetime(line['day']),
                        'open': float(line['open']),
                        'close': float(line['close']),
                        'high': float(line['high']),
                        'low': float(line['low']),
                        'volume': float(line['volume'])
                    })
                
                return pd.DataFrame(rows)
                
            except Exception as e:
                if i == 2:
                    raise e
                time.sleep(1)
        return None

    def _fetch_from_tx(self) -> Optional[pd.DataFrame]:
        """从腾讯获取K线数据"""
        market_prefix, code = self._get_market_code()
        full_code = f"{market_prefix}{code}" if market_prefix else code
        
        period_map = {'1': 'm1', '5': 'm5', '15': 'm15', '30': 'm30', '60': 'm60'}
        tx_period = period_map.get(self.period, 'm5')
        
        url = f"http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={full_code},{tx_period},,500"
        
        for i in range(3):
            try:
                session = requests.Session()
                session.trust_env = False
                resp = session.get(url, timeout=5)
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                if not data or 'data' not in data:
                    return None
                
                stock_data = data['data'].get(full_code, {})
                kline_data = stock_data.get(tx_period, [])
                
                if not kline_data:
                    return None
                
                rows = []
                for line in kline_data:
                    rows.append({
                        'time': pd.to_datetime(line[0]),
                        'open': float(line[1]),
                        'close': float(line[2]),
                        'high': float(line[3]),
                        'low': float(line[4]),
                        'volume': float(line[5]) if len(line) > 5 else 0
                    })
                
                return pd.DataFrame(rows)
                
            except Exception as e:
                if i == 2:
                    raise e
                time.sleep(1)
        return None

    def _fetch_from_em(self) -> Optional[pd.DataFrame]:
        """从东方财富获取K线数据"""
        import sys
        from io import StringIO
        
        try:
            import akshare as ak
            
            # 转换周期
            period_map = {'1': '1', '5': '5', '15': '15', '30': '30', '60': '60'}
            ak_period = period_map.get(self.period, '5')
            
            # 获取完整代码和纯数字代码
            if self.symbol[:2] in ('sh', 'sz', 'bj'):
                full_code = self.symbol
                pure_code = self.symbol[2:]
            else:
                pure_code = self.symbol
                # 根据代码判断市场
                if pure_code.startswith(('6', '11')):
                    full_code = f"sh{pure_code}"
                else:
                    full_code = f"sz{pure_code}"
            
            df = None
            
            if self.security_type == '基':
                # ETF 使用专用接口
                df = ak.fund_etf_hist_min_em(symbol=pure_code, period=ak_period)
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '时间': 'time',
                        '开盘': 'open',
                        '收盘': 'close',
                        '最高': 'high',
                        '最低': 'low',
                        '成交量': 'volume'
                    })
            elif self.security_type == '债':
                # 可转债使用专用接口
                df = ak.bond_zh_hs_cov_min(symbol=full_code, period=ak_period)
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '时间': 'time',
                        '开盘': 'open',
                        '收盘': 'close',
                        '最高': 'high',
                        '最低': 'low',
                        '成交量': 'volume'
                    })
            else:
                # 股票使用股票接口（抑制akshare的stdout输出）
                old_stdout = sys.stdout
                sys.stdout = StringIO()
                try:
                    df = ak.stock_zh_a_minute(symbol=full_code, period=ak_period)
                finally:
                    sys.stdout = old_stdout
                    
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        'day': 'time',
                        'open': 'open',
                        'close': 'close',
                        'high': 'high',
                        'low': 'low',
                        'volume': 'volume'
                    })
            
            if df is not None and not df.empty:
                df['time'] = pd.to_datetime(df['time'])
                return df
                
        except Exception as e:
            logger.debug(f"东方财富接口失败: {e}")
        
        return None

    def _fetch_snapshot_from_em(self) -> Optional[Dict[str, Any]]:
        """
        从东方财富获取单只股票/ETF/可转债的快照数据
        使用单股接口而非批量接口，避免每次下载全部列表
        """
        try:
            import datetime
            
            # 获取纯数字代码
            pure_code = self.symbol[2:] if self.symbol[:2] in ('sh', 'sz', 'bj') else self.symbol
            
            # 确定市场代码：沪市=1，深市=0，北交所=0
            # 沪市：6开头(股票), 5开头(ETF/基金), 11开头(可转债)
            # 深市：0/3开头(股票), 1开头(ETF/基金), 12开头(可转债)
            if self.symbol.startswith('sh'):
                market = '1'
            elif self.symbol.startswith('sz') or self.symbol.startswith('bj'):
                market = '0'
            elif pure_code.startswith(('6', '5', '11')):
                market = '1'
            else:
                market = '0'
            
            # 东方财富单股实时行情接口（统一接口，支持股票/ETF/可转债）
            url = 'https://push2.eastmoney.com/api/qt/stock/get'
            params = {
                'secid': f'{market}.{pure_code}',
                # f43=最新价, f44=最高, f45=最低, f46=开盘, f47=成交量, f48=成交额
                # f51=涨停价, f52=跌停价, f57=代码, f58=名称, f60=昨收
                # f19=买一价, f20=买一量, f17=卖一价, f18=卖一量
                'fields': 'f43,f44,f45,f46,f47,f48,f51,f52,f57,f58,f60,f19,f20,f17,f18',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
            }
            
            r = requests.get(url, params=params, timeout=5)
            data = r.json()
            
            if data.get('rc') != 0 or not data.get('data'):
                return None
            
            d = data['data']
            
            # 东财返回的价格单位是"分"，需要除以100转换为"元"
            price = (d.get('f43', 0) or 0) / 100
            high_limit = (d.get('f51', 0) or 0) / 100
            low_limit = (d.get('f52', 0) or 0) / 100
            
            return {
                'time': datetime.datetime.now().strftime('%H:%M:%S'),
                'price': float(price),
                'high_limit': float(high_limit) if self.security_type == '股' else 0,
                'low_limit': float(low_limit) if self.security_type == '股' else 0,
                'bid1_vol': float(d.get('f20', 0) or 0),  # 买一量
                'ask1_vol': float(d.get('f18', 0) or 0),  # 卖一量
                'volume': float(d.get('f47', 0) or 0),
            }
            
        except Exception as e:
            logger.debug(f"获取快照失败: {e}")
            return None


# ==========================================
# 股票名称管理器
# ==========================================
class StockNameManager:
    """
    股票信息管理器 - 缓存股票名称、类型、市场等信息
    
    stock_names.json 结构:
    {
        "timestamp": 1234567890,
        "stocks": {
            "600519": {"name": "贵州茅台", "type": "股", "market": "沪"},
            "510300": {"name": "沪深300ETF", "type": "基", "market": "沪"},
            "113050": {"name": "南银转债", "type": "债", "market": "沪"},
            ...
        }
    }
    """
    
    _instance = None  # 单例
    
    @classmethod
    def get_instance(cls, logger=None, cache_file: str = None):
        """获取单例实例"""
        if cls._instance is None and logger and cache_file:
            cls._instance = cls(logger, cache_file)
        return cls._instance
    
    def __init__(self, logger, cache_file: str, target_symbols: List[str] = None):
        self.logger = logger
        self.cache_file = cache_file
        self.stocks: Dict[str, Dict[str, str]] = {}  # symbol -> {name, type, market}
        self.target_symbols = target_symbols or []
        self._load_cache()
        
        # 设置单例
        StockNameManager._instance = self
        
        # 检查缺失的symbol
        if target_symbols:
            self._check_and_fetch(target_symbols)

    def _load_cache(self):
        """加载缓存"""
        import os
        import json
        
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 兼容旧格式
                    if 'stocks' in data:
                        self.stocks = data.get('stocks', {})
                    elif 'names' in data:
                        # 迁移旧格式
                        old_names = data.get('names', {})
                        old_types = data.get('types', {})
                        for symbol, name in old_names.items():
                            self.stocks[symbol] = {
                                'name': name,
                                'type': old_types.get(symbol, '股'),
                                'market': self._get_market_from_code(symbol)
                            }
                        # 保存为新格式
                        self._save_cache()
                    self.logger.info(f"已加载股票信息缓存，共 {len(self.stocks)} 条")
            except Exception as e:
                self.logger.error(f"读取缓存失败: {e}")

    def _get_market_from_code(self, code: str) -> str:
        """根据代码获取市场"""
        from .utils import get_market_short_name
        return get_market_short_name(code)

    def _check_and_fetch(self, symbols: List[str]):
        """检查并获取缺失的股票信息"""
        missing = []
        for s in symbols:
            # 使用 _get_cached_info 统一检查（支持双向格式兼容）
            if self._get_cached_info(s) is None:
                missing.append(s)
        if missing:
            self._fetch_and_update(missing)

    def _fetch_single_stock_name(self, symbol: str, pure_code: str) -> Optional[Dict[str, str]]:
        """
        使用东财单股接口获取股票/ETF/可转债名称
        这是一个轻量级接口，不会下载全部列表
        """
        try:
            # 确定市场代码
            if symbol.startswith('sh'):
                market = '1'
            elif symbol.startswith('sz') or symbol.startswith('bj'):
                market = '0'
            elif pure_code.startswith(('6', '5', '11')):
                market = '1'
            else:
                market = '0'
            
            # 东财单股接口
            url = 'https://push2.eastmoney.com/api/qt/stock/get'
            params = {
                'secid': f'{market}.{pure_code}',
                'fields': 'f57,f58',  # f57=代码, f58=名称
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b'
            }
            
            r = requests.get(url, params=params, timeout=5)
            data = r.json()
            
            if data.get('rc') != 0 or not data.get('data'):
                return None
            
            d = data['data']
            name = d.get('f58', '')
            if not name:
                return None
            
            # 判断证券类型
            if pure_code.startswith(('51', '58', '15', '16')):
                sec_type = '基'
            elif pure_code.startswith(('11', '12')):
                sec_type = '债'
            else:
                sec_type = '股'
            
            return {
                'name': name,
                'type': sec_type,
                'market': self._get_market_from_code(symbol)
            }
            
        except Exception as e:
            self.logger.debug(f"查询 {symbol} 名称失败: {e}")
            return None

    def _fetch_and_update(self, missing_symbols: List[str]):
        """
        获取并更新股票信息 - 逐个查询
        使用东财单股接口，不再批量下载全部列表
        """
        if not missing_symbols:
            return
            
        new_stocks = {}
        
        for symbol in missing_symbols:
            pure_code = symbol[2:] if symbol[:2] in ('sh', 'sz', 'bj') else symbol
            
            # 使用单股接口查询名称
            info = self._fetch_single_stock_name(symbol, pure_code)
            if info:
                new_stocks[symbol] = info
                self.logger.debug(f"已获取 {symbol} 信息: {info['name']}")
        
        if new_stocks:
            self.stocks.update(new_stocks)
            self.logger.info(f"本次共更新 {len(new_stocks)} 条股票信息")
            self._save_cache()

    def _save_cache(self):
        """保存缓存"""
        import json
        import datetime
        
        cache_data = {
            'timestamp': datetime.datetime.now().timestamp(),
            'stocks': self.stocks
        }
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存缓存失败: {e}")

    def _get_cached_info(self, symbol: str) -> Optional[Dict[str, str]]:
        """获取缓存信息，兼容带前缀和不带前缀的格式"""
        # 1. 直接查找完整代码
        if symbol in self.stocks:
            return self.stocks[symbol]
        
        # 2. 如果是带前缀的，尝试纯数字代码
        pure_code = symbol[2:] if symbol[:2] in ('sh', 'sz', 'bj') else symbol
        if pure_code != symbol and pure_code in self.stocks:
            return self.stocks[pure_code]
        
        # 3. 如果是纯数字的，尝试添加前缀查找
        if symbol[:2] not in ('sh', 'sz', 'bj'):
            # 尝试添加不同的前缀
            for prefix in ('sh', 'sz'):
                full_code = f"{prefix}{symbol}"
                if full_code in self.stocks:
                    return self.stocks[full_code]
        
        return None
    
    def get_name(self, symbol: str) -> str:
        """获取股票名称"""
        info = self._get_cached_info(symbol)
        return info.get('name', symbol) if info else symbol
    
    def get_type(self, symbol: str) -> str:
        """获取证券类型（股/基/债）"""
        info = self._get_cached_info(symbol)
        return info.get('type', '股') if info else '股'
    
    def get_market(self, symbol: str) -> str:
        """获取市场（沪/深/京等）"""
        info = self._get_cached_info(symbol)
        if info and 'market' in info:
            return info['market']
        return self._get_market_from_code(symbol)
    
    def get_info(self, symbol: str) -> Dict[str, str]:
        """获取完整股票信息"""
        info = self._get_cached_info(symbol)
        if info:
            return info
        return {
            'name': symbol,
            'type': '股',
            'market': self._get_market_from_code(symbol)
        }
    
    def ensure_symbols(self, symbols: List[str]):
        """确保指定的股票代码都有缓存信息"""
        self._check_and_fetch(symbols)
