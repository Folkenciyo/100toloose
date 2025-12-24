import httpx
import asyncio

async def test():
    token = "8268709352:AAFsVMfURjy3gnbY5ovDs6aBGiQ2lS5m9Lg"
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        data = response.json()
        print("Bot Info:", data)
        
        if data.get("ok"):
            bot = data.get("result", {})
            print(f"\n✅ Bot is valid!")
            print(f"   Username: @{bot.get('username')}")
            print(f"   Name: {bot.get('first_name')}")
            print(f"\n📱 To get your Chat ID:")
            print(f"   1. Open Telegram and search for @{bot.get('username')}")
            print(f"   2. Click 'Start' or send any message")
            print(f"   3. Wait 2-3 seconds")
            print(f"   4. Go to Profile page and click 'Get Chat ID'")
        else:
            print("❌ Error:", data.get("description"))

asyncio.run(test())

