"""Pokemon Showdown authentication via Playwright headless browser."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from smogon_vgc_mcp.fetcher.replay_list import _strip_dispatch_prefix
from smogon_vgc_mcp.logging import get_logger

logger = get_logger(__name__)

SHOWDOWN_PLAY_URL = "https://play.pokemonshowdown.com/"
SHOWDOWN_CHECK_LOGIN_URL = "https://replay.pokemonshowdown.com/api/replays/check-login"


class AuthenticationError(Exception):
    """Raised when Showdown authentication fails."""


@dataclass
class ShowdownSession:
    sid_cookie: str
    username: str

    def cookie_header(self) -> str:
        return f"sid={self.sid_cookie}"


async def authenticate_showdown(username: str, password: str) -> ShowdownSession:
    """Log into Pokemon Showdown via headless browser and extract the sid cookie.

    Requires the `playwright` package (install with `pip install smogon-vgc-mcp[browser]`).
    Credentials are used only within this function and never logged or stored.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ImportError(
            "playwright is required for private replay access. "
            "Install with: pip install smogon-vgc-mcp[browser] && playwright install chromium"
        )

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(SHOWDOWN_PLAY_URL)
            await page.wait_for_selector("button[name='login']", timeout=15000)
            await page.click("button[name='login']")

            await page.wait_for_selector("input[name='username']", timeout=10000)
            await page.fill("input[name='username']", username)
            await page.press("input[name='username']", "Enter")

            try:
                await page.wait_for_selector(
                    "input[name='password']", timeout=5000
                )
                await page.fill("input[name='password']", password)
                await page.click("button[type='submit']")
            except Exception:
                pass

            await page.wait_for_function(
                "() => document.cookie.includes('sid=')",
                timeout=15000,
            )

            cookies = await context.cookies()
            sid_cookie = None
            for cookie in cookies:
                if cookie["name"] == "sid":
                    sid_cookie = cookie["value"]
                    break

            if not sid_cookie:
                raise AuthenticationError("Login succeeded but sid cookie not found")

            verified_user = await verify_session(sid_cookie)
            if not verified_user:
                raise AuthenticationError("Session verification failed after login")

            return ShowdownSession(sid_cookie=sid_cookie, username=verified_user)

        except AuthenticationError:
            raise
        except ImportError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Showdown login failed: {e}") from e
        finally:
            if browser:
                await browser.close()


async def verify_session(sid_cookie: str) -> str | None:
    """Verify a Showdown session by calling check-login.

    Returns the userid if valid, None if the session is invalid/expired.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                SHOWDOWN_CHECK_LOGIN_URL,
                headers={"Cookie": f"sid={sid_cookie}"},
            )
            response.raise_for_status()
            text = _strip_dispatch_prefix(response.text)

            if not text or text.startswith("guest"):
                return None

            userid = text.split(",")[0] if "," in text else text.strip()
            if not userid or userid == "guest":
                return None

            return userid
        except httpx.HTTPError:
            return None
