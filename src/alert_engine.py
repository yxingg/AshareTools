# alert_engine.py - 预警监控引擎
"""
预警监控引擎
负责策略计算和信号推送
"""

import logging
import time
import importlib.util
import threading
from typing import Dict, List, Optional, Callable, Any

from .config import (
    STRATEGIES_FILE,
    DEFAULT_SCAN_INTERVAL, AVAILABLE_DATA_SOURCES
)
from .constants import DEFAULT_GOLD_TARGETS
from .data_fetcher import KLineFetcher, StockNameManager, GoldQuoteFetcher
from .indicators import calculate_indicators
from .scheduler import TradingScheduler

logger = logging.getLogger(__name__)


class StrategyLoader:
    """策略动态加载器"""
    
    def __init__(self):
        self._module = None
        self._last_load_time = 0
        self._strategies_info = {}
        self._Strategy_class = None
        self.load()

    def load(self) -> bool:
        """加载或重载策略文件"""
        try:
            strategies_path = str(STRATEGIES_FILE)
            
            # 加载模块
            spec = importlib.util.spec_from_file_location("strategies_dynamic", strategies_path)
            if spec is None or spec.loader is None:
                logger.error(f"无法加载策略文件: {strategies_path}")
                return False
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            self._module = module
            self._last_load_time = time.time()
            
            # 获取策略信息
            if hasattr(module, 'get_all_strategies_info'):
                self._strategies_info = module.get_all_strategies_info()
            elif hasattr(module, 'STRATEGIES'):
                self._strategies_info = module.STRATEGIES.copy()
            else:
                self._strategies_info = {}
            
            # 获取策略类
            if hasattr(module, 'Strategy'):
                self._Strategy_class = module.Strategy
            else:
                self._Strategy_class = None
                
            logger.info(f"策略文件加载成功，共 {len(self._strategies_info)} 个策略")
            return True
            
        except Exception as e:
            logger.error(f"加载策略文件失败: {e}")
            return False

    def reload(self) -> bool:
        """重载策略文件"""
        return self.load()

    def get_strategy_list(self) -> List[str]:
        """获取所有策略ID列表"""
        return list(self._strategies_info.keys())

    def get_strategy_info(self, strategy_id: str) -> Optional[Dict]:
        """获取策略详细信息"""
        return self._strategies_info.get(strategy_id)

    def get_all_strategies_info(self) -> Dict:
        """获取所有策略信息"""
        return self._strategies_info.copy()

    def create_strategy(self, strategy_id: str):
        """创建策略实例"""
        if self._Strategy_class is None:
            return None
        try:
            return self._Strategy_class(strategy_id)
        except Exception as e:
            logger.error(f"创建策略实例失败 {strategy_id}: {e}")
            return None


class AlertEngine:
    """预警监控引擎"""
    
    def __init__(self, notifier=None, on_signal: Callable = None):
        """
        初始化预警引擎
        
        Args:
            notifier: 钉钉通知器实例
            on_signal: 信号回调函数 (symbol, strategy, signal, message)
        """
        self.notifier = notifier
        self.on_signal = on_signal
        self.logger = logging.getLogger(__name__)
        
        self.strategy_loader = StrategyLoader()
        self.scheduler = TradingScheduler(self.logger)
        
        # 任务列表
        self.tasks: List[Dict] = []
        self.scan_interval = DEFAULT_SCAN_INTERVAL
        self.gold_tasks: List[Dict[str, Any]] = []
        self.gold_scan_interval = DEFAULT_SCAN_INTERVAL
        self._gold_last_scan_time = 0.0
        self.gold_fetcher = GoldQuoteFetcher()
        self._gold_target_names = {
            t.get('key', ''): t.get('name', t.get('key', ''))
            for t in DEFAULT_GOLD_TARGETS
            if t.get('key')
        }
        
        # 数据获取器
        self.data_fetchers: Dict[tuple, Dict] = {}
        
        # 股票名称管理器
        self.name_manager: Optional[StockNameManager] = None
        
        # 运行状态
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def update_tasks(
        self,
        tasks: List[Dict],
        scan_interval: int = None,
        gold_tasks: Optional[List[Dict]] = None,
        gold_scan_interval: Optional[int] = None,
    ):
        """
        更新预警任务
        
        Args:
            tasks: 任务列表 [{"symbol": "600519", "strategy": "MA_TREND", "period": "5"}, ...]
            scan_interval: 股票预警扫描间隔（秒）
            gold_tasks: 黄金预警任务列表
            gold_scan_interval: 黄金预警扫描间隔（秒）
        """
        self.tasks = []
        self.data_fetchers = {}
        
        if scan_interval:
            self.scan_interval = scan_interval
        if gold_scan_interval:
            self.gold_scan_interval = max(1, int(gold_scan_interval))
        
        enabled_tasks = [t for t in (tasks or []) if bool(t.get('enabled', True))]

        # 提取所有 symbol
        target_symbols = list(set([t['symbol'] for t in enabled_tasks]))
        
        # 使用全局名称管理器单例（确保缓存已有对应symbol）
        self.name_manager = StockNameManager.get_instance()
        if self.name_manager and target_symbols:
            self.name_manager.ensure_symbols(target_symbols)
        
        # 按 symbol + period 去重创建数据获取器
        unique_keys = set()
        for task in enabled_tasks:
            key = (task['symbol'], task.get('period', '5'))
            unique_keys.add(key)
        
        # 分配数据源
        source_index = 0
        for key in unique_keys:
            symbol, period = key
            preferred_source = AVAILABLE_DATA_SOURCES[source_index % len(AVAILABLE_DATA_SOURCES)]
            
            self.data_fetchers[key] = {
                'fetcher': KLineFetcher(symbol, period, preferred_source),
                'data': None,
                'snapshot': None,
                'last_fetch_time': None,
                'consecutive_errors': 0,
                'interval': self.scan_interval,
            }
            
            # 涨跌停预警使用更快的轮询
            for t in enabled_tasks:
                if t['symbol'] == symbol and t.get('strategy') == 'LIMIT_BOARD_WARNING':
                    self.data_fetchers[key]['interval'] = 1
                    
            source_index += 1
            self.logger.info(f"数据源加载: {symbol} - {period}分 (首选: {preferred_source})")

        # 创建任务
        seen_tasks = set()
        for task in enabled_tasks:
            task_id = (task['symbol'], task['strategy'], task.get('period', '5'))
            
            if task_id in seen_tasks:
                continue
            seen_tasks.add(task_id)
            
            strategy = self.strategy_loader.create_strategy(task['strategy'])
            if strategy is None:
                self.logger.warning(f"未知策略: {task['strategy']}")
                continue
            
            self.tasks.append({
                'config': task,
                'strategy': strategy,
                'data_key': (task['symbol'], task.get('period', '5')),
                'last_time': None,
                'position': 0
            })

        # 黄金价格预警任务
        self.gold_tasks = []
        for task in (gold_tasks or []):
            target = str(task.get('target', '')).strip()
            if not target:
                continue
            try:
                price = float(task.get('price', 0) or 0)
            except Exception:
                continue
            if price <= 0:
                continue
            try:
                frequency = int(task.get('frequency', 0) or 0)
            except Exception:
                frequency = 0
            enabled = bool(task.get('enabled', True))
            config = {
                'target': target,
                'price': price,
                'frequency': max(0, frequency),
                'enabled': enabled,
            }
            self.gold_tasks.append({
                'config': config,
                'active': enabled,
                'auto_rearm': False,
                'next_rearm_time': 0.0,
            })
        
        self._gold_last_scan_time = 0.0
        self.logger.info(f"预警任务更新完成，股票任务 {len(self.tasks)} 个，黄金任务 {len(self.gold_tasks)} 个")

    def get_gold_tasks_snapshot(self) -> List[Dict[str, Any]]:
        """获取黄金任务当前运行状态快照（用于界面刷新）"""
        result: List[Dict[str, Any]] = []
        for task in self.gold_tasks:
            cfg = dict(task.get('config', {}))
            cfg['enabled'] = bool(task.get('active', cfg.get('enabled', True)))
            result.append(cfg)
        return result

    def reload_strategies(self) -> bool:
        """重载策略文件"""
        success = self.strategy_loader.reload()
        if success:
            # 重新创建策略实例
            for task in self.tasks:
                strategy_name = task['config']['strategy']
                new_strategy = self.strategy_loader.create_strategy(strategy_name)
                if new_strategy:
                    task['strategy'] = new_strategy
        return success

    def get_available_strategies(self) -> Dict:
        """获取可用策略列表"""
        return self.strategy_loader.get_all_strategies_info()

    def start(self):
        """启动预警引擎"""
        if self._running:
            return
        
        if not self.tasks and not self.gold_tasks:
            self.logger.info("没有预警任务，跳过启动")
            return
        
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("预警引擎已启动")
        
        # 发送启动消息（包含当前状态）
        is_trading = self.scheduler.is_trading_time()
        if is_trading:
            start_msg = (
                f"【系统启动】\n智能监控已启动\n当前状态: 交易中\n"
                f"股票监控标的数: {len(self.data_fetchers)}\n股票策略任务数: {len(self.tasks)}\n"
                f"黄金预警任务数: {len(self.gold_tasks)}"
            )
        else:
            sleep_sec, reason, target_time = self.scheduler.calculate_sleep_seconds()
            start_msg = (
                f"【系统启动】\n智能监控已启动\n当前状态: 休市\n原因: {reason}\n预计开盘: {target_time}\n"
                f"股票监控标的数: {len(self.data_fetchers)}\n股票策略任务数: {len(self.tasks)}\n"
                f"黄金预警任务数: {len(self.gold_tasks)}"
            )
        
        self.logger.info(start_msg.replace('\n', ' '))
        if self.notifier:
            self.notifier.send(start_msg)

    def stop(self):
        """停止预警引擎"""
        if not self._running and self._thread is None:
            return

        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                self.logger.warning("预警线程未在超时时间内退出")
        self._thread = None

        self.logger.info("预警引擎已停止")
        # 注意：关闭预警时不推送任何消息

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    def _run_loop(self):
        """主循环"""
        # 标记当前状态，用于检测状态切换
        was_in_trading = self.scheduler.is_trading_time()
        
        while self._running:
            try:
                is_trading = self.scheduler.is_trading_time()
                
                # 检测状态切换：从交易中 -> 休市
                if was_in_trading and not is_trading:
                    sleep_sec, reason, target_time = self.scheduler.calculate_sleep_seconds()
                    sleep_msg = f"【系统休眠】\n原因: {reason}\n预计唤醒: {target_time}\n休眠时长: {sleep_sec/3600:.1f}小时"
                    self.logger.info(sleep_msg.replace('\n', ' '))
                    if self.notifier:
                        self.notifier.send(sleep_msg)
                
                # 检测状态切换：从休市 -> 交易中
                if not was_in_trading and is_trading:
                    wake_msg = f"【系统唤醒】\n当前时间: {self.scheduler.get_now()}\n开始监控..."
                    self.logger.info("系统唤醒")
                    if self.notifier:
                        self.notifier.send(wake_msg)
                
                was_in_trading = is_trading
                
                if not is_trading and not self.gold_tasks:
                    # 非交易时间，休眠等待
                    sleep_sec, _, _ = self.scheduler.calculate_sleep_seconds()
                    # 分段休眠，以便能够响应停止信号
                    for _ in range(int(min(sleep_sec, 60))):  # 最多休眠60秒后重新检查
                        if not self._running or self._stop_event.wait(timeout=1):
                            return
                    continue
                
                # 执行一轮扫描：股票仅在交易时段，黄金按自身间隔执行
                self._scan_once(is_trading)

                # 统一按 1 秒节拍循环，具体频率由各任务内部 interval 控制
                if not self._running or self._stop_event.wait(timeout=1):
                    return
                    
            except Exception as e:
                self.logger.error(f"预警循环异常: {e}")
                if self._stop_event.wait(timeout=5):
                    return

    def _scan_once(self, is_trading: bool = True):
        """执行一轮扫描"""
        if not self.tasks and not self.gold_tasks:
            return
        
        current_time = time.time()

        # 黄金价格预警（不依赖 A 股交易时段）
        self._scan_gold_alerts(current_time)

        if not is_trading or not self.tasks:
            return
        
        # 阶段1: 获取数据
        for key, fetcher_info in self.data_fetchers.items():
            try:
                interval = fetcher_info.get('interval', self.scan_interval)
                last_time = fetcher_info.get('last_fetch_time')
                
                if last_time and (current_time - last_time) < interval:
                    continue
                
                fetcher = fetcher_info['fetcher']
                
                # 获取 K 线数据
                df = fetcher.fetch_latest()
                if df is not None and not df.empty:
                    df = calculate_indicators(df)
                    fetcher_info['data'] = df
                    fetcher_info['consecutive_errors'] = 0
                else:
                    fetcher_info['consecutive_errors'] += 1
                
                # 获取快照（用于涨跌停预警）
                snapshot = fetcher.fetch_snapshot()
                fetcher_info['snapshot'] = snapshot
                
                fetcher_info['last_fetch_time'] = current_time
                
            except Exception as e:
                self.logger.warning(f"获取数据失败 {key}: {e}")
                fetcher_info['consecutive_errors'] += 1

        # 阶段2: 执行策略
        for task in self.tasks:
            try:
                data_key = task['data_key']
                fetcher_info = self.data_fetchers.get(data_key)
                
                if not fetcher_info:
                    continue
                
                df = fetcher_info['data']
                snapshot = fetcher_info['snapshot']
                strategy = task['strategy']
                
                if df is None or df.empty:
                    continue
                
                # 取最新一行
                row = df.iloc[-1].to_dict()
                
                # 检查信号
                signal = strategy.check_signal(
                    row, 
                    task['position'], 
                    snapshot=snapshot, 
                    df=df
                )
                
                if signal:
                    self._handle_signal(task, signal)
                    
            except Exception as e:
                self.logger.warning(f"策略执行失败 {task['config']}: {e}")

    def _scan_gold_alerts(self, current_time: float) -> None:
        """执行黄金价格预警扫描"""
        if not self.gold_tasks:
            return

        # 检查黄金预警时间窗口：周一6:00 - 周六4:45
        is_in_gold_time_window = self.scheduler.is_gold_alert_time()
        
        # 如果不在时间窗口内，强制暂停所有活跃的黄金任务
        if not is_in_gold_time_window:
            # 检查是否有任务需要暂停
            has_active_tasks = any(task.get('active', False) for task in self.gold_tasks)
            if has_active_tasks:
                for task in self.gold_tasks:
                    if task.get('active', False):
                        task['active'] = False
                        task['auto_rearm'] = False
                        task['next_rearm_time'] = 0.0
                        cfg = task.get('config', {})
                        cfg['enabled'] = False
                
                # 记录暂停信息
                now_str = self.scheduler.get_now().strftime('%Y-%m-%d %H:%M:%S')
                self.logger.info(f"黄金预警时间窗口外 ({now_str})，已暂停所有黄金预警任务")
            
            # 时间窗口外不执行扫描
            return

        if (current_time - self._gold_last_scan_time) < max(1, int(self.gold_scan_interval)):
            return
        self._gold_last_scan_time = current_time

        # 自动重启已到期任务
        for task in self.gold_tasks:
            if task.get('active', False):
                continue
            if not task.get('auto_rearm', False):
                continue
            if current_time >= float(task.get('next_rearm_time', 0.0)):
                task['active'] = True
                task['auto_rearm'] = False
                task['next_rearm_time'] = 0.0
                task['config']['enabled'] = True

        active_targets = {
            task['config']['target']
            for task in self.gold_tasks
            if task.get('active', False)
        }
        if not active_targets:
            return

        try:
            quotes = self.gold_fetcher.fetch(self._gold_target_names, list(active_targets))
        except Exception as e:
            self.logger.warning(f"黄金预警行情获取失败: {e}")
            return

        quote_map = {q.key: q for q in quotes}
        for task in self.gold_tasks:
            if not task.get('active', False):
                continue
            cfg = task.get('config', {})
            target = cfg.get('target', '')
            quote = quote_map.get(target)
            if quote is None:
                continue

            threshold = float(cfg.get('price', 0) or 0)
            if threshold <= 0:
                continue
            current_price = float(quote.last_price)

            # 达到阈值即触发
            if current_price < threshold:
                continue

            freq_min = int(cfg.get('frequency', 0) or 0)
            target_name = self._gold_target_names.get(target, target)
            msg = (
                f"【黄金价格预警】\n"
                f"标的: {target_name}({target})\n"
                f"当前价格: {current_price:.4f}\n"
                f"预警价格: {threshold:.4f}\n"
                f"频率: {freq_min} 分钟"
            )
            self.logger.info(f"触发黄金预警: {target} 当前 {current_price} 阈值 {threshold}")
            if self.notifier:
                self.notifier.send(msg)
            if self.on_signal:
                try:
                    self.on_signal(target, 'GOLD_PRICE_ALERT', 'TRIGGER', msg)
                except Exception as e:
                    self.logger.warning(f"黄金预警回调失败: {e}")

            if freq_min <= 0:
                task['active'] = False
                task['auto_rearm'] = False
                task['next_rearm_time'] = 0.0
                cfg['enabled'] = False
            else:
                task['active'] = False
                task['auto_rearm'] = True
                task['next_rearm_time'] = current_time + (freq_min * 60)
                cfg['enabled'] = False

    def _handle_signal(self, task: Dict, signal: str):
        """处理信号"""
        import datetime
        
        config = task['config']
        symbol = config['symbol']
        strategy_name = config['strategy']
        period = config.get('period', '5')
        
        # 获取股票名称
        stock_name = symbol
        if self.name_manager:
            stock_name = self.name_manager.get_name(symbol)
        
        # 获取当前价格
        data_key = task['data_key']
        fetcher_info = self.data_fetchers.get(data_key)
        price = ''
        current_time = datetime.datetime.now().strftime('%H:%M:%S')
        
        if fetcher_info and fetcher_info['data'] is not None:
            df = fetcher_info['data']
            if not df.empty:
                latest_row = df.iloc[-1]
                price = latest_row.get('close', '')
                if 'time' in latest_row:
                    current_time = str(latest_row['time'])
        
        # 构造消息（与 signal 项目格式一致）
        if signal.startswith('WARNING:'):
            # 开板预警消息
            warning_detail = signal.split(':', 1)[1] if ':' in signal else signal
            message = (
                f"【开板预警】\n"
                f"{stock_name}({symbol})\n"
                f"{warning_detail}\n"
                f"时间: {current_time}"
            )
        else:
            # 买卖信号消息
            action_text = "买点" if signal == 'BUY' else "卖点"
            message = (
                f"【交易提醒】\n"
                f"{stock_name}({symbol}) 触发 {action_text}\n"
                f"策略: {strategy_name} ({period}分)\n"
                f"时间: {current_time}\n"
                f"价格: {price}"
            )
        
        self.logger.info(f"触发信号: {message.replace(chr(10), ' ')}")
        
        # 发送钉钉通知
        if self.notifier:
            self.notifier.send(message)
        
        # 回调
        if self.on_signal:
            try:
                self.on_signal(symbol, strategy_name, signal, message)
            except Exception as e:
                self.logger.warning(f"信号回调失败: {e}")
