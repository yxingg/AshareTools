# scheduler.py - 交易时间调度器
"""交易时间调度模块"""

import datetime

# 尝试导入中国日历
try:
    from chinese_calendar import is_workday
    HAS_CHINESE_CALENDAR = True
except ImportError:
    HAS_CHINESE_CALENDAR = False


class TradingScheduler:
    """交易时间调度器"""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.tz = datetime.timezone(datetime.timedelta(hours=8))  # 北京时间

    def get_now(self) -> datetime.datetime:
        """获取当前北京时间"""
        return datetime.datetime.now(self.tz)

    def is_trading_time(self) -> bool:
        """判断当前是否为交易时间 (9:25-11:32, 12:55-15:02)"""
        now = self.get_now()
        
        # 先检查是否为交易日
        if not self._is_market_open_day(now.date()):
            return False
            
        current_time = now.time()
        t1_start = datetime.time(9, 25)
        t1_end = datetime.time(11, 32)
        t2_start = datetime.time(12, 55)
        t2_end = datetime.time(15, 2)
        
        return (t1_start <= current_time <= t1_end) or (t2_start <= current_time <= t2_end)

    def is_in_time_period(self, periods: list) -> bool:
        """
        判断当前时间是否在指定时间段内
        
        Args:
            periods: 时间段列表, 格式 [{"start": "09:25", "end": "11:35"}, ...]
        """
        now = self.get_now().time()
        
        for period in periods:
            start_str = period.get('start', '00:00')
            end_str = period.get('end', '23:59')
            
            try:
                start_parts = start_str.split(':')
                end_parts = end_str.split(':')
                
                start_time = datetime.time(int(start_parts[0]), int(start_parts[1]))
                end_time = datetime.time(int(end_parts[0]), int(end_parts[1]))
                
                if start_time <= now <= end_time:
                    return True
            except (ValueError, IndexError):
                continue
        
        return False

    def get_next_trading_time(self) -> tuple:
        """
        计算下一个交易时段的开始时间
        
        Returns:
            (target_time, reason_description)
        """
        now = self.get_now()
        
        # 中午休市
        if datetime.time(11, 32) < now.time() < datetime.time(12, 55):
            target = now.replace(hour=12, minute=55, second=0, microsecond=0)
            return target, "中午休市"

        # 下午收盘后或盘前
        target_date = now.date()
        
        if now.time() >= datetime.time(15, 2):
            target_date += datetime.timedelta(days=1)
        
        # 找下一个工作日
        while True:
            if self._is_market_open_day(target_date):
                break
            target_date += datetime.timedelta(days=1)
            
        target = datetime.datetime.combine(target_date, datetime.time(9, 25)).replace(tzinfo=self.tz)
        
        desc = "周末/节假日" if (target.date() - now.date()).days > 1 else "休市"
        return target, desc

    def _is_market_open_day(self, date_obj: datetime.date) -> bool:
        """判断某天是否开盘"""
        if HAS_CHINESE_CALENDAR:
            return is_workday(date_obj)
        else:
            return date_obj.weekday() < 5

    def calculate_sleep_seconds(self) -> tuple:
        """
        计算需要休眠的时间
        
        Returns:
            (sleep_seconds, reason, target_time)
        """
        target_time, reason = self.get_next_trading_time()
        now = self.get_now()
        delta = (target_time - now).total_seconds()
        
        return max(1, delta), reason, target_time
