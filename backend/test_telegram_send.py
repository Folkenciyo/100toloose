import asyncio
import httpx

async def test():
    token = "8268709352:AAFsVMfURjy3gnbY5ovDs6aBGiQ2lS5m9Lg"
    chat_id = "5446411593"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": "✅ Test message from 100toLoose Trading Bot!"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload)
        data = response.json()
        print("Status:", response.status_code)
        print("Response:", data)
        
        if data.get("ok"):
            print("\n✅ Message sent successfully!")
        else:
            print(f"\n❌ Error: {data.get('description')}")

asyncio.run(test())

