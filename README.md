# Dual Momentum Backtester

A Streamlit application for backtesting Dual Momentum strategies with S&P 500 stocks.

## Features
- Fetches real-time S&P 500 data (top 50 by weight)
- Customizable lookback periods and weights
- Interactive charts and performance metrics
- Monthly/Weekly rebalancing simulation

## Running Locally
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   streamlit run app.py
   ```

## Deploying to Streamlit Cloud
1. Push this repository to GitHub.
2. Go to [Streamlit Cloud](https://streamlit.io/cloud).
3. Connect your GitHub account.
4. Select this repository and the main file `app.py`.
5. Click "Deploy".
