import ccxt
import pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime

# --- CONFIGURATION ---
SYMBOL = 'ETH/USDT'     # Coin to trade
QUANTITY = 40           # 40 Contracts = 0.04 ETH (Approx ₹500 Margin)
LEVERAGE = 20           # Leverage (Risk)
TF_STRUCTURE = '4h'     # Timeframe for finding Zones (Major Trend)
TF_ENTRY = '1h'         # Timeframe for Entry (Minor Trend)
CHECK_INTERVAL = 15     # How often to check (Seconds)

# --- 1. CONNECT TO DELTA EXCHANGE ---
api_key = os.getenv('DELTA_API_KEY')
api_secret = os.getenv('DELTA_SECRET')

if not api_key or not api_secret:
    print("❌ ERROR: Keys missing from GitHub Secrets.")
    sys.exit(1)

# Initialize Exchange
try:
    exchange = ccxt.delta({
        'apiKey': api_key,
        'secret': api_secret,
        'options': {'defaultType': 'future'} 
    })
    print("✅ Connected to Delta Exchange!")
except Exception as e:
    print(f"❌ Connection Error: {e}")
    sys.exit(1)

# --- 2. DATA FUNCTIONS ---
def fetch_data(tf):
    """Fetches the last 100 candles for the given timeframe"""
    try:
        bars = exchange.fetch_ohlcv(SYMBOL, timeframe=tf, limit=100)
        df = pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        df['t'] = pd.to_datetime(df['t'], unit='ms')
        return df
    except Exception as e:
        print(f"⚠️ Data Error ({tf}): {e}")
        return pd.DataFrame()

def get_zones(df):
    """Finds V-Shape (Demand) and A-Shape (Supply) Zones"""
    dz, sz = [], []
    # Loop through candles to find peaks and valleys
    for i in range(20, len(df)-5):
        # DEMAND ZONE (V-Shape: Low is lower than previous & next)
        if df['l'][i] < df['l'][i-1] and df['l'][i] < df['l'][i+1]:
            # Check if it led to a rally (Fractal check)
            if df['h'][i+1:i+15].max() > df['h'][i-10:i].max():
                dz.append(df['l'][i])
        
        # SUPPLY ZONE (A-Shape: High is higher than previous & next)
        if df['h'][i] > df['h'][i-1] and df['h'][i] > df['h'][i+1]:
            # Check if it led to a drop
            if df['l'][i+1:i+15].min() < df['l'][i-10:i].min():
                sz.append(df['h'][i])
    return dz, sz

# --- 3. TRADING LOGIC ---
def execute_trade():
    print(f"🔎 Scanning {SYMBOL} at {datetime.now().strftime('%H:%M:%S')}...")
    
    # Get Data
    df4 = fetch_data(TF_STRUCTURE)
    df1 = fetch_data(TF_ENTRY)
    
    if df4.empty or df1.empty:
        print("   -> Failed to get data. Retrying next loop.")
        return

    # Find Zones based on 4H Structure
    dz, sz = get_zones(df4)
    current_price = df1['c'].iloc[-1]
    open_price = df1['o'].iloc[-1]
    
    # --- BUY LOGIC (Demand Zone) ---
    buy_zones = [z for z in dz if z < current_price]
    if buy_zones:
        zone = buy_zones[-1] # Closest zone below price
        dist = (current_price - zone) / zone
        
        # Condition: Price is very close (0.5%) AND Candle is GREEN
        if dist < 0.005 and current_price > open_price:
            sl = zone * 0.99  # <--- STOP LOSS: 1% below Zone
            print(f"🚀 BUY SIGNAL! Price: {current_price}, Zone: {zone}, SL: {sl}")
            
            try:
                # 1. Set Leverage
                try: exchange.set_leverage(LEVERAGE, SYMBOL)
                except: pass 
                
                # 2. Place Order
                exchange.create_order(SYMBOL, 'market', 'buy', QUANTITY, params={'stopLoss': sl})
                print("✅ BUY ORDER SENT! Sleeping for 5 mins...")
                time.sleep(300) # Wait 5 mins to avoid double buy
            except Exception as e:
                print(f"❌ Order Failed: {e}")
            return

    # --- SELL LOGIC (Supply Zone) ---
    sell_zones = [z for z in sz if z > current_price]
    if sell_zones:
        zone = sell_zones[-1] # Closest zone above price
        dist = (zone - current_price) / current_price
        
        # Condition: Price is very close (0.5%) AND Candle is RED
        if dist < 0.005 and current_price < open_price:
            sl = zone * 1.01  # <--- STOP LOSS: 1% above Zone
            print(f"📉 SELL SIGNAL! Price: {current_price}, Zone: {zone}, SL: {sl}")
            
            try:
                # 1. Set Leverage
                try: exchange.set_leverage(LEVERAGE, SYMBOL)
                except: pass
                
                # 2. Place Order
                exchange.create_order(SYMBOL, 'market', 'sell', QUANTITY, params={'stopLoss': sl})
                print("✅ SELL ORDER SENT! Sleeping for 5 mins...")
                time.sleep(300) # Wait 5 mins
            except Exception as e:
                print(f"❌ Order Failed: {e}")
            return
            
    print(f"   -> No trade found. Price: {current_price}")

# --- 4. MAIN LOOP ---
if __name__ == "__main__":
    print("🤖 Whale Bot Started in Continuous Mode...")
    print("   -> Qty: 40 | Leverage: 20x | SL: 1%")
    
    while True:
        try:
            execute_trade()
        except Exception as e:
            print(f"CRASH: {e}")
            print("Restarting loop in 10 seconds...")
            time.sleep(10)
        
        # Wait before next check
        time.sleep(CHECK_INTERVAL)
        
