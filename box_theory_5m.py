import ccxt
import pandas as pd
from datetime import datetime

# Parameters
symbol = 'SOL/USDT'
timeframe = '5m'
lookback_days = 5
top_threshold = 0.9
bottom_threshold = 0.1
trade_size = 1

# Set up exchange
exchange = ccxt.binance()

# Fetch 5m data
since = exchange.milliseconds() - lookback_days * 24 * 60 * 60 * 1000
ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df.set_index('datetime', inplace=True)

# Get daily high/low boxes from 1D resample
daily_boxes = df.resample('1D').agg({'high': 'max', 'low': 'min'})
daily_boxes['date'] = daily_boxes.index.date
box_lookup = daily_boxes.shift(1).dropna().set_index('date')

df['date'] = df.index.date
df = df[df['date'].isin(box_lookup.index)]
df = df.join(box_lookup, on='date', rsuffix='_box')
df.dropna(subset=['high_box', 'low_box'], inplace=True)

# Apply the box theory logic
trades = []
in_position = False

for i, row in df.iterrows():
    open_price = row['open']
    close_price = row['close']
    high_box = row['high_box']
    low_box = row['low_box']
    range_ = high_box - low_box

    top = low_box + top_threshold * range_
    bottom = low_box + bottom_threshold * range_

    signal = 'NO TRADE'
    pnl = 0.0

    if not in_position:
        if open_price >= top:
            signal = 'SELL'
            entry_price = open_price
            in_position = 'SHORT'
        elif open_price <= bottom:
            signal = 'BUY'
            entry_price = open_price
            in_position = 'LONG'
    else:
        if in_position == 'LONG':
            pnl = close_price - entry_price
        elif in_position == 'SHORT':
            pnl = entry_price - close_price

        trades.append({
            'Timestamp': i,
            'Signal': in_position,
            'Entry': entry_price,
            'Exit': close_price,
            'P&L': pnl
        })
        in_position = False

# Save results
results_df = pd.DataFrame(trades)
results_df.to_csv("box_theory_5m_trades.csv", index=False)
print("Saved: box_theory_5m_trades.csv")
