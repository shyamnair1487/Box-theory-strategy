import ccxt
import pandas as pd
from datetime import datetime, timedelta

# PARAMETERS
symbol = 'SOL/USDT'
timeframe = '5m'
lookback_days = 14  # Adjust as needed
output_file = 'sol_5m_14d.csv'

# INITIALIZE BINANCE EXCHANGE
exchange = ccxt.binance()

# CALCULATE START TIME
since = exchange.milliseconds() - lookback_days * 24 * 60 * 60 * 1000  # milliseconds ago

# FETCH OHLCV DATA
print(f"Fetching {timeframe} data for {symbol} from Binance...")
ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since)

# FORMAT DATA TO DATAFRAME
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

# SAVE TO CSV
df.to_csv(output_file, index=False)
print(f"Saved {len(df)} rows to {output_file}")
