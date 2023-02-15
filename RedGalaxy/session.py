
import asyncio
import base64
import enum
import logging
import random
import typing

import aiohttp

from . import SessionManagerException

# Nitter's Bear token. A bit old but it works as of 03/02/2023
_DEFAULT_BEARER = "AAAAAAAAAAAAAAAAAAAAAPYXBAAAAAAACLXUNDekMxqa8h%2F40K4moUkGsoc%3DTYfbDKbT3jJPCEVnMYqilB28NHfOPqkca3qaAxGfsyKCs0wRbw"

class SessionMode(enum.IntEnum):
    BEARER = 1
    CONSUMER = 2

class SessionManager:

    def __init__(self, mode: SessionMode, key=None, secret=None):
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
        self._session: typing.Optional[aiohttp.ClientSession] = None
        self.logging = logging.getLogger("SessionManager")

        self.gt0 = None

    def do_headers(self, referer, set_auth=True, guest_token=False):
        self.logging.debug(f"Writing Headers, set_auth: {set_auth}, referer: {referer}")
        self.headers = {
            "User-Agent": f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          f'Chrome/109.0.0.0 Safari/537.{random.randint(0, 99)}',
            'Authorization': self.auth,
            'Referer': referer,
            'Accept-Language': 'en-US,en;q=0.5',
        }
        if not set_auth:
            del self.headers['Authorization']
        if self._session:
            self._session.headers.update(self.headers)
        if guest_token and self.gt0:
            self.headers = {**self.headers,
                            "x-guest-token": self.gt0,
                            "x-twitter-active-user": "yes"}
            self._session.cookie_jar.clear_domain("twitter.com")
            self._session.cookie_jar.update_cookies({"gt": self.gt0})
            self._session.headers.update(self.headers)
        return self.headers

    @property
    def session(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
        if self.headers:
            self._session.headers.update(self.headers)
        return self._session

    async def get(self, url, referer="https://twitter.com/", set_auth=True, guest_token=False, **kwargs):
        await self.get_access_token()
        self.do_headers(referer, set_auth, guest_token)
        return await self.request("GET", url, **kwargs)

    async def request(self, method, url, **kwargs):
        session = self.session
        headers = {**session.headers,
                   **kwargs.get("mixin_headers", {})}
        if kwargs.get("mixin_headers", {}):
            del kwargs["mixin_headers"]
        kwargs["headers"] = headers
        self.logging.debug(f"{method.title()} {url} headers: {headers}, {kwargs}")
        resp = await session.request(method, url, **kwargs)
        return resp

    async def post(self, url, referer="https://twitter.com/", set_auth=True, guest_token=False, skip_access_check=False, **kwargs):
        if not skip_access_check:
            await self.get_access_token()
        self.do_headers(referer, set_auth, guest_token)
        return await self.request("POST", url, **kwargs)

    async def guest_token(self):
        self.do_headers("https://twitter.com/")
        post_token = await self.post('https://api.twitter.com/1.1/guest/activate.json', data=b'')
        tk = await post_token.json()
        self.gt0 = tk['guest_token']

    async def get_access_token(self):
        if self.access_token:
            return self.access_token
        elif self.consumer[0] and self.consumer[1]:

            self.do_headers("https://twitter.com/")
            encode = base64.standard_b64encode(f"{self.consumer[0]}:{self.consumer[1]}".encode())
            self.auth = f"Basic {encode.decode()}"
            post_token = await self.post('https://api.twitter.com/oauth2/token?grant_type=client_credentials', skip_access_check=True)
            if post_token.status == 200:
                code: dict = await post_token.json()
                self.access_token = code["access_token"]
                self.auth = f"Bearer {self.access_token}"
            else:
                print("Err:", await post_token.text())
                raise SessionManagerException(f"Expected 200. Got {post_token.status}")
        else:
            raise SessionManagerException("Missing Credentials for either access/bearer token and "
                                          "consumer key+secret.")

    def __del__(self):
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.session.close())
        except Exception:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.session.close())


global_instance = SessionManager(SessionMode.BEARER, _DEFAULT_BEARER)
