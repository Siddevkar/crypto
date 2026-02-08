import ccxt
import pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime

# --- CONFIGURATION ---
SYMBOL = 'ETH/USDT'     # Coin
QUANTITY = 4            # Number of Contracts
LEVERAGE = 20           # Leverage
TF_STRUCTURE = '4h'     # Major Trend
TF_ENTRY = '1h'         # Entry Timeframe
CHECK_INTERVAL = 15     # Seconds to wait between checks (Don't go lower than 10)

# --- 1. CONNECT TO DELTA ---
api_key = os.getenv('DELTA_API_KEY')
api_secret = os.getenv('DELTA_SECRET')

if not api_key or not api_secret:
    print("❌ ERROR: Keys missing from GitHub Secrets.")
    sys.exit(1)

exchange = ccxt.delta({
    'apiKey': api_key,
    'secret': api_secret,
    'options': {'defaultType': 'future'}
})

def fetch_data(tf):
    try:
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=tf, limit=100)
        df = pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        df['t'] = pd.to_datetime(df['t'], unit='ms')
        return df
    except Exception as e:
        print(f"⚠️ Data Error: {e}")
        return pd.DataFrame()

def get_zones(df):
    dz, sz = [], []
    # Simple Fractal Supply/Demand Logic
    for i in range(20, len(df)-5):
        # Demand Zone (V-Shape)
        if df['l'][i] < df['l'][i-1] and df['l'][i] < df['l'][i+1]:
            if df['h'][i+1:i+15].max() > df['h'][i-10:i].max():
                dz.append(df['l'][i])
        # Supply Zone (A-Shape)
        if df['h'][i] > df['h'][i-1] and df['h'][i] > df['h'][i+1]:
            if df['l'][i+1:i+15].min() < df['l'][i-10:i].min():
                sz.append(df['h'][i])
    return dz, sz

def execute_trade():
    print(f"🔎 Scanning {SYMBOL} at {datetime.now().strftime('%H:%M:%S')}...")
    
    # 1. Get Data
    df4 = fetch_data(TF_STRUCTURE)
    df1 = fetch_data(TF_ENTRY)
    
    if df4.empty or df1.empty:
        print("   -> Failed to get data. Retrying next loop.")
        return

    # 2. Find Zones
    dz, sz = get_zones(df4)
    current_price = df1['c'].iloc[-1]
    open_price = df1['o'].iloc[-1]
    
    # 3. Check BUY (Demand)
    buy_zones = [z for z in dz if z < current_price]
    if buy_zones:
        zone = buy_zones[-1]
        dist = (current_price - zone) / zone
        # Logic: Price is inside 0.5% buffer of zone AND candle is Green
        if dist < 0.005 and current_price > open_price:
            sl = zone * 0.995
            print(f"🚀 BUY SIGNAL! Price: {current_price}, Zone: {zone}, SL: {sl}")
            try:
                # Set Leverage first (Safety)
                try: exchange.set_leverage(LEVERAGE, SYMBOL)
                except: pass 
                
                # Send Order
                exchange.create_order(SYMBOL, 'market', 'buy', QUANTITY, params={'stopLoss': sl})
                print("✅ BUY ORDER EXECUTED!")
                time.sleep(300) # Sleep 5 mins after trade to avoid double buy
            except Exception as e:
                print(f"❌ Order Failed: {e}")
            return

    # 4. Check SELL (Supply)
    sell_zones = [z for z in sz if z > current_price]
    if sell_zones:
        zone = sell_zones[-1]
        dist = (zone - current_price) / current_price
        # Logic: Price is inside 0.5% buffer of zone AND candle is Red
        if dist < 0.005 and current_price < open_price:
            sl = zone * 1.005
            print(f"📉 SELL SIGNAL! Price: {current_price}, Zone: {zone}, SL: {sl}")
            try:
                try: exchange.set_leverage(LEVERAGE, SYMBOL)
                except: pass

                exchange.create_order(SYMBOL, 'market', 'sell', QUANTITY, params={'stopLoss': sl})
                print("✅ SELL ORDER EXECUTED!")
                time.sleep(300) # Sleep 5 mins after trade
            except Exception as e:
                print(f"❌ Order Failed: {e}")
            return
            
    print(f"   -> No trade. Price: {current_price}. Waiting...")

# --- MAIN LOOP ---
if __name__ == "__main__":
    print("🤖 Bot Started. Press Ctrl+C to stop (if local).")
    while True:
        try:
            execute_trade()
        except Exception as e:
            print(f"CRASH: {e}")
        
        # WAIT 15 SECONDS (To avoid API Ban)
        time.sleep(CHECK_INTERVAL)
