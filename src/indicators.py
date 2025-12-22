# indicators.py - 技术指标计算模块
"""技术指标计算模块"""

import pandas as pd

# 策略所需的最小数据量
MIN_DATA_LENGTH = 60


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算常用的技术指标
    
    Args:
        df: 包含 OHLCV 数据的 DataFrame
        
    Returns:
        添加了技术指标的 DataFrame
    """
    if df is None or df.empty:
        return df

    # MACD
    df['ema_fast'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=26, adjust=False).mean()
    df['dif'] = df['ema_fast'] - df['ema_slow']
    df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
    df['macd'] = 2 * (df['dif'] - df['dea'])

    # MA 均线
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma60_slope'] = df['ma60'].diff()

    # BOLL 布林带
    df['std20'] = df['close'].rolling(window=20).std()
    df['upper_band'] = df['ma20'] + 2 * df['std20']
    df['lower_band'] = df['ma20'] - 2 * df['std20']

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 成交量均线
    df['vol_ma5'] = df['volume'].rolling(window=5).mean()
    
    # 前值（用于判断金叉死叉）
    df['dif_prev'] = df['dif'].shift(1)
    df['dea_prev'] = df['dea'].shift(1)
    df['macd_prev'] = df['macd'].shift(1)
    df['ma10_prev'] = df['ma10'].shift(1)
    df['ma60_prev'] = df['ma60'].shift(1)

    # 标记数据是否有效
    df.attrs['data_valid'] = len(df) >= MIN_DATA_LENGTH

    return df


def is_data_valid(df: pd.DataFrame) -> bool:
    """检查数据是否足够计算指标"""
    if df is None or df.empty:
        return False
    return df.attrs.get('data_valid', len(df) >= MIN_DATA_LENGTH)
