# Nitter's Bear token. A bit old but it works as of 03/02/2023
import http.cookies
import logging
import random
import re
import typing
from contextlib import contextmanager

import aiohttp

_DEFAULT_BEARER = "AAAAAAAAAAAAAAAAAAAAAPYXBAAAAAAACLXUNDekMxqa8h%2F40K4moUkGsoc%3DTYfbDKbT3jJPCEVnMYqilB28NHfOPqkca3qaAxGfsyKCs0wRbw"


class SessionManager:

    def __init__(self, bearer_token):
        self.bearer_token = bearer_token
        self.headers = None
        self._session: typing.Optional[aiohttp.ClientSession] = None
        self.logging = logging.getLogger("SessionManager")
        self.gt0 = None

    def do_headers(self, referer, set_auth=True, guest_token=False):
        self.logging.debug(f"Writing Headers, set_auth: {set_auth}, referer: {referer}")
        self.headers = {
            "User-Agent": f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          f'Chrome/109.0.0.0 Safari/537.{random.randint(0, 99)}',
            'Authorization': f"Bearer {self.bearer_token}",
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

    async def get(self, url, *args, **kwargs):
        self.logging.debug(f"Get request: {url}, {args}, {kwargs}")
        resp = await self.session.get(url, *args, **kwargs)
        # print(self.session.headers)
        return resp

    async def post(self, url, *args, **kwargs):
        self.logging.debug(f"Post request: {url}, {args}, {kwargs}")
        resp = await self.session.post(url, *args, **kwargs)
        return resp

    guest = re.compile(
        r'document\.cookie = decodeURIComponent\("gt=(\d+); Max-Age=10800; Domain=\.twitter\.com; Path=/; Secure"\);')

    async def guest_token(self):
        self.do_headers("https://twitter.com/")
        post_token = await self.post('https://api.twitter.com/1.1/guest/activate.json',
                                     data=b'', headers=self.do_headers("https://twitter.com/"))
        tk = await post_token.json()
        self.gt0 = tk['guest_token']


global_instance = SessionManager(_DEFAULT_BEARER)
