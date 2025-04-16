import ccxt
import time
from datetime import datetime, timedelta
# from config import BINANCE_API_KEY, BINANCE_SECRET_KEY  
import os
from dotenv import load_dotenv
load_dotenv()
import smtplib
from email.message import EmailMessage



BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

# === CONFIG ===
symbol = 'NEAR/USDT'
timeframe = '5m'
risk_pct = 0.01
stop_loss_pct = 0.005
qty_precision = 2  # NEAR typically supports 2 decimal places
DRY_RUN = False  # Set to False when you're ready to go live

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

def send_email(subject, body):
    try:
        email_host = os.getenv("EMAIL_HOST")
        email_port = int(os.getenv("EMAIL_PORT"))
        email_user = os.getenv("EMAIL_USER")
        email_pass = os.getenv("EMAIL_PASS")
        email_to = os.getenv("EMAIL_TO")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = email_user
        msg["To"] = email_to
        msg.set_content(body)

        with smtplib.SMTP(email_host, email_port) as server:
            server.starttls()
            server.login(email_user, email_pass)
            server.send_message(msg)
        print("📧 Email sent.")
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")


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
            return entry_price
        except Exception as e:
            print(f"⚠️ Error placing order: {e}")
            logging.error(f"Order failed — {e}")

open_position = None  # or dict with entry_price, qty, entry_time

def run_bot():
    global open_position
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

            # Show simulated P&L only during dry runs
            if DRY_RUN and open_position:
                entry_price = open_position['entry_price']
                qty = open_position['qty']
                pnl = (c - entry_price) * qty
                print(f"📈 Simulated P&L: {pnl:.2f} USDT since entry @ {entry_price:.4f}")

            # Evaluate entry conditions
            if o <= entry_zone and c > o:
                usdt_balance = get_balance()
                risk_amount = usdt_balance * risk_pct

                # Estimate how much NEAR you can buy based on the risk and stop-loss
                raw_qty = risk_amount / (o * stop_loss_pct)

                # Cap the quantity to what you can actually afford
                max_qty_affordable = usdt_balance * 0.98 / o

                qty = min(raw_qty, max_qty_affordable)
                qty = round(qty, qty_precision)

                # Abort if quantity is too low to be traded
                if qty * o < 5.10:  # Binance minimum notional is ~$5 for many pairs
                    message = (
                        f"❌ Order Skipped — Qty too low: {qty} NEAR @ {o:.4f} USDT\n"
                        f"Total Value: {qty * o:.2f} USDT"
                    )
                    print(message)
                    logging.warning(message)
                    send_email("❌ Order Skipped (Too Small)", message)
                    time.sleep(300)
                    return

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
                send_email("📈 Trade Executed", summary)

                logging.info(summary)

                entry_price = place_market_order(qty, o)

                if entry_price:
                    open_position = {
                        'entry_price': entry_price,
                        'qty': qty,
                        'entry_time': datetime.utcfromtimestamp(ts/1000)
                    }


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
            send_email("⚠️ Bot Error", str(e))

        # === CHECK FOR EXIT (Take Profit or Stop Loss) ===
        if open_position and not DRY_RUN:
            entry_price = open_position['entry_price']
            qty = open_position['qty']
            entry_time = open_position['entry_time']

            tp_price = entry_price * 1.01
            sl_price = entry_price * 0.995

            if c >= tp_price or c <= sl_price:
                exit_reason = "🎯 Take Profit" if c >= tp_price else "🛑 Stop Loss"
                try:
                    order = exchange.create_market_sell_order(symbol, qty)
                    exit_price = float(order['average'] or order['price'])
                    pnl = (exit_price - entry_price) * qty

                    message = (
                        f"--- TRADE CLOSED ---\n"
                        f"{exit_reason}\n"
                        f"Entry: {entry_price:.4f}, Exit: {exit_price:.4f}, Qty: {qty}\n"
                        f"Realized P&L: {pnl:.2f} USDT\n"
                        f"Entry Time: {entry_time}, Exit Time: {datetime.utcfromtimestamp(ts/1000)}\n"
                        f"---------------------"
                    )
                    print(message)
                    logging.info(message)
                    send_email(exit_reason, message)

                except Exception as e:
                    print(f"⚠️ Failed to close position: {e}")
                    logging.error(f"Sell error: {e}")
                    send_email("❌ Sell Failed", str(e))
                finally:
                    open_position = None  # Reset position


        time.sleep(300)  # Wait 5 minutes before next check

if __name__ == '__main__':
    run_bot()
