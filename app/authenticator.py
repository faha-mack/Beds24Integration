# import asyncio
import random
# import time
import traceback
# import bezier
import imapclient
# import numpy as np
import pyzmail
from datetime import datetime, timedelta, timezone
import re
from dotenv import load_dotenv
# import os

load_dotenv()

def get_cookies_from_page(page):
    cookies = page.context.cookies()
    return cookies

# async def human_like_delay():
#     await asyncio.sleep(random.uniform(0.1, 0.8))

# def get_bezier_curve(start, end, control_points=2):
#     points = [start]
#     # Generate random control points between start and end
#     for _ in range(control_points):
#         points.append([
#             random.randint(int(min(start[0], end[0])), int(max(start[0], end[0]))),
#             random.randint(int(min(start[1], end[1])), int(max(start[1], end[1])))
#         ])
#     points.append(end)
#     nodes = np.asfortranarray(points).T
#     return bezier.Curve(nodes, degree=control_points + 1)

async def move_mouse_naturally(page, frame, target_selector):
    current_pos = await page.evaluate("""() => { 
        return {x: window.mouseX || 0, y: window.mouseY || 0}
    }""")
    target_pos = await frame.evaluate(f"""(selector) => {{
        const elem = document.querySelector(selector);
        const rect = elem.getBoundingClientRect();
        return {{x: rect.x + rect.width/2, y: rect.y + rect.height/2}}
    }}""", target_selector)
    frame_rect = await frame.evaluate("""() => {
        const rect = document.body.getBoundingClientRect();
        return {x: rect.x, y: rect.y}
    }""")
    target_pos['x'] += frame_rect['x']
    target_pos['y'] += frame_rect['y']
    curve = get_bezier_curve(
        [current_pos['x'], current_pos['y']],
        [target_pos['x'], target_pos['y']]
    )
    steps = 25
    for i in range(steps):
        t = i / (steps - 1)
        point = curve.evaluate(t).flatten()
        jitter_x = random.uniform(-2, 2)
        jitter_y = random.uniform(-2, 2)
        
        await page.mouse.move(
            point[0] + jitter_x,
            point[1] + jitter_y
        )
        await human_like_delay()

async def check_gmail(username, app_password):
    dt = datetime.now()
    try:
        # Connect to the Gmail IMAP server
        server = imapclient.IMAPClient('imap.gmail.com', ssl=True)
        server.login(username, app_password)
        
        # Select the inbox
        server.select_folder('INBOX')
        
        # Search for the most recent 50 emails (both seen and unseen)
        messages = server.search(['ALL'])
        messages = messages[-50:]  # Limit to the most recent 50 emails
        
        # Fetch the email details
        response = server.fetch(messages, ['BODY.PEEK[]', 'FLAGS'])
        
        emails = []
        for msgid, data in response.items():
            email_message = pyzmail.PyzMessage.factory(data[b'BODY[]'])
            sender = email_message.get_address('from')[1]
            if sender in ['ticket@beds24.com', 'support@beds24.com']:
                body = None
                if email_message.text_part:
                    body = email_message.text_part.get_payload().decode(email_message.text_part.charset)
                elif email_message.html_part:
                    body = email_message.html_part.get_payload().decode(email_message.html_part.charset)
                
                emails.append({
                    'subject': email_message.get_subject(),
                    'from': sender,
                    'to': email_message.get_address('to'),
                    'date': email_message.get('date'),
                    'body': body
                })
        # Filter emails received within the past 15 minutes
        philippine_timezone = timezone(timedelta(hours=8))
        now = datetime.now(philippine_timezone)
        twenty_four_hours_ago = now - timedelta(minutes=5)
        recent_emails = [email for email in emails if datetime.strptime(email['date'], '%a, %d %b %Y %H:%M:%S %z').astimezone(philippine_timezone) > twenty_four_hours_ago]
        if not recent_emails or len(recent_emails) == 0:
            return {"status": "error", "message": "No recent emails found."}
        # Sort emails by date in descending order
        recent_emails.sort(key=lambda x: datetime.strptime(x['date'], '%a, %d %b %Y %H:%M:%S %z'), reverse=True)
        
        # Get the most recent email
        most_recent_email = recent_emails[0] if recent_emails else None

        login_code = None
        if most_recent_email and most_recent_email['body']:
            if most_recent_email['from'] == 'support@beds24.com':
                match = re.search(r'Your login code for account \S+ is (\d+)', most_recent_email['body'])
                login_code = match.group(1) if match else None
            elif most_recent_email['from'] == 'ticket@beds24.com':
                match = re.search(r'https://beds24\.com/control2\.php\?logincode=\w+', most_recent_email['body'])
                login_code = match.group(0) if match else None
                

        # Logout from the server
        server.logout()
        
        if most_recent_email:
            return {"status":"success", "code": login_code, "sender": most_recent_email['from']}
        else:
            return {"status":"error", "code": None, "sender": None}
    except Exception as e:
        traceback.print_exc()
        print("An error occurred:", e)
        return {"status": "error", "message": str(e)}
