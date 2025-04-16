import ccxt
import time
from datetime import datetime, timedelta
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY  

# === CONFIG ===
symbol = 'NEAR/USDT'
timeframe = '5m'
risk_pct = 0.01
stop_loss_pct = 0.005
qty_precision = 2  # NEAR typically supports 2 decimal places

# === INIT BINANCE ===
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})


def fetch_5m_ohlcv():
    since = exchange.parse8601((datetime.utcnow() - timedelta(days=2)).isoformat())
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=500)
    return ohlcv

def get_previous_day_box(ohlcv):
    today = datetime.utcnow().date()
    yesterday_candles = [c for c in ohlcv if datetime.utcfromtimestamp(c[0] / 1000).date() < today]
    highs = [c[2] for c in yesterday_candles]
    lows = [c[3] for c in yesterday_candles]
    return max(highs), min(lows)

def get_balance():
    return float(exchange.fetch_balance()['total']['USDT'])

def place_market_order(qty):
    print(f"[TRADE] Executing BUY for {qty} NEAR")
    order = exchange.create_market_buy_order('NEAR/USDT', qty)
    return order

def run_bot():
    print("⏳ Bot starting...")
    while True:
        try:
            ohlcv = fetch_5m_ohlcv()
            prev_high, prev_low = get_previous_day_box(ohlcv)

            latest = ohlcv[-1]
            ts, o, h, l, c, v = latest
            print(f"📊 {datetime.utcfromtimestamp(ts/1000)} - Open: {o}, Close: {c}")

            box_range = prev_high - prev_low
            entry_zone = prev_low + 0.1 * box_range

            if o <= entry_zone and c > o:
                usdt_balance = get_balance()
                risk_amount = usdt_balance * risk_pct
                qty = risk_amount / (o * stop_loss_pct)
                qty = round(qty, qty_precision)

                print("✅ Entry signal detected!")
                place_market_order(qty)
            else:
                print("❌ No valid signal.")

        except Exception as e:
            print(f"⚠️ Error: {e}")

        time.sleep(300)  # Wait 5 minutes before next check

if __name__ == '__main__':
    run_bot()
