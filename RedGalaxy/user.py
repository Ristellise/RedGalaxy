import json
import logging

from . import global_instance, SessionManager, HighGravity, User, UtilBox


class TwitterUser:

    def __init__(self, sessionInstance: SessionManager = None):
        if sessionInstance is None:
            sessionInstance = global_instance
        self.session = sessionInstance
        self.gravity = HighGravity(self.session)
        self._routes = []
        self.logging = logging.getLogger("TwitterUser")
        # I'm not sure if we are going to use a custom bearer in the future...
        self.bearer = ""

    getUserFeatures = {'responsive_web_twitter_blue_verified_badge_is_enabled': True,
                       'verified_phone_label_enabled': True,
                       'responsive_web_graphql_timeline_navigation_enabled': True,
                       'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                       'responsive_web_graphql_exclude_directive_enabled': False}

    @property
    async def routes(self):
        if not self._routes:
            self._routes = await self.gravity.retrieve_routes()
        return self._routes

    async def get_user(self, username: [str, User]):
        """
        Retrieves a User by it's username/screenname.
        :param username: The user's username. (e.g. Twitter)
        :return: A User object containing the user's information.
        """
        routes = await self.routes

        if isinstance(username, User):
            username = username.username
            if username is None:
                raise Exception("Malformed User data? Expected username to exist.")

        variables = {'screen_name': username,
                     'withSafetyModeUserFields': False,
                     'withSuperFollowsUserFields': True}

        if routes.get("UserByScreenName"):
            route = routes.get("UserByScreenName")
            url = route[0]

            # Twitter raises an error if we have a missing feature not present in the list.
            # We could just look at the defaults but at the same time,
            # it would be better to not follow blindly.
            set_features = list(self.getUserFeatures.keys())
            for feature in route[1]['featureSwitches']:
                if feature not in set_features:
                    self.logging.warning(f"!! {feature} found in featureSwitch but missing in setFeatures.")
            a = await self.session.get(url, params={'variables': json.dumps(variables).replace(" ", ""),
                                                    'features': json.dumps(self.getUserFeatures).replace(" ", "")})
            # print(a)
            data: dict = await a.json()
            true_user = data["data"]["user"]["result"]['legacy']
            true_user["id"] = data["data"]["user"]["result"]["rest_id"]
            return UtilBox.make_user(true_user)
        else:
            print("Routes list:")
            print(routes)
            raise Exception("Missing routes?")

    getTweetFeatures = {"responsive_web_twitter_blue_verified_badge_is_enabled": True,
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
                        "responsive_web_enhance_cards_enabled": False
                        }

    async def get_tweet(self, tweet_id: int):
        routes = await self.routes

        variables = {"focalTweetId": str(tweet_id),
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
                     "withV2Timeline": True}

        if routes.get("TweetDetail"):
            route = routes.get("TweetDetail")
            url = route[0]

            # Twitter raises an error if we have a missing feature not present in the list.
            # We could just look at the defaults but at the same time,
            # it would be better to not follow blindly.
            features = self.getTweetFeatures
            set_features = list(features.keys())
            for feature in route[1]['featureSwitches']:
                if feature not in set_features:
                    self.logging.warning(f"{feature} found in featureSwitch but missing in setFeatures.")
            await self.session.guest_token()
            replaced = url.replace("https://api.twitter.com/", "https://twitter.com/i/api/")
            a = await self.session.get(replaced,
                                       params={'variables': json.dumps(variables).replace(" ", ""),
                                               'features': json.dumps(features).replace(" ", "")},
                                       guest_token=True)
            data: dict = await a.json()
            inner_data: dict = data.get("data", {})
            for instruction in inner_data['threaded_conversation_with_injections_v2'].get("instructions"):
                type_instruct = instruction["type"]
                if type_instruct == "TimelineAddEntries":
                    for entry in instruction["entries"]:
                        if entry["entryId"].startswith("tweet-"):
                            base_tweet = entry["content"]["itemContent"]["tweet_results"]["result"]
                            return UtilBox.common_tweet(base_tweet, None)
