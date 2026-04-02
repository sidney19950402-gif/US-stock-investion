import yfinance as yf
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import ssl
import urllib.request
import requests

# SSL 憑證驗證繞過 (針對 macOS Python 環境常見問題)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

class DataFetcher:
    def __init__(self):
        pass

    @st.cache_data(ttl=3600)
    def fetch_data(_self, tickers: list, start_date: str, end_date: str = None) -> pd.DataFrame:
        """
        獲取指定代碼的調整後收盤僷 (Adjusted Close)。
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 确保 tickers 是 tuple (可雜湊型態)，避免快取 key 錯誤
        tickers = tuple(sorted(set(tickers)))
        
        print(f"Downloading {len(tickers)} tickers from {start_date} to {end_date}...")

        # 大量股票分批下載，每批最多 100 檔
        BATCH_SIZE = 100
        ticker_list = list(tickers)
        
        if len(ticker_list) <= BATCH_SIZE:
            # 小量直接一次下載
            df = yf.download(ticker_list, start=start_date, end=end_date,
                             auto_adjust=True, threads=True, progress=False)
            if df.empty:
                raise ValueError("Download failed: No data returned from Yahoo Finance.")
            batches = [df]
        else:
            # 大量分批下載
            batches = []
            for i in range(0, len(ticker_list), BATCH_SIZE):
                batch = ticker_list[i:i + BATCH_SIZE]
                print(f"Downloading batch {i//BATCH_SIZE + 1}/{(len(ticker_list)-1)//BATCH_SIZE + 1}: {len(batch)} tickers...")
                try:
                    b_df = yf.download(batch, start=start_date, end=end_date,
                                       auto_adjust=True, threads=True, progress=False)
                    if not b_df.empty:
                        batches.append(b_df)
                except Exception as batch_err:
                    print(f"Batch error: {batch_err}")
            if not batches:
                raise ValueError("All batches failed.")

        # 合併所有批次的 Close 欄位
        all_data_parts = []
        for b_df in batches:
            if 'Close' in b_df:
                part = b_df['Close']
            elif isinstance(b_df.columns, pd.MultiIndex):
                part = b_df.xs('Close', axis=1, level=0) if 'Close' in b_df.columns.get_level_values(0) else b_df.iloc[:, 0:1]
            else:
                continue
            if isinstance(part, pd.Series):
                part = part.to_frame()
            all_data_parts.append(part)
        
        if not all_data_parts:
            raise ValueError("No usable Close data found.")
        
        data = pd.concat(all_data_parts, axis=1)
        # 移除重複欄
        data = data.loc[:, ~data.columns.duplicated()]
        
        # 數據清洗
        # 1. 刪除全空行 (休市日)
        data.dropna(how='all', inplace=True)
        # 2. 不做 ffill — 保留 NaN 讓動能計算自然處理，避免影響歷史結果。
        # (新上市股票在 IPO 前期為 NaN 是正確行為)
        
        if data.empty:
            raise ValueError("Data is empty after processing.")
        
        return data

    def fetch_sp500_tickers(self) -> list:
        """
        從 Wikipedia 抓取 S&P 500 成分股代碼。
        """
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            
            # 使用 urllib 設置 User-Agent 以避免 403 Forbidden
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                html = response.read()
                
            tables = pd.read_html(html)
            # 第一個表格通常是成分股列表
            df = tables[0]
            # Symbol 欄位
            tickers = df['Symbol'].tolist()
            # 處理特殊代碼格式，例如 BRK.B -> BRK-B (Yahoo Finance 格式)
            tickers = [t.replace('.', '-') for t in tickers]
            return tickers
        except Exception as e:
            print(f"Error fetching S&P 500 tickers: {e}")
            return []

    def get_top_n_by_market_cap(self, n: int = 50):
        """
        獲取 S&P 500 中市值最大的前 N 檔股票代碼。
        回傳 (tickers: list, source: str) 元組。
        """
        # --- 主要來源：Slickcharts (已依 S&P 500 權重排序) ---
        try:
            url = "https://www.slickcharts.com/sp500"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'Connection': 'keep-alive',
            }
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            from io import StringIO
            tables = pd.read_html(StringIO(response.text))
            df = tables[0]
            tickers = df['Symbol'].tolist()
            tickers = [t.replace('.', '-') for t in tickers]
            if tickers:
                return tickers[:n], "Slickcharts（依 S&P 500 指數權重排序）"
        except Exception as slick_err:
            print(f"Slickcharts 失敗: {slick_err}")

        # --- 備援 1：GitHub 公開 CSV (datasets/s-and-p-500-companies) ---
        try:
            csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
            r = requests.get(csv_url, timeout=10, verify=False)
            r.raise_for_status()
            from io import StringIO
            df = pd.read_csv(StringIO(r.text))
            tickers = df['Symbol'].tolist()
            tickers = [t.replace('.', '-') for t in tickers]
            if tickers:
                return tickers[:n], "GitHub CSV（字母排序，非市值排序）"
        except Exception as csv_err:
            print(f"GitHub CSV 失敗: {csv_err}")

        # --- 備援 2：Wikipedia ---
        try:
            wiki_tickers = self.fetch_sp500_tickers()
            if wiki_tickers:
                return wiki_tickers[:n], "Wikipedia（字母排序，非市值排序）"
        except Exception:
            pass

        return [], "無法獲取"

    def _get_top_n_fallback(self, n: int) -> list:
        """
        舊的邏輯：Wiki -> Yahoo Market Cap (並行抓取)
        """
        tickers = self.fetch_sp500_tickers()
        if not tickers:
            return []
        
        print(f"Fetching market caps for {len(tickers)} tickers...")
        
        market_caps = []
        import concurrent.futures

        def fetch_cap(t):
            try:
                # 使用 fast_info 避免完整請求
                mc = yf.Ticker(t).fast_info.get('marketCap')
                if mc:
                    return (t, mc)
            except Exception:
                pass
            return None

        # 使用執行緒池並行處理
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_ticker = {executor.submit(fetch_cap, t): t for t in tickers}
            for future in concurrent.futures.as_completed(future_to_ticker):
                res = future.result()
                if res:
                    market_caps.append(res)
        
        # 排序
        market_caps.sort(key=lambda x: x[1], reverse=True)
        
        top_n_tickers = [x[0] for x in market_caps[:n]]
        return top_n_tickers
