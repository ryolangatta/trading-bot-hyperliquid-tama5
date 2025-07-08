#!/usr/bin/env python3
"""
Place a test order on Hyperliquid (automatic, no confirmation)
"""

import sys
import os
import asyncio
import logging
from dotenv import load_dotenv

# Load .env file from hyperliquid_bot directory
env_path = os.path.join(os.path.dirname(__file__), 'hyperliquid_bot', '.env')
load_dotenv(env_path)

# Add the hyperliquid_bot directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hyperliquid_bot'))

from config import Config
from hyperliquid_wrapper.hyperliquid_client import HyperliquidClient

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def place_test_order():
    """Place a test order automatically"""
    try:
        print("🧪 Placing Test Order on Hyperliquid MAINNET")
        print("=" * 50)
        
        # Load configuration
        config = Config()
        
        if config.dry_run:
            print("❌ DRY_RUN mode enabled - cannot place real orders")
            return
            
        # Initialize client
        client = HyperliquidClient(config)
        await client.connect()
        
        # Get market data
        market_data = await client.get_market_data(config.symbol)
        current_price = market_data.price
        bid = market_data.bid
        
        print(f"📊 Market: {config.symbol} @ ${current_price:.6f}")
        
        # Calculate minimum order
        limit_price = bid * 0.999  # Slightly below bid
        limit_price = round(limit_price, 6)
        quantity = 10.0 / limit_price  # Exactly $10 order
        quantity = round(quantity, 6)
        
        print(f"🎯 Order: BUY {quantity} {config.symbol} @ ${limit_price:.6f}")
        print(f"💰 Total Value: ${quantity * limit_price:.2f}")
        print()
        
        # Place the order
        print("📤 Placing order...")
        order_result = await client.place_order(
            symbol=config.symbol,
            side='buy',
            size=quantity,
            price=limit_price,
            order_type='limit'
        )
        
        if order_result.success:
            print("✅ ORDER PLACED SUCCESSFULLY!")
            print(f"  📋 Order ID: {order_result.order_id}")
            
            if order_result.filled_size > 0:
                print(f"  ⚡ FILLED: {order_result.filled_size} @ ${order_result.filled_price:.6f}")
                print(f"  💸 Fees: ${order_result.fees:.4f}")
            else:
                print(f"  ⏳ RESTING: Order waiting for fill")
                
        else:
            print("❌ ORDER FAILED!")
            print(f"  Error: {order_result.error_message}")
            
        # Show updated balance
        account_info = await client.get_account_info()
        balance = account_info.get('balance', 0)
        
        print(f"💰 Updated Balance: ${balance:.2f}")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(place_test_order())