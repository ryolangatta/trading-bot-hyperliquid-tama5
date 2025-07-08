#!/usr/bin/env python3
"""
Test Hyperliquid order structure
"""

try:
    from hyperliquid.utils.signing import OrderType
    from hyperliquid.utils.types import Cloid
    import inspect
    
    print("🔍 OrderType structure:")
    print("=" * 30)
    
    # Check if it's a TypedDict
    print(f"OrderType: {OrderType}")
    print(f"OrderType annotations: {getattr(OrderType, '__annotations__', {})}")
    
    # Try to understand the expected structure
    print("\n📝 Trying to create order type structures:")
    
    # Common order type patterns
    test_structures = [
        {"limit": {}},
        {"limit": {"tif": "Gtc"}},
        {"market": {}},
        "limit",
        "market"
    ]
    
    for struct in test_structures:
        print(f"  Testing: {struct}")
        
    # Check Cloid structure too
    print(f"\n🏷️  Cloid: {Cloid}")
    print(f"Cloid annotations: {getattr(Cloid, '__annotations__', {})}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()