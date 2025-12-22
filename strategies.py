# strategies.py - 策略定义文件 (支持热重载)
"""
策略定义文件 - 此文件可在运行时动态重载

如何添加新策略：
1. 在 STRATEGIES 字典中添加新的策略定义
2. 在 Strategy 类中添加对应的策略方法 _xxx_strategy()
3. 在程序菜单中点击"重载策略"即可生效

策略方法返回值：
- 'BUY': 买入信号
- 'SELL': 卖出信号  
- 'WARNING:xxx': 预警信息
- None: 无信号
"""

# ================= 策略注册表 =================
# 格式: {"策略ID": {"name": "显示名称", "description": "策略描述", "periods": [可用周期]}}
STRATEGIES = {
    "MA_TREND": {
        "name": "均线趋势",
        "description": "MA10/MA60 金叉死叉策略",
        "periods": ["1", "5", "15", "30", "60"]
    },
    "MACD_MOMENTUM": {
        "name": "MACD动量",
        "description": "MACD 0轴上方金叉策略",
        "periods": ["1", "5", "15", "30", "60"]
    },
    "BOLL_REVERSION": {
        "name": "布林带回归",
        "description": "布林带触底反弹策略",
        "periods": ["1", "5", "15", "30", "60"]
    },
    "TIME_BREAKOUT": {
        "name": "时间突破",
        "description": "早盘高低点突破策略",
        "periods": ["1", "5"]
    },
    "GRID": {
        "name": "网格交易",
        "description": "固定网格间距交易策略",
        "periods": ["1", "5", "15"]
    },
    "LIMIT_BOARD_WARNING": {
        "name": "涨跌停预警",
        "description": "涨跌停板开板预警",
        "periods": ["1"]
    },
}


def get_strategy_list():
    """获取所有可用策略列表"""
    return list(STRATEGIES.keys())


def get_strategy_info(strategy_id):
    """获取策略详细信息"""
    return STRATEGIES.get(strategy_id, None)


def get_all_strategies_info():
    """获取所有策略信息"""
    return STRATEGIES.copy()


# ================= 策略实现类 =================
class Strategy:
    """策略执行类"""
    
    def __init__(self, name):
        self.name = name
        self.context = {
            'last_trade_type': None,
            'last_buy_price': 0.0,
            'last_sell_price': 0.0,
            'entry_low': 0.0,
            'grid_base_price': None,
            'last_grid_level': None,
            'day_high': -1.0,
            'day_low': 99999.0,
            'current_date_str': ""
        }

    def reset_context(self):
        """重置策略上下文"""
        self.context = {
            'last_trade_type': None,
            'last_buy_price': 0.0,
            'last_sell_price': 0.0,
            'entry_low': 0.0,
            'grid_base_price': None,
            'last_grid_level': None,
            'day_high': -1.0,
            'day_low': 99999.0,
            'current_date_str': ""
        }

    def check_signal(self, row, position, snapshot=None, df=None):
        """
        检查信号
        返回: 'BUY', 'SELL', 'WARNING:xxx', 或 None
        """
        signal = None
        
        if self.name == 'MA_TREND':
            signal = self._ma_trend_strategy(row, position)
        elif self.name == 'BOLL_REVERSION':
            signal = self._boll_reversion_strategy(row, position)
        elif self.name == 'MACD_MOMENTUM':
            signal = self._macd_momentum_strategy(row, position)
        elif self.name == 'TIME_BREAKOUT':
            signal = self._time_breakout_strategy(row, position, df)
        elif self.name == 'GRID':
            signal = self._grid_strategy(row, position)
        elif self.name == 'LIMIT_BOARD_WARNING':
            signal = self._limit_board_warning_strategy(snapshot)
        
        return signal

    def _ma_trend_strategy(self, row, position):
        """均线趋势策略"""
        # 检查必要字段
        required = ['ma10', 'ma60', 'ma10_prev', 'ma60_prev', 'ma60_slope', 'volume', 'vol_ma5', 'low']
        if not all(k in row for k in required):
            return None
            
        # 买入: MA10金叉MA60, MA60向上, 放量
        is_golden_cross = (row['ma10'] > row['ma60']) and (row['ma10_prev'] <= row['ma60_prev'])
        is_ma60_up = (row['ma60_slope'] > 0)
        is_volume_up = (row['volume'] > 1.5 * row['vol_ma5'])
        
        if is_golden_cross and is_ma60_up and is_volume_up:
            self.context['entry_low'] = row['low']
            return 'BUY'
            
        # 卖出: MA10死叉MA60
        is_death_cross = (row['ma10'] < row['ma60']) and (row['ma10_prev'] >= row['ma60_prev'])
        if is_death_cross:
            return 'SELL'
        
        return None

    def _macd_momentum_strategy(self, row, position):
        """MACD动量策略"""
        required = ['dif', 'dea', 'dif_prev', 'dea_prev', 'macd', 'close']
        if not all(k in row for k in required):
            return None
            
        # 买入: MACD金叉 + DIF在0轴上方
        is_golden_cross = (row['dif'] > row['dea']) and (row['dif_prev'] <= row['dea_prev'])
        is_above_zero = row['dif'] > 0
        
        if is_golden_cross and is_above_zero:
            return 'BUY'
            
        # 卖出: MACD死叉
        is_death_cross = (row['dif'] < row['dea']) and (row['dif_prev'] >= row['dea_prev'])
        if is_death_cross:
            return 'SELL'
        
        return None

    def _boll_reversion_strategy(self, row, position):
        """布林带回归策略"""
        required = ['close', 'lower_band', 'ma20', 'upper_band']
        if not all(k in row for k in required):
            return None
            
        close = row['close']
        
        # 买入: 价格触及下轨后反弹
        if close <= row['lower_band'] * 1.01:
            return 'BUY'
            
        # 卖出: 价格触及上轨
        if close >= row['upper_band'] * 0.99:
            return 'SELL'
        
        return None

    def _time_breakout_strategy(self, row, position, df=None):
        """时间突破策略"""
        import datetime
        
        if df is None or df.empty:
            return None
            
        now = datetime.datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        
        # 重置日内高低点
        if self.context['current_date_str'] != current_date:
            self.context['current_date_str'] = current_date
            self.context['day_high'] = -1.0
            self.context['day_low'] = 99999.0
        
        # 更新日内高低点
        if 'high' in row:
            self.context['day_high'] = max(self.context['day_high'], row['high'])
        if 'low' in row:
            self.context['day_low'] = min(self.context['day_low'], row['low'])
        
        close = row.get('close', 0)
        
        # 早盘 9:30 - 10:00 不产生信号，只记录高低点
        if now.hour == 9 and now.minute < 60:
            return None
        
        # 突破日内高点
        if close > self.context['day_high'] * 1.001:
            return 'BUY'
        
        # 跌破日内低点
        if close < self.context['day_low'] * 0.999:
            return 'SELL'
        
        return None

    def _grid_strategy(self, row, position):
        """网格交易策略"""
        close = row.get('close', 0)
        if close <= 0:
            return None
            
        grid_pct = 0.02  # 2% 网格间距
        
        # 初始化基准价格
        if self.context['grid_base_price'] is None:
            self.context['grid_base_price'] = close
            self.context['last_grid_level'] = 0
            return None
        
        base = self.context['grid_base_price']
        current_level = int((close - base) / (base * grid_pct))
        last_level = self.context['last_grid_level']
        
        signal = None
        
        # 向下突破一格 -> 买入
        if current_level < last_level:
            signal = 'BUY'
        # 向上突破一格 -> 卖出
        elif current_level > last_level:
            signal = 'SELL'
        
        if signal:
            self.context['last_grid_level'] = current_level
            
        return signal

    def _limit_board_warning_strategy(self, snapshot):
        """涨跌停板开板预警"""
        if not snapshot:
            return None
        
        import time as _time
        import datetime
        
        # 跨日重置
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        if self.context.get('limit_warning_date') != current_date:
            self.context['limit_warning_date'] = current_date
            self.context['was_limit'] = False
            self.context['last_limit_vol'] = None
            self.context['init_limit_vol'] = None
            self.context['consecutive_drop_count'] = 0
            self.context['last_warning_time'] = 0
            self.context['last_warning_type'] = None
            self.context['last_snapshot_time_str'] = None
        
        # 数据去重
        snap_time = snapshot.get('time', '')
        if self.context.get('last_snapshot_time_str') == snap_time:
            return None
        self.context['last_snapshot_time_str'] = snap_time
        
        price = snapshot.get('price', 0)
        high_limit = snapshot.get('high_limit', 0)
        low_limit = snapshot.get('low_limit', 0)
        
        if high_limit == 0 or low_limit == 0 or price == 0:
            return None
        
        # 使用相对误差判断涨跌停状态（0.1%容差）
        is_high_limit = abs(price - high_limit) / high_limit < 0.001
        is_low_limit = abs(price - low_limit) / low_limit < 0.001

        # 记录封板状态
        if 'was_limit' not in self.context:
            self.context['was_limit'] = False

        # 当前不在涨跌停状态
        if not is_high_limit and not is_low_limit:
            # 如果之前在涨跌停状态，说明已开板，重置监控状态以便回封时重新监控
            if self.context.get('was_limit'):
                self.context['last_limit_vol'] = None
                self.context['init_limit_vol'] = None
                self.context['consecutive_drop_count'] = 0
            self.context['was_limit'] = False
            return None

        self.context['was_limit'] = True

        # 获取封单量 (涨停看买一量，跌停看卖一量)
        current_limit_vol = snapshot.get('bid1_vol', 0) if is_high_limit else snapshot.get('ask1_vol', 0)
        
        # 封单量数据异常检查（可能数据源问题导致为0）
        if current_limit_vol <= 0:
            return None
        
        # 初始化基准封单量
        if self.context.get('last_limit_vol') is None or self.context.get('init_limit_vol') is None:
            self.context['last_limit_vol'] = current_limit_vol
            self.context['init_limit_vol'] = current_limit_vol
            self.context['max_limit_vol'] = current_limit_vol  # 记录最大封单量
            self.context['consecutive_drop_count'] = 0
            return None

        # 更新最大封单量（用于计算比例，更准确）
        max_limit_vol = self.context.get('max_limit_vol', current_limit_vol)
        if current_limit_vol > max_limit_vol:
            self.context['max_limit_vol'] = current_limit_vol
            max_limit_vol = current_limit_vol

        # 使用最大封单量作为基准，更合理
        base_vol = max(max_limit_vol, 1)

        # 计算相对上次的变化（使用相对比例而非绝对值）
        last_limit_vol = self.context['last_limit_vol']
        if last_limit_vol > 0:
            drop_pct = (last_limit_vol - current_limit_vol) / last_limit_vol if current_limit_vol < last_limit_vol else 0
        else:
            drop_pct = 0
            
        # 计算相对最大封单量的剩余比例
        current_remain_pct = current_limit_vol / base_vol
        
        self.context['last_limit_vol'] = current_limit_vol
        
        # 阈值
        SIGNIFICANT_DROP_PCT = 0.10  # 单次下降10%视为显著
        DANGER_REMAIN_PCT = 0.20     # 剩余20%以下视为危险
        
        if drop_pct >= SIGNIFICANT_DROP_PCT:
            self.context['consecutive_drop_count'] = self.context.get('consecutive_drop_count', 0) + 1
        else:
            self.context['consecutive_drop_count'] = max(0, self.context.get('consecutive_drop_count', 0) - 1)
            
        warning_msg = None
        board_type = "涨停" if is_high_limit else "跌停"
        
        # 冷却机制
        current_ts = _time.time()
        last_warning_time = self.context.get('last_warning_time', 0)
        last_warning_type = self.context.get('last_warning_type', None)
        
        warning_type = None
        
        # 预警条件 A: 连续封单减少（3次以上显著下降）
        if self.context['consecutive_drop_count'] >= 3:
            warning_type = 'consecutive_drop'
            warning_msg = f"WARNING:{board_type}封单连续减少，注意开板风险"
            self.context['consecutive_drop_count'] = 0
        # 预警条件 B: 封单严重不足（使用 elif 避免覆盖）
        elif current_remain_pct < DANGER_REMAIN_PCT:
            warning_type = 'low_seal'
            warning_msg = f"WARNING:{board_type}封单严重不足 (剩余{current_remain_pct*100:.0f}%)，即将开板"

        # 冷却
        if warning_msg:
            cooldown = 60 if warning_type == last_warning_type else 10
            if current_ts - last_warning_time < cooldown:
                return None
            self.context['last_warning_time'] = current_ts
            self.context['last_warning_type'] = warning_type

        return warning_msg


# 模块重载标记
_MODULE_VERSION = 1
