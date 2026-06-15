# -*- coding: utf-8 -*-
r"""TradingAgents 网页界面（Streamlit）。

启动方式（在项目根目录）:
    .\.venv\Scripts\streamlit.exe run app.py

它会自动在浏览器打开 http://localhost:8501
LLM 配置（MiniMax 中国站 / 模型 / 语言）从 .env 读取。
"""
import datetime
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # 读取 .env 里的 MiniMax 配置

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from cli.utils import detect_asset_type

# ---------- 常量 ----------
ANALYSTS = {
    "market": "📈 市场/技术面分析师",
    "social": "💬 社交情绪分析师",
    "news": "📰 新闻分析师",
    "fundamentals": "📊 基本面分析师",
}
# 分析师 key -> 它产出的报告字段
ANALYST_REPORT_KEY = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}
DEPTH_LABELS = {1: "浅 (1轮 · 快·省额度)", 2: "中 (2轮)", 3: "深 (3轮 · 慢·更全面)"}
RESULTS_DIR = Path(DEFAULT_CONFIG["results_dir"])

# 报告分区的中文标题与对应 final_state 字段
REPORT_SECTIONS = [
    ("market_report", "📈 市场 / 技术面分析"),
    ("sentiment_report", "💬 社交情绪分析"),
    ("news_report", "📰 新闻分析"),
    ("fundamentals_report", "📊 基本面分析"),
    ("investment_plan", "🐂🐻 多空研究员辩论与研究主管结论"),
    ("trader_investment_plan", "💼 交易员方案"),
    ("final_trade_decision", "⚖️ 风控辩论与投资组合经理最终裁决"),
]

st.set_page_config(page_title="TradingAgents 智能交易分析", page_icon="📈", layout="wide")


# ---------- 工具函数 ----------
def build_config(depth: int, language: str) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    cfg["max_debate_rounds"] = depth
    cfg["max_risk_discuss_rounds"] = depth
    cfg["output_language"] = language
    return cfg


def section_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(v) for v in value)
    return str(value)


def merge_debate(final_state: dict):
    """把辩论状态拼成可读 markdown，填进 investment_plan / final_trade_decision。"""
    inv = final_state.get("investment_debate_state") or {}
    parts = []
    if inv.get("bull_history"):
        parts.append(f"### 🐂 多方研究员\n{inv['bull_history']}")
    if inv.get("bear_history"):
        parts.append(f"### 🐻 空方研究员\n{inv['bear_history']}")
    if inv.get("judge_decision"):
        parts.append(f"### 🧑‍⚖️ 研究主管结论\n{inv['judge_decision']}")
    if parts and not final_state.get("investment_plan"):
        final_state["investment_plan"] = "\n\n".join(parts)

    risk = final_state.get("risk_debate_state") or {}
    rparts = []
    if risk.get("aggressive_history"):
        rparts.append(f"### 🔥 激进派\n{risk['aggressive_history']}")
    if risk.get("conservative_history"):
        rparts.append(f"### 🛡️ 保守派\n{risk['conservative_history']}")
    if risk.get("neutral_history"):
        rparts.append(f"### ⚖️ 中性派\n{risk['neutral_history']}")
    if risk.get("judge_decision"):
        rparts.append(f"### 🧑‍⚖️ 投资组合经理最终裁决\n{risk['judge_decision']}")
    if rparts:
        final_state["final_trade_decision"] = "\n\n".join(rparts)


def save_reports(final_state: dict, ticker: str, date: str, decision: str) -> Path:
    """把完整报告保存为一份 markdown。"""
    out_dir = RESULTS_DIR / ticker / date
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# {ticker} 交易分析报告（{date}）", f"\n**最终决策：{decision}**\n", "---"]
    for key, title in REPORT_SECTIONS:
        txt = section_text(final_state.get(key)).strip()
        if txt:
            lines.append(f"\n## {title}\n\n{txt}")
    path = out_dir / "complete_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def decision_style(decision: str):
    d = (decision or "").upper()
    if "BUY" in d:
        return "🟢 买入 (BUY)", "#16a34a"
    if "SELL" in d:
        return "🔴 卖出 (SELL)", "#dc2626"
    return "🟡 持有 / 观望 (HOLD)", "#ca8a00"


# ---------- 侧边栏：参数 ----------
st.sidebar.title("📈 TradingAgents")
st.sidebar.caption("多智能体股票分析 · MiniMax 驱动")

ticker = st.sidebar.text_input("股票代码", value="AAPL",
                               help="美股 AAPL；港股 0700.HK；A股 600519.SS / 000001.SZ；加密 BTC-USD")
analysis_date = st.sidebar.date_input("分析日期", value=datetime.date.today() - datetime.timedelta(days=1))
selected = st.sidebar.multiselect("分析师团队", options=list(ANALYSTS.keys()),
                                  default=list(ANALYSTS.keys()),
                                  format_func=lambda k: ANALYSTS[k])
depth = st.sidebar.select_slider("研究深度", options=[1, 2, 3], value=1,
                                 format_func=lambda d: DEPTH_LABELS[d])
language = st.sidebar.selectbox("报告语言", options=["Chinese", "English"], index=0)

with st.sidebar.expander("当前模型配置", expanded=False):
    st.write(f"**Provider:** `{DEFAULT_CONFIG['llm_provider']}`")
    st.write(f"**深度模型:** `{DEFAULT_CONFIG['deep_think_llm']}`")
    st.write(f"**快思考模型:** `{DEFAULT_CONFIG['quick_think_llm']}`")
    st.caption("（改模型请编辑项目根目录的 .env）")

run = st.sidebar.button("🚀 开始分析", type="primary", use_container_width=True)

tab_run, tab_history = st.tabs(["🔬 运行分析", "📚 历史报告"])


# ---------- 运行分析 ----------
with tab_run:
    if run:
        if not ticker.strip():
            st.error("请先填写股票代码")
            st.stop()
        if not selected:
            st.error("请至少选择一个分析师")
            st.stop()

        ticker_u = ticker.strip().upper()
        date_str = analysis_date.strftime("%Y-%m-%d")
        cfg = build_config(depth, language)
        asset_type = detect_asset_type(ticker_u).value

        st.subheader(f"正在分析 {ticker_u} @ {date_str}")
        progress = st.progress(0.0)
        status_box = st.empty()
        timer_box = st.empty()

        # 流水线阶段
        stages = [(f"analyst_{k}", ANALYSTS[k]) for k in selected]
        stages += [
            ("research", "🐂🐻 多空研究员辩论"),
            ("trader", "💼 交易员决策"),
            ("risk", "⚖️ 风控团队辩论"),
            ("final", "🏁 最终裁决"),
        ]
        stage_status = {sid: "pending" for sid, _ in stages}

        def render_status():
            icon = {"pending": "⚪", "running": "🔄", "done": "✅"}
            md = " &nbsp;|&nbsp; ".join(
                f"{icon[stage_status[sid]]} {label}" for sid, label in stages
            )
            done = sum(1 for v in stage_status.values() if v == "done")
            progress.progress(done / len(stages))
            status_box.markdown(md)

        render_status()

        try:
            start = time.time()
            graph = TradingAgentsGraph(selected, config=cfg, debug=True)
            ctx = graph.resolve_instrument_context(ticker_u, asset_type)
            init_state = graph.propagator.create_initial_state(
                ticker_u, date_str, asset_type=asset_type, instrument_context=ctx
            )
            args = graph.propagator.get_graph_args()

            # 第一个分析师标记进行中
            if selected:
                stage_status[f"analyst_{selected[0]}"] = "running"
                render_status()

            final_state = {}
            for chunk in graph.graph.stream(init_state, **args):
                final_state.update(chunk)
                timer_box.caption(f"⏱️ 已用时 {int(time.time() - start)} 秒")

                # 分析师完成判断
                running_set = False
                for k in selected:
                    if final_state.get(ANALYST_REPORT_KEY[k]):
                        stage_status[f"analyst_{k}"] = "done"
                    elif not running_set and stage_status[f"analyst_{k}"] != "done":
                        stage_status[f"analyst_{k}"] = "running"
                        running_set = True

                inv = final_state.get("investment_debate_state") or {}
                if inv.get("bull_history") or inv.get("bear_history"):
                    stage_status["research"] = "running"
                if inv.get("judge_decision"):
                    stage_status["research"] = "done"
                    stage_status["trader"] = "running"
                if final_state.get("trader_investment_plan"):
                    stage_status["trader"] = "done"
                    stage_status["risk"] = "running"
                risk = final_state.get("risk_debate_state") or {}
                if any(risk.get(x) for x in ("aggressive_history", "conservative_history", "neutral_history")):
                    stage_status["risk"] = "running"
                if risk.get("judge_decision") or final_state.get("final_trade_decision"):
                    stage_status["risk"] = "done"
                    stage_status["final"] = "done"
                render_status()

            # 收尾
            for sid in stage_status:
                stage_status[sid] = "done"
            render_status()
            merge_debate(final_state)
            decision = graph.process_signal(final_state.get("final_trade_decision", ""))
            saved = save_reports(final_state, ticker_u, date_str, decision)

            # ---- 展示结果 ----
            label, color = decision_style(decision)
            st.markdown(
                f"<div style='padding:16px;border-radius:10px;background:{color};"
                f"color:white;font-size:24px;font-weight:700;text-align:center'>"
                f"最终决策：{label}</div>",
                unsafe_allow_html=True,
            )
            st.success(f"分析完成，用时 {int(time.time() - start)} 秒。报告已保存：{saved}")

            for key, title in REPORT_SECTIONS:
                txt = section_text(final_state.get(key)).strip()
                if txt:
                    with st.expander(title, expanded=(key == "final_trade_decision")):
                        st.markdown(txt)

            with open(saved, "r", encoding="utf-8") as f:
                st.download_button("⬇️ 下载完整报告 (Markdown)", f.read(),
                                   file_name=f"{ticker_u}_{date_str}.md", mime="text/markdown")
        except Exception as e:
            st.error(f"运行出错：{e}")
            st.exception(e)
    else:
        st.info("👈 在左侧填写参数，点击 **开始分析**。\n\n"
                "提示：研究深度选「浅」最快也最省额度，适合先试。完整流程约几分钟。")


# ---------- 历史报告 ----------
with tab_history:
    st.subheader("历史分析报告")
    if not RESULTS_DIR.exists():
        st.info("还没有任何历史报告。先去「运行分析」跑一次。")
    else:
        tickers = sorted([p.name for p in RESULTS_DIR.iterdir() if p.is_dir()])
        if not tickers:
            st.info("还没有任何历史报告。")
        else:
            col1, col2 = st.columns(2)
            sel_ticker = col1.selectbox("股票", tickers)
            dates_dir = RESULTS_DIR / sel_ticker
            dates = sorted([p.name for p in dates_dir.iterdir() if p.is_dir()], reverse=True)
            sel_date = col2.selectbox("日期", dates) if dates else None
            if sel_date:
                report_path = RESULTS_DIR / sel_ticker / sel_date / "complete_report.md"
                if report_path.exists():
                    content = report_path.read_text(encoding="utf-8")
                    st.download_button("⬇️ 下载", content,
                                       file_name=f"{sel_ticker}_{sel_date}.md", mime="text/markdown")
                    st.markdown(content)
                else:
                    st.warning("该日期没有 complete_report.md（可能是命令行旧格式，去对应目录手动查看）。")
