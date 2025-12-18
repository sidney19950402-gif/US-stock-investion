import yfinance as yf
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import ssl
import urllib.request

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

    def __init__(self):
        pass

    @st.cache_data(ttl=3600)
    def fetch_data(_self, tickers: list, start_date: str, end_date: str = None) -> pd.DataFrame:
        """
        獲取指定代碼的調整後收盤價 (Adjusted Close)。
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            
        print(f"Downloading data for {tickers} from {start_date} to {end_date}...")
        
        # [修正] 使用 auto_adjust=True，這是 yfinance 推薦的方式，直接獲取調整後價格
        # 並使用 threads=False 以降低並發導致的錯誤率 (雖然慢一點但較穩)
        df = yf.download(tickers, start=start_date, end=end_date, auto_adjust=True, threads=False)
        
        if df.empty:
            raise ValueError("Download failed: No data returned from Yahoo Finance.")

        # 使用 'Close' (因為 auto_adjust=True，這已經是調整後收盤價)
        if 'Close' in df:
            data = df['Close']
        else:
            # Fallback (極少見)
            print(f"Available columns: {df.columns}")
            # 嘗試找 Adj Close 或 Close
            for col in ['Adj Close', 'Close']:
                if col in df:
                    data = df[col]
                    break
            else:
                 raise ValueError(f"Required columns not found. Available: {df.columns}")

        # 如果只下載了一個代碼，yfinance 可能會返回一個 Series。將其轉換為 DataFrame。
        if isinstance(data, pd.Series):
            data = data.to_frame()
            data.columns = tickers
        
        # [修正] 數據清洗標準化：
        # 1. 刪除全空行 (休市日)
        data.dropna(how='all', inplace=True)
        # 2. 前向填充 (Forward Fill)：處理個別股票缺漏數據，假設價格未變
        data.ffill(inplace=True)
        # 3. 後向填充 (Backward Fill)：處理剛上市前幾天的短暫缺口 (選用)
        # data.bfill(inplace=True)
        
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

    def get_top_n_by_market_cap(self, n: int = 50) -> list:
        """
        獲取 S&P 500 中市值最大的前 N 檔股票代碼。
        改用 Slickcharts 來源，因為它已經依照指數權重排序。
        """
        try:
            url = "https://www.slickcharts.com/sp500"
            
            # 使用 urllib 設置 User-Agent 以避免 403 Forbidden
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                html = response.read()
                
            tables = pd.read_html(html)
            df = tables[0]
            
            # Slickcharts 的表格有一個 Symbol 欄位
            tickers = df['Symbol'].tolist()
            
            # 處理特殊代碼格式，例如 BRK.B -> BRK-B
            tickers = [t.replace('.', '-') for t in tickers]
            
            # 因為已經排好序了，直接取前 N 個
            return tickers[:n]
            
        except Exception as e:
            print(f"Error fetching data from Slickcharts: {e}")
            # Fallback: 如果 Slickcharts 失敗，嘗試回退到 Wikipedia + 多執行緒抓取 (舊邏輯)
            print("Fallback to Wikipedia + Yahoo Finance...")
            return self._get_top_n_fallback(n)

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
