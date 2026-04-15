from modules.browser import BrowserManager
import asyncio

def send_whatsapp_message(recipient, message):
    async def main():
        browser_manager = BrowserManager(headless=False)
        page = browser_manager.navigate('https://web.whatsapp.com')

        # Wait for user to scan QR code manually
        page.wait_for_selector("[aria-label='Search or start new chat']")

        # Search for recipient
        search_box = page.query_selector("[aria-label='Search or start new chat']")
        search_box.click()
        page.keyboard.type(recipient)
        page.keyboard.press('Enter')

        # Type and send the message
        message_box = page.query_selector("[aria-label^='Type a message']")
        message_box.click()
        page.keyboard.type(message)
        page.keyboard.press('Enter')

        # Clean up
        await browser_manager.close()

    asyncio.run(main())

# Example use
send_whatsapp_message('Dad', 'Hello, this is a test message from S.A.I.')