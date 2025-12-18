from data import DataFetcher
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

def debug():
    fetcher = DataFetcher()
    print("Testing get_top_n_by_market_cap(10) from Slickcharts...")
    top_n = fetcher.get_top_n_by_market_cap(n=10)
    print(f"Top 10 Result: {top_n}")

if __name__ == "__main__":
    debug()
