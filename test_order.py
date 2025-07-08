#!/usr/bin/env python3
"""
Test script to place a real order on Hyperliquid
IMPORTANT: This will place a REAL order with REAL money!
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

async def test_order_placement():
    """Test placing a real order on Hyperliquid"""
    try:
        print("⚠️  WARNING: This will place a REAL order with REAL money!")
        print("=" * 60)
        
        # Load configuration
        config = Config()
        print(f"✓ Configuration loaded")
        print(f"  - Environment: {'TESTNET' if config.testnet else 'MAINNET'}")
        print(f"  - Mode: {'DRY_RUN' if config.dry_run else 'LIVE'}")
        print(f"  - Symbol: {config.symbol}")
        print(f"  - Leverage: {config.leverage}x")
        
        if config.dry_run:
            print("❌ DRY_RUN mode enabled - cannot place real orders")
            return
            
        if config.testnet:
            print("ℹ️  Using TESTNET - test funds only")
        else:
            print("🚨 Using MAINNET - REAL MONEY!")
            
        print()
        
        # Initialize client
        client = HyperliquidClient(config)
        await client.connect()
        
        # Get current account info
        print("💰 Checking account balance...")
        account_info = await client.get_account_info()
        balance = account_info.get('balance', 0)
        available = account_info.get('available_balance', 0)
        
        print(f"  - Total Balance: ${balance:.2f}")
        print(f"  - Available: ${available:.2f}")
        
        if available < 10:
            print("❌ Insufficient balance for minimum $10 order")
            return
            
        print()
        
        # Get current market data
        print(f"📊 Getting market data for {config.symbol}...")
        market_data = await client.get_market_data(config.symbol)
        
        if not market_data:
            print(f"❌ Failed to get market data for {config.symbol}")
            return
            
        current_price = market_data.price
        bid = market_data.bid
        ask = market_data.ask
        
        print(f"  - Current Price: ${current_price:.6f}")
        print(f"  - Bid: ${bid:.6f}")
        print(f"  - Ask: ${ask:.6f}")
        print()
        
        # Calculate order parameters for minimum $10 order
        # Use minimum $10 order size (meets Hyperliquid requirement)
        min_order_value = 10.0
        risk_amount = min_order_value / config.leverage  # Actual risk with leverage
        position_size_usd = min_order_value  # Position size = $10
        quantity = position_size_usd / current_price
        
        # Round to appropriate precision (6 decimal places)
        quantity = round(quantity, 6)
        
        print("📝 Order Parameters:")
        print(f"  - Risk Amount: ${risk_amount:.2f}")
        print(f"  - Position Size (with {config.leverage}x leverage): ${position_size_usd:.2f}")
        # Place a limit buy order slightly below current price (conservative)
        limit_price = bid * 0.999  # 0.1% below bid for better fill chance
        limit_price = round(limit_price, 6)
        
        # Adjust quantity to ensure minimum $10 order value with limit price
        min_quantity_for_limit = 10.0 / limit_price
        if quantity < min_quantity_for_limit:
            quantity = min_quantity_for_limit
            quantity = round(quantity, 6)
        
        print(f"  - Quantity: {quantity} {config.symbol}")
        print(f"  - Estimated Cost: ${quantity * current_price:.2f}")
        print(f"  - Order Value at Limit Price: ${quantity * limit_price:.2f}")
        
        if quantity * limit_price < 10:
            print("❌ Order value below $10 minimum")
            return
            
        print()
        
        print(f"🎯 Placing LIMIT BUY order:")
        print(f"  - Symbol: {config.symbol}")
        print(f"  - Side: BUY")
        print(f"  - Quantity: {quantity}")
        print(f"  - Limit Price: ${limit_price:.6f}")
        print(f"  - Total Value: ${quantity * limit_price:.2f}")
        print()
        
        # Confirm before placing order
        print("⚠️  FINAL CONFIRMATION:")
        print("This will place a REAL order with REAL money!")
        
        if input("Type 'YES' to confirm order placement: ").upper() != 'YES':
            print("❌ Order cancelled by user")
            return
            
        print()
        print("📤 Placing order...")
        
        # Place the order
        order_result = await client.place_order(
            symbol=config.symbol,
            side='buy',
            size=quantity,
            price=limit_price,
            order_type='limit'
        )
        
        if order_result.success:
            print("✅ ORDER PLACED SUCCESSFULLY!")
            print(f"  - Order ID: {order_result.order_id}")
            print(f"  - Filled Size: {order_result.filled_size}")
            print(f"  - Filled Price: ${order_result.filled_price:.6f}")
            print(f"  - Fees: ${order_result.fees:.4f}")
            
            if order_result.filled_size > 0:
                print(f"  - ✅ IMMEDIATELY FILLED: {order_result.filled_size}")
            else:
                print(f"  - 📋 ORDER RESTING: Waiting for fill at ${limit_price:.6f}")
                
        else:
            print("❌ ORDER FAILED!")
            print(f"  - Error: {order_result.error_message}")
            
        # Get updated account info
        print()
        print("💰 Updated account balance...")
        account_info = await client.get_account_info()
        new_balance = account_info.get('balance', 0)
        new_available = account_info.get('available_balance', 0)
        
        print(f"  - New Balance: ${new_balance:.2f}")
        print(f"  - New Available: ${new_available:.2f}")
        print(f"  - Balance Change: ${new_balance - balance:.2f}")
        
        # Cleanup
        await client.disconnect()
        print("✓ Test completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 Hyperliquid Real Order Test")
    print("=" * 40)
    print()
    print("⚠️  WARNING: This script places REAL orders with REAL money!")
    print("Make sure you understand the risks before proceeding.")
    print()
    
    asyncio.run(test_order_placement())