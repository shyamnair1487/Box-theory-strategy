#!/usr/bin/env python3
import ccxt
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURATION PARAMETERS ---
symbol = 'SOL/USDT'         # Trading pair
timeframe = '1d'            # Daily candles
limit = 100                 # Number of daily candles to fetch (adjust as needed)
trade_size = 1              # For backtesting, assume trading 1 SOL per trade
top_threshold = 0.9         # Top 10% of the box triggers a sell signal
bottom_threshold = 0.1      # Bottom 10% of the box triggers a buy signal

# --- INITIALIZE BINANCE EXCHANGE INSTANCE ---
exchange = ccxt.binance({
    'rateLimit': 1200,
    'enableRateLimit': True,
})

def fetch_ohlcv_data(symbol, timeframe, limit):
    """
    Fetches historical OHLCV data from Binance.
    Returns a pandas DataFrame with columns: datetime, open, high, low, close, volume.
    """
    # Fetch data from exchange
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # Convert timestamp to datetime in UTC
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    # Drop the timestamp column (we already have the index)
    df.drop('timestamp', axis=1, inplace=True)
    return df

def backtest_box_theory(df):
    """
    Backtests the Box Theory strategy.
    For each day (starting from the second day) uses the previous day's high and low as the box.
    Determines if a trade signal is triggered at the open based on the thresholds.
    Exits at the close of the same day.
    
    Returns a list of trades and overall summary P&L.
    """
    trades = []
    cumulative_pl = 0.0

    # We start from index 1 because day 0 does not have a previous day.
    for i in range(1, len(df)):
        prev_day = df.iloc[i - 1]
        today = df.iloc[i]

        # Define the box using previous day's high and low.
        box_high = prev_day['high']
        box_low = prev_day['low']
        box_range = box_high - box_low

        # Today's open price is our signal trigger.
        open_price = today['open']
        close_price = today['close']
        date_str = today.name.strftime('%Y-%m-%d')

        # Calculate threshold levels
        threshold_sell = box_low + top_threshold * box_range   # upper 10% of range
        threshold_buy = box_low + bottom_threshold * box_range   # lower 10% of range

        signal = None
        pl = 0.0

        # Decide trade direction:
        if open_price >= threshold_sell:
            signal = 'SELL'
            # For a short trade: profit = (entry - exit)
            pl = (open_price - close_price) * trade_size
        elif open_price <= threshold_buy:
            signal = 'BUY'
            # For a long trade: profit = (exit - entry)
            pl = (close_price - open_price) * trade_size
        else:
            signal = 'NO TRADE'

        cumulative_pl += pl
        trades.append({
            'Date': date_str,
            'Signal': signal,
            'Entry': open_price,
            'Exit': close_price,
            'Daily P&L': pl
        })

    return trades, cumulative_pl

def main():
    # Fetch OHLCV data
    print("Fetching historical data for", symbol)
    df = fetch_ohlcv_data(symbol, timeframe, limit)
    print("Data fetched. Number of days:", len(df))
    
    # Run the backtest
    trades, cumulative_pl = backtest_box_theory(df)
    
    # Convert trade results to DataFrame for nicer output.
    trades_df = pd.DataFrame(trades)
    
    # Filter out "NO TRADE" days for clarity (optional)
    trades_executed = trades_df[trades_df['Signal'] != 'NO TRADE']
    
    print("\n--- Trade Details ---")
    if not trades_executed.empty:
        print(trades_executed.to_string(index=False))
    else:
        print("No trades were executed based on the strategy conditions.")

     # Save both all trades and just executed trades
    trades_df.to_csv("box_theory_trades.csv", index=False)
    trades_executed.to_csv("box_theory_executed_trades.csv", index=False)
    print("\nSaved 'box_theory_trades.csv' and 'box_theory_executed_trades.csv' to disk.")

    print("\n--- Summary ---")
    print("Total Trades Executed:", trades_executed.shape[0])
    print("Cumulative P&L (in USDT):", round(cumulative_pl, 2))

if __name__ == '__main__':
    main()
