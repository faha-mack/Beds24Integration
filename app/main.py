import traceback
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx
from playwright.async_api import async_playwright, Browser, TimeoutError as PlaywrightTimeoutError
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
import uuid
import os
import authenticator
from dotenv import load_dotenv

# MongoDB setup
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://fah-db-stg:ABkaR4Tobo9Njo1N@cluster0.5obcm3m.mongodb.net/fah-stg?retryWrites=true&w=majority")
client = AsyncIOMotorClient(MONGODB_URL)
db = client["test"]
sessions_collection = db["sessions"]

# In-memory storage of active Playwright instances
active_playwrights = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    # Load environment variables from .env file
    load_dotenv()
    async for session in sessions_collection.find({"in_use": True}):
        await close_playwright(session["_id"])

    yield

    # Shutdown logic
    async for session in sessions_collection.find({"in_use": True}):
        await close_playwright(session["_id"])

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your frontend's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")

async def start_playwright(session_id: str):
    # Start a new Playwright session and browser for the session ID
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch()
    
    # Create a new context and a blank page
    context = await browser.new_context()
    page = await context.new_page()
    
    # Store the sessions in memory
    active_playwrights[session_id] = (playwright, browser, context, page)

    # Record only the session ID and status in the database
    await sessions_collection.insert_one({
        "_id": session_id,
        "in_use": True
    })

async def close_playwright(session_id: str):
    if session_id in active_playwrights:
        playwright, browser = active_playwrights.pop(session_id)
        try:
            await browser.close()
        except Exception as e:
            print(f"Error closing browser for session {session_id}: {e}")
        try:
            await playwright.stop()
        except Exception as e:
            print(f"Error stopping playwright for session {session_id}: {e}")
        
    await sessions_collection.delete_one({"_id": session_id})

async def get_browser(session_id: str) -> Browser:
    # Retrieve the browser for the given session ID
    if session_id not in active_playwrights:
        raise HTTPException(status_code=404, detail="Session not found")
    _, browser, _, _ = active_playwrights[session_id]
    return browser

async def switch_to_non_headless(session_id: str):
    browser = await get_browser(session_id)
    context = browser.contexts[0]
    await context.close()
    await browser.close()
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    active_playwrights[session_id] = (active_playwrights[session_id][0], browser, context, page)

async def switch_to_headless(session_id: str):
    browser = await get_browser(session_id)
    context = browser.contexts[0]
    await context.close()
    await browser.close()
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch()
    context = await browser.new_context()
    page = await context.new_page()
    active_playwrights[session_id] = (active_playwrights[session_id][0], browser, context, page)

async def get_context(session_id: str):
    # Retrieve the context for the given session ID
    if session_id not in active_playwrights:
        raise HTTPException(status_code=404, detail="Session not found")
    _, _, context, _ = active_playwrights[session_id]
    return context

async def save_context_state(context):
    # Save cookies and local storage data
    cookies = await context.cookies()
    local_storage = await context.storage_state()
    return cookies, local_storage

async def restore_context_state(context, cookies, local_storage):
    # Restore cookies and local storage data
    await context.add_cookies(cookies)
    await context.add_init_script(f"""
        window.localStorage.clear();
        const entries = {local_storage['origins'][0]['localStorage']};
        for (const [key, value] of entries) {{
            window.localStorage.setItem(key, value);
        }}
    """)

async def get_session_instance(session_id: str):
    # Retrieve the Playwright instance for the given session ID
    if session_id not in active_playwrights:
        raise HTTPException(status_code=404, detail="Session not found")
    browser = await get_browser(session_id)
    context = browser.contexts[0]
    page = context.pages[0]
    return browser, context, page

@app.post("/generate-session", tags=["Utilities"])
async def generate_session(background_tasks: BackgroundTasks):
    os.environ.pop("BEDS24_USERNAME", None)
    os.environ.pop("BEDS24_PASSWORD", None)
    os.environ.pop("GMAIL_APP_EMAIL", None)
    os.environ.pop("GMAIL_APP_PASSWORD", None)
    load_dotenv()
    session_id = str(uuid.uuid4())
    background_tasks.add_task(start_playwright, session_id)
    return {"session_id": session_id}

@app.post("/open-website", tags=["Utilities"])
async def open_website(session_id: str, url: str):
    browser = await get_browser(session_id)
    
    if not browser.contexts:
        context = await browser.new_context()
    else:
        context = browser.contexts[0]

    if not context.pages:
        page = await context.new_page()
    else:
        page = context.pages[0]
    try:
        await page.goto(url)
        title = await page.title()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {"url": url, "title": title}

@app.get("/current-page", tags=["Utilities"])
async def current_page(session_id: str):

    await switch_to_non_headless(session_id)
    
    browser = await get_browser(session_id)
    context = browser.contexts[0] 
    if not context.pages:
        raise HTTPException(status_code=404, detail="No open pages found")
    page = context.pages[0]
    url = page.url
    return {"session_id": session_id, "current_url": url}

@app.get("/authenticate", tags=["Utilities"])
async def authenticate(session_id: str):
    username = os.getenv("BEDS24_USERNAME")
    password = os.getenv("BEDS24_PASSWORD")
    await switch_to_non_headless(session_id)
    browser = await get_browser(session_id)
    context = browser.contexts[0]
    page = context.pages[0]
    await page.goto("https://beds24.com/control2.php")
    await page.wait_for_timeout(3000)
    try:
        # Wait for the reCAPTCHA iframe to load
        await page.wait_for_selector("iframe[src*='recaptcha']", timeout=10000)

        # Move mouse naturally to username field
        await authenticator.move_mouse_naturally(page, page, "input[name='username']")
        await page.fill("input.form-control.input-sm[name='username']", username)
        await authenticator.human_like_delay()
        
        # Move mouse naturally to password field
        await authenticator.move_mouse_naturally(page, page, "input[name='loginpass']")
        await page.fill("input.form-control.input-sm[name='loginpass']", password)
        await authenticator.human_like_delay()
        
        # Find and switch to recaptcha frame
        recaptcha_frame = next(
            frame for frame in page.frames 
            if "recaptcha" in frame.url
        )
        
        # Move mouse naturally to recaptcha checkbox
         # Move mouse naturally to recaptcha checkbox
        await authenticator.move_mouse_naturally(page, recaptcha_frame, "div.recaptcha-checkbox-border")
        await authenticator.human_like_delay()
        
        # Click with natural movement
        await recaptcha_frame.click("div.recaptcha-checkbox-border")
        await page.wait_for_timeout(3000)
        
        # Move to and click login button
        await authenticator.move_mouse_naturally(page, page, ".b24btn_Login")
        await page.click(".b24btn_Login")
        
        await page.wait_for_timeout(10000)

        # Check if login was successful
        current_url = page.url
        if current_url != "https://beds24.com/control2.php":
            cookies = await authenticator.get_cookies_from_page(page)
            return {"status": "success", "cookies": cookies}
        else:
            username = os.getenv("GMAIL_APP_EMAIL")
            app_password = os.getenv("GMAIL_APP_PASSWORD")
            code = await authenticator.check_gmail(username, app_password)
            if code.get('sender') == 'support@beds24.com':
                login_code = code.get('code')
                await page.fill("input[name='logincode']", str(login_code))
                await page.wait_for_timeout(10000)
                await page.click("button[type='submit']")
                await page.wait_for_timeout(3000)
                current_url = page.url
                if current_url != "https://beds24.com/control2.php":
                    try:
                        cookies_ = await authenticator.get_cookies_from_page(page)
                        cookies, local_storage = await save_context_state(context)
                        await switch_to_headless(session_id)
                        browser = await get_browser(session_id)
                        context = browser.contexts[0]
                        await restore_context_state(context, cookies, local_storage)
                        return {"status": "success", "cookies": cookies_}
                    except Exception as e:
                        traceback.print_exc()
                        return {"status": "error", "message": str(e)}
            elif code.get('sender') == 'ticket@beds24.com':
                await page.goto(code.get('code'))
                await page.wait_for_timeout(3000)
                current_url = page.url
                if current_url != "https://beds24.com/control2.php":
                    cookies_ = await authenticator.get_cookies_from_page(page)
                    cookies, local_storage = await save_context_state(context)
                    await switch_to_headless(session_id)
                    browser = await get_browser(session_id)
                    context = browser.contexts[0]
                    await restore_context_state(context, cookies, local_storage)
                    return {"status": "success", "cookies": cookies_}
            
    except PlaywrightTimeoutError:
        print("reCAPTCHA not found or took too long to load")
        return {"status": "reCAPTCHA not found or timeout"}


@app.get("/switch-user", tags=["Utilities"])
async def switch_user(session_id: str, user_email: str):
    browser, context, page = await get_session_instance(session_id)
    await page.goto("https://beds24.com/controladmin.php")
    await page.wait_for_selector('#_accountlist_admintable')
    selector = f'//table[@id="_accountlist_admintable"]//tr[td[3][normalize-space()="{user_email}"]]//button[@value="Log into Account"]'
    await page.click(selector)
    await page.wait_for_timeout(1000)


@app.get("/get_session_information", tags=["Utilities"])
async def get_session_information(session_id: str):
    browser, context, page = await get_session_instance(session_id)
    cookies = await context.cookies()
    user_element = await page.query_selector("body > div.fixed-top.shadow > div:nth-child(4) > nav.d-none.d-md-flex.navbar.navbar-light.navbar-bottom > div > ul.navbar-nav.justify-content-end.bottomrowrightul > li.nav-item.dropdown.show > div > a:nth-child(1)")
    response = {
        "beds_24_cookies": cookies,
        "current_url": page.url,
        "current_beds_24_user": await user_element.inner_text()
    }
    return {"cookies": cookies}

# @app.get("/connect_airbnb", tags=["Airbnb"])
# async def connect_airbnb(session_id: str):
#     browser, context, page = await get_session_instance(session_id)
#     await page.goto("https://beds24.com/control3.php?pagetype=syncroniserairbnbaccount")
#     await page.wait_for_selector("a[href*='airbnb.com']")
#     await page.click("a[href*='airbnb.com']")
#     await page.wait_for_timeout(3000)
#     await page.wait_for_selector("button[data-testid='login-sign-in-button']")
#     return {"status": "success"}

def generate_airbnb_auth_url():
    # Example authorization URL
    return "https://www.airbnb.com/oauth2/auth?client_id=6gsna623mfeic93fod1fcqlr&redirect_uri=https%3A%2F%2Fapi.beds24.com%2Fairbnb.com%2Fpush.php&scope=property_management%2Creservations_web_hooks%2Cmessages_read%2Cmessages_write&state=s%3A%2F%2Fbeds24.com%2Fcontrol3.php%3Fpagetype%3Dsyncroniserairbnbaccount"


@app.get("/airbnb/connect/get_connection_uri", tags=["Airbnb"])
async def connect_airbnb():
    auth_url = generate_airbnb_auth_url()
    return RedirectResponse(url=auth_url)

@app.get("/airbnb/connect/callback", tags=["Airbnb"])
async def airbnb_callback(request: Request, sessionId: str):
    code = request.query_params.get("code")
    print(code)
    browser, context, page = await get_session_instance(sessionId)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserairbnbaccount&code={code}")
    await page.wait_for_timeout(3000)
    return {"status": "success"}

@app.get("/get_airbnb_userIds_on_an_account", tags=["Airbnb"])
async def get_airbnb_userIds_on_an_account(token: str):
    pass

@app.get("/import_new_property_from_airbnb", tags=["Airbnb"])
async def import_new_property_from_airbnb(token: str, airbnb_user_id: str, airbnb_listing_id: str):
    pass

@app.get("/sync_properties_from_airbnb", tags=["Airbnb"])
async def sync_properties_from_airbnb(token: str, airbnb_user_id: str, airbnb_listing_id: str, beds24_propertyId: str):
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)