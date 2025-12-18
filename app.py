import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
from data import DataFetcher
from strategy import MomentumStrategy
from backtest import Backtest

st.set_page_config(page_title="美股雙動能策略回測", layout="wide")

st.title("美股雙動能策略回測工具")

# 側邊欄參數
st.sidebar.header("回測參數設定") 

if st.sidebar.button("清除快取 (Clear Cache)", help="若遇到數據錯誤或無法更新的情況，請點擊此按鈕清除所有暫存資料。"):
    st.cache_data.clear()
    st.success("快取已清除！")
    st.rerun() 
# 側邊欄參數
st.sidebar.header("回測參數設定") 

if 'risky_assets' not in st.session_state:
    # 啟動時自動抓取 Slickcharts 前 50 大
    with st.spinner("正在初始化：從 Slickcharts 獲取最新 S&P 500 前 50 大清單..."):
        try:
            fetcher = DataFetcher()
            top_50 = fetcher.get_top_n_by_market_cap(50)
            if top_50:
                st.session_state['risky_assets'] = ", ".join(top_50)
            else:
                st.session_state['risky_assets'] = "SPY" # Fallback
        except Exception:
            st.session_state['risky_assets'] = "SPY"

col_params, col_update = st.sidebar.columns([3, 1])
if col_update.button("更新", help="從 Slickcharts 獲取最新 S&P 500 權重前 50 大企業 (速度較快)"):
    with st.spinner("正在從 Slickcharts 獲取最新名單..."):
        try:
            fetcher = DataFetcher()
            # 獲取前 50 大
            top_50 = fetcher.get_top_n_by_market_cap(50)
            if top_50:
                st.session_state['risky_assets'] = ", ".join(top_50)
                st.success("更新完成！")
                st.rerun()
            else:
                st.error("更新失敗，無法獲取數據。")
        except Exception as e:
            st.error(f"發生錯誤: {e}")

risky_assets_input = st.sidebar.text_area("攻擊型資產 (逗號分隔)", value=st.session_state['risky_assets'], key='risky_assets_input', help="請輸入美股代碼。注意：使用當前市值前50大進行歷史回測會存在倖存者偏差。", on_change=lambda: st.session_state.update({'risky_assets': st.session_state.risky_assets_input}))
safe_assets_input = st.sidebar.text_input("防禦型資產 (逗號分隔)", "TLT, IEF, GLD, UUP", help="當攻擊型資產轉弱時，將從中選擇動能最強的一個持有。")

# 頻率選擇
freq_option = st.sidebar.selectbox("回測/再平衡頻率", ["月 (Monthly)", "週 (Weekly)"])
freq_map = {"月 (Monthly)": "ME", "週 (Weekly)": "W-FRI"}
selected_freq = freq_map[freq_option]

# 複合動能參數
st.sidebar.markdown("### 複合動能參數")
default_lookbacks = "3, 6, 9" if selected_freq == "ME" else "13, 26, 39"
lookbacks_input = st.sidebar.text_input("回顧期 (逗號分隔)", default_lookbacks)
weights_input = st.sidebar.text_input("權重 (逗號分隔)", "34, 33, 33")

# 解析回顧期和權重
try:
    lookbacks = [int(x.strip()) for x in lookbacks_input.split(',')]
    weights = [float(x.strip()) for x in weights_input.split(',')]
    if len(lookbacks) != len(weights):
        st.error("警告：回顧期與權重數量不符！")
        st.stop()
except ValueError:
    st.error("輸入格式錯誤，請輸入數字 (逗號分隔)")
    st.stop()


top_n = st.sidebar.number_input("持有資產數量 (Top N)", min_value=1, max_value=10, value=1)
cash_protection = st.sidebar.checkbox("啟用現金保護", value=False, help="當最佳防禦型資產動能也為負時，持有現金 (回報率0%)。")

start_date = st.sidebar.date_input("開始日期", pd.to_datetime("2010-01-01"))
initial_capital = st.sidebar.number_input("初始資金", value=10000.0)
benchmark_ticker = st.sidebar.text_input("對照基準", "SPY")

# 解析輸入
risky_assets = [x.strip() for x in risky_assets_input.split(',')]
safe_assets = [x.strip() for x in safe_assets_input.split(',')]
benchmark = benchmark_ticker.strip()
# 確保基準指標在獲取列表中，但處理重複項
all_tickers = sorted(list(set(risky_assets + safe_assets + [benchmark])))

if st.sidebar.button("開始回測"):
    with st.spinner("下載數據中..."):
        try:
            fetcher = DataFetcher()
            
            # 計算緩衝區間：找出最大回顧期 (月) -> 轉換為天數 -> 加上緩衝
            # 假設一個月30天，若用週頻率大約是 4.3 週/月。
            # 為了安全，我們多抓 2 年 (730天) 或 2倍的最大回顧期。
            max_lb = max(lookbacks)
            # 月頻率乘 30 天，週頻率乘 7 天，這裡簡化直接給充足緩衝
            buffer_days = int(max_lb * 32 * 1.5) + 365 
            
            fetch_start_date = start_date - timedelta(days=buffer_days)
            # 只顯示日期字串
            st.info(f"系統自動抓取緩衝數據起始日: {fetch_start_date.strftime('%Y-%m-%d')} (為了計算初期指標)")
            
            prices = fetcher.fetch_data(all_tickers, start_date=fetch_start_date.strftime('%Y-%m-%d'))
        except Exception as e:
            st.error(f"數據下載失敗: {e}。請檢查網路連線或代碼是否正確。")
            st.stop()
    
    if prices.empty:
        st.error("無法取得數據，請確認代碼是否正確。")
    else:
        st.success(f"成功取得數據，共 {len(prices)} 筆。")
        
        with st.spinner("計算策略與回測中..."):
            strategy = MomentumStrategy(prices) # init 中的 lookback_period 現在未被使用/可選
            # 傳遞新參數
            signals = strategy.generate_signals(risky_assets, safe_assets, top_n=top_n, frequency=selected_freq, lookbacks=lookbacks, weights=weights, cash_protection=cash_protection)
            
            # [修正] 截斷信號與價格，只進行使用者指定區間的回測
            # 必須保留一個緩衝，因為回測器計算回報需要 t-1
            # 但我們的 backtest.py 邏輯比較簡單，直接用 signals 索引對齊
            # 所以我們可以先切片
            
            analysis_start = pd.Timestamp(start_date)
            # 確保有數據的日期 (信號可能會從 buffer 期開始產生)
            valid_start = max(analysis_start, signals.index[0]) if not signals.empty else analysis_start
            
            signals = signals.loc[valid_start:]
            # 價格不需要切片給 Backtest，它會自己對齊，但為了效能可以切
            # 但 Backtest 用的是 prices，如果 prices 太大沒關係，重點是 signals
            
            backtest = Backtest(prices, signals, initial_capital)
            results = backtest.run_backtest()
            
            # 從使用者指定的開始日期後開始顯示結果
            results = results.loc[valid_start:]
            
            if results.empty:
               st.error("回測結果為空，可能是因為回顧期太長導致有效數據不足，請嘗試提前開始日期或縮短回顧期。")
               st.stop()

            metrics = backtest.calculate_metrics(results['Portfolio Value'])
            
            # 計算基準指標表現
            # 將基準價格重新索引以匹配投資組合結果索引 (日期) 以進行公平比較
            if benchmark in prices.columns:
                bench_prices = prices[benchmark].loc[results.index]
                # 將基準指標歸一化至初始資金
                bench_returns = bench_prices / bench_prices.iloc[0] * initial_capital
            else:
                bench_returns = None
            
        # 顯示指標
        col1, col2, col3 = st.columns(3)
        col1.metric("CAGR (年化報酬率)", f"{metrics['CAGR']:.2%}")
        col2.metric("最大回撤 (MDD)", f"{metrics['MDD']:.2%}")
        col3.metric("夏普比率 (Sharpe Ratio)", f"{metrics['Sharpe Ratio']:.2f}")
        
        # 繪圖
        st.subheader("資產淨值走勢")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=results.index, y=results['Portfolio Value'], name="投資組合 (Portfolio)"))
        
        if bench_returns is not None:
             fig.add_trace(go.Scatter(x=bench_returns.index, y=bench_returns, name=f"對照基準 ({benchmark})", line=dict(dash='dash')))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 最新信號顯示
        st.subheader("當月預計買進標的")
        
        latest_signal = strategy.get_latest_signal(
            risky_assets, safe_assets, top_n=top_n, frequency=selected_freq, 
            lookbacks=lookbacks, weights=weights, cash_protection=cash_protection
        )
        
        if "Error" in latest_signal:
            st.warning(f"無法計算最新信號: {latest_signal['Error']}")
        else:
            # 格式化信號字串
            signal_text = []
            for asset, weight in latest_signal.items():
                signal_text.append(f"**{asset}** ({weight:.0%})")
            
            st.info(f"📅 下期建議持倉: {', '.join(signal_text)}")

        # 如果需要，用於查看歷史的擴展器
        with st.expander("查看歷史持倉紀錄 (包含回測期間)"):
            st.markdown("""
            > **💡 日期說明**：表中的日期為該持有期間的 **「結算/結束日 (End of Period)」**。
            > *   例如：若頻率為月，`2023-01-31` 顯示 `NVDA`，代表 **整個 1 月份** (12月底至 1月底) 皆持有 NVDA。
            > *   也就是說，該決策是在 **12月底** 做出的。
            """)
            # 將稀疏矩陣 (全部資產) 轉換為僅顯示持有的資產
            # 對每一行，找出值 > 0 的欄位名稱
            def get_held_assets(row):
                held = []
                for asset, weight in row.items():
                    if weight > 0:
                        held.append(f"{asset}")
                return ", ".join(held) if held else "CASH"

            historical_holdings = signals.apply(get_held_assets, axis=1).to_frame("本期持倉")
            # 按日期降序排列，方便查看最近紀錄
            st.dataframe(historical_holdings.sort_index(ascending=False), width=800)
            
        st.subheader("每月回報")
        st.bar_chart(results['Portfolio Returns'])

st.markdown("---")
st.markdown("Developed by Antigravity.")
