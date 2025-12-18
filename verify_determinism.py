from data import DataFetcher
from strategy import MomentumStrategy
from backtest import Backtest
import pandas as pd
import numpy as np

def run_once():
    # Inputs
    risky_assets = ["AAPL", "NVDA", "MSFT"]
    safe_assets = ["TLT", "IEF"]
    all_tickers = sorted(list(set(risky_assets + safe_assets)))
    start_date = "2020-01-01"
    
    # 1. Fetch
    fetcher = DataFetcher()
    # Mocking cache clearing by not using st cache here, just raw call
    # Note: fetch_data inside data.py has @st.cache_data, but running as script outside streamlit 
    # might bypass it or behave differently. We want to test RAW logic consistency.
    prices = fetcher.fetch_data(all_tickers, start_date="2018-01-01") # Buffer included
    
    # 2. Strategy
    strategy = MomentumStrategy(prices)
    signals = strategy.generate_signals(
        risky_assets, safe_assets, 
        top_n=1, frequency='ME', 
        lookbacks=[12], weights=[100], 
        cash_protection=False
    )
    
    # Slice
    analysis_start = pd.Timestamp(start_date)
    signals = signals.loc[analysis_start:]
    
    # 3. Backtest
    backtest = Backtest(prices, signals, 10000.0)
    results = backtest.run_backtest()
    results = results.loc[analysis_start:]
    
    metrics = backtest.calculate_metrics(results['Portfolio Value'])
    return metrics['CAGR'], metrics['Sharpe Ratio']

def verify():
    print("Running determinism check (5 runs)...")
    results = []
    for i in range(5):
        cagr, sharpe = run_once()
        print(f"Run {i+1}: CAGR={cagr}, Sharpe={sharpe}")
        results.append((cagr, sharpe))
    
    # Check if all identical
    first = results[0]
    all_match = all(r == first for r in results)
    
    if all_match:
        print("\nSUCCESS: All runs produced identical results.")
    else:
        print("\nFAILURE: Results differ!")

if __name__ == "__main__":
    verify()
