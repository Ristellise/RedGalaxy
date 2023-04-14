import asyncio
import base64
import enum
import json
import logging
import pathlib
import random
import time
from getpass import getpass

import httpx
from bs4 import BeautifulSoup

from .exceptions import SessionManagerException, XAuthException

try:
    import oauthlib
    import oauthlib.oauth1
except ImportError:
    oauthlib = None

# Nitter's Bear token. A bit old, but it works as of 03/02/2023
_DEFAULT_BEARER = "AAAAAAAAAAAAAAAAAAAAAPYXBAAAAAAACLXUNDekMxqa8h%2F40K4moUkGsoc%3DTYfbDKbT3jJPCEVnMYqilB28NHfOPqkca3qaAxGfsyKCs0wRbw"


class SessionMode(enum.IntEnum):
    BEARER = 1
    CONSUMER = 2


class TokenManager:
    def __init__(self, cache_folder: pathlib.Path = pathlib.Path.home()):
        if cache_folder is not None:
            self.cacheFile = cache_folder.resolve() / ".redgalaxy" / "guest-token.json"
        else:
            self.cacheFile = None
        self._token = None
        self._setTime = 0

    def read(self):
        if self.cacheFile and self.cacheFile.exists():
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
        if self.cacheFile:
            self.cacheFile.parent.mkdir(parents=True, exist_ok=True)
            self.cacheFile.write_text(
                json.dumps({"tk": self._token, "st": self._setTime})
            )


class SessionManager:
    def __init__(
        self,
        mode: SessionMode,
        key=None,
        secret=None,
        token_manager: TokenManager = None,
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
        self.tokenManager = TokenManager() if not token_manager else token_manager
        self._session = httpx.AsyncClient()
        self.logging = logging.getLogger("SessionManager")

    async def do_headers(self, referer, set_auth=True):
        """
        Sets twitter headers for use.
        :param referer: The url to use as referer
        :param set_auth: Sets the authorization header.
        :return:
        """
        self.logging.debug(f"Writing Headers, set_auth: {set_auth}, referer: {referer}")

        if self.auth is None and not self.is_bearer:
            raise NotImplementedError(
                "Non-Bearer tokens are currently not working at the moment!"
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
        """
        Ensures that the guest token has been set and can be used.
        :param retry: Retry to get the token. Even if the token manager has a token stored previously.
        :return:
        """
        if not self.tokenManager.token or retry:
            response = await self._session.post(
                "https://api.twitter.com/1.1/guest/activate.json",
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
        """Sends a http request.

        This wraps around httpx session and provides some additional features tat can be used.

        :param method: The method to use. GET, POST, PUT and related requests are accepted.
        :param url: The url.
        :param kwargs: Additional keyword arguments to pass to the request.
        Additionally, "mixin_headers" can be used to "mixin" additional headers.
        :return:
        """
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
        """
        Retrieves the access token.
        :return:
        """
        if self.access_token:
            return self.access_token
        elif self.consumer[0] and self.consumer[1]:
            await self.do_headers("https://twitter.com/")
            encode = base64.standard_b64encode(
                f"{self.consumer[0]}:{self.consumer[1]}".encode()
            )
            self.auth = f"Basic {encode.decode()}"
            post_token = await self.post(
                "https://api.twitter.com/oauth2/token?grant_type=client_credentials",
                skip_access_check=True,
            )
            if post_token.status_code == 200:
                code: dict = await post_token.json()
                self.access_token = code["access_token"]
                self.auth = f"Bearer {self.access_token}"
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

    async def xlogin(self, username, password):
        """
        Logins in via xauth.
        This only works for PIN based "Official" twitter keys.
        2FA/Code Auth also works. But it can be finicky/untested.

        :param username: The username
        :param password: Password for the said user.
        :return:
        """
        if self.is_bearer:
            raise SessionManagerException(
                "login works only for CONSUMER based sessions. "
                "(global_instance is not a Consumer based session.)"
            )
        if not oauthlib:
            raise SessionManagerException(
                "oauthlib is required for the login part of the process."
            )
        await self.ensure_token()  # Ensure we have guest token

        auth = await self.post(
            "https://api.twitter.com/auth/1/xauth_password.json",
            params={
                "x_auth_identifier": username,
                "x_auth_password": password,
                "send_error_codes": "true",
                "x_auth_login_challenge": "1",
                "x_auth_login_verification": "1",
                "x_auth_country_code": "US",
                "ui_metrics": "",
            },
        )
        if auth.status_code != 200:
            print(auth.text)
            raise XAuthException(f"Expected 200. Got {auth.status_code}")
        json_data = auth.json()
        if "login_verification_request_url" in json_data.keys():
            print("Challenge required.")
            await self._try_challenge(json_data)

    async def _try_challenge(self, xauth_dict: dict):
        challenge_url = xauth_dict["login_verification_request_url"]
        request_id = xauth_dict["login_verification_request_id"]
        r = await self.session.get(challenge_url)
        soup = BeautifulSoup(r.content, "lxml")
        authenticity_token = soup.select_one("input[name=authenticity_token]")["value"]
        challenge_id = soup.select_one("input[name=challenge_id]")["value"]
        user_id = soup.select_one("input[name=user_id]")["value"]
        challenge_type = soup.select_one("input[name=challenge_type]")["value"]
        print(f"Code Input required for {challenge_type}. Please check your device.")
        print(
            "Entering an empty/invalid code may prevent you from logging in from other devices!\n"
        )

        async def get_challange_token():
            print("Attempting to get tokens.")
            if not oauthlib:
                raise SessionManagerException(
                    "oauthlib not present. This should not trigger."
                )
            cli = oauthlib.oauth1.Client(self.consumer[0], self.consumer[1])
            params = {
                "login_verification_request_id": request_id,
                "login_verification_user_id": user_id,
                "send_error_codes": "true",
                "x_auth_login_challenge": "1",
                "x_auth_login_verification": "1",
                "x_auth_mode": "client_auth",
            }

            uri, headers, body = cli.sign(
                "https://api.twitter.com/oauth/access_token", "POST", params
            )
            response = await self.request("POST", uri, mixin_headers=headers, data=body)

        while True:
            code = getpass("Code >: ")
            print("Attempting code...")

            data = {
                "authenticity_token": authenticity_token,
                "challenge_id": challenge_id,
                "user_id": user_id,
                "challenge_type": challenge_type,
                "platform": "mobile",
                "redirect_after_login": "",
                "remember_me": "true",
                "challenge_response": code,
            }
            r = await self.session.post(
                "https://twitter.com/account/login_challenge", data=data
            )
            if r.status_code == 200:
                print("Challenge Solved.")
                return await get_challange_token()
            else:
                print("Challenge Solved.")

    def __del__(self):
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.session.aclose())
        except Exception:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.session.aclose())


global_instance = SessionManager(SessionMode.BEARER, _DEFAULT_BEARER)
