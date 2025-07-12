#!/usr/bin/env python3
"""Close existing LINK position with market order"""

import asyncio
import logging
from config import Config
from hyperliquid_wrapper.hyperliquid_client import HyperliquidClient
from utils.logger import setup_logger

async def close_position():
    """Close the LINK position"""
    config = Config()
    setup_logger('INFO')
    logger = logging.getLogger(__name__)
    
    logger.info("=== CLOSING LINK POSITION ===")
    
    client = HyperliquidClient(config)
    await client.connect()
    
    try:
        # Check current position
        position = await client.get_position('LINK')
        if position:
            position_size = abs(position['size'])
            logger.info(f"Found LINK position: {position_size} @ ${position['entry_price']}")
            logger.info(f"Unrealized PnL: ${position['unrealized_pnl']}")
        else:
            logger.warning("No LINK position found on exchange")
            # Still try to sell 0.7 LINK from our test
            position_size = 0.7
            logger.info(f"Will attempt to sell {position_size} LINK from test order")
        
        # Get current market price
        market_data = await client.get_market_data('LINK')
        current_price = market_data.price
        logger.info(f"Current LINK price: ${current_price:.4f}")
        
        # Calculate P&L if we have position info
        if position:
            entry_price = position['entry_price']
            pnl = (current_price - entry_price) * position_size
            pnl_percent = (pnl / (entry_price * position_size)) * 100
            logger.info(f"P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)")
        
        # Place market SELL order
        logger.info(f"Placing MARKET SELL order for {position_size} LINK...")
        order_result = await client.place_order(
            symbol='LINK',
            side='sell',
            size=position_size,
            price=None,  # Market order
            order_type='market'
        )
        
        if order_result.success:
            if order_result.filled_size > 0:
                logger.info("✅ POSITION CLOSED!")
                logger.info(f"Order ID: {order_result.order_id}")
                logger.info(f"Sold: {order_result.filled_size} @ ${order_result.filled_price}")
                logger.info(f"Fees: ${order_result.fees}")
                
                # Calculate final P&L
                if position:
                    final_pnl = (order_result.filled_price - position['entry_price']) * order_result.filled_size
                    logger.info(f"Final P&L: ${final_pnl:.2f}")
            else:
                logger.info("✅ SELL ORDER PLACED")
                logger.info(f"Order ID: {order_result.order_id}")
                logger.info("Status: Pending execution")
        else:
            logger.error(f"❌ SELL ORDER FAILED: {order_result.error_message}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(close_position())