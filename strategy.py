import pandas as pd
import numpy as np

class MomentumStrategy:
    def __init__(self, prices: pd.DataFrame, lookback_period: int = 12):
        self.prices = prices
        self.lookback_period = lookback_period

    def calculate_momentum(self, resample_freq='ME', lookbacks: list = [12], weights: list = [1.0]) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        根據回顧期和權重計算動能。
        複合動能 = Sum(w_i * Return_{t-lb_i}) / Sum(w_i)
        """
        # 重新取樣數據
        # 'ME' = 月底, 'W-FRI' = 週五
        resampled_prices = self.prices.resample(resample_freq).last()
        
        # 計算複合動能
        composite_momentum = pd.DataFrame(0.0, index=resampled_prices.index, columns=resampled_prices.columns)
        total_weight = sum(weights)
        
        if total_weight == 0:
            return composite_momentum, resampled_prices

        for lb, w in zip(lookbacks, weights):
            # 計算該回顧期的回報率
            # 動能 = (Price_t / Price_{t-lookback}) - 1
            mom = resampled_prices.pct_change(lb)
            
            # 將加權動能加入複合動能
            # 處理潛在的 NaN？ pct_change 會在開頭產生 NaN。
            # 如果任何成分是 NaN，複合動能可能是 NaN 或部分值。
            # 標準做法：結果為 NaN 直到達到 max(lookbacks)。
            composite_momentum += mom * w
            
        # 除以總權重進行歸一化 (可選，但保持規模可解釋為「平均回報」)
        composite_momentum /= total_weight
        
        return composite_momentum, resampled_prices

    def generate_signals(self, risky_assets: list, safe_assets: list, top_n: int = 1, frequency: str = 'ME', lookbacks: list = [12], weights: list = [1.0], cash_protection: bool = False) -> pd.DataFrame:
        """
        生成支援 Top N、複合動能和現金保護的雙動能信號。
        
        邏輯:
        1. 計算動能。
        2. 找出動能最高的 Top N 攻擊型資產。
        3. 對於每個 Top N:
           - 如果動能 > 0 -> 持有攻擊型資產。
           - 如果動能 <= 0 -> 檢查防禦型資產池。
             - 從 safe_assets 中找出動能最高的一個。
             - 如果開啟現金保護且最佳防禦動能 <= 0 -> 持有現金 (不配置)。
             - 否則 -> 持有最佳防禦型資產。
        """
        momentum, resampled_prices = self.calculate_momentum(resample_freq=frequency, lookbacks=lookbacks, weights=weights)
        
        # 確保 safe_assets 是列表
        if isinstance(safe_assets, str):
            safe_assets = [safe_assets]

        # 初始化信號 DataFrame，全為零。
        # 所有的資產欄位都需要包含
        all_assets = list(set(risky_assets + safe_assets))
        signals = pd.DataFrame(0.0, index=momentum.index, columns=all_assets)
        
        weight_per_asset = 1.0 / top_n
        
        for date in momentum.index:
            # 跳過動能為 NaN 的初始日期
            # Skip only if all data for this date is NaN
            if momentum.loc[date].isnull().all():
                continue

            # 獲取該日期攻擊型資產的動能
            risky_momentum = momentum.loc[date, risky_assets]
            
            # 找出最好的 Top N 攻擊型資產
            best_risky_assets = risky_momentum.sort_values(ascending=False).head(top_n)
            
            # 獲取當前防禦型資產的動能
            # 過濾掉不在 momentum columns 中的 (例如如果沒下載到)
            valid_safe_assets = [sa for sa in safe_assets if sa in momentum.columns]
            if valid_safe_assets:
                safe_mom_series = momentum.loc[date, valid_safe_assets]
                best_safe_asset = safe_mom_series.idxmax()
                best_safe_mom_val = safe_mom_series.max()
            else:
                best_safe_asset = None
                best_safe_mom_val = -999 # 假設無數據很差
            
            for asset, mom_val in best_risky_assets.items():
                # 絕對動能檢查
                if mom_val > 0:
                    signals.loc[date, asset] += weight_per_asset
                else:
                    # 攻擊型資產表現不好。檢查防禦型體系。
                    # 如果有現金保護，且最佳防禦資產動能 <= 0
                    if cash_protection and best_safe_mom_val <= 0:
                        # 全現金
                        pass
                    elif best_safe_asset:
                        # 持有最佳防禦資產
                        signals.loc[date, best_safe_asset] += weight_per_asset
            
        return signals.shift(1).fillna(0)

    def get_latest_signal(self, risky_assets: list, safe_assets: list, top_n: int = 1, frequency: str = 'ME', lookbacks: list = [12], weights: list = [1.0], cash_protection: bool = False) -> dict:
        """
        根據最新數據獲取下一期的交易信號。
        """
        momentum, _ = self.calculate_momentum(resample_freq=frequency, lookbacks=lookbacks, weights=weights)
        
        if momentum.empty:
            return {}
            
        # 確保 safe_assets 是列表
        if isinstance(safe_assets, str):
            safe_assets = [safe_assets]

        # 獲取最後一行的動能數據
        last_date = momentum.index[-1]
        last_mom = momentum.iloc[-1]
        
        # 檢查最新動能是否為 NaN (例如數據不足以計算回顧期)
        if last_mom.isnull().all():
            return {"Error": "數據不足以計算最新信號"}

        # 攻擊型資產動能
        risky_momentum = last_mom[risky_assets]
        
        # 最佳攻擊型資產
        best_risky_assets = risky_momentum.sort_values(ascending=False).head(top_n)
        
        # 最佳防禦型資產
        valid_safe_assets = [sa for sa in safe_assets if sa in last_mom.index]
        if valid_safe_assets:
            safe_mom_series = last_mom[valid_safe_assets]
            best_safe_asset = safe_mom_series.idxmax()
            best_safe_mom_val = safe_mom_series.max()
        else:
            best_safe_asset = None
            best_safe_mom_val = -999

        signal = {}
        weight_per_asset = 1.0 / top_n
        
        for asset, mom_val in best_risky_assets.items():
            if mom_val > 0:
                signal[asset] = signal.get(asset, 0) + weight_per_asset
            else:
                if cash_protection and best_safe_mom_val <= 0:
                    signal["CASH"] = signal.get("CASH", 0) + weight_per_asset
                elif best_safe_asset:
                    signal[best_safe_asset] = signal.get(best_safe_asset, 0) + weight_per_asset
                    
        return signal
