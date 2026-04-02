import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
from data import DataFetcher
from strategy import MomentumStrategy
from backtest import Backtest

st.set_page_config(page_title="美股雙動能策略回測", layout="wide")
st.title("美股雙動能策略回測工具")

# ──────────────────────────────────────────────
# 側邊欄：全局操作
# ──────────────────────────────────────────────
st.sidebar.header("回測參數設定")

if st.sidebar.button("清除快取", help="若遇到數據錯誤或想強制重新下載，請點此清除所有快取。"):
    st.cache_data.clear()
    st.sidebar.success("快取已清除！")
    st.rerun()

# ──────────────────────────────────────────────
# 靜態預設清單（啟動即用，不需等待網路）
# ──────────────────────────────────────────────
DEFAULT_TOP_50 = (
    "NVDA, AAPL, MSFT, AMZN, GOOGL, GOOG, META, TSLA, AVGO, BRK-B, "
    "JPM, LLY, V, UNH, XOM, MA, COST, HD, PG, WMT, JNJ, ABBV, NFLX, "
    "BAC, KO, MRK, CVX, CRM, AMD, PEP, TMO, ORCL, LIN, MCD, ADBE, "
    "CSCO, ACN, IBM, GE, QCOM, TXN, VZ, AXP, PM, INTU, AMGN, ISRG, "
    "RTX, BKNG, SPGI"
)

# ──────────────────────────────────────────────
# Session State 初始化
# ──────────────────────────────────────────────
if 'risky_assets_str' not in st.session_state:
    st.session_state['risky_assets_str'] = DEFAULT_TOP_50
    st.session_state['risky_assets_source'] = "內建靜態清單（2025 Q1 近似市值前 50 大，可按更新取得即時排名）"

if 'sp500_all_tickers' not in st.session_state:
    st.session_state['sp500_all_tickers'] = []  # 全 500 檔清單（需手動載入）

# ──────────────────────────────────────────────
# 攻擊型資產區塊
# ──────────────────────────────────────────────
st.sidebar.markdown("### 攻擊型資產")
source_label = st.session_state.get('risky_assets_source', '內建靜態清單')
st.sidebar.caption(f"📌 來源：{source_label}")

# 更新前 50 大按鈕（yfinance 市值排序，約 30-60 秒）
col_title, col_btn = st.sidebar.columns([2, 1])
col_title.markdown("**市值前 50 大**")
update_placeholder = st.sidebar.empty()

if col_btn.button("🔄 更新", help="使用 yfinance 查詢即時市值，依市值排序取前 50 大。約需 30-60 秒。"):
    update_placeholder.info("⏳ 正在查詢 500 檔市值，請耐心等待（約 30-60 秒）...")
    try:
        fetcher = DataFetcher()
        top_50, source = fetcher.get_top_n_by_market_cap(50)
        tickers_str = ", ".join(top_50)
        # 同時更新兩個 session state，確保 widget 顯示內容也更新
        st.session_state['risky_assets_str'] = tickers_str
        st.session_state['risky_assets_input'] = tickers_str
        st.session_state['risky_assets_source'] = source
        update_placeholder.success(f"✅ 更新完成！來源：{source}")
        st.rerun()
    except RuntimeError as e:
        update_placeholder.error(f"❌ 更新失敗：{e}")
    except Exception as e:
        update_placeholder.error(f"❌ 未預期錯誤：{e}")

# 全部 500 檔模式
st.sidebar.markdown("**或使用全部 S&P 500**")
use_all_sp500 = st.sidebar.checkbox(
    "使用全部 S&P 500（約 500 檔）",
    value=False,
    key="use_all_sp500",
    help="勾選後啟用，需先點「載入 500 檔」。回測時間顯著增加。"
)

if use_all_sp500:
    already_loaded = len(st.session_state['sp500_all_tickers'])
    if already_loaded > 0:
        st.sidebar.success(f"✅ 已載入 {already_loaded} 檔（S&P 500 全部成分股）")
    else:
        st.sidebar.warning("⚠️ 尚未載入，請點下方按鈕。")

    if st.sidebar.button("📥 載入 500 檔", type="primary"):
        with st.spinner("從 GitHub 取得 S&P 500 完整清單..."):
            try:
                fetcher = DataFetcher()
                all_sp500 = fetcher.fetch_sp500_tickers()
                st.session_state['sp500_all_tickers'] = all_sp500
                st.session_state['risky_assets_source'] = f"S&P 500 全部成分股（共 {len(all_sp500)} 檔，GitHub CSV，非市值排序）"
                st.sidebar.success(f"✅ 已載入 {len(all_sp500)} 檔！")
                st.rerun()
            except RuntimeError as e:
                st.sidebar.error(f"❌ 載入失敗：{e}")
            except Exception as e:
                st.sidebar.error(f"❌ 未預期錯誤：{e}")

# 攻擊型資產文字框（500 檔模式時反灰）
if use_all_sp500 and st.session_state['sp500_all_tickers']:
    # 500 檔模式：禁用輸入框並顯示已載入數量
    n_loaded = len(st.session_state['sp500_all_tickers'])
    st.sidebar.text_area(
        "攻擊型資產（已由 500 檔模式接管）",
        value=f"（已啟用 S&P 500 全部 {n_loaded} 檔模式，輸入框已停用）",
        disabled=True,
        help="請取消勾選「使用全部 S&P 500」以恢復手動輸入。"
    )
    risky_assets = st.session_state['sp500_all_tickers']
elif use_all_sp500 and not st.session_state['sp500_all_tickers']:
    # 勾選了但尚未載入
    st.sidebar.text_area(
        "攻擊型資產（待載入）",
        value="（請點擊「載入 500 檔」按鈕）",
        disabled=True
    )
    risky_assets = [x.strip() for x in st.session_state['risky_assets_str'].split(',')]
else:
    # 正常模式：可編輯
    risky_assets_input = st.sidebar.text_area(
        "攻擊型資產（逗號分隔）",
        value=st.session_state['risky_assets_str'],
        key='risky_assets_input',
        help="輸入美股代碼（逗號分隔）。注意：使用當前市值排名回測存在倖存者偏差。",
        on_change=lambda: st.session_state.update({'risky_assets_str': st.session_state.risky_assets_input})
    )
    risky_assets = [x.strip() for x in risky_assets_input.split(',') if x.strip()]

# ──────────────────────────────────────────────
# 防禦型資產與回測參數
# ──────────────────────────────────────────────
st.sidebar.markdown("### 防禦型資產")
safe_assets_input = st.sidebar.text_input(
    "防禦型資產（逗號分隔）",
    "TLT, IEF, GLD, UUP",
    help="攻擊型資產轉弱時，從中選動能最強的一個持有。"
)

st.sidebar.markdown("### 回測設定")
freq_option = st.sidebar.selectbox("再平衡頻率", ["月 (Monthly)", "週 (Weekly)"])
freq_map = {"月 (Monthly)": "ME", "週 (Weekly)": "W-FRI"}
selected_freq = freq_map[freq_option]

st.sidebar.markdown("#### 複合動能參數")
default_lookbacks = "3, 6, 9" if selected_freq == "ME" else "13, 26, 39"
lookbacks_input = st.sidebar.text_input("回顧期（逗號分隔）", default_lookbacks)
weights_input = st.sidebar.text_input("權重（逗號分隔）", "34, 33, 33")

# 解析回顧期和權重，有錯誤立即顯示
try:
    lookbacks = [int(x.strip()) for x in lookbacks_input.split(',') if x.strip()]
    weights = [float(x.strip()) for x in weights_input.split(',') if x.strip()]
    if not lookbacks:
        st.sidebar.error("❌ 回顧期不可為空。")
        st.stop()
    if len(lookbacks) != len(weights):
        st.sidebar.error(f"❌ 回顧期數量（{len(lookbacks)}）與權重數量（{len(weights)}）不符。")
        st.stop()
except ValueError as e:
    st.sidebar.error(f"❌ 格式錯誤（需為數字，逗號分隔）：{e}")
    st.stop()

top_n = st.sidebar.number_input("持有資產數量（Top N）", min_value=1, max_value=20, value=1)
cash_protection = st.sidebar.checkbox(
    "啟用現金保護",
    value=False,
    help="當最佳防禦資產動能也為負時，持有現金（回報率 0%）。"
)
start_date = st.sidebar.date_input("回測開始日期", pd.to_datetime("2010-01-01"))
initial_capital = st.sidebar.number_input("初始資金（USD）", value=10000.0, min_value=100.0)
benchmark_ticker = st.sidebar.text_input("對照基準", "SPY")

# ──────────────────────────────────────────────
# 組合資產清單（攻擊 + 防禦 + 基準）
# ──────────────────────────────────────────────
safe_assets = [x.strip() for x in safe_assets_input.split(',') if x.strip()]
benchmark = benchmark_ticker.strip()
# 移除空字串，排序去重
risky_assets = [t for t in risky_assets if t]
all_tickers = tuple(sorted(set(risky_assets + safe_assets + [benchmark])))

# ──────────────────────────────────────────────
# 開始回測
# ──────────────────────────────────────────────
n_risky = len(risky_assets)
if n_risky == 0:
    st.warning("⚠️ 攻擊型資產清單為空，請先輸入或載入代碼。")
    st.stop()

if st.sidebar.button("🚀 開始回測", type="primary"):
    # 大量標的時顯示預估時間
    if n_risky > 100:
        n_batches = (n_risky - 1) // 100 + 1
        st.info(f"ℹ️ 攻擊型資產共 **{n_risky}** 檔，數據下載分 **{n_batches}** 批進行，預計需要數分鐘，請耐心等待。")

    # 計算緩衝起始日期（確保動能計算初期有足夠數據）
    max_lb = max(lookbacks)
    buffer_days = int(max_lb * 35) + 365  # 保守估計多抓一年
    fetch_start = start_date - timedelta(days=buffer_days)

    with st.spinner(f"下載 {len(all_tickers)} 檔數據（{fetch_start.strftime('%Y-%m-%d')} 起）..."):
        try:
            fetcher = DataFetcher()
            prices = fetcher.fetch_data(all_tickers, start_date=fetch_start.strftime('%Y-%m-%d'))
        except ValueError as e:
            st.error(f"❌ 數據下載失敗：{e}")
            st.stop()
        except Exception as e:
            st.error(f"❌ 未預期錯誤：{e}")
            st.stop()

    # 驗證下載結果
    missing = [t for t in risky_assets if t not in prices.columns]
    if missing:
        st.warning(f"⚠️ 以下 {len(missing)} 個代碼未能取得數據（可能代碼有誤或已下市）：`{', '.join(missing[:10])}{'...' if len(missing) > 10 else ''}`")

    valid_risky = [t for t in risky_assets if t in prices.columns]
    valid_safe = [t for t in safe_assets if t in prices.columns]

    if not valid_risky:
        st.error("❌ 攻擊型資產全部下載失敗，無法進行回測。請確認代碼是否正確。")
        st.stop()
    if not valid_safe:
        st.error("❌ 防禦型資產全部下載失敗，無法進行回測。請確認代碼是否正確。")
        st.stop()

    st.success(f"✅ 成功取得 {len(prices.columns)} 檔數據（共 {len(prices)} 個交易日）")

    with st.spinner("計算動能信號與回測中..."):
        strategy = MomentumStrategy(prices)
        signals = strategy.generate_signals(
            valid_risky, valid_safe,
            top_n=top_n, frequency=selected_freq,
            lookbacks=lookbacks, weights=weights,
            cash_protection=cash_protection
        )

        # 切片至使用者指定的起始日期
        analysis_start = pd.Timestamp(start_date)
        valid_start = max(analysis_start, signals.index[0]) if not signals.empty else analysis_start
        signals_sliced = signals.loc[valid_start:]

        if signals_sliced.empty:
            st.error("❌ 回測結果為空：有效信號期間不足，請嘗試提前回測開始日期或縮短回顧期。")
            st.stop()

        backtest = Backtest(prices, signals_sliced, initial_capital)
        results = backtest.run_backtest()
        results = results.loc[valid_start:]

        if results.empty:
            st.error("❌ 回測結果為空，請確認日期範圍與數據是否完整。")
            st.stop()

        metrics = backtest.calculate_metrics(results['Portfolio Value'])

        # 計算基準表現
        if benchmark in prices.columns:
            bench_prices = prices[benchmark].reindex(results.index).dropna()
            if not bench_prices.empty:
                bench_series = bench_prices / bench_prices.iloc[0] * initial_capital
            else:
                bench_series = None
        else:
            bench_series = None

    # ────────── 顯示指標 ──────────
    col1, col2, col3 = st.columns(3)
    col1.metric("📈 CAGR（年化報酬率）", f"{metrics['CAGR']:.2%}")
    col2.metric("📉 最大回撤（MDD）", f"{metrics['MDD']:.2%}")
    col3.metric("⚖️ 夏普比率", f"{metrics['Sharpe Ratio']:.2f}")

    # ────────── 走勢圖 ──────────
    st.subheader("資產淨值走勢")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=results.index, y=results['Portfolio Value'],
        name="投資組合", line=dict(color='#00C4FF', width=2)
    ))
    if bench_series is not None:
        fig.add_trace(go.Scatter(
            x=bench_series.index, y=bench_series,
            name=f"對照基準（{benchmark}）",
            line=dict(dash='dash', color='#FF6B6B', width=1.5)
        ))
    fig.update_layout(hovermode='x unified', height=450)
    st.plotly_chart(fig, use_container_width=True)

    # ────────── 最新信號 ──────────
    st.subheader("📅 現在應操作的持倉（本期動能最新信號）")
    st.caption("本期信號 = 用「最新一期結算日（上月底）」的動能計算，代表現在到下次結算日間應持有什麼。與歷史最後一筆不同，因為歷史表最後一筆是上期已結束的持倉。")
    try:
        latest_signal = strategy.get_latest_signal(
            valid_risky, valid_safe,
            top_n=top_n, frequency=selected_freq,
            lookbacks=lookbacks, weights=weights,
            cash_protection=cash_protection
        )
        if "Error" in latest_signal:
            st.warning(f"無法計算最新信號：{latest_signal['Error']}")
        elif not latest_signal:
            st.info("📋 當期信號：**持有現金**")
        else:
            parts = [f"**{asset}** ({weight:.0%})" for asset, weight in latest_signal.items()]
            st.info(f"📋 建議持倉：{', '.join(parts)}")
    except Exception as e:
        st.warning(f"計算最新信號時發生錯誤：{e}")

    # ────────── 歷史持倉紀錄 ──────────
    with st.expander("📋 查看歷史持倉紀錄"):
        st.markdown("""
        > **💡 日期說明**：日期為該期間的**結算/結束日**，持倉內容為當期持有的標的。
        > - 例如 `2025-03-31` 持有 `NVDA`，代表 3 月份（2/28 至 3/31）持有 NVDA，決策於 2 月底做出。
        > - ✅ **最後一筆（最新日期）= 現在應操作的持倉**，與上方「現在應操作的持倉」相同。
        """)


        def get_held_assets(row):
            held = [asset for asset, w in row.items() if w > 0]
            return ", ".join(held) if held else "CASH"

        historical = signals_sliced.apply(get_held_assets, axis=1).to_frame("本期持倉")
        st.dataframe(historical.sort_index(ascending=False), use_container_width=True)

    # ────────── 每月回報 ──────────
    st.subheader("每期回報率")
    st.bar_chart(results['Portfolio Returns'])

st.markdown("---")
st.markdown("Developed by Antigravity.")
