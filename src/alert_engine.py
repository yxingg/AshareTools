# alert_engine.py - 预警监控引擎
"""
预警监控引擎
负责策略计算和信号推送
"""

import logging
import time
import importlib.util
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any, Callable

from .config import (
    BASE_DIR, STRATEGIES_FILE, STOCK_CACHE_FILE,
    DEFAULT_SCAN_INTERVAL, DEFAULT_MAX_WORKERS, AVAILABLE_DATA_SOURCES
)
from .data_fetcher import KLineFetcher, StockNameManager
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
        
        # 数据获取器
        self.data_fetchers: Dict[tuple, Dict] = {}
        
        # 股票名称管理器
        self.name_manager: Optional[StockNameManager] = None
        
        # 运行状态
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._executor: Optional[ThreadPoolExecutor] = None

    def update_tasks(self, tasks: List[Dict], scan_interval: int = None):
        """
        更新预警任务
        
        Args:
            tasks: 任务列表 [{"symbol": "600519", "strategy": "MA_TREND", "period": "5"}, ...]
            scan_interval: 扫描间隔（秒）
        """
        self.tasks = []
        self.data_fetchers = {}
        
        if scan_interval:
            self.scan_interval = scan_interval
        
        # 提取所有 symbol
        target_symbols = list(set([t['symbol'] for t in tasks]))
        
        # 使用全局名称管理器单例（确保缓存已有对应symbol）
        self.name_manager = StockNameManager.get_instance()
        if self.name_manager and target_symbols:
            self.name_manager.ensure_symbols(target_symbols)
        
        # 按 symbol + period 去重创建数据获取器
        unique_keys = set()
        for task in tasks:
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
            for t in tasks:
                if t['symbol'] == symbol and t.get('strategy') == 'LIMIT_BOARD_WARNING':
                    self.data_fetchers[key]['interval'] = 1
                    
            source_index += 1
            self.logger.info(f"数据源加载: {symbol} - {period}分 (首选: {preferred_source})")

        # 创建任务
        seen_tasks = set()
        for task in tasks:
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
        
        self.logger.info(f"预警任务更新完成，共 {len(self.tasks)} 个任务")

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
        
        if not self.tasks:
            self.logger.info("没有预警任务，跳过启动")
            return
        
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=min(DEFAULT_MAX_WORKERS, len(self.tasks) + 3))
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.logger.info("预警引擎已启动")
        
        # 发送启动消息（包含当前状态）
        is_trading = self.scheduler.is_trading_time()
        if is_trading:
            start_msg = f"【系统启动】\n智能监控已启动\n当前状态: 交易中\n监控标的数: {len(self.data_fetchers)}\n策略任务数: {len(self.tasks)}"
        else:
            sleep_sec, reason, target_time = self.scheduler.calculate_sleep_seconds()
            start_msg = f"【系统启动】\n智能监控已启动\n当前状态: 休市\n原因: {reason}\n预计开盘: {target_time}\n监控标的数: {len(self.data_fetchers)}\n策略任务数: {len(self.tasks)}"
        
        self.logger.info(start_msg.replace('\n', ' '))
        if self.notifier:
            self.notifier.send(start_msg)

    def stop(self):
        """停止预警引擎"""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
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
                
                if not is_trading:
                    # 非交易时间，休眠等待
                    sleep_sec, _, _ = self.scheduler.calculate_sleep_seconds()
                    # 分段休眠，以便能够响应停止信号
                    for _ in range(int(min(sleep_sec, 60))):  # 最多休眠60秒后重新检查
                        if not self._running:
                            return
                        time.sleep(1)
                    continue
                
                # 执行一轮扫描
                self._scan_once()
                
                # 休眠
                for _ in range(self.scan_interval):
                    if not self._running:
                        return
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"预警循环异常: {e}")
                time.sleep(5)

    def _scan_once(self):
        """执行一轮扫描"""
        if not self.tasks:
            return
        
        current_time = time.time()
        
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
