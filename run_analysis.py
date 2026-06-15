r"""一键运行单次股票分析（用 .env 里预设的 MiniMax 配置）。

用法:
    .\.venv\Scripts\python.exe run_analysis.py AAPL 2026-06-12
    .\.venv\Scripts\python.exe run_analysis.py 0700.HK 2026-06-12

参数:
    第1个 = 股票代码 (默认 AAPL)；港股如 0700.HK，A股如 600519.SS，加密货币如 BTC-USD
    第2个 = 分析日期 YYYY-MM-DD (默认昨天)
"""
import sys
from datetime import date, timedelta

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
analysis_date = sys.argv[2] if len(sys.argv) > 2 else str(date.today() - timedelta(days=1))

config = DEFAULT_CONFIG.copy()  # 已含 .env 里的 MiniMax 中国站设置

print(f"=== 分析 {ticker} @ {analysis_date} ===")
print(f"Provider: {config['llm_provider']} | Deep: {config['deep_think_llm']} | Quick: {config['quick_think_llm']}\n")

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate(ticker, analysis_date)

print("\n=== 最终决策 ===")
print(decision)
