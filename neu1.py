import ccxt
import pandas as pd
import numpy as np
import time
from datetime import datetime

# Binance API-Zugangsdaten
api_key = "2PIPzpJaFK9MyUqiUMypaT3FAtDrc09SCGG0rA2IR7xPYO7FyG7oupNWw2FCY2d3"
api_secret = "togQqv9P38fCrPUC1iLBwz1GQO2npmX0wRfdconz0SownuBwXvItynyBwQWgwNc8"

# Binance Exchange initialisieren
exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'rateLimit': 1200,
    'enableRateLimit': True,
})

# Trading-Parameter
symbol = 'DOGE/USDT'
timeframe = '5m'  # 5-Minuten-Kerzen
macd_short = 12
macd_long = 26
macd_signal = 9
rsi_period = 14
bollinger_period = 20
bollinger_std_dev = 2
trade_amount = 50  # USDT pro Trade
stop_loss_pct = 0.95  # Stop-Loss bei -5%
take_profit_pct = 1.05  # Take-Profit bei +5%

# Historische Marktdaten abrufen
def fetch_data(symbol, timeframe='5m', limit=100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Indikatoren berechnen
def calculate_indicators(df):
    df['ema_short'] = df['close'].ewm(span=macd_short, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=macd_long, adjust=False).mean()
    df['macd'] = df['ema_short'] - df['ema_long']
    df['macd_signal'] = df['macd'].ewm(span=macd_signal, adjust=False).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    delta = df['close'].diff(1)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=rsi_period, min_periods=1).mean()
    avg_loss = pd.Series(loss).rolling(window=rsi_period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['bollinger_mid'] = df['close'].rolling(window=bollinger_period).mean()
    df['bollinger_std'] = df['close'].rolling(window=bollinger_period).std()
    df['bollinger_upper'] = df['bollinger_mid'] + (bollinger_std_dev * df['bollinger_std'])
    df['bollinger_lower'] = df['bollinger_mid'] - (bollinger_std_dev * df['bollinger_std'])
    
    return df

# Kauf-/Verkaufssignale
def generate_signals(df):
    df['buy_signal'] = (df['macd'] > df['macd_signal']) & (df['rsi'] < 30) & (df['close'] < df['bollinger_lower'])
    df['sell_signal'] = (df['macd'] < df['macd_signal']) & (df['rsi'] > 70) & (df['close'] > df['bollinger_upper'])
    
    # Debugging: Indikator-Werte ausgeben
    last_row = df.iloc[-1]
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} 🧐 MACD: {last_row['macd']:.6f} | Signal: {last_row['macd_signal']:.6f} | RSI: {last_row['rsi']:.2f} | Close: {last_row['close']:.6f} | Bollinger Low: {last_row['bollinger_lower']:.6f} | Bollinger High: {last_row['bollinger_upper']:.6f}")

    return df

# Aktuelles Guthaben abrufen
def get_balance():
    balance = exchange.fetch_balance()
    return balance['total']['USDT'], balance['total']['DOGE']

# Zeitstempel-Funktion
def timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Kauforder ausführen
def place_buy_order(amount):
    price = exchange.fetch_ticker(symbol)['last']
    quantity = amount / price
    order = exchange.create_market_buy_order(symbol, quantity)
    print(f"{timestamp()} ✅ Gekauft: {quantity:.2f} DOGE zu {price:.4f} USDT")
    return price, quantity

# Verkaufsorder ausführen
def place_sell_order(quantity):
    price = exchange.fetch_ticker(symbol)['last']
    order = exchange.create_market_sell_order(symbol, quantity)
    print(f"{timestamp()} ❌ Verkauft: {quantity:.2f} DOGE zu {price:.4f} USDT")
    return price

# Trailing Stop-Loss setzen
def trailing_stop_loss(buy_price, quantity):
    stop_price = buy_price * stop_loss_pct
    take_profit = buy_price * take_profit_pct

    while True:
        current_price = exchange.fetch_ticker(symbol)['last']
        if current_price < stop_price:
            print(f"{timestamp()} 🔻 Stop-Loss erreicht. Verkauf!")
            place_sell_order(quantity)
            break
        elif current_price > take_profit:
            print(f"{timestamp()} 🚀 Take-Profit erreicht. Verkauf!")
            place_sell_order(quantity)
            break
        time.sleep(10)

# Live-Trading starten
def live_trading():
    print(f"{timestamp()} 📈 Starte Live-Trading für DOGE/USDT...")
    while True:
        df = fetch_data(symbol, timeframe)
        df = calculate_indicators(df)
        df = generate_signals(df)
        
        usdt_balance, doge_balance = get_balance()
        last_row = df.iloc[-1]

        print(f"{timestamp()} 🔍 Letztes Signal: Buy={last_row['buy_signal']}, Sell={last_row['sell_signal']}")
        print(f"{timestamp()} 💰 Kontostand: {usdt_balance:.2f} USDT | {doge_balance:.2f} DOGE")

        if last_row['buy_signal'] and usdt_balance > trade_amount:
            buy_price, quantity = place_buy_order(trade_amount)
            trailing_stop_loss(buy_price, quantity)

        elif last_row['sell_signal'] and doge_balance > 0:
            place_sell_order(doge_balance)

        time.sleep(300)  # 5 Minuten warten, bevor der nächste Check erfolgt

# Script starten
if __name__ == "__main__":
    live_trading()
