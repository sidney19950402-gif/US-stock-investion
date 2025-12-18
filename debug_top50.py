from data import DataFetcher
import pandas as pd
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

def debug():
    fetcher = DataFetcher()
    print("Testing fetch_sp500_tickers()...")
    tickers = fetcher.fetch_sp500_tickers()
    print(f"Tickers found: {len(tickers)}")
    if len(tickers) > 0:
        print(f"First 5 tickers: {tickers[:5]}")
    else:
        print("No tickers found from Wikipedia.")
        # Try to print read_html result if possible
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            tables = pd.read_html(url)
            print(f"Tables found: {len(tables)}")
        except Exception as e:
            print(f"pd.read_html failed: {e}")
            return

    print("\nTesting get_top_n_by_market_cap(5)...")
    top_n = fetcher.get_top_n_by_market_cap(n=5)
    print(f"Top 5 Result: {top_n}")

if __name__ == "__main__":
    debug()
