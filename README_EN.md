# AShareTools - A-Share Market Monitor & Alert Tool

[简体中文](README.md) | [English](README_EN.md)

A Python + PyQt6 based A-Share market monitoring and strategy alert tool, integrating real-time floating windows and intelligent trading alerts.

## Features

### 🖥️ Market Monitor Window
- **Multi-Market Support**: Supports Shanghai/Shenzhen A-Shares, Convertible Bonds, HK Stocks, US Stocks, ETFs, etc.
- **Independent Floating Window**: Borderless floating window for each symbol, draggable anywhere.
- **Always on Top**: Supports keeping the window always on top for easy viewing.
- **Highly Customizable**: Font size, opacity, column display, refresh rate, etc., are adjustable.
- **Scheduled Display**: Supports setting time periods to automatically show/hide windows.

### 🥇 Gold Market Window
- **Built-in Gold Targets**: Includes London Spot, USD/CNY, London Spot (RMB/g), NY Gold, and AU9999.
- **Per-Target Independent Windows**: Each gold target has its own floating window that can be enabled/disabled separately.
- **Display Customization**: Supports font size, opacity, code display, refresh interval, and always-on-top settings.
- **Per-Target Scheduled Display**: You can configure separate auto-display time periods for different gold targets.

### 📊 Intelligent Alert System
- **Multiple Strategies**: Built-in strategies like MA Trend, MACD Momentum, Bollinger Reversion, Limit Board Warning, etc.
- **Strategy Hot Reload**: Strategy definition files support dynamic reloading at runtime without restarting the program.
- **Multi-Data Source**: Supports EastMoney, Tencent, and Sina data sources with automatic failover.
- **DingTalk Notification**: Supports pushing trading signals via DingTalk robot.
- **Gold Price Alerts**: Supports threshold-based gold alerts with configurable repeat frequency.

### 🎛️ System Tray
- **Tray Icon**: Displays an icon in the system tray after the program starts.
- **Context Menu**: Quick access to all features.
- **Double-Click Toggle**: Double-click the tray icon to quickly show/hide market windows.

## Prerequisites

- Windows 10 / 11
- Python 3.9 and above

```powershell
# Clone the project
cd AShareTools

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## How to Run

```powershell
python -m src.main
```

Or run directly:

```powershell
python src/main.py
```

After startup, an icon will appear in the system tray. Right-click to access all features.

## Usage Guide

After startup, an icon appears in the system tray. **Double-click the icon** to quickly show/hide the market window.
Most configurations are done via **Right-click Tray Icon → Settings**.

### 1. Market Window Settings

In the "Market Window" tab of the Settings window:

- **Monitor Stocks**: Enter stock codes (e.g., `sh600519` or `sz000001`) and click "Add". Select a stock to remove it.
- **Display Settings**:
  - **Font & Opacity**: Adjust font size, background opacity, and text opacity using sliders.
  - **Refresh Interval**: Set the refresh frequency of market data.
  - **Display Options**: Toggle display of stock name, code, title bar, and "Always on Top".
- **Scheduled Display**: When enabled, the market window only appears during specified time periods (e.g., 09:25-11:35, 12:55-15:05) and hides otherwise.

### 2. Gold Market Settings

In the "Gold Market" tab of the Settings window:

- **Target Switches**: Independently control window visibility for London Spot, USD/CNY, London Spot (RMB/g), NY Gold, and AU9999.
- **Display Settings**:
  - **Font & Opacity**: Adjust font size, background opacity, and text opacity.
  - **Refresh Interval**: Set the gold quote refresh interval (seconds).
  - **Display Options**: Toggle code display and always-on-top.
- **Scheduled Display**: Configure multiple time periods per gold target. When enabled, each target window is shown only during its configured periods.

### 3. Market Alert Settings

In the "Market Alerts" tab of the Settings window:

- **DingTalk Notification**: Configure the Webhook and Secret for the DingTalk robot to receive alert messages.
- **Alert Tasks**:
  - **Scan Interval**: Set the time interval for strategy checks.
  - **Task List**: Add stocks to monitor, select a strategy (e.g., Bollinger Reversion, MA Trend), and K-line period.
- **Gold Market Alerts**:
  - **Scan Interval**: Set the gold alert scan interval (seconds).
  - **Task List**: Configure alert price, alert frequency (minutes), and switch state for each gold target.
  - **Trigger Rule**: An alert is triggered when current price >= alert price.
  - **Frequency Behavior**: If frequency is 0, the task alerts once and auto-disables; if greater than 0, the task is automatically re-armed after the configured minutes.
  - **Runtime Window**: Gold alerts are not tied to A-share trading hours and continue scanning in non-trading hours.
- **Strategy Control**:
  - **Reload Strategies**: Click this button to hot-reload strategy code after modifying `strategies.py`.
  - **Refresh Status**: Refresh the running status of current alert tasks.

### Strategy Configuration

Strategies are defined in the `strategies.py` file in the project root directory. You can edit this file directly to add or modify strategies.

Click "Reload Strategies" after modification to take effect without restarting the program.

#### Built-in Strategies

| Strategy ID | Name | Description |
|-------------|------|-------------|
| MA_TREND | MA Trend | MA10/MA60 Golden/Death Cross Strategy |
| MACD_MOMENTUM | MACD Momentum | MACD Golden Cross above 0 axis |
| BOLL_REVERSION | Bollinger Reversion | Bollinger Band Rebound Strategy |
| TIME_BREAKOUT | Time Breakout | Morning High/Low Breakout Strategy |
| GRID | Grid Trading | Fixed Grid Spacing Trading Strategy |
| LIMIT_BOARD_WARNING | Limit Board Warning | Limit Up/Down Open Warning |

#### Add Custom Strategy

1. Edit `strategies.py` file
2. Add strategy definition in `STRATEGIES` dictionary
3. Add corresponding strategy method in `Strategy` class
4. Click "Reload Strategies"

## Configuration Files

### settings.json

Runtime configuration file, automatically created on first run. Contains:
- Market window stock list and display settings
- Gold window target switches, display styles, and per-target schedule settings (`gold_window`)
- A-share alert tasks, gold alert tasks, and their scan intervals (`alert.tasks` / `alert.gold_tasks`)
- DingTalk notification configuration

### strategies.py

Strategy definition file, contains:
- Strategy Registry (`STRATEGIES` dictionary)
- Strategy Implementation Class (`Strategy` class)

## Build as Standalone EXE

Use PyInstaller to package the program into a single executable file.

### 1. Install Packaging Tool

```powershell
.\venv\Scripts\activate
pip install pyinstaller
```

### 2. Execute Packaging

```powershell
pyinstaller AShareTools.spec
```

### 3. Packaged File Structure

```
dist/
  AShareTools.exe    # Executable file
  
Files required in the same directory for deployment:
  strategies.py      # Strategy definition file (Required, supports hot reload)
  settings.json      # Configuration file (Automatically created on first run)
  icon.ico           # (Optional) Custom icon file
  
Automatically generated at runtime:
  asharetools.log    # Log file
  stock_names.json   # Stock name cache
```

### 4. Deployment Instructions

1. Copy `dist/AShareTools.exe` to the target directory
2. Copy `strategies.py` to the same directory as the EXE
3. (Optional) Copy `settings.json.example` to `settings.json` and modify configuration
4. Double-click `AShareTools.exe` to run

**Notes:**
- `strategies.py` must be in the same directory as the EXE, otherwise strategies cannot be loaded
- `settings.json` and log files will be automatically created in the same directory as the EXE
- Stock names will be automatically fetched and cached on first run
- The program has a built-in default icon. To customize it, place an `icon.ico` file in the same directory as the EXE (prioritized).

## Project Structure

```
AShareTools/
├── src/
│   ├── __init__.py
│   ├── main.py              # Program Entry
│   ├── config.py            # Static Config
│   ├── constants.py         # Constants
│   ├── utils.py             # Utility Functions
│   ├── logger.py            # Logger
│   ├── scheduler.py         # Scheduler
│   ├── settings_manager.py  # Settings Manager
│   ├── indicators.py        # Technical Indicators
│   ├── data_fetcher.py      # Data Fetcher
│   ├── alert_engine.py      # Alert Engine
│   └── gui/
│       ├── __init__.py
│       ├── float_window.py  # Floating Window
│       ├── gold_manager.py  # Gold Window Manager
│       ├── main_window.py   # Settings Window
│       ├── quote_manager.py # Quote Manager
│       ├── toggle_switch.py # Toggle Control
│       ├── tray_icon.py     # System Tray
│       └── win11_style.py   # Win11 Style
├── strategies.py            # Strategy Definitions (Hot Reload)
├── settings.json            # Runtime Config (Auto-generated)
├── requirements.txt         # Dependencies
├── AShareTools.spec         # Build Config
└── README.md
```

## FAQ

### Q: Can't see the window after startup?
A: The program minimizes to the system tray by default. Please check the icon in the taskbar tray area.

### Q: Strategy modification not taking effect?
A: Click the "Reload Strategies" button, or check the strategy file for syntax errors.

### Q: Packaged EXE fails to run?
A: Ensure `strategies.py` file is in the same directory as the EXE.

### Q: How to configure gold price alerts?
A: In the "Market Alerts" tab of the Settings window, find the "Gold Market Alerts" section. First configure the DingTalk robot's Webhook and Secret, then add alert tasks and set price thresholds.

### Q: Can stock alerts and gold alerts run simultaneously?
A: Yes. Both alert systems run independently and share the same DingTalk notification configuration. You can configure separate scan intervals for each.

### Q: Scheduled display not working?
A: Ensure that "Scheduled Display" is enabled in the corresponding tab and the time range is configured correctly. Time format must be `HH:MM` (24-hour format).

## Disclaimer

This tool is for learning and personal use only. Market data comes from public interfaces, and the accuracy and timeliness of data are not guaranteed. Investment involves risks, please make decisions cautiously.

## License

This project is licensed under the [MIT License](LICENSE).
