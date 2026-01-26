import os
import httpx
from typing import Optional, List
from datetime import datetime, timedelta
from msal import ConfidentialClientApplication

MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:5173/auth/callback")

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

SCOPES = [
    "User.Read",
    "Calendars.ReadWrite",
    "Mail.Send",
    "Sites.ReadWrite.All",
    "offline_access"
]


def get_msal_app() -> ConfidentialClientApplication:
    authority = f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}"
    return ConfidentialClientApplication(
        MICROSOFT_CLIENT_ID,
        authority=authority,
        client_credential=MICROSOFT_CLIENT_SECRET
    )


def get_auth_url(redirect_uri: str) -> str:
    app = get_msal_app()
    return app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )


async def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    app = get_msal_app()
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    return result


async def refresh_access_token(refresh_token: str) -> dict:
    app = get_msal_app()
    result = app.acquire_token_by_refresh_token(
        refresh_token,
        scopes=SCOPES
    )
    return result


async def get_user_profile(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GRAPH_API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json()


async def get_calendar_events(
    access_token: str,
    calendar_email: str,
    start_datetime: datetime,
    end_datetime: datetime
) -> List[dict]:
    async with httpx.AsyncClient() as client:
        start_str = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        
        url = f"{GRAPH_API_BASE}/users/{calendar_email}/calendar/calendarView"
        params = {
            "startDateTime": start_str,
            "endDateTime": end_str,
            "$select": "subject,start,end,showAs"
        }
        
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("value", [])
        return []


async def create_calendar_event(
    access_token: str,
    calendar_email: str,
    subject: str,
    start_datetime: datetime,
    end_datetime: datetime,
    body: str = "",
    attendees: List[str] = None
) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        event_data = {
            "subject": subject,
            "start": {
                "dateTime": start_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            },
            "body": {
                "contentType": "HTML",
                "content": body
            }
        }
        
        if attendees:
            event_data["attendees"] = [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendees
            ]
        
        response = await client.post(
            f"{GRAPH_API_BASE}/users/{calendar_email}/calendar/events",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=event_data
        )
        
        if response.status_code == 201:
            return response.json()
        return None


async def update_calendar_event(
    access_token: str,
    calendar_email: str,
    event_id: str,
    subject: str = None,
    start_datetime: datetime = None,
    end_datetime: datetime = None,
    body: str = None
) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        event_data = {}
        
        if subject:
            event_data["subject"] = subject
        if start_datetime:
            event_data["start"] = {
                "dateTime": start_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            }
        if end_datetime:
            event_data["end"] = {
                "dateTime": end_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": "UTC"
            }
        if body:
            event_data["body"] = {
                "contentType": "HTML",
                "content": body
            }
        
        response = await client.patch(
            f"{GRAPH_API_BASE}/users/{calendar_email}/calendar/events/{event_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=event_data
        )
        
        if response.status_code == 200:
            return response.json()
        return None


async def delete_calendar_event(
    access_token: str,
    calendar_email: str,
    event_id: str
) -> bool:
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{GRAPH_API_BASE}/users/{calendar_email}/calendar/events/{event_id}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        return response.status_code == 204


async def send_email(
    access_token: str,
    to_emails: List[str],
    subject: str,
    body: str,
    is_html: bool = True
) -> bool:
    async with httpx.AsyncClient() as client:
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if is_html else "Text",
                    "content": body
                },
                "toRecipients": [
                    {"emailAddress": {"address": email}}
                    for email in to_emails
                ]
            },
            "saveToSentItems": True
        }
        
        response = await client.post(
            f"{GRAPH_API_BASE}/me/sendMail",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=email_data
        )
        
        return response.status_code == 202


async def get_sharepoint_site(access_token: str, site_name: str) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GRAPH_API_BASE}/sites?search={site_name}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            sites = data.get("value", [])
            if sites:
                return sites[0]
        return None


async def create_sharepoint_list_item(
    access_token: str,
    site_id: str,
    list_id: str,
    fields: dict
) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GRAPH_API_BASE}/sites/{site_id}/lists/{list_id}/items",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={"fields": fields}
        )
        
        if response.status_code == 201:
            return response.json()
        return None


async def update_sharepoint_list_item(
    access_token: str,
    site_id: str,
    list_id: str,
    item_id: str,
    fields: dict
) -> Optional[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{GRAPH_API_BASE}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=fields
        )
        
        if response.status_code == 200:
            return response.json()
        return None


async def get_sharepoint_list_items(
    access_token: str,
    site_id: str,
    list_id: str,
    filter_query: str = None
) -> List[dict]:
    async with httpx.AsyncClient() as client:
        url = f"{GRAPH_API_BASE}/sites/{site_id}/lists/{list_id}/items?expand=fields"
        if filter_query:
            url += f"&$filter={filter_query}"
        
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("value", [])
        return []
