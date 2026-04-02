import yfinance as yf
import streamlit as st
import pandas as pd
import requests
import concurrent.futures
from datetime import datetime
from io import StringIO
import ssl

# SSL 憑證驗證繞過（針對 macOS Python 環境常見問題）
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass


class DataFetcher:
    def __init__(self):
        pass

    @st.cache_data(ttl=3600)
    def fetch_data(_self, tickers: tuple, start_date: str, end_date: str = None) -> pd.DataFrame:
        """
        分批下載調整後收盤價，支援大量標的（自動分批 100 檔/批）。
        tickers 必須傳入 tuple（可雜湊），以確保快取 key 穩定。
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # 去重並排序，確保相同清單的 cache key 一致
        tickers = tuple(sorted(set(tickers)))
        ticker_list = list(tickers)
        n = len(ticker_list)

        print(f"開始下載 {n} 檔數據，期間：{start_date} ~ {end_date}")

        BATCH_SIZE = 100
        batches_input = [ticker_list[i:i + BATCH_SIZE] for i in range(0, n, BATCH_SIZE)]
        all_parts = []

        for idx, batch in enumerate(batches_input):
            batch_label = f"第 {idx+1}/{len(batches_input)} 批（{len(batch)} 檔）"
            print(f"下載 {batch_label}...")
            try:
                df = yf.download(
                    batch, start=start_date, end=end_date,
                    auto_adjust=True, threads=True, progress=False
                )
                if df.empty:
                    print(f"{batch_label} 回傳空資料，跳過。")
                    continue

                # 提取 Close 欄位，相容單標的（Series）和多標的（DataFrame）
                if isinstance(df.columns, pd.MultiIndex):
                    # 多標的：columns = (指標, 代碼)
                    if 'Close' in df.columns.get_level_values(0):
                        part = df['Close']
                    else:
                        print(f"{batch_label} 找不到 Close 欄位，可用：{df.columns.get_level_values(0).unique().tolist()}")
                        continue
                else:
                    # 單標的：columns = ['Close', 'Open', ...]
                    if 'Close' in df.columns:
                        part = df[['Close']].rename(columns={'Close': batch[0]})
                    else:
                        print(f"{batch_label} 找不到 Close 欄位。")
                        continue

                if isinstance(part, pd.Series):
                    part = part.to_frame(name=batch[0] if len(batch) == 1 else 'unknown')

                all_parts.append(part)

            except Exception as e:
                print(f"{batch_label} 下載失敗：{e}")

        if not all_parts:
            raise ValueError("所有批次下載均失敗，請確認代碼是否正確或重試。")

        # 合併所有批次
        data = pd.concat(all_parts, axis=1)
        # 移除重複欄（不同批次可能有重疊代碼）
        data = data.loc[:, ~data.columns.duplicated()]
        # 刪除全空行（休市日）
        data.dropna(how='all', inplace=True)

        if data.empty:
            raise ValueError("數據合併後為空，請確認日期範圍是否有效。")

        print(f"下載完成：{len(data.columns)} 檔，共 {len(data)} 筆交易日數據。")
        return data

    @st.cache_data(ttl=86400)  # 每日快取一次
    def fetch_sp500_tickers(_self) -> list:
        """
        從 GitHub 公開 CSV 取得完整 S&P 500 成分股清單（約 503 檔）。
        此來源不受雲端環境封鎖，穩定可用。
        """
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        try:
            r = requests.get(url, timeout=15, verify=False)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
            if 'Symbol' not in df.columns:
                raise ValueError(f"CSV 格式異常，找不到 Symbol 欄位。可用欄位：{df.columns.tolist()}")
            tickers = [t.replace('.', '-') for t in df['Symbol'].tolist()]
            if not tickers:
                raise ValueError("CSV 解析後清單為空。")
            print(f"成功取得 S&P 500 成分股清單：{len(tickers)} 檔。")
            return tickers
        except requests.RequestException as e:
            raise RuntimeError(f"網路請求失敗（{url}）：{e}") from e
        except Exception as e:
            raise RuntimeError(f"解析 S&P 500 清單失敗：{e}") from e

    @st.cache_data(ttl=86400)  # 每日快取一次
    def get_top_n_by_market_cap(_self, n: int = 50):
        """
        使用 yfinance 查詢 S&P 500 成分股即時市值，依市值排序後回傳前 N 大。
        回傳 (tickers: list, summary: str) 元組。

        注意：500 檔並行查詢約需 30-60 秒，此為正確且必要的延遲。
        """
        # 步驟 1：取得完整成分股清單
        all_tickers = _self.fetch_sp500_tickers()

        # 步驟 2：並行查詢市值（20 執行緒）
        print(f"開始並行查詢 {len(all_tickers)} 檔市值（20 執行緒）...")

        def _fetch_market_cap(ticker):
            try:
                mc = yf.Ticker(ticker).fast_info.market_cap
                if mc and mc > 0:
                    return (ticker, mc)
            except Exception:
                pass
            return None

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(_fetch_market_cap, t): t for t in all_tickers}
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)

        if not results:
            raise RuntimeError("市值查詢全部失敗，請確認 yfinance 可正常連線。")

        # 步驟 3：依市值排序，取前 N 大
        results.sort(key=lambda x: x[1], reverse=True)
        top_tickers = [t for t, _ in results[:n]]
        success_rate = f"{len(results)}/{len(all_tickers)}"

        summary = f"yfinance 即時市值排序（成功查詢 {success_rate} 檔）"
        print(f"完成！前 {n} 大：{top_tickers[:5]}...")
        return top_tickers, summary
