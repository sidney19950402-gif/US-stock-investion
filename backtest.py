import pandas as pd
import numpy as np

class Backtest:
    def __init__(self, prices: pd.DataFrame, signals: pd.DataFrame, initial_capital: float = 10000.0):
        self.prices = prices
        self.signals = signals
        self.initial_capital = initial_capital

    def run_backtest(self) -> pd.DataFrame:
        """
        計算隨時間變化的投資組合價值。
        """
        # 從信號索引確定頻率
        # 我們假設信號索引是再平衡頻率 (例如每週或每月)
        
        # 重新取樣價格以匹配信號頻率 (例如，如果信號是每週，我們需要每週價格)
        # 我們可以推斷頻率或只是使用信號索引來重新索引價格
        
        # 獲取與信號相同頻率的回報率
        # 我們將價格重新索引到信號日期。
        # 使用 'asfreq' 或 'reindex' 確保我們選取該特定日期的價格。
        # 注意：如果信號日期是例如週五，我們需要週五的價格。
        # 我們的信號邏輯使用 resample().last()，所以日期應該與重新取樣的日期匹配。
        
        model_prices = self.prices.loc[self.prices.index.intersection(self.signals.index)]
        
        if model_prices.empty:
            # 如果確切日期不匹配的備案 (例如由於假期偏移，如果不小心)
            # 但由於信號來自價格，除非被操縱，否則它們應該匹配。
            # 讓我們試著更穩健：如果我們傳遞了它，使用相同的邏輯重新取樣？
            # 最好依賴交集。
            pass
            
        # 計算這些期間基礎資產的回報率
        returns = model_prices.pct_change()
        
        # 對齊信號和回報率
        common_index = returns.index.intersection(self.signals.index)
        returns = returns.loc[common_index]
        signals = self.signals.loc[common_index]
        
        # 計算投資組合回報率
        # 投資組合回報_t = sum(信號_{t, 資產} * 回報_{t, 資產})
        # 使用 fillna(0) 處理資產信號=0 但回報=NaN (IPO 前) 導致 0*NaN=NaN 的情況
        weighted_returns = (signals * returns)
        portfolio_returns = weighted_returns.sum(axis=1, min_count=1).fillna(0)
        
        # 計算累積回報
        portfolio_value = self.initial_capital * (1 + portfolio_returns).cumprod()
        
        # 結合成結果 DataFrame
        result = pd.DataFrame({
            'Portfolio Returns': portfolio_returns,
            'Portfolio Value': portfolio_value
        })
        
        return result

    def calculate_metrics(self, portfolio_value: pd.Series):
        """
        計算 CAGR, MDD, 夏普比率 (Sharpe Ratio)。
        """
        # CAGR
        start_val = portfolio_value.iloc[0]
        end_val = portfolio_value.iloc[-1]
        years = (portfolio_value.index[-1] - portfolio_value.index[0]).days / 365.25
        cagr = (end_val / start_val) ** (1 / years) - 1
        
        # MDD
        rolling_max = portfolio_value.cummax()
        drawdown = (portfolio_value - rolling_max) / rolling_max
        mdd = drawdown.min()
        
        # 夏普比率 (假設無風險利率 ~ 0 以簡化，或使用超額回報)
        monthly_returns = portfolio_value.pct_change().dropna()
        mean_return = monthly_returns.mean()
        std_return = monthly_returns.std()
        sharpe = (mean_return / std_return) * np.sqrt(12) if std_return != 0 else 0
        
        return {
            'CAGR': cagr,
            'MDD': mdd,
            'Sharpe Ratio': sharpe
        }
