import aiohttp
import asyncio
from urllib.parse import quote
import json

class HardBypass:
    def __init__(self):
        self.base_url = "https://captchakiller1.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-key': "90c2ea2c97mshbc9082cf24cf7d0p1dabfdjsnff442f00af00",
            'x-rapidapi-host': "captchakiller1.p.rapidapi.com"
        }
    
    async def solve_captcha(self, site_url: str, site_key: str) -> str:
        # URL encode the site_url
        encoded_url = quote(site_url)
        endpoint = f"/solvev2e?site={encoded_url}&sitekey={site_key}&gdomain=false&invisible=false"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}{endpoint}", 
                headers=self.headers
            ) as response:
                data = await response.json()
                
                if response.status != 200:
                    raise Exception("Failed to initialize captcha solving")
                
                return data.get("result", "")
    
# Example usage
async def main():
    bypass = HardBypass()
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
