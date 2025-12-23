# AShareTools - A股行情监控与预警工具

[简体中文](README.md) | [English](README_EN.md)

一个基于 Python + PyQt6 的 A 股行情监控和策略预警工具，整合了实时行情悬浮窗口和智能交易预警功能。

## 功能特点

### 🖥️ 行情监控窗口
- **多市场支持**：支持沪深 A 股、可转债、港股、美股、ETF 基金等
- **独立浮动窗口**：每个标的使用独立的无边框悬浮窗口，可随意拖动
- **始终置顶**：支持窗口始终置顶，方便随时查看
- **高度自定义**：字体大小、透明度、列显示、刷新频率等均可调整
- **定时显示**：支持设置时间段自动显示/隐藏窗口

### 📊 智能预警系统
- **多种策略**：内置均线趋势、MACD动量、布林带回归、涨跌停预警等策略
- **策略热重载**：策略定义文件支持运行时动态重载，无需重启程序
- **多数据源**：支持东方财富、腾讯、新浪三大数据源，自动故障切换
- **钉钉通知**：支持钉钉机器人推送交易信号

### 🎛️ 系统托盘
- **托盘图标**：程序运行后在系统托盘显示图标
- **右键菜单**：快速访问所有功能
- **双击切换**：双击托盘图标快速显示/隐藏行情窗口

## 环境准备

- Windows 10 / 11
- Python 3.9 及以上

```powershell
# 克隆项目
cd AShareTools

# 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

## 运行方式

```powershell
python -m src.main
```

或者直接运行：

```powershell
python src/main.py
```

程序启动后会在系统托盘显示图标，右键点击可访问所有功能。

## 使用说明

程序启动后在系统托盘显示图标。**双击图标**可快速显示/隐藏行情窗口。
主要功能配置请通过 **右键托盘图标 → 设置** 进入设置窗口进行操作。

### 1. 行情窗口设置

在设置窗口的"行情窗口"标签页中：

- **监控股票**：输入股票代码（如 `sh600519` 或 `sz000001`），点击"添加"加入监控列表。选中股票可删除。
- **显示设置**：
  - **字体与透明度**：拖动滑块调整字体大小、背景透明度和文字透明度。
  - **刷新间隔**：设置行情数据的刷新频率。
  - **显示选项**：可选择是否显示股票名称、代码、标题栏，以及是否始终置顶。
- **定时显示**：启用后，行情窗口仅在设定的时间段内（如 09:25-11:35, 12:55-15:05）自动显示，其余时间隐藏。

### 2. 行情预警设置

在设置窗口的"行情预警"标签页中：

- **钉钉通知**：配置钉钉机器人的 Webhook 和 Secret，用于接收策略触发的预警消息。
- **预警任务**：
  - **扫描间隔**：设置策略检查的时间间隔。
  - **任务列表**：添加需要预警的股票，选择策略（如布林带回归、均线趋势等）和 K 线周期。
- **策略控制**：
  - **重载策略**：修改 `strategies.py` 文件后，点击此按钮可热重载策略代码。
  - **刷新状态**：刷新当前预警任务的运行状态。

### 策略配置

策略定义在项目根目录的 `strategies.py` 文件中，可以直接编辑该文件添加或修改策略。

修改后点击"重载策略"即可生效，无需重启程序。

#### 内置策略

| 策略ID | 名称 | 说明 |
|--------|------|------|
| MA_TREND | 均线趋势 | MA10/MA60 金叉死叉策略 |
| MACD_MOMENTUM | MACD动量 | MACD 0轴上方金叉策略 |
| BOLL_REVERSION | 布林带回归 | 布林带触底反弹策略 |
| TIME_BREAKOUT | 时间突破 | 早盘高低点突破策略 |
| GRID | 网格交易 | 固定网格间距交易策略 |
| LIMIT_BOARD_WARNING | 涨跌停预警 | 涨跌停板开板预警 |

#### 添加自定义策略

1. 编辑 `strategies.py` 文件
2. 在 `STRATEGIES` 字典中添加策略定义
3. 在 `Strategy` 类中添加对应的策略方法
4. 点击"重载策略"

## 配置文件说明

### settings.json

运行时配置文件，首次运行会自动创建。包含：
- 行情窗口股票列表和显示设置
- 时间段配置
- 预警任务和钉钉配置

### strategies.py

策略定义文件，包含：
- 策略注册表（STRATEGIES 字典）
- 策略实现类（Strategy 类）

## 打包为独立 EXE

使用 PyInstaller 将程序打包为单文件可执行程序。

### 1. 安装打包工具

```powershell
.\venv\Scripts\activate
pip install pyinstaller
```

### 2. 执行打包

**方式一：使用 spec 文件（推荐）**

```powershell
pyinstaller AShareTools.spec
```

**方式二：命令行打包**

```powershell
pyinstaller --onefile --noconsole --name AShareTools ^
    --hidden-import PyQt6.sip ^
    --hidden-import pandas ^
    --hidden-import akshare ^
    --hidden-import chinese_calendar ^
    --collect-all PyQt6 ^
    --strip --clean --noconfirm ^
    src/main.py
```

### 3. 打包后的文件结构

```
dist/
  AShareTools.exe    # 可执行文件
  
部署时需要将以下文件放在 EXE 同目录:
  strategies.py      # 策略定义文件（必需，支持热重载）
  settings.json      # 配置文件（首次运行自动创建）
  
运行时自动生成:
  asharetools.log    # 日志文件
  stock_names.json   # 股票名称缓存
```

### 4. 部署说明

1. 将 `dist/AShareTools.exe` 复制到目标目录
2. 将 `strategies.py` 复制到 EXE 同目录
3. （可选）复制 `settings.json.example` 为 `settings.json` 并修改配置
4. 双击运行 `AShareTools.exe`

**注意事项：**
- `strategies.py` 必须放在 EXE 同目录，否则无法加载策略
- `settings.json` 和日志文件会自动在 EXE 同目录创建
- 首次运行时会自动获取股票名称并缓存

## 项目结构

```
AShareTools/
├── src/
│   ├── __init__.py
│   ├── main.py              # 程序入口
│   ├── config.py            # 静态配置
│   ├── constants.py         # 常量定义
│   ├── utils.py             # 工具函数
│   ├── logger.py            # 日志模块
│   ├── scheduler.py         # 时间调度
│   ├── settings_manager.py  # 配置管理
│   ├── indicators.py        # 技术指标
│   ├── data_fetcher.py      # 数据获取
│   ├── alert_engine.py      # 预警引擎
│   └── gui/
│       ├── __init__.py
│       ├── float_window.py  # 浮动窗口
│       ├── quote_manager.py # 行情管理
│       ├── tray_icon.py     # 系统托盘
│       └── dialogs.py       # 对话框
├── strategies.py            # 策略定义（热重载）
├── settings.json            # 运行配置（自动生成）
├── requirements.txt         # 依赖列表
├── AShareTools.spec         # 打包配置
└── README.md
```

## 常见问题

### Q: 程序启动后看不到窗口？
A: 程序默认最小化到系统托盘，请在任务栏托盘区域查找图标。

### Q: 策略修改后不生效？
A: 点击"重载策略"按钮，或者检查策略文件是否有语法错误。

### Q: 打包后的 EXE 无法运行？
A: 确保 `strategies.py` 文件在 EXE 同目录。

## 免责声明

本工具仅供学习和个人使用，行情数据来源于公开接口，不保证数据的准确性和及时性。投资有风险，请谨慎决策。

## License

本项目采用 [MIT License](LICENSE) 开源授权。
