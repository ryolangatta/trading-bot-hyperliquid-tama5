#!/usr/bin/env python3
"""
Simple order test using exact Hyperliquid SDK patterns
"""

import sys
import os
import asyncio
from dotenv import load_dotenv

# Load .env
env_path = os.path.join(os.path.dirname(__file__), 'hyperliquid_bot', '.env')
load_dotenv(env_path)

try:
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    from eth_account import Account
    
    async def simple_order_test():
        print("🧪 Simple Order Test")
        print("=" * 30)
        
        # Setup
        private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
        wallet = Account.from_key(private_key)
        
        print(f"📋 Wallet: {wallet.address}")
        
        # Create exchange (synchronous)
        exchange = Exchange(wallet, base_url=constants.MAINNET_API_URL)
        
        # Get market price first
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        
        # Simple limit buy order - exact minimal parameters
        symbol = "PENGU"
        is_buy = True
        size = 650.0  # About $10 worth
        price = 0.015400  # Slightly below market
        
        order_type = {"limit": {"tif": "Gtc"}}
        
        print(f"📊 Order: BUY {size} {symbol} @ ${price:.6f}")
        print(f"💰 Value: ${size * price:.2f}")
        print(f"🎯 Order Type: {order_type}")
        print()
        
        try:
            print("📤 Placing order...")
            
            # Place order using minimal parameters
            result = exchange.order(
                symbol,      # name
                is_buy,      # is_buy  
                size,        # sz
                price,       # limit_px
                order_type   # order_type
            )
            
            print("✅ ORDER RESULT:")
            print(f"  Type: {type(result)}")
            print(f"  Value: {result}")
            
            if isinstance(result, dict):
                if result.get('status') == 'ok':
                    data = result.get('response', {}).get('data', {})
                    statuses = data.get('statuses', [])
                    if statuses:
                        status = statuses[0]
                        if 'resting' in status:
                            print(f"  📋 Order resting - ID: {status['resting'].get('oid')}")
                        elif 'filled' in status:
                            filled = status['filled']
                            print(f"  ⚡ Order filled:")
                            print(f"    Size: {filled.get('totalSz')}")
                            print(f"    Price: ${filled.get('avgPx')}")
                            print(f"    ID: {filled.get('oid')}")
                else:
                    print(f"  ❌ Error: {result}")
            else:
                print(f"  ❌ Unexpected response type: {type(result)}")
                
        except Exception as e:
            print(f"❌ Order failed: {e}")
            import traceback
            traceback.print_exc()
            
    asyncio.run(simple_order_test())
    
except Exception as e:
    print(f"❌ Setup failed: {e}")
    import traceback
    traceback.print_exc()