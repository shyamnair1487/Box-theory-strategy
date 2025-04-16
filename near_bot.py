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
DRY_RUN = True  # Set to False when you're ready to go live

# === INIT BINANCE ===
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

import logging

# === Setup Logging ===
logging.basicConfig(
    filename='logs.txt',
    filemode='a',
    format='%(asctime)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)


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

def place_market_order(qty, simulated_price):
    if DRY_RUN:
        print(f"[SIMULATION] Buying {qty} NEAR @ {simulated_price:.4f} USDT (Dry Run)")
        usdt_balance = get_balance()
        log_message = (
            f"[SIMULATED] BUY — Qty: {qty} NEAR @ {simulated_price:.4f} USDT | "
            f"Simulated Balance: {usdt_balance:.2f} USDT"
        )
        logging.info(log_message)
    else:
        print(f"[TRADE] Executing LIVE BUY for {qty} NEAR")
        try:
            order = exchange.create_market_buy_order('NEAR/USDT', qty)
            entry_price = float(order['average'] or order['price'])
            usdt_balance = get_balance()

            log_message = (
                f"BUY executed — Qty: {qty} NEAR @ {entry_price:.4f} USDT | "
                f"Balance: {usdt_balance:.2f} USDT"
            )
            print(log_message)
            logging.info(log_message)
        except Exception as e:
            print(f"⚠️ Error placing order: {e}")
            logging.error(f"Order failed — {e}")

open_position = None  # or dict with entry_price, qty, entry_time

def run_bot():
    print("⏳ Bot starting...")
    while True:
        try:
            ohlcv = fetch_5m_ohlcv()
            prev_high, prev_low = get_previous_day_box(ohlcv)

            latest = ohlcv[-1]
            usdt_balance = get_balance()
            print(f"💰 Current Balance: {usdt_balance:.2f} USDT")
            ts, o, h, l, c, v = latest
            print(f"📊 {datetime.utcfromtimestamp(ts/1000)} - Open: {o}, Close: {c}")

            # Calculate entry zone and market context
            box_range = prev_high - prev_low
            entry_zone = prev_low + 0.1 * box_range

            print("\n--- MARKET CONTEXT ---")
            print(f"Time: {datetime.utcfromtimestamp(ts/1000)}")
            print(f"Box High: {prev_high:.3f}, Box Low: {prev_low:.3f}")
            print(f"Entry Zone Threshold: <= {entry_zone:.3f}")
            print(f"Candle - Open: {o:.3f}, Close: {c:.3f}")
            print("-----------------------")

            # Show P&L if there's an open simulated position
            if open_position:
                entry_price = open_position['entry_price']
                qty = open_position['qty']
                pnl = (c - entry_price) * qty
                print(f"📈 Simulated P&L: {pnl:.2f} USDT since entry @ {entry_price:.4f}")

            # Evaluate entry conditions
            if o <= entry_zone and c > o:
                usdt_balance = get_balance()
                risk_amount = usdt_balance * risk_pct
                qty = risk_amount / (o * stop_loss_pct)
                qty = round(qty, qty_precision)

                print("\n✅ Entry signal detected!")
                print(f"💰 Balance: {usdt_balance:.2f} USDT")
                print(f"🎯 Risk: {risk_amount:.2f}, Qty: {qty} NEAR")

                summary = (
                    f"--- TRADE SUMMARY ---\n"
                    f"Time: {datetime.utcfromtimestamp(ts/1000)}\n"
                    f"Box High: {prev_high:.3f}, Box Low: {prev_low:.3f}, Entry Zone: <= {entry_zone:.3f}\n"
                    f"Candle - Open: {o:.3f}, Close: {c:.3f}\n"
                    f"Risk: {risk_amount:.2f}, Qty: {qty} NEAR\n"
                    f"Simulated Price: {o:.4f}\n"
                    f"----------------------"
                )

                print(summary)
                logging.info(summary)

                # Save simulated position
                open_position = {
                    'entry_price': o,
                    'qty': qty,
                    'entry_time': datetime.utcfromtimestamp(ts/1000)
                }
                place_market_order(qty, o)

            else:
                reason = "❌ No valid signal."
                if o > entry_zone:
                    reason += f" (Open {o:.3f} > Entry Zone {entry_zone:.3f})"
                elif c <= o:
                    reason += f" (Close {c:.3f} <= Open {o:.3f})"

                print(reason)
                logging.info(
                    f"REJECTED — {datetime.utcfromtimestamp(ts/1000)} | Open: {o:.3f}, Close: {c:.3f}, Entry Zone: <= {entry_zone:.3f} | Reason: {reason}"
                )


        except Exception as e:
            print(f"⚠️ Error: {e}")

        time.sleep(300)  # Wait 5 minutes before next check

if __name__ == '__main__':
    run_bot()
