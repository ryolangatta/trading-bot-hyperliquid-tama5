#!/usr/bin/env python3
"""
Test script to manually send trading signals to the bot
This simulates sending a Discord command to test the manual signal functionality
"""

import sys
import os
import asyncio
from datetime import datetime

# Add the hyperliquid_bot directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hyperliquid_bot'))

from notifications.discord_commands import ManualSignal, DiscordWebhookCommands
from config import Config


async def test_manual_signal():
    """Test manual signal functionality"""
    print("=== Manual Signal Test ===")
    
    # Load configuration
    config = Config()
    
    # Create a dummy Discord notifier (we don't need actual Discord functionality for this test)
    class DummyDiscordNotifier:
        async def send_notification(self, message):
            print(f"[DISCORD] Would send: {message.title} - {message.description}")
    
    # Create Discord command processor
    discord_commands = DiscordWebhookCommands(config, DummyDiscordNotifier())
    
    # Get user input
    print("\nAvailable commands: BUY, SELL")
    command = input("Enter command: ").strip().upper()
    
    if command not in ['BUY', 'SELL']:
        print("Invalid command. Please use BUY or SELL")
        return
    
    # Simulate an authorized user (you'll need to add your Discord user ID to DISCORD_AUTHORIZED_USERS)
    user_id = input("Enter Discord user ID (must be in DISCORD_AUTHORIZED_USERS): ").strip()
    username = input("Enter Discord username: ").strip() or "TestUser"
    
    # Queue the manual signal
    success = discord_commands.queue_manual_signal(command, user_id, username)
    
    if success:
        print(f"\n✅ Manual {command} signal queued successfully!")
        
        # Check if signal is in queue
        pending_signal = discord_commands.get_pending_signal()
        if pending_signal:
            print(f"\nPending signal details:")
            print(f"  Command: {pending_signal.command}")
            print(f"  Symbol: {pending_signal.symbol}")
            print(f"  User: {pending_signal.username} ({pending_signal.user_id})")
            print(f"  Timestamp: {pending_signal.timestamp}")
    else:
        print(f"\n❌ Failed to queue signal - user not authorized")


async def test_direct_signal_injection():
    """Test direct signal injection into the bot's queue"""
    print("\n=== Direct Signal Injection Test ===")
    
    # Load configuration
    config = Config()
    
    # Create Discord command processor
    discord_commands = DiscordWebhookCommands(config, None)
    
    # Create a manual signal directly
    signal = ManualSignal(
        command='BUY',
        symbol=config.symbol,
        user_id='123456789',  # Replace with your Discord user ID
        username='DirectTest',
        timestamp=datetime.now()
    )
    
    # Add to queue directly (bypassing authorization for testing)
    discord_commands.signal_queue.append(signal)
    
    print(f"✅ Signal injected directly into queue")
    print(f"Queue size: {len(discord_commands.signal_queue)}")
    
    # Get the signal
    pending = discord_commands.get_pending_signal()
    if pending:
        print(f"Retrieved signal: {pending.command} from {pending.username}")


async def main():
    """Main test function"""
    print("Hyperliquid Bot - Manual Signal Tester")
    print("=====================================\n")
    
    print("1. Test manual signal with authorization")
    print("2. Test direct signal injection (no auth)")
    
    choice = input("\nSelect test option (1 or 2): ").strip()
    
    if choice == '1':
        await test_manual_signal()
    elif choice == '2':
        await test_direct_signal_injection()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())