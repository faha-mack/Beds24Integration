import asyncio
import datetime
from datetime import timedelta, timezone
from enum import Enum
import json
from typing import Optional
from bson import json_util
import traceback
from fastapi import Body, FastAPI, HTTPException, BackgroundTasks, Request, logger
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
from models import CheckOutInstructions, Descriptions, ListingDetails, PricingSettings, SessionRequest, BookingRules
from models import Custom, PropertyDetails, PropertyProfile, InvoicesContact, ReservationsContact, Policies
from bs4 import BeautifulSoup
import captcha_audio_bypass

load_dotenv()
# MongoDB setup
MONGODB_URL = os.environ.get("MONGODB_URL")
client = AsyncIOMotorClient(MONGODB_URL)
db = client["test"]
sessions_collection = db["sessions"]
refresh_tokens_collection = db["integrations_refresh_tokens"]

# In-memory storage of active Playwright instances
active_playwrights = {}
last_access_times = {}

TIMEOUT_PERIOD = datetime.timedelta(hours=1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load state from MongoDB on startup
    await load_state_from_mongodb()

    # Startup logic
    asyncio.create_task(periodic_cleanup())
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

async def save_state_to_mongodb():
    try:
        state = {
            "active_playwrights": {
                session_id: {
                    "url": page.url,
                    "cookies": await context.cookies(),
                    "local_storage": await context.storage_state()
                }
                for session_id, (playwright, browser, context, page) in active_playwrights.items()
                if browser.is_connected() and not page.is_closed()
            },
            "last_access_times": last_access_times
        }
        serialized_state = json.loads(json_util.dumps(state))
        await sessions_collection.update_one(
            {"_id": "playwright_state"},
            {"$set": {"data": serialized_state}},
            upsert=True
        )
    except Exception as e:
        print(f"Error saving state to MongoDB: {e}")
    
async def load_state_from_mongodb():
    global active_playwrights, last_access_times
    try:
        state_data = await sessions_collection.find_one({"_id": "playwright_state"})
        if state_data:
            state = json_util.loads(json.dumps(state_data["data"]))
            last_access_times = state.get("last_access_times", {})

            for session_id, session_data in state.get("active_playwrights", {}).items():
                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch(
                    headless=True,  # Use the new headless mode
                    args=["--no-sandbox"],
                    timeout=300000  # Increase the timeout to 300 seconds
                )
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(session_data["url"])
                await context.add_cookies(session_data["cookies"])

                local_storage_data = session_data["local_storage"].get('origins', [])
                if local_storage_data:
                    local_storage_entries = local_storage_data[0].get('localStorage', [])
                    await context.add_init_script(f"""
                        window.localStorage.clear();
                        const entries = {json.dumps(local_storage_entries)};
                        for (const [key, value] of entries) {{
                            window.localStorage.setItem(key, value);
                        }}
                    """)

                active_playwrights[session_id] = (playwright, browser, context, page)
    except Exception as e:
        traceback.print_exc()
        print(f"Error loading state from MongoDB: {e}")
        
async def start_playwright(session_id: str, email: str):
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch()
        
        # Create a new context and a blank page
        context = await browser.new_context()
        page = await context.new_page()
        
        # Store the sessions in memory
        active_playwrights[session_id] = (playwright, browser, context, page)
        last_access_times[session_id] = datetime.datetime.now(timezone.utc)
        await save_state_to_mongodb()
    except Exception as e:
        print(f"Error starting Playwright: {e}")
        raise HTTPException(status_code=500, detail="Error starting Playwright")

    # Record only the session ID and status in the database
    await sessions_collection.insert_one({
        "_id": session_id,
        "email": email,
        "in_use": True,
        "created_at": datetime.datetime.now(timezone.utc)
    })

async def access_playwright(session_id: str):
    # Update the last access time whenever the session is accessed
    if session_id in last_access_times:
        last_access_times[session_id] = datetime.datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=404, detail="Session not found")

async def cleanup_playwright_instance(session_id: str):
    # Retrieve the Playwright instance from memory
    instance = active_playwrights.pop(session_id, None)
    if instance:
        playwright, browser, context, page = instance

        # Close the browser and Playwright instance
        await page.close()
        await context.close()
        await browser.close()
        await playwright.stop()

        # Update the database to mark the session as not in use
        await sessions_collection.update_one(
            {"_id": session_id},
            {"$set": {"in_use": False}}
        )

async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  # Run the cleanup task every hour
        current_time = datetime.datetime.now(timezone.utc)
        for session_id, last_access in list(last_access_times.items()):
            last_access = last_access.replace(tzinfo=timezone.utc)  # Ensure last_access is offset-aware
            if current_time - last_access > TIMEOUT_PERIOD:
                await cleanup_playwright_instance(session_id)
        await save_state_to_mongodb()

async def close_playwright(session_id: str):
    if session_id in active_playwrights:
        playwright, browser, context, page = active_playwrights[session_id]
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
    await save_state_to_mongodb()

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
    await save_state_to_mongodb()

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

async def get_session_instance(session_id: str):
    # Retrieve the Playwright instance for the given session ID
    if session_id not in active_playwrights:
        raise HTTPException(status_code=404, detail="Session not found")
    browser = await get_browser(session_id)
    context = browser.contexts[0]
    page = context.pages[0]
    return browser, context, page

async def authenticate(session_id: str, phpsessid: str = None):
    if phpsessid:
        browser = await get_browser(session_id)
        context = browser.contexts[0]
        page = context.pages[0]
        await page.set_extra_http_headers({"Cookie": f"PHPSESSID={phpsessid}"})
        await page.goto("https://beds24.com/control2.php")
        cookies = await authenticator.get_cookies_from_page(page)
        return {"status": "success", "cookies": cookies}
    username = os.environ.get("BEDS24_USERNAME") if os.environ.get("BEDS24_USERNAME") else "channel.manager"
    password = os.environ.get("BEDS24_PASSWORD") if os.environ.get("BEDS24_PASSWORD") else "P0s>b.m2s4]e"
    await switch_to_non_headless(session_id)
    browser = await get_browser(session_id)
    context = browser.contexts[0]
    page = context.pages[0]
    await page.goto("https://beds24.com/control2.php")
    await page.wait_for_load_state('load') 
    try:
        # Wait for the reCAPTCHA iframe to load
        current_url = page.url
        if current_url != "https://beds24.com/control2.php":
            cookies = await authenticator.get_cookies_from_page(page)
            return {"status": "success", "cookies": cookies}
        await page.wait_for_selector("iframe[src*='recaptcha']", timeout=10000)

        # Find and switch to recaptcha frame
        recaptcha_frame = next(
            frame for frame in page.frames 
            if "recaptcha" in frame.url
        )
                
        await authenticator.move_mouse_naturally(page, recaptcha_frame, "div.recaptcha-checkbox-border")
        await recaptcha_frame.click("div.recaptcha-checkbox-border")
        print("reCAPTCHA checkbox clicked")
        await page.wait_for_timeout(3000)
        recaptcha_iframe = await page.query_selector_all("iframe[src*='recaptcha']")
        recaptcha_frame = await recaptcha_iframe[1].content_frame()
        recaptcha_audio = await recaptcha_frame.query_selector("#recaptcha-audio-button")
        recaptcha_image = await recaptcha_frame.query_selector("#recaptcha-image-button")
        if recaptcha_audio or recaptcha_image:
            if recaptcha_audio:
                await authenticator.move_mouse_naturally(page, recaptcha_frame, "#recaptcha-audio-button")
                audio_button = await recaptcha_frame.query_selector("#recaptcha-audio-button")
                if audio_button != None:
                    await authenticator.human_like_delay()
                    await audio_button.click()
                    print("Audio button clicked")
            await authenticator.human_like_delay()
            audio_url_element = await recaptcha_frame.query_selector("#audio-source")
            try:
                audio_url = await audio_url_element.get_attribute("src")
            except Exception as e:
                print("Audio not found... Trying again")
                return {"status": "error", "message": "Automation Detected/Audio not found... Trying again"}
            await authenticator.human_like_delay()
            captcha_bypass = captcha_audio_bypass.BypassAudioCaptcha(audio_url)
            text = await captcha_bypass.run()
            audio_input = await recaptcha_frame.query_selector("#audio-response")
            await authenticator.move_mouse_naturally(page, recaptcha_frame, "#audio-response")
            await audio_input.fill(text)
            print("Audio text entered: ", text)
            await authenticator.move_mouse_naturally(page, recaptcha_frame, "#recaptcha-verify-button")
            verify_button = await recaptcha_frame.query_selector("#recaptcha-verify-button")
            await verify_button.click()
            print("Verify button clicked")
            await page.wait_for_timeout(3000)
        print("reCAPTCHA checkbox checked")

        # Move mouse naturally to username field
        await page.fill("input.form-control.input-sm[name='username']", username)
        print("Username entered")
        
        # Move mouse naturally to password field
        await page.fill("input.form-control.input-sm[name='loginpass']", password)
        print("Password entered")

        await page.wait_for_timeout(3000)
        await page.click(".b24btn_Login")
        await page.wait_for_timeout(5000)
        current_url = page.url
        if current_url != "https://beds24.com/control2.php":
            cookies = await authenticator.get_cookies_from_page(page)
            return {"status": "success", "cookies": cookies}
        else:
            username = os.environ.get("GMAIL_APP_EMAIL") if os.environ.get("GMAIL_APP_EMAIL") else "channel.manager@findahost.io"
            app_password = os.environ.get("GMAIL_APP_PASSWORD") if os.environ.get("GMAIL_APP_PASSWORD") else "efbdsqfyxefvtptb"
            code = await authenticator.check_gmail(username, app_password)
            f_attempt = 0
            while code.get('status') != 'success':
                print("Username: ", username)
                print("App Password: ", app_password)
                print("Fetching code error... Trying again in 10 seconds")
                await page.wait_for_timeout(10000)
                code = await authenticator.check_gmail(username, app_password)
                f_attempt += 1
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
            await save_state_to_mongodb()
        
        # Move to and click login button
        
    except PlaywrightTimeoutError:
        traceback.print_exc()
        return {"status":"error", "message":"reCAPTCHA not found or timeout"}

async def get_current_user_refresh_token(user_email):
    user = await refresh_tokens_collection.find_one({"email": user_email})
    print('user', user)
    if user:
        return user.get("refresh_token")
    else:
        return None

async def get_authtoken_from_refresh_token(refresh_token):
    url = "https://beds24.com/api/v2/authentication/token"
    headers = {
        "accept": "application/json",
        "refreshToken": refresh_token
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            r = response.json()
            return r.get("token")
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)


@app.post("/generate_session", tags=["Utilities"])
async def generate_session(request: SessionRequest, background_tasks: BackgroundTasks):
    load_dotenv()
    # Persist authentication
    auth_retries = 0
    session_id = str(uuid.uuid4())

    while True:
        session_id = str(uuid.uuid4())
        await start_playwright(session_id, request.email)
        try:
            authenticated = await authenticate(session_id, None)
            if authenticated.get("status") == "success" or auth_retries >= 5:
                break
        except Exception as e:
            print(f"Error authenticating session {session_id}: {e}. Retrying...")
            await close_playwright(session_id)
        auth_retries += 1

    if request.email:
        user_switched = await switch_user(session_id, request.email)
        if user_switched.get("status") == "error":
            return {"status": "error", "session_id": session_id, "message": user_switched.get("message")}
        return {"status": "success", "session_id": session_id, "cookies": authenticated.get("cookies")}
    else:
        return {"status": "success", "session_id": session_id, "cookies": authenticated.get("cookies")}

@app.get("/test_session_authentication", tags=["Utilities"])
async def test_session(session_id: str):
    await access_playwright(session_id)
    browser = await get_browser(session_id)
    context = browser.contexts[0] 
    if not context.pages:
        raise HTTPException(status_code=404, detail="No open pages found")
    page = context.pages[0]
    await page.goto("https://beds24.com/control3.php?pagetype=properties")
    await page.wait_for_timeout(3000)
    if page.url == "https://beds24.com/control3.php?pagetype=properties":
        return {"status": "success", "message": "Session is authenticated"}
    else:
        return {"status": "error", "message": "Session is not authenticated"}

@app.get("/get_session_information", tags=["Utilities"])
async def get_session_information(session_id: str):
    is_authenticated = await test_session(session_id)
    if is_authenticated.get("status") == "success":
        browser, context, page = await get_session_instance(session_id)
        await page.goto("https://beds24.com/control3.php?pagetype=account")
        await page.wait_for_selector("body > div.container-fluid.b24container-fluid > div > main > div.background_box > div.innerbackground_boxhide > div.innerbackground_box > div.twelvecol.first.setting_row.menusetting-AdministratorEmail > div.ninecol.last > div > div")
        user_element = await page.query_selector("body > div.container-fluid.b24container-fluid > div > main > div.background_box > div.innerbackground_boxhide > div.innerbackground_box > div.twelvecol.first.setting_row.menusetting-AdministratorEmail > div.ninecol.last > div > div")
        user_name = await user_element.inner_text()
        cookies = await context.cookies()
        await save_state_to_mongodb()
        return {"status":"success", "username":user_name, "cookies":cookies}
    else:
        return {"status": "error", "message": "Session is not authenticated"}

@app.get("/switch-user", tags=["Utilities"])
async def switch_user(session_id: str, user_email: str):
    try:
        browser, context, page = await get_session_instance(session_id)
        await page.goto("https://beds24.com/controladmin.php")
        await page.wait_for_selector('#_accountlist_admintable')
        if not await page.query_selector('#_accountlist_admintable'):
            password_element = await page.query_selector("#settingformid > div > div.innerbackground_boxhide > div.innerbackground_box > div.twelvecol.first.setting_row.menusetting-passwordcheck > div.ninecol.last > input")
            await password_element.fill("P0s>b.m2s4]e")
            await page.click("#settingformid > div > div.innerbackground_boxhide > div.setting_footer_section > button")
            await page.wait_for_selector('#_accountlist_admintable')
        selector = f'//table[@id="_accountlist_admintable"]//tr[td[3][normalize-space()="{user_email}"]]//button[@value="Log into Account"]'
        await page.click(selector)
        await page.wait_for_timeout(1000)
        await save_state_to_mongodb()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/get_new_token_from_session", tags=["Utilities"])
async def get_fresh_token_from_session(session_id: str):
    is_authenticated = await test_session(session_id)
    if is_authenticated.get("status") == "success":
        username_fetch = await get_session_information(session_id)
        username = username_fetch.get("username")
        print('username', username)
        current_refresh_token = await get_current_user_refresh_token(username)
        print('current_refresh_token', current_refresh_token)
        if current_refresh_token:
            token = await get_authtoken_from_refresh_token(current_refresh_token)
            return {"status": "success", "token": token}
        else:
            return {"status": "error", "message": "Refresh token not found for user "+username}
        
@app.get("/get_airbnb_userIds_on_an_account", tags=["Airbnb"])
async def get_airbnb_userIds_on_an_account(token: str):
    url = "https://beds24.com/api/v2/channels/airbnb/users"
    headers = {
        "accept": "application/json",
        "token": token
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

@app.post("/import_new_property_from_airbnb", tags=["Airbnb"])
async def import_new_property_from_airbnb(token: str, airbnb_user_id: str, airbnb_listing_id: str):
    url = "https://beds24.com/api/v2/channels/airbnb"
    headers = {
        "accept": "application/json",
        "token": token,
        "Content-Type": "application/json"
    }
    data = [
        {
            "action": "importAsNewProperty",
            "airbnbUserId": airbnb_user_id,
            "airbnbListingId": airbnb_listing_id,
            "connect": "full"
        }
    ]

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            r = response.json()
            return {
                "status": "success",
                "details": r
            }
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

@app.post("/sync_properties_from_airbnb", tags=["Airbnb"])
async def sync_properties_from_airbnb(token: str, airbnb_user_id: str, airbnb_listing_id: str, beds24_propertyId: str):
    url = "https://beds24.com/api/v2/channels/airbnb"
    headers = {
        "accept": "application/json",
        "token": token,
        "Content-Type": "application/json"
    }
    data = [
        {
            "action": "importToExistingProperty",
            "airbnbUserId": airbnb_user_id,
            "airbnbListingId": airbnb_listing_id,
            "connect": "full",
            "propertyId": beds24_propertyId
        }
    ]

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.text)

@app.get("/get_airbnb_property_content_extensive", tags=["Airbnb"])
async def get_airbnb_property_content_extensive(session_id: str, beds24roomId: str = "533105"):
    browser, context, page = await get_session_instance(session_id)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserairbnbview&id={beds24roomId}")
    await page.wait_for_timeout(3000)
    
    elements_selectors = {
        "listingdetails": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(13)",
        "listingdescriptions": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(17)",
        "priceandavailability": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(25)",
        "listingrooms": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(29)",
        "listingpictures": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(33)",
    }
    
    data = {}

    for key, selector in elements_selectors.items():
        element_handle = await page.query_selector(selector)
        if element_handle:
            html_content = await element_handle.inner_html()
            # Parse the HTML table to a dictionary
            table_data = parse_table(html_content)
            data[key] = table_data
    return data

@app.get("/get_airbnb_property_content", tags=["Airbnb"])
async def get_airbnb_property_content(session_id: str, beds24roomId: str = "533105"):
    browser, context, page = await get_session_instance(session_id)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserairbnbroom&id={beds24roomId}")
    await page.wait_for_timeout(3000)
    results = {}

    listing_details = {
        "publish": await page.eval_on_selector("#publish option:checked", "el => el.innerText"),
        "propertytypegroup": await page.eval_on_selector("#proptypegroup option:checked", "el => el.innerText"),
        "listingtype": await page.eval_on_selector("#listingtype option:checked", "el => el.innerText"),
        "updateaddress": await page.eval_on_selector("#hideaddress option:checked", "el => el.innerText"),
        "picsource": await page.eval_on_selector("#picsource option:checked", "el => el.innerText"),
        "bathroomshared": await page.eval_on_selector("#bathroomshared option:checked", "el => el.innerText"),
        "commonshared": await page.eval_on_selector("#commonshared option:checked", "el => el.innerText"),
        "checkincategory": await page.eval_on_selector("#checkincategory option:checked", "el => el.innerText"),
        "checkindesc": await page.eval_on_selector("#checkindesc", "el => el.value"),
        "housemanual": await page.eval_on_selector("#housemanual", "el => el.value")
    }

    checkout_instructions = {
        "checkoutrk": await page.eval_on_selector("#checkoutrk", "el => el.value"),
        "checkouttto": await page.eval_on_selector("#checkouttto", "el => el.value"),
        "checkoutt": await page.eval_on_selector("#checkoutt", "el => el.value"),
        "checkoutlu": await page.eval_on_selector("#checkoutlu", "el => el.value"),
        "checkoutgt": await page.eval_on_selector("#checkoutgt", "el => el.value"),
        "checkoutar": await page.eval_on_selector("#checkoutar", "el => el.value")
    }

    descriptions = {
        "multilang": await page.eval_on_selector("#multilang option:checked", "el => el.innerText"),
        "propnameEN": await page.eval_on_selector("#propnameEN", "el => el.value"),
        "summaryEN": await page.eval_on_selector("#summaryEN", "el => el.value"),
        "spaceEN": await page.eval_on_selector("#spaceEN", "el => el.value"),
        "accessEN": await page.eval_on_selector("#accessEN", "el => el.value"),
        "interactionEN": await page.eval_on_selector("#interactionEN", "el => el.value"),
        "neighborhoodEN": await page.eval_on_selector("#neighborhoodEN", "el => el.value"),
        "transitEN": await page.eval_on_selector("#transitEN", "el => el.value"),
        "notesEN": await page.eval_on_selector("#notesEN", "el => el.value"),
    }

    booking_rules = {
        "prebookmsg": await page.eval_on_selector("#prebookmsg", "el => el.value"),
        "instantbookallow": await page.eval_on_selector("#instantbookallow option:checked", "el => el.innerText"),
        "cancelpolicy": await page.eval_on_selector("#cancelpolicy option:checked", "el => el.innerText"),
        "nonrefundfactor": await page.eval_on_selector("#nonrefundfactor option:checked", "el => el.innerText"),
    }

    pricing_settings = {
        "extraPersonPrice": await page.eval_on_selector("#extraperson", "el => el.value"),
        "pricingstrategy": await page.eval_on_selector("#losprices option:checked", "el => el.innerText"),
        "guestsincluded": await page.eval_on_selector("#guestinc option:checked", "el => el.innerText"),
        "dateswithnoprice": await page.eval_on_selector("#datenoprice option:checked", "el => el.innerText"),
        "twodaydiscounts": await page.eval_on_selector("#day2disc option:checked", "el => el.innerText"),
        "threedaydiscounts": await page.eval_on_selector("#day3disc option:checked", "el => el.innerText"),
        "fourdaydiscounts": await page.eval_on_selector("#day4disc option:checked", "el => el.innerText"),
        "fivedaydiscounts": await page.eval_on_selector("#day5disc option:checked", "el => el.innerText"),
        "sixdaydiscounts": await page.eval_on_selector("#day6disc option:checked", "el => el.innerText"),
        "sevendaydiscounts": await page.eval_on_selector("#day7disc option:checked", "el => el.innerText"),
        "fourteendaydiscounts": await page.eval_on_selector("#day14disc option:checked", "el => el.innerText"),
        "twentyonedaydiscounts": await page.eval_on_selector("#day21disc option:checked", "el => el.innerText"),
        "twentyeightdaydiscounts": await page.eval_on_selector("#day28disc option:checked", "el => el.innerText"),
        "maxdaysinadvance": await page.eval_on_selector("#maxnotice option:checked", "el => el.innerText"),
        "advancenotice": await page.eval_on_selector("#leadtime option:checked", "el => el.innerText"),
        "advancenoticerequest": await page.eval_on_selector("#leadrequest option:checked", "el => el.innerText"),
        "earlybirddaystocheckin": await page.eval_on_selector("#bookbeyondd option:checked", "el => el.innerText"),
        "earlybirddiscountpercent": await page.eval_on_selector("#bookbeyondp option:checked", "el => el.innerText"),
        "lastminutedaystocheckin": await page.eval_on_selector("#bookwithind option:checked", "el => el.innerText"),
        "lastminutediscountpercent": await page.eval_on_selector("#bookwithinp option:checked", "el => el.innerText"),
    }
    custom = await page.eval_on_selector("#custom", "el => el.value")

    results["listing_details"] = listing_details
    results["checkout_instructions"] = checkout_instructions
    results["descriptions"] = descriptions
    results["booking_rules"] = booking_rules
    results["pricing_settings"] = pricing_settings
    results["custom"] = custom

    return results

@app.patch("/modify_property_content", tags=["Airbnb"])
async def modify_property_content(
    session_id: str,
    room_id: str,
    listing_details: ListingDetails = Body(...),
    checkout_instructions: CheckOutInstructions = Body(...),
    descriptions: Descriptions = Body(...),
    booking_rules: BookingRules = Body(...),
    pricing_settings: PricingSettings = Body(...),
    custom: Optional[str] = Body(None)
):
    browser, context, page = await get_session_instance(session_id)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserairbnbroom&id={room_id}")
    await page.wait_for_timeout(3000)
    await page.select_option("#publish", listing_details.publish)
    await page.select_option("#proptypegroup", listing_details.propertytypegroup)
    await page.select_option("#listingtype", listing_details.listingtype)
    await page.select_option("#hideaddress", listing_details.updateaddress)
    await page.select_option("#picsource", listing_details.picsource)
    await page.select_option("#bathroomshared", listing_details.bathroomshared)
    await page.select_option("#commonshared", listing_details.commonshared)
    await page.select_option("#checkincategory", listing_details.checkincategory)
    await page.fill("#checkindesc", listing_details.checkindesc)
    await page.fill("#housemanual", listing_details.housemanual)
    
    await page.fill("#checkoutrk", checkout_instructions.checkoutrk)
    await page.fill("#checkouttto", checkout_instructions.checkouttto)
    await page.fill("#checkoutt", checkout_instructions.checkoutt)
    await page.fill("#checkoutlu", checkout_instructions.checkoutlu)
    await page.fill("#checkoutgt", checkout_instructions.checkoutgt)
    await page.fill("#checkoutar", checkout_instructions.checkoutar)
    
    await page.select_option("#multilang", descriptions.multilang)
    await page.fill("#propnameEN", descriptions.propnameEN)
    await page.fill("#summaryEN", descriptions.summaryEN)
    await page.fill("#spaceEN", descriptions.spaceEN)
    await page.fill("#accessEN", descriptions.accessEN)
    await page.fill("#interactionEN", descriptions.interactionEN)
    await page.fill("#neighborhoodEN", descriptions.neighborhoodEN)
    await page.fill("#transitEN", descriptions.transitEN)
    await page.fill("#notesEN", descriptions.notesEN)

    await page.fill("#prebookmsg", booking_rules.prebookmsg)
    await page.select_option("#instantbookallow", booking_rules.instantbookallow)
    await page.select_option("#cancelpolicy", booking_rules.cancelpolicy)
    await page.select_option("#nonrefundfactor", booking_rules.nonrefundfactor)

    await page.fill("#extraperson", pricing_settings.extraPersonPrice)
    await page.select_option("#losprices", pricing_settings.pricingstrategy)
    await page.select_option("#guestinc", pricing_settings.guestsincluded)
    await page.select_option("#datenoprice", pricing_settings.dateswithnoprice)
    await page.select_option("#day2disc", pricing_settings.twodaydiscounts)
    await page.select_option("#day3disc", pricing_settings.threedaydiscounts)
    await page.select_option("#day4disc", pricing_settings.fourdaydiscounts)
    await page.select_option("#day5disc", pricing_settings.fivedaydiscounts)
    await page.select_option("#day6disc", pricing_settings.sixdaydiscounts)
    await page.select_option("#day7disc", pricing_settings.sevendaydiscounts)
    await page.select_option("#day14disc", pricing_settings.fourteendaydiscounts)
    await page.select_option("#day21disc", pricing_settings.twentyonedaydiscounts)
    await page.select_option("#day28disc", pricing_settings.twentyeightdaydiscounts)
    await page.select_option("#maxnotice", pricing_settings.maxdaysinadvance)
    await page.select_option("#leadtime", pricing_settings.advancenotice)
    await page.select_option("#leadrequest", pricing_settings.advancenoticerequest)
    await page.select_option("#bookbeyondd", pricing_settings.earlybirddaystocheckin)
    await page.select_option("#bookbeyondp", pricing_settings.earlybirddiscountpercent)
    await page.select_option("#bookwithind", pricing_settings.lastminutedaystocheckin)
    await page.select_option("#bookwithinp", pricing_settings.lastminutediscountpercent)

    await page.fill("#custom", custom)

    button_elements = await page.query_selector_all('button[name="dosubmit"]')
    for button_element in button_elements:
        await button_element.click()
        await page.wait_for_timeout(3000)
        break
    
    await page.goto('https://beds24.com/control3.php?pagetype=syncroniserairbnbmap')
    await page.wait_for_load_state("load")
    update_button = await page.query_selector('body > div.container-fluid.b24container-fluid > div > main > form:nth-child(9) > div.form-group.row.settingrow3.overflowxvisible > div > div > div.card-body > div.table-responsive.overflowxvisible > table > tbody > tr > td:nth-child(6) > div > button.btn.btn-primary.btn-xs.rounded.mb-1.mr-1.airbnbupdatebtn')
    await update_button.click()
    await page.wait_for_timeout(1000)
    select_all = await page.wait_for_selector('#bookingUpdateSelector > tfoot > tr > td:nth-child(1) > span.fakelink.select-all')
    select_all_button = await page.query_selector('#bookingUpdateSelector > tfoot > tr > td:nth-child(1) > span.fakelink.select-all')
    await select_all_button.click()
    confirm_button =  await page.query_selector('#confirmationmodal > div > div > div.modal-footer > button.btn.btn-primary')
    await confirm_button.click()
    await page.wait_for_timeout(7000)
    
    new_values = await get_airbnb_property_content(session_id, room_id)
    response = {
        "status": "success",
        "new_values": new_values
    }
    
    return response

@app.post("/import_new_property_from_bookingcom", tags=["Booking.com"])
async def import_new_property_from_bookingcom(session_id: str, bookingcom_property_id: str):
    browser, context, page = await get_session_instance(session_id)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserbookingcomxmlimport")
    await page.wait_for_selector("#settingformid > div > div > div > div.card-body > div > div:nth-child(2) > div > input.form-control")
    await page.fill("#settingformid > div > div > div > div.card-body > div > div:nth-child(2) > div > input.form-control", bookingcom_property_id)
    return {"status": "success"}

@app.post("/connect_bookingcom_to_existing_room", tags=["Booking.com"])
async def connect_bookingcom_to_existing_room(session_id: str, beds24_property_id: str):
    browser, context, page = await get_session_instance(session_id)
    await page.goto("https://beds24.com/control3.php?pagetype=syncroniserbookingcomxml")
    await page.wait_for_selector("body > div.container-fluid.b24container-fluid > div > main > form:nth-child(8) > select")
    await page.select_option("body > div.container-fluid.b24container-fluid > div > main > form:nth-child(8) > select", beds24_property_id)
    await page.wait_for_timeout(3000)
    button = await page.wait_for_selector("#booking-widget")
    if button:
        link_element = await page.query_selector("#booking-widget")
        link = await link_element.get_attribute("href")
        return {"status": "success", "link": link}
    else:
        return {"status": "error", "message": "Booking.com connection failed: Given id does not exist or already been connected"}
    
def parse_table(table_html: str) -> dict:
    soup = BeautifulSoup(table_html, "html.parser")
    data = {}
    rows = soup.find_all("tr")[1:]  # Skip header row
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 3:
            key = cols[0].text.strip()
            value = cols[2].text.strip()
            data[key] = value
    return data

@app.get("/get_bookingcom_property_content_extensive", tags=["Booking.com"])
async def get_bookingcom_property_content_extensive(session_id: str, beds24roomId: str = "253855"):
    browser, context, page = await get_session_instance(session_id)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserbookingcomxmlview")
    await page.wait_for_selector("body > div.container-fluid.b24container-fluid > div > main > form > select")
    await page.select_option("body > div.container-fluid.b24container-fluid > div > main > form > select", beds24roomId)
    await page.wait_for_timeout(3000)
    
    elements_selectors = {
        "address": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(15)",
        "property_details": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(19)",
        "rules": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(23)",
        "profile": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(27)",
        "pictures": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(31)",
        "bookingcom_content": "body > div.container-fluid.b24container-fluid > div > main > table:nth-child(36)",
    }
    
    data = {}

    for key, selector in elements_selectors.items():
        element_handle = await page.query_selector(selector)
        if element_handle:
            html_content = await element_handle.inner_html()
            # Parse the HTML table to a dictionary
            table_data = parse_table(html_content)
            data[key] = table_data
    return data

@app.get("/get_bookingcom_property_content", tags=["Booking.com"])
async def get_bookingcom_property_content(session_id: str, beds24roomId: str = "253855"):
    browser, context, page = await get_session_instance(session_id)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserbookingcomxmlprop&id={beds24roomId}")
    await page.wait_for_timeout(3000)
    results = {}

    custom_element = await page.query_selector("#custom")
    custom = await custom_element.input_value()
    results['custom'] = {
        "custom": custom
    }

    pd_number_of_floors_element = await page.query_selector("#qtyfloor option:checked")
    pd_number_of_floors = await pd_number_of_floors_element.inner_text()
    pd_max_lenght_stay_element = await page.query_selector("#maxlos option:checked")
    pd_max_lenght_stay = await pd_max_lenght_stay_element.inner_text()
    results['property_details'] = {
        "number_of_floors": pd_number_of_floors,
        "max_lenght_stay": pd_max_lenght_stay
    }

    pp_host_name_element = await page.query_selector("#hostname")
    pp_host_name = await pp_host_name_element.input_value()
    pp_host_location_element = await page.query_selector("#hostloc option:checked")
    pp_host_location = await pp_host_location_element.inner_text()
    pp_company_element = await page.query_selector("#hosttype option:checked")
    pp_company = await pp_company_element.inner_text()
    pp_built_element = await page.query_selector("#hostbuild")
    pp_built = await pp_built_element.input_value()
    pp_last_renovation_element = await page.query_selector("#hostreno")
    pp_last_renovation = await pp_last_renovation_element.input_value()
    pp_rented_since_element = await page.query_selector("#hostrent")
    pp_rented_since = await pp_rented_since_element.input_value()
    pp_host_pic_url_element = await page.query_selector("#hostpic")
    pp_host_pic = await pp_host_pic_url_element.input_value()
    pp_welcome_msg_element = await page.query_selector("#welcomemsgEN")
    pp_welcome_msg = await pp_welcome_msg_element.input_value()
    pp_owner_listing_story_element = await page.query_selector("#liststoryEN")
    pp_owner_listing_story = await pp_owner_listing_story_element.input_value()
    pp_neighborhood_overview_element = await page.query_selector("#neighborhoodEN")
    pp_neighborhood_overview = await pp_neighborhood_overview_element.input_value()
    pp_local_tips_element = await page.query_selector("#localtipsEN")
    pp_local_tips = await pp_local_tips_element.input_value()
    results['property_profile'] = {
        "host_name": pp_host_name,
        "host_location": pp_host_location,
        "company": pp_company,
        "built": pp_built,
        "last_renovation": pp_last_renovation,
        "rented_since": pp_rented_since,
        "host_pic": pp_host_pic,
        "welcome_msg": pp_welcome_msg,
        "owner_listing_story": pp_owner_listing_story,
        "neighborhood_overview": pp_neighborhood_overview,
        "local_tips": pp_local_tips
    }

    ic_first_name_element = await page.query_selector('input[name="coninvfn"]')
    ic_first_name = await ic_first_name_element.input_value()
    ic_last_name_element = await page.query_selector('input[name="coninvln"]')
    ic_last_name = await ic_last_name_element.input_value()
    ic_email_element = await page.query_selector('input[name="coninvem"]')
    ic_email = await ic_email_element.input_value()
    ic_phone_element = await page.query_selector('input[name="coninvph"]')
    ic_phone = await ic_phone_element.input_value()
    ic_address_element = await page.query_selector('input[name="coninvad"]')
    ic_address = await ic_address_element.input_value()
    ic_city_element = await page.query_selector('input[name="coninvac"]')
    ic_city = await ic_city_element.input_value()
    ic_postcode_element = await page.query_selector('input[name="coninvap"]')
    ic_postcode = await ic_postcode_element.input_value()
    results['invoices_contact'] = {
        'first_name': ic_first_name,
        'last_name': ic_last_name,
        'email': ic_email,
        'phone': ic_phone,
        'address': ic_address,
        'city': ic_city,
        'postcode': ic_postcode
    }

    rc_first_name_element = await page.query_selector('input[name="conresfn"]')
    rc_first_name = await rc_first_name_element.input_value()
    rc_last_name_element = await page.query_selector('input[name="conresln"]')
    rc_last_name = await rc_last_name_element.input_value()
    rc_email_element = await page.query_selector('input[name="conresem"]')
    rc_email = await rc_email_element.input_value()
    rc_phone_element = await page.query_selector('input[name="conresph"]')
    rc_phone = await rc_phone_element.input_value()
    results['reservations_contact'] = {
        'first_name': rc_first_name,
        'last_name': rc_last_name,
        'email': rc_email,
        'phone': rc_phone
    }

    # List to store policies
    checked_policies = []

    # Select all checkbox elements within the policy section
    checkboxes = await page.query_selector_all('.settingrow3 input[type="checkbox"]')

    # Iterate through all checkboxes to find the checked ones
    for checkbox in checkboxes:
        is_checked = await checkbox.is_checked()
        if is_checked:
            # Get the parent label element's text if the checkbox is checked
            parent_label = await checkbox.evaluate_handle("checkbox => checkbox.closest('label')")
            policy_text = await parent_label.inner_text()
            checked_policies.append(policy_text.strip())
    results["policies"] = checked_policies

    return results

@app.patch("/modify_bookingcom_property_content", tags=["Booking.com"])
async def modify_bookingcom_property_content(
    session_id: str,
    room_id: str,
    custom: Custom = Body(None),
    property_details: PropertyDetails = Body(...),
    property_profile: PropertyProfile = Body(...),
    invoices_contact: InvoicesContact = Body(...),
    reservations_contact: ReservationsContact = Body(...),
    policies: Policies = Body(...)
):
    browser, context, page = await get_session_instance(session_id)
    await page.goto(f"https://beds24.com/control3.php?pagetype=syncroniserbookingcomxmlprop&id={room_id}")
    await page.wait_for_timeout(3000)
    await page.fill("#custom", custom.custom)

    await page.select_option("#qtyfloor", property_details.numberoffloors)
    await page.select_option("#maxlos", property_details.maxstay)

    await page.fill("#hostname", property_profile.hostname)
    await page.select_option("#hostloc", property_profile.hostlocation)
    await page.select_option("#hosttype", property_profile.company)
    built_str = property_profile.built.strftime("%A, %d %B, %Y")
    lastrenovated_str = property_profile.lastrenovated.strftime("%A, %d %B, %Y")
    rentedSince_str = property_profile.rentedSince.strftime("%A, %d %B, %Y")
    await page.fill("#hostbuild", built_str)
    await page.fill("#hostreno", lastrenovated_str)
    await page.fill("#hostrent", rentedSince_str)
    await page.fill("#hostpic", property_profile.host_pic_url)
    await page.fill("#welcomemsgEN", property_profile.welcome_msg)
    await page.fill("#liststoryEN", property_profile.owner_listing_story)
    await page.fill("#neighborhoodEN", property_profile.neighborhood_overview)
    await page.fill("#localtipsEN", property_profile.local_tips)

    await page.fill('input[name="coninvfn"]', invoices_contact.firstname)
    await page.fill('input[name="coninvln"]', invoices_contact.lastname)
    await page.fill('input[name="coninvem"]', invoices_contact.email)
    await page.fill('input[name="coninvph"]', invoices_contact.phone)
    await page.fill('input[name="coninvad"]', invoices_contact.address)
    await page.fill('input[name="coninvac"]', invoices_contact.city)
    await page.fill('input[name="coninvap"]', invoices_contact.postcode)

    await page.fill('input[name="conresfn"]', reservations_contact.firstname)
    await page.fill('input[name="conresln"]', reservations_contact.lastname)
    await page.fill('input[name="conresem"]', reservations_contact.email)
    await page.fill('input[name="conresph"]', reservations_contact.phone)

    button_elements = await page.query_selector_all('button[name="dosubmit"]')
    for button_element in button_elements:
        await button_element.click()
        await page.wait_for_timeout(3000)
        break
    
    await page.goto('https://beds24.com/control3.php?pagetype=syncroniserbookingcomxmlsend')
    await page.wait_for_load_state("load")
    update_button = await page.query_selector('#settingformid > div:nth-child(7) > div > div > div.card-body > button.btn.btn-primary.btn-sm.rounded.mr-1.mb-1.float-right')
    await update_button.click()
    await page.wait_for_timeout(3000)
    select_all = await page.wait_for_selector('#bookingUpdateSelector > tfoot > tr > td:nth-child(1) > span.fakelink.select-all')
    select_all_button = await page.query_selector('#bookingUpdateSelector > tfoot > tr > td:nth-child(1) > span.fakelink.select-all')
    await select_all_button.click()
    confirm_button =  await page.query_selector('#confirmationmodal > div > div > div.modal-footer > button.btn.btn-primary')
    await confirm_button.click()
    await page.wait_for_timeout(7000)

    new_values = await get_bookingcom_property_content(session_id, room_id)
    response = {
        "status": "success",
        "new_values": new_values
    }

    return response
    

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to Beds24 API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    # result = asyncio.run(test_session("1e3d5831-a6ae-4bda-88f5-579dea2cec74"))
    # print(result)