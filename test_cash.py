from data import DataFetcher
from strategy import MomentumStrategy
from backtest import Backtest
import pandas as pd
import numpy as np

def test_cash_protection():
    print("Testing Cash Protection Logic...")
    
    # Mock Data:
    # 1. Risky (A) goes down.
    # 2. Safe (B) goes down.
    # 3. Expect signals to be 0 for both (Cash).
    
    dates = pd.date_range(start='2020-01-01', periods=10, freq='ME')
    # Prices declining: 100, 99, 98...
    prices_data = {
        'A': [100 - i*2 for i in range(10)], # -2% per month approx
        'B': [100 - i*1 for i in range(10)], # -1% per month approx
        'C': [100 + i for i in range(10)]    # Benchmark up
    }
    prices = pd.DataFrame(prices_data, index=dates)
    
    print("Prices (Declining):")
    print(prices.tail())
    
    strategy = MomentumStrategy(prices)
    
    print("\n--- Test 1: Cash Protection OFF ---")
    signals_off = strategy.generate_signals(['A'], 'B', top_n=1, frequency='ME', lookbacks=[1], weights=[1], cash_protection=False)
    print(signals_off.tail(3))
    # Expectation: A is bad (-2%), B is bad (-1%). 
    # Logic: A < 0 -> Switch to Safe. Safe is B. So B should be 1.0.
    
    if signals_off['B'].iloc[-1] == 1.0:
        print("SUCCESS: Without protection, invested in Safe asset (even if down).")
    else:
        print("FAILED: Should be in Safe asset.")

    print("\n--- Test 2: Cash Protection ON ---")
    signals_on = strategy.generate_signals(['A'], 'B', top_n=1, frequency='ME', lookbacks=[1], weights=[1], cash_protection=True)
    print(signals_on.tail(3))
    # Expectation: A < 0 -> Check Safe. Safe (B) < 0 -> Cash.
    # Both A and B signals should be 0.
    
    if signals_on['A'].iloc[-1] == 0.0 and signals_on['B'].iloc[-1] == 0.0:
        print("SUCCESS: With protection, invested in Cash (Signals=0) when Safe asset is down.")
    else:
        print("FAILED: Should be in Cash.")

if __name__ == "__main__":
    test_cash_protection()
