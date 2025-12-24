import httpx
import asyncio

async def test():
    token = "8268709352:AAFsVMfURjy3gnbY5ovDs6aBGiQ2lS5m9Lg"
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        data = response.json()
        print("Response:", data)
        
        if data.get("ok"):
            updates = data.get("result", [])
            print(f"\nFound {len(updates)} updates")
            if updates:
                for update in updates[-3:]:  # Last 3
                    msg = update.get("message") or update.get("edited_message")
                    if msg:
                        chat = msg.get("chat", {})
                        from_user = msg.get("from", {})
                        print(f"  - Chat ID: {chat.get('id')}, Type: {chat.get('type')}, From: {from_user.get('first_name', 'Unknown')} (bot: {from_user.get('is_bot', False)})")
        else:
            print("Error:", data.get("description"))

asyncio.run(test())

