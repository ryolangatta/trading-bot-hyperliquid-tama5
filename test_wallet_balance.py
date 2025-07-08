#!/usr/bin/env python3
"""
Test script to check wallet balance functionality locally
"""

import sys
import os
import asyncio
import logging
from dotenv import load_dotenv

# Load .env file from hyperliquid_bot directory
env_path = os.path.join(os.path.dirname(__file__), 'hyperliquid_bot', '.env')
load_dotenv(env_path)
print(f"Loading .env from: {env_path}")

# Add the hyperliquid_bot directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hyperliquid_bot'))

from config import Config
from hyperliquid_wrapper.hyperliquid_client import HyperliquidClient

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_wallet_balance():
    """Test wallet balance retrieval"""
    try:
        print("🔍 Testing Hyperliquid Wallet Balance...")
        print("=" * 50)
        
        # Load configuration
        config = Config()
        print(f"✓ Configuration loaded")
        print(f"  - Testnet: {config.testnet}")
        print(f"  - Private key provided: {'Yes' if config.hyperliquid_private_key else 'No'}")
        
        if config.hyperliquid_private_key:
            print(f"  - Private key starts with 0x: {config.hyperliquid_private_key.startswith('0x')}")
            print(f"  - Private key length: {len(config.hyperliquid_private_key)}")
        else:
            print("❌ No private key found in .env file")
            return
        
        print()
        
        # Initialize Hyperliquid client
        print("🔗 Initializing Hyperliquid client...")
        client = HyperliquidClient(config)
        await client.connect()
        print("✓ Client connected")
        print()
        
        # Test account info retrieval
        print("💰 Fetching account information...")
        account_info = await client.get_account_info()
        
        if account_info:
            balance = account_info.get('balance', 0)
            available = account_info.get('available_balance', 0)
            margin_used = account_info.get('total_margin_used', 0)
            positions = account_info.get('positions', 0)
            
            print("✓ Account info retrieved successfully:")
            print(f"  - Total Balance: ${balance:,.2f} USDC")
            print(f"  - Available Balance: ${available:,.2f} USDC")
            print(f"  - Margin Used: ${margin_used:,.2f} USDC")
            print(f"  - Open Positions: {positions}")
        else:
            print("❌ Failed to retrieve account information")
            
        print()
        
        # Test market data
        print("📊 Testing market data...")
        try:
            market_data = await client.get_market_data("PENGU")
            if market_data:
                print(f"✓ Market data for PENGU:")
                print(f"  - Price: ${market_data.price:.6f}")
                print(f"  - Bid: ${market_data.bid:.6f}")
                print(f"  - Ask: ${market_data.ask:.6f}")
            else:
                print("❌ Failed to get market data")
        except Exception as e:
            print(f"❌ Market data error: {e}")
            
        print()
        
        # Test health check
        print("❤️  Testing API health...")
        health = await client.health_check()
        print(f"✓ API Health: {'OK' if health else 'FAILED'}")
        
        # Cleanup
        await client.disconnect()
        print("✓ Client disconnected")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print("Full traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    print("Hyperliquid Wallet Balance Test")
    print("=" * 50)
    
    # Check if .env file exists
    env_path = os.path.join("hyperliquid_bot", ".env")
    if not os.path.exists(env_path):
        print(f"❌ No .env file found at {env_path}")
        print("Please create a .env file with your Hyperliquid configuration")
        sys.exit(1)
    
    asyncio.run(test_wallet_balance())