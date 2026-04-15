from modules.browser import BrowserManager
import asyncio
import sys

async def send_whatsapp_message(recipient, message):
    browser_manager = BrowserManager(headless=False)
    
    print("Navigating to WhatsApp Web...")
    await browser_manager.navigate('https://web.whatsapp.com')

    # Wait for user to scan QR code manually
    print("Waiting for session... (Please scan QR code if necessary)")
    await browser_manager.wait_for("[aria-label='Search or start new chat']", state="visible")

    # Search for recipient
    print(f"Searching for {recipient}...")
    await browser_manager.click("[aria-label='Search or start new chat']")
    await browser_manager.type_text("[aria-label='Search or start new chat']", recipient)
    await browser_manager.press_key(None, 'Enter')

    # Type and send the message
    print(f"Sending message to {recipient}...")
    await browser_manager.wait_for("div[contenteditable='true'][role='textbox'][title^='Type a message']", state="visible")
    await browser_manager.type_text("div[contenteditable='true'][role='textbox'][title^='Type a message']", message)
    await browser_manager.press_key(None, 'Enter')

    print("Success! Message sent.")
    
    # Wait a bit before closing
    await asyncio.sleep(2)
    # Clean up
    await browser_manager.close()

if __name__ == "__main__":
    recipient = sys.argv[1] if len(sys.argv) > 1 else 'Dad'
    message = sys.argv[2] if len(sys.argv) > 2 else 'Hello, this is a test message from S.A.I.'
    asyncio.run(send_whatsapp_message(recipient, message))