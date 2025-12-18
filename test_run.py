from data import DataFetcher
from strategy import MomentumStrategy
from backtest import Backtest
import pandas as pd

def test_logic():
    print("Starting verification...")
    
    # 1. Test Data Fetcher
    fetcher = DataFetcher()
    tickers = ['SPY', 'EFA', 'AGG']
    # Use a fixed date range for reproducibility
    print("Fetching data...")
    prices = fetcher.fetch_data(tickers, start_date='2020-01-01', end_date='2021-01-01')
    
    if prices.empty:
        print("FAILED: Data fetch returned empty DataFrame.")
        return
    print(f"Data fetched successfully. Shape: {prices.shape}")
    
    # 2. Test Strategy
    print("Calculating momentum (Weekly, Top 2, Composite [1, 4])...")
    strategy = MomentumStrategy(prices)
    signals = strategy.generate_signals(
        risky_assets=['SPY', 'EFA'], 
        safe_assets=['AGG'], 
        top_n=2, 
        frequency='W-FRI',
        lookbacks=[1, 4],
        weights=[0.5, 0.5]
    )
    
    print("Signals generated (Tail):")
    print(signals.tail())
    
    if signals.shape[1] != 3:
        print("FAILED: Signals columns mismatch.")
        return
        
    # Check if we have weights like 0.5
    if (signals == 0.5).any().any():
        print("SUCCESS: Found fractional weights (Top N > 1 logic working).")
    else:
        print("WARNING: No fractional weights found. (Could be normal if only 1 asset qualified always, but unlikely for Top N=2 unless one always bad)")

    if signals.isnull().all().all():
        print("FAILED: Signals are all NaN or empty.")
        return

    # 3. Test Backtest
    print("Running backtest...")
    backtest = Backtest(prices, signals, initial_capital=10000)
    results = backtest.run_backtest()
    
    print("Backtest results:")
    print(results.tail())
    
    if results.empty:
        print("FAILED: Backtest results empty.")
        return
        
    metrics = backtest.calculate_metrics(results['Portfolio Value'])
    print("Metrics:")
    print(metrics)
    print("VERIFICATION SUCCESSFUL")

if __name__ == "__main__":
    test_logic()
