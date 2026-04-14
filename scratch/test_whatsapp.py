import time

def automate_whatsapp_vision(sai_hub_instance, device_id: str, contact_name: str, message: str):
    """
    Step 5: Reference Demonstration of WhatsApp Automation strictly using Vision & Action engine.
    """
    interaction = sai_hub_instance.interaction
    vision = sai_hub_instance.vision
    
    print("[1] Opening app via command execution (Hybrid Fallback hierarchy)...")
    sai_hub_instance.device_manager.queue_command(device_id, "open_app", {"app_name": "whatsapp"})
    time.sleep(5)  # Wait for app UI to render
    
    print("[2] Searching for screen Search icon visually...")
    # Assume 'search_icon.png' exists in assets
    search_res = interaction.click_ui_template(device_id, "assets/search_icon_template.png", threshold=0.7)
    if search_res.get("status") == "error":
        print("[-] Fallback: Searching via text 'Search' instead of icon template")
        search_res = interaction.click_text(device_id, "Search", ignore_case=True)
    
    time.sleep(2)
    
    print(f"[3] Typing contact name: {contact_name}")
    interaction.type_text(device_id, contact_name)
    
    print("[4] Using Feedback loop to verify Contact appeared, then clicking...")
    def click_contact():
        return interaction.click_text(device_id, contact_name)
    
    def verify_chat_open():
        # Check if the text "Type a message" is visible, verifying we entered the chat
        r = vision.find_text_on_screen(device_id, "Type a message")
        return r.get("found", False)

    loop_res = interaction.execute_with_verification(device_id, click_contact, verify_chat_open)
    if loop_res["status"] == "error":
        return print("[-] Failed to open contact chat.")
        
    print(f"[5] Chat open. Typing message: {message} & Sending...")
    interaction.type_text(device_id, message)
    time.sleep(1)
    
    # We can either use a Send icon template, or hit 'Enter' key via execution fallback
    interaction.tap_or_click(device_id, x=950, y=1000) # Hardcode generic send layout OR
    sai_hub_instance.device_manager.queue_command(device_id, "press_key", {"key": "enter"})
    
    print("[+] WhatsApp Vision Automation task complete.")

