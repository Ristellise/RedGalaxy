import webbrowser

import aiohttp

from . import global_instance, SessionManager, XAuthException


class xAuth:

    def __init__(self, username, password, session: SessionManager = global_instance):
        self.username = username
        self.password = password
        self.session = session
        self.cache = {}

    async def retrieve_credentials(self):
        """
        Retrieve the user credentials.
        This involves logging in the user. So use it with caution.
        :return: None or a oauth token.
        """

        await self.session.guest_token()

        # Authorization code adapted from oxtwitter.cpp on github:
        # (https://github.com/SimoDax/Bird10/blob/master/Bird10HeadlessService/src/o2/oxtwitter.cpp)
        # This appears to be an older/modified version of o2. So I'm not too sure of the license

        # It appears it's the same as what twitter uses.
        data = {
            "x_auth_identifier": self.username,
            "x_auth_password": self.password,
            "send_error_codes": "true",
            "x_auth_login_challenge": 1,
            "x_auth_login_verification": 1,
            "x_auth_country_code": "US",
            "ui_metrics": ""
        }

        if self.session.is_bearer:
            raise XAuthException("Bearer Only token is not allowed. "
                                 "Route only available to consumer based access.")



        response = await self.session.post("https://api.twitter.com/auth/1/xauth_password.json",
                                           data=aiohttp.FormData(data),
                                           mixin_headers={"Content-Type": "application/x-www-form-urlencoded"},
                                           guest_token=True)
        if response.status == 500:
            print(await response.text())
            raise XAuthException(f"Expected 200. Got {response.status}.\n"
                                 f"You may have attempted to login but cancelled the procedure. "
                                 f"Wait a while before retrying.")
        if response.status == 401:
            j_context = await response.json()
            raise XAuthException(f"Expected 200. Got {response.status}.\n"
                                 f"Timed out for too many login attempts. Try again an hour.\n"
                                 f"{j_context.get('errors')[0]['message']}")
        if response.status != 200:
            print(await response.text())
            raise XAuthException(f"Expected 200. Got {response.status}")
        response_json: dict = await response.json()
        print(response_json)
        url = response_json.get("login_verification_request_url")
        if url:
            print("2FA Enabled. You will need to enter your token in a browser.")
            print(f"If there isn't a browser on the current machine, "
                  f"you can use the following link: {url}")
            webbrowser.open(url)
            print(
                "Once done, press enter to resume the login process."
                "Type \"cancel\" to cancel the abort the process.")
            while True:
                terminate = input(">:")
                if terminate.lower() == "cancel":
                    print("Terminating the process...")
                    return None
                url = "https://api.twitter.com/oauth/access_token"
                data = {
                    "login_verification_user_id": response_json.get("login_verification_user_id"),
                    "login_verification_request_id": response_json.get("login_verification_request_id"),
                    "send_error_codes": "true",
                    "x_auth_login_challenge": 1,
                    "x_auth_login_verification": 1,
                    "x_auth_mode": "client_auth",
                }
                response = await self.session.post(url,
                                                   data=data,
                                                   mixin_headers={"Content-Type": "application/x-www-form-urlencoded"},
                                                   guest_token=True)
                if response.status != 200:
                    print(await response.text())
                    raise Exception(f"Expected 200. Got {response.status}")
                response_json: dict = await response.json()
        token = response_json.get("oauth_token", None)
        secret = response_json.get("oauth_token_secret", None)
        return token, secret
