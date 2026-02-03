import ccxt
import pandas as pd
import numpy as np
import os
import sys
import time

# 1. CONNECT
api_key = os.getenv('DELTA_API_KEY')
api_secret = os.getenv('DELTA_SECRET')

if not api_key or not api_secret:
    print("❌ ERROR: Keys missing.")
    sys.exit(1)

exchange = ccxt.delta({
    'apiKey': api_key,
    'secret': api_secret,
    'options': {'defaultType': 'future'}
})

# 2. SETTINGS (ETH / 4 Contracts)
SYMBOL = 'ETH/USDT'
TF_STRUCTURE = '4h'
TF_ENTRY = '1h'
QUANTITY = 4 
LEVERAGE = 20

def fetch_data(tf):
    try:
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=tf, limit=100)
        return pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
    except: return pd.DataFrame()

def get_zones(df):
    dz, sz = [], []
    for i in range(20, len(df)-5):
        # DEMAND (Low < Prev & Next)
        if df['l'][i] < df['l'][i-1] and df['l'][i] < df['l'][i+1]:
            if df['h'][i+1:i+15].max() > df['h'][i-10:i].max():
                dz.append(df['l'][i])
        # SUPPLY (High > Prev & Next)
        if df['h'][i] > df['h'][i-1] and df['h'][i] > df['h'][i+1]:
            if df['l'][i+1:i+15].min() < df['l'][i-10:i].min():
                sz.append(df['h'][i])
    return dz, sz

def run():
    print(f"🔎 Scanning {SYMBOL}...")
    df4 = fetch_data(TF_STRUCTURE)
    df1 = fetch_data(TF_ENTRY)
    if df4.empty or df1.empty: return

    dz, sz = get_zones(df4)
    price = df1['c'].iloc[-1]
    
    # BUY CHECK
    buy_zones = [z for z in dz if z < price]
    if buy_zones:
        zone = buy_zones[-1]
        if (price - zone)/zone < 0.005 and df1['c'].iloc[-1] > df1['o'].iloc[-1]:
            sl = zone * 0.995
            print(f"🚀 BUYING! SL: {sl}")
            # REAL TRADE EXECUTION
            exchange.create_order(SYMBOL, 'market', 'buy', QUANTITY, params={'stopLoss': sl})
            return

    # SELL CHECK
    sell_zones = [z for z in sz if z > price]
    if sell_zones:
        zone = sell_zones[-1]
        if (zone - price)/price < 0.005 and df1['c'].iloc[-1] < df1['o'].iloc[-1]:
            sl = zone * 1.005
            print(f"📉 SELLING! SL: {sl}")
            # REAL TRADE EXECUTION
            exchange.create_order(SYMBOL, 'market', 'sell', QUANTITY, params={'stopLoss': sl})
            return
            
    print("😴 No trade found.")

if __name__ == "__main__":
    run()
