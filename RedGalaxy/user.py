import json
import logging
import typing

from . import (
    RedGalaxyException,
    global_instance,
    SessionManager,
    HighGravity,
    User,
    UtilBox,
    UploadMedia,
    Tweet,
)


class TwitterUser:
    def __init__(self, sessionInstance: SessionManager = None):
        """
        Routes relating to getting tweets and users.

        :param sessionInstance:
        """
        if sessionInstance is None:
            sessionInstance = global_instance
        self.session = sessionInstance
        self.gravity = HighGravity(self.session)
        self._routes = []
        self.logging = logging.getLogger("TwitterUser")
        # I'm not sure if we are going to use a custom bearer in the future...
        self.bearer = ""

    getUserFeatures = {
        "responsive_web_twitter_blue_verified_badge_is_enabled": True,
        "verified_phone_label_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_exclude_directive_enabled": False,
        "blue_business_profile_image_shape_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True
    }

    @property
    async def routes(self):
        if not self._routes:
            self._routes = await self.gravity.retrieve_routes()
        return self._routes

    async def get_user(self, username: typing.Union[str, User]):
        """
        Retrieves a User by its username/screenname.
        :param username: The user's username. (e.g. Twitter)
        :return: A User object containing the user's information.
        """
        routes = await self.routes

        if isinstance(username, User):
            username = username.username
            if username is None:
                raise Exception("Malformed User data? Expected username to exist.")

        variables = {
            "screen_name": username,
            "withSafetyModeUserFields": False,
            "withSuperFollowsUserFields": True,
        }
        route = routes.get("UserByScreenName")
        if not route:
            print("Routes list:")
            print(routes)
            raise Exception("Missing routes?")
        url = route[0]

        # Twitter raises an error if we have a missing feature not present in the list.
        # We could just look at the defaults but at the same time,
        # it would be better to not follow blindly.
        set_features = list(self.getUserFeatures.keys())
        for feature in route[1]["featureSwitches"]:
            if feature not in set_features:
                self.logging.warning(
                    f"!! {feature} found in featureSwitch but missing in setFeatures."
                )
        a = await self.session.get(
            url,
            params={
                "variables": json.dumps(variables).replace(" ", ""),
                "features": json.dumps(self.getUserFeatures).replace(" ", ""),
            },
        )
        if a.status_code != 200:
            self.logging.debug(a.content)
            raise RedGalaxyException(f"Expected 200. Got {a.status_code}")
        # print(a)
        data: dict = a.json()
        true_user = data["data"]["user"]["result"]["legacy"]
        true_user["id"] = data["data"]["user"]["result"]["rest_id"]
        return UtilBox.make_user(true_user)

    getUserIdFeatures = {
        "responsive_web_twitter_blue_verified_badge_is_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    }

    async def get_user_by_id(
        self, *users: typing.Union[int, User]
    ) -> typing.Optional[User]:
        user_id_str = []
        for user_id in users:
            uid = None
            if isinstance(user_id, User):
                if user_id.id is None:
                    raise Exception("Malformed User data? Expected username to exist.")
            elif isinstance(user_id, int):
                uid = user_id
            elif isinstance(user_id, str):
                uid = int(user_id)  # Test for an integer.
            else:
                raise Exception(f"{user_id} is not a int or User object.")

            user_id_str.append(str(uid))
        routes = await self.routes

        variables = {
            "userIds": user_id_str,
            "withSafetyModeUserFields": False,
        }

        route = routes.get("UsersByRestIds")
        if not route:
            print("Routes list:")
            print(routes)
            raise Exception("Missing routes?")
        url = route[0]

        # Twitter raises an error if we have a missing feature not present in the list.
        # We could just look at the defaults but at the same time,
        # it would be better to not follow blindly.
        features = self.getUserIdFeatures
        set_features = list(features.keys())
        for feature in route[1]["featureSwitches"]:
            if feature not in set_features:
                self.logging.warning(
                    f"{feature} found in featureSwitch but missing in setFeatures."
                )
        await self.session.guest_token()
        replaced = url.replace("https://api.twitter.com/", "https://twitter.com/i/api/")

        a = await self.session.get(
            replaced,
            params={
                "variables": json.dumps(variables).replace(" ", ""),
                "features": json.dumps(features).replace(" ", ""),
            },
            guest_token=True,
        )

        data: dict = a.json()
        inner_data: dict = data.get("data", {})
        if inner_data:
            if len(user_id_str) == 1:
                inner_data["users"][0]["result"]["legacy"]["id"] = user_id_str[0]
                return UtilBox.make_user(inner_data["users"][0]["result"]["legacy"])
            else:
                users = []
                for idx, user in enumerate(inner_data["users"]):
                    if user:
                        user["result"]["legacy"]["id"] = user_id_str[idx]
                        user = UtilBox.make_user(user["result"]["legacy"])
                        users.append(user)
                    else:
                        users.append(None)
                return users

        return None

    getTweetFeatures = {
        "responsive_web_twitter_blue_verified_badge_is_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": False,
        "verified_phone_label_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "longform_notetweets_consumption_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "vibe_api_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "freedom_of_speech_not_reach_appeal_label_enabled": False,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
        "interactive_text_enabled": True,
        "responsive_web_text_conversations_enabled": False,
        "responsive_web_enhance_cards_enabled": False,
    }

    async def get_tweet(self, tweet_id: int) -> typing.Optional[Tweet]:
        """
        Get a tweet by its snowflake/tweet_id
        :param tweet_id: The tweet ID as an integer. E.G (1564598913784549376).
        :return: a Tweet Object. May return None if the tweet has been deleted or doesn't exist.
        """
        routes = await self.routes

        variables = {
            "focalTweetId": str(tweet_id),
            "with_rux_injections": False,
            "includePromotedContent": True,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": True,
            "withSuperFollowsUserFields": True,
            "withDownvotePerspective": False,
            "withReactionsMetadata": False,
            "withReactionsPerspective": False,
            "withSuperFollowsTweetFields": True,
            "withVoice": True,
            "withV2Timeline": True,
        }

        route = routes.get("TweetDetail")
        if not route:
            print("Routes list:")
            print(routes)
            raise Exception("Missing routes?")
        url = route[0]

        # Twitter raises an error if we have a missing feature not present in the list.
        # We could just look at the defaults but at the same time,
        # it would be better to not follow blindly.
        features = self.getTweetFeatures
        set_features = list(features.keys())
        for feature in route[1]["featureSwitches"]:
            if feature not in set_features:
                self.logging.warning(
                    f"{feature} found in featureSwitch but missing in setFeatures."
                )
        await self.session.ensure_token()
        replaced = url.replace("https://api.twitter.com/", "https://twitter.com/i/api/")
        a = await self.session.get(
            replaced,
            params={
                "variables": json.dumps(variables).replace(" ", ""),
                "features": json.dumps(features).replace(" ", ""),
            },
            guest_token=True,
        )
        data: dict = a.json()
        inner_data: dict = data.get("data", {})
        for instruction in inner_data["threaded_conversation_with_injections_v2"].get(
            "instructions"
        ):
            type_instruct = instruction["type"]
            if type_instruct == "TimelineAddEntries":
                for entry in instruction["entries"]:
                    if entry["entryId"].startswith("tweet-"):
                        base_tweet = entry["content"]["itemContent"]["tweet_results"][
                            "result"
                        ]
                        return UtilBox.common_tweet(base_tweet, None)
