from playwright.sync_api import sync_playwright


def inject_cookies(context, cookies):
    for cookie in cookies:
        context.add_cookies([cookie])
    return context