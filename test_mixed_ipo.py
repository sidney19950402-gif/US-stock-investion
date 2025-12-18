from data import DataFetcher
from strategy import MomentumStrategy
from backtest import Backtest
import pandas as pd

def test_mixed_ipo():
    print("Testing Mixed IPO dates logic...")
    
    # 1. Fetch Data for SPY (old) and UBER (new, ~2019)
    # Start date 2018 to see the transition
    fetcher = DataFetcher()
    tickers = ['SPY', 'UBER', 'TLT'] 
    print("Fetching data (SPY, UBER, TLT) from 2018...")
    prices = fetcher.fetch_data(tickers, start_date='2018-01-01', end_date='2020-01-01')
    
    if prices.empty:
        print("FAILED: prices is empty.")
        return
        
    print(f"Prices shape: {prices.shape}")
    print("First few rows (Should have NaNs for UBER):")
    print(prices.head())
    
    if prices['UBER'].iloc[0] == prices['UBER'].iloc[0]: # Check if not NaN (NaN != NaN)
         print("WARNING: UBER has data at start? Should be NaN if start is 2018. (UBER IPO May 2019)")
    else:
         print("SUCCESS: UBER is NaN at start as expected.")

    # 2. Strategy
    print("Running Strategy...")
    strategy = MomentumStrategy(prices)
    signals = strategy.generate_signals(risky_assets=['SPY', 'UBER'], safe_assets=['TLT'], top_n=1)
    
    print("Signals around UBER IPO:")
    # Find index where UBER starts having data
    first_valid = prices['UBER'].first_valid_index()
    if first_valid:
        loc = prices.index.get_loc(first_valid)
        print(signals.iloc[loc-2:loc+5])
    else:
        print("UBER data never valid?")

    # 3. Backtest
    print("Running Backtest...")
    backtest = Backtest(prices, signals)
    results = backtest.run_backtest()
    
    if results['Portfolio Returns'].isnull().any():
        print("FAILED: Portfolio Returns contain NaNs!")
        print(results[results['Portfolio Returns'].isnull()])
    else:
        print("SUCCESS: No NaNs in Portfolio Returns.")
        
    print("Final Portfolio Value:", results['Portfolio Value'].iloc[-1])

if __name__ == "__main__":
    test_mixed_ipo()
