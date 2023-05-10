import asyncio
import base64
import enum
import json
import logging
import pathlib
import random

import httpx
import time

from .exceptions import RedGalaxyException, SessionManagerException

# Nitter's Bear token. A bit old, but it works as of 03/02/2023
_DEFAULT_BEARER = "AAAAAAAAAAAAAAAAAAAAAPYXBAAAAAAACLXUNDekMxqa8h%2F40K4moUkGsoc%3DTYfbDKbT3jJPCEVnMYqilB28NHfOPqkca3qaAxGfsyKCs0wRbw"
# _DEFAULT_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
# _DEFAULT_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


class SessionMode(enum.IntEnum):
    BEARER = 1
    CONSUMER = 2


class TokenManager:
    def __init__(self, cacheFolder: pathlib.Path = pathlib.Path.home()):
        self.cacheFile = cacheFolder.resolve() / ".redgalaxy" / "guest-token.json"
        self._token = None
        self._setTime = 0

    def read(self):
        if self.cacheFile.exists():
            cached = json.loads(self.cacheFile.read_text(encoding="utf-8"))
            self._token = cached.get("tk")
            self._setTime = cached.get("st", 0)

    @property
    def token(self):
        if self._setTime < time.time() - 10800:
            # Expired, but don't unset.
            return None
        if not self._token:
            self.read()
        return self._token

    @token.setter
    def token(self, value):
        self._token = value
        self._setTime = time.time()
        self.cacheFile.parent.mkdir(parents=True, exist_ok=True)
        self.cacheFile.write_text(json.dumps({"tk": self._token, "st": self._setTime}))


class SessionManager:
    def __init__(
        self,
        mode: SessionMode,
        key=None,
        secret=None,
        tokenManager: TokenManager = None,
    ):
        if mode == SessionMode.BEARER:
            self.consumer = None
            self.access_token = key
            self.is_bearer = True
            self.auth = f"Bearer {self.access_token}"
        elif mode == SessionMode.CONSUMER:
            self.consumer = [key, secret]
            self.access_token = None
            self.is_bearer = False
            self.auth = None
        else:
            raise SessionManagerException("Mode undefined. Either: BEARER or CONSUMER.")
        self.headers = None
        self.tokenManager = TokenManager() if not tokenManager else tokenManager
        self._session = httpx.AsyncClient()
        self.logging = logging.getLogger("SessionManager")

    async def do_headers(self, referer, set_auth=True):
        self.logging.debug(f"Writing Headers, set_auth: {set_auth}, referer: {referer}")

        if self.auth is None and not self.is_bearer:
            raise RedGalaxyException(
                "Non-Bearer tokens needs to be initalized seperately before calling any function."
            )
            # await self.get_access_token()
        self.headers = {
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/109.0.0.0 Safari/537.{random.randint(0, 99)}",
            "Authorization": self.auth,
            "Referer": referer,
            "Accept-Language": "en-US,en;q=0.5",
        }
        if not set_auth:
            del self.headers["Authorization"]

        if self._session:
            self._session.headers.clear()
            self._session.headers.update(self.headers)

        # I'm personally not sure, 06/05/23 twitter seems to break if you try to get with bearer token?
        if set_auth:
            # Ensure we have Guest Token
            await self.ensure_token()
            self.headers = {
                **self.headers,
                "x-guest-token": self.tokenManager.token,
                # "x-twitter-active-user": "yes",
            }
        # self._session.cookies.clear()
        self._session.cookies.set("gt", self.tokenManager.token, domain=".twitter.com")
        self._session.headers.update(self.headers)
        return self.headers

    async def ensure_token(self, retry=False):  # Taken from snscrape
        if not self.tokenManager.token or retry:
            self.logging.debug("Requesting guest token")
            uri = "https://api.twitter.com/1.1/guest/activate.json"
            self.logging.debug(f"{self.headers}, {uri}")
            response = await self._session.post(
                uri,
                data=b"",
                headers=self.headers,
            )
            if response.status_code == 200:
                self.tokenManager.token = json.loads(response.text)["guest_token"]
            else:
                response.raise_for_status()  # Oh no
        return self.tokenManager.token

    @property
    def session(self):
        if self.headers:
            self._session.headers.update(self.headers)
        return self._session

    async def get(
        self,
        url,
        referer="https://twitter.com/",
        set_auth=True,
        **kwargs,
    ):

        await self.get_access_token()
        await self.do_headers(referer, set_auth)
        return await self.request("GET", url, **kwargs)

    async def request(self, method, url, **kwargs):
        session = self.session
        headers = {**session.headers, **kwargs.get("mixin_headers", {})}
        if kwargs.get("mixin_headers", {}):
            del kwargs["mixin_headers"]
        kwargs["headers"] = headers
        self.logging.debug(f"{method.title()} {url} headers: {headers}, {kwargs}")
        resp = await session.request(method, url, **kwargs)
        return resp

    async def post(
        self,
        url,
        referer="https://twitter.com/",
        set_auth=True,
        skip_access_check=False,
        **kwargs,
    ):
        if not skip_access_check:
            await self.get_access_token()
        await self.do_headers(referer, set_auth)
        return await self.request("POST", url, **kwargs)

    async def get_access_token(self):
        if self.access_token:
            return self.access_token
        elif self.consumer[0] and self.consumer[1]:
            # await self.do_headers("https://twitter.com/")
            encode = base64.standard_b64encode(
                f"{self.consumer[0]}:{self.consumer[1]}".encode()
            )
            self.auth = f"Basic {encode.decode()}"
            headers = {
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/109.0.0.0 Safari/537.{random.randint(0, 99)}",
                "Authorization": self.auth,
                "Referer": "https://twitter.com/",
                "Accept-Language": "en-US,en;q=0.5",
            }
            post_token = await self.session.post(
                "https://api.twitter.com/oauth2/token?grant_type=client_credentials",
                headers=headers,
            )
            if post_token.status_code == 200:
                code: dict = post_token.json()
                self.access_token = code["access_token"]
                self.auth = f"Bearer {self.access_token}"
                self.logging.info(f"Success. Set bearer to: {self.auth}")
            else:
                print("Err:", post_token.text)
                raise SessionManagerException(
                    f"Expected 200. Got {post_token.status_code}"
                )
        else:
            raise SessionManagerException(
                "Missing Credentials for either access/bearer token and "
                "consumer key+secret."
            )

    def __del__(self):
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.session.aclose())
        except Exception:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.session.aclose())


global_instance = SessionManager(SessionMode.BEARER, _DEFAULT_BEARER)
