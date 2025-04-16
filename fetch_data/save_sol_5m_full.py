import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta

# PARAMETERS
symbol = 'SOL/USDT'
timeframe = '5m'
lookback_days = 14
output_file = 'sol_5m_full_14d.csv'

# Binance 5m limit per request = 500 candles (~1.7 days)
limit = 500
seconds_per_candle = 5 * 60
total_candles = (lookback_days * 24 * 60) // 5

# INIT EXCHANGE
exchange = ccxt.binance()
since = exchange.milliseconds() - lookback_days * 24 * 60 * 60 * 1000

# FETCH IN CHUNKS
all_data = []
print(f"Fetching ~{total_candles} candles ({lookback_days} days)...")

while total_candles > 0:
    print(f"Fetching from: {datetime.utcfromtimestamp(since / 1000)}")
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not data:
            break
        all_data += data
        since = data[-1][0] + (seconds_per_candle * 1000)  # move forward
        total_candles -= len(data)
        time.sleep(exchange.rateLimit / 1000)  # respect rate limit
    except Exception as e:
        print("Error:", e)
        break

# FORMAT TO CSV
df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df.to_csv(output_file, index=False)

print(f"\n✅ Saved {len(df)} rows to {output_file}")
