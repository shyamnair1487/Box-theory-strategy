import ccxt
import pandas as pd
import time
from datetime import datetime

# === USER CONFIGURATION ===
symbol = 'FLOKI/USDT'       # 👈 Change this to any pair on Binance
timeframe = '5m'
lookback_days = 14
output_file = symbol.replace('/', '_') + '_5m_full.csv'

# === SCRIPT CONFIG ===
limit = 500
seconds_per_candle = 5 * 60
total_candles = (lookback_days * 24 * 60) // 5

exchange = ccxt.binance()
since = exchange.milliseconds() - lookback_days * 24 * 60 * 60 * 1000

# === DATA FETCH LOOP ===
all_data = []
print(f"📥 Fetching {timeframe} data for {symbol} over {lookback_days} days...")

while total_candles > 0:
    print(f"Fetching from: {datetime.utcfromtimestamp(since / 1000)}")
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not data:
            break
        all_data += data
        since = data[-1][0] + (seconds_per_candle * 1000)
        total_candles -= len(data)
        time.sleep(exchange.rateLimit / 1000)
    except Exception as e:
        print("❌ Error:", e)
        break

# === SAVE TO CSV ===
df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df.to_csv(f'Results/{output_file}', index=False)


print(f"\n✅ Saved {len(df)} candles to {output_file}")
