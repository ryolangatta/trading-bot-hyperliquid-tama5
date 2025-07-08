#!/usr/bin/env python3
"""
Test Hyperliquid SDK methods to understand correct signatures
"""

import sys
import os
from dotenv import load_dotenv

# Load .env file
env_path = os.path.join(os.path.dirname(__file__), 'hyperliquid_bot', '.env')
load_dotenv(env_path)

# Add hyperliquid_bot to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hyperliquid_bot'))

try:
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    from eth_account import Account
    
    print("🔍 Inspecting Hyperliquid SDK Methods")
    print("=" * 50)
    
    # Create a wallet (we won't use it for orders, just inspection)
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
    if not private_key:
        print("❌ No private key found")
        exit(1)
        
    wallet = Account.from_key(private_key)
    print(f"✓ Wallet: {wallet.address}")
    
    # Create Exchange instance
    exchange = Exchange(wallet, base_url=constants.MAINNET_API_URL)
    
    # Inspect the order method
    print("\n📋 Exchange.order method signature:")
    import inspect
    sig = inspect.signature(exchange.order)
    print(f"Method signature: {sig}")
    print(f"Parameters: {list(sig.parameters.keys())}")
    
    # Show parameter details
    for name, param in sig.parameters.items():
        print(f"  - {name}: {param.annotation if param.annotation != param.empty else 'Any'}")
        if param.default != param.empty:
            print(f"    Default: {param.default}")
    
    print(f"\n📖 Method docstring:")
    print(exchange.order.__doc__)
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()