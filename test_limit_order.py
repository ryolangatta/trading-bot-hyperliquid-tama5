#!/usr/bin/env python3
"""
Test LimitOrderType structure
"""

try:
    from hyperliquid.utils.signing import LimitOrderType
    
    print("🔍 LimitOrderType structure:")
    print("=" * 35)
    
    print(f"LimitOrderType: {LimitOrderType}")
    print(f"LimitOrderType annotations: {getattr(LimitOrderType, '__annotations__', {})}")
    
    # Try to create a limit order
    print("\n📝 Creating limit order structure:")
    
    # Based on documentation, limit orders can have TIF (Time in Force)
    limit_order_types = [
        {"tif": "Gtc"},  # Good til canceled
        {"tif": "Alo"},  # Add liquidity only  
        {"tif": "Ioc"},  # Immediate or cancel
        {}  # Default
    ]
    
    for order_type in limit_order_types:
        print(f"  - Limit order: {order_type}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()