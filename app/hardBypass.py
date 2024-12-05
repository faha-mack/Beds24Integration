import aiohttp
import asyncio
from urllib.parse import quote
import json

class HardBypass:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://fast-multisolver.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-key': api_key,
            'x-rapidapi-host': "fast-multisolver.p.rapidapi.com"
        }
    
    async def solve_captcha(self, site_url: str, site_key: str) -> str:
        # Initial request to get the task ID
        async with aiohttp.ClientSession() as session:
            # URL encode the site_url
            encoded_url = quote(site_url)
            initial_endpoint = f"/in.php?sitekey={site_key}&pageurl={encoded_url}&method=userrecaptcha&json=1"
            
            async with session.get(
                f"{self.base_url}{initial_endpoint}", 
                headers=self.headers
            ) as response:
                initial_data = await response.json()
                
                if initial_data.get("status") != 1:
                    raise Exception("Failed to initialize captcha solving")
                
                request_id = initial_data["request"]
                return await self._poll_result(session, request_id)
    
    async def _poll_result(self, session: aiohttp.ClientSession, request_id: str) -> str:
        while True:
            async with session.get(
                f"{self.base_url}/res.php?id={request_id}&json=1",
                headers=self.headers
            ) as response:
                result_data = await response.json()
                
                if result_data.get("status") == 1:
                    print("Captcha solved")
                    return result_data["request"]
                
                # Wait 5 seconds before next poll
                print("Waiting 5 seconds before next poll for request id: ", request_id)
                print(result_data)
                await asyncio.sleep(5)

# Example usage
async def main():
    bypass = HardBypass("3e7b41810dmsh36643b0730bb46fp1ab16bjsnf465416451bc")
    site_url = input("Enter the site URL: ")
    site_key = input("Enter the site key: ")
    try:
        result = await bypass.solve_captcha(
            site_url,
            site_key
        )
        print(f"Captcha solved: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
