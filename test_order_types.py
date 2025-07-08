#!/usr/bin/env python3
"""
Check available OrderType values in Hyperliquid SDK
"""

try:
    from hyperliquid.utils.signing import OrderType
    
    print("🔍 Available OrderType values:")
    print("=" * 40)
    
    # Try to inspect OrderType
    if hasattr(OrderType, '__members__'):
        # It's an enum
        for name, value in OrderType.__members__.items():
            print(f"  - {name}: {value}")
    else:
        # Try other inspection methods
        print(f"OrderType type: {type(OrderType)}")
        print(f"OrderType dir: {[x for x in dir(OrderType) if not x.startswith('_')]}")
        
    # Test creating order type instances
    print("\n🧪 Testing OrderType creation:")
    try:
        limit_order = OrderType.LIMIT if hasattr(OrderType, 'LIMIT') else OrderType.limit
        print(f"✓ Limit order type: {limit_order}")
    except:
        print("❌ Could not create limit order type")
        
    try:
        market_order = OrderType.MARKET if hasattr(OrderType, 'MARKET') else OrderType.market
        print(f"✓ Market order type: {market_order}")
    except:
        print("❌ Could not create market order type")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()