import os
import sys
import asyncio

# Append the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from sai import SAI

async def run_headless_test():
    print("Initializing Core S.A.I...")
    sai = SAI()
    
    # 1. Navigate
    print("\\n[1] Instructing S.A.I. to surf to Hacker News...")
    nav_res = await sai.execute_tool("browser.navigate", {"url": "https://news.ycombinator.com"})
    print("Navigation Result:", nav_res)
    
    # Wait for page elements to load
    await asyncio.sleep(2)
    
    # 2. Explore interactive DOM elements
    print("\\n[2] Requesting DOM Elements (Headless Explore)...")
    explore_res = await sai.execute_tool("browser.explore", {})
    if explore_res.get("status") == "success":
        elements = explore_res.get("elements", [])
        print(f"Discovered {len(elements)} interactive buttons/links.")
        if len(elements) > 0:
            print(f"Sample element: {elements[0]}")
    else:
        print("Explore Error:", explore_res)
        
    # 3. Scrape the page
    print("\\n[3] Extract text payload via headless scraping...")
    scrape_res = await sai.execute_tool("browser.scrape", {})
    if scrape_res.get("status") == "success":
        text = scrape_res.get("text", "")
        print(f"Scraped {len(text)} characters of text.")
        print("Snippet:", text[:200].replace("\\n", " "))
    else:
        print("Scrape Error:", scrape_res)

    print("\\nShutting down browser node...")
    await sai.browser.close()

if __name__ == "__main__":
    asyncio.run(run_headless_test())

