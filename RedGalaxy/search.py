import asyncio
import json
import urllib.parse

from . import global_instance, SessionManager, UtilBox, RedGalaxyException, HighGravity


class TwitterSearch:
    def __init__(self, session_instance: SessionManager = None):
        """

        :param session_instance:
        """
        if session_instance is None:
            session_instance = global_instance
        self.session = session_instance
        self.logging = self.session.logging.getChild("TwitterSearch")
        self.gravity = HighGravity(self.session)
        self._routes = None

    search_base = {
        # Users
        "include_profile_interstitial_type": 1,
        "include_blocking": 1,
        "include_blocked_by": 1,
        "include_followed_by": 1,
        "include_want_retweets": 1,
        "include_mute_edge": 1,
        "include_can_dm": 1,
        "include_can_media_tag": 1,
        "include_ext_has_nft_avatar": 1,
        "include_ext_is_blue_verified": 1,
        "include_ext_verified_type": 1,
        "skip_status": 1,
        # endpoints.Tweets (m.getGlobalDefaults(e))
        "cards_platform": "Web-12",
        "include_cards": "true",
        "include_ext_alt_text": "true",
        "include_ext_limited_action_results": "true",
        "include_quote_count": "true",
        "include_reply_count": 1,
        "tweet_mode": "extended",
        "include_ext_collab_control": "true",
        "include_ext_views": "true",
        # Base (endpoints.URT.js)
        "include_entities": 1,
        "include_user_entities": 1,
        "include_ext_media_color": 1,
        "include_ext_media_availability": 1,
        "include_ext_sensitive_media_warning": 1,
        "include_ext_trusted_friends_metadata": 1,
        "send_error_codes": 1,
        "simple_quoted_tweet": 1,
        "pc": 0,  # Promoted Content
        # Rest
        # q: "#SearchTag"
        # tweet_search_mode: ["live", "top", "user", "image", "video"]
        # count: (int)
        # query_source:
        #   - AdvancedSearchPage: "advanced_search_page",
        #   - CashtagClick: "cashtag_click",
        #   - HashtagClick: "hashtag_click",
        #   - PromotedTrendClick: "promoted_trend_click",
        #   - RecentSearchClick: "recent_search_click",
        #   - SavedSearchClick: "saved_search_click",
        #   - RelatedQueryClick: "related_query_click",
        #   - SpellingCorrectionClick: "spelling_correction_click",
        #   - SpellingCorrectionRevertClick: "spelling_suggestion_revert_click",
        #   - SpellingExpansionClick: "spelling_expansion_click",
        #   - SpellingExpansionRevertClick: "spelling_expansion_revert_click",
        #   - SpellingSuggestionClick: "spelling_suggestion_click",
        #   - TrendClick: "trend_click",
        #   - TrendView: "trend_view",
        #   - TypeaheadClick: "typeahead_click",
        #   - Typed: "typed_query",
        #   - TweetDetailQuoteTweet: "tdqt"
        # cursor: Cursor
        # spelling_corrections: 1
        # include_ext_edit_control: 0
        # ext: mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,
        #      superFollowMetadata,unmentionInfo,editControl,collab_control,vibe
    }

    featureFlags = {
        "rweb_lists_timeline_redesign_enabled": True,
        "blue_business_profile_image_shape_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": False,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "tweetypie_unmention_optimization_enabled": False,
        "vibe_api_enabled": True,
        "responsive_web_edit_tweet_api_enabled": False,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": False,
        "standardized_nudges_misinfo": False,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
        "interactive_text_enabled": False,
        "responsive_web_text_conversations_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": True,
    }

    @property
    async def routes(self):
        if not self._routes:
            self._routes = await self.gravity.retrieve_routes()
        return self._routes

    async def search(self, query, limit=-1, mode="Top"):
        """
        Search for tweets with the specified query.

        :param query: The query arguments. Anything on Twitter's /search route works.
        :param limit: Limits then umber of tweets returned. 0 to scrape all.
        :param mode: The type of search to do. Available modes: ["Top", "People", "Photos", "Videos", "Latest"]
        :return: An async generator of tweets.
        """

        count = 20

        routes: dict = await self.routes

        route = routes.get("SearchTimeline")
        if not route:
            self.logging.error("Routes list:")
            self.logging.error(routes)
            raise Exception("Missing routes?")

        # args = {
        #     **self.search_base,
        #     "q": query,
        #     "tweet_search_mode": mode,
        #     "count": count,
        #     "query_source": "spelling_expansion_revert_click",
        #     "cursor": None,
        #     "pc": 1,
        #     "spelling_corrections": 1,
        #     "include_ext_edit_control": True,
        #     "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,"
        #     "superFollowMetadata,unmentionInfo,editControl,collab_control,vibe",
        # }
        args = {
            "rawQuery": query,
            "count": count,
            "product": mode,
            "querySource": "spelling_expansion_revert_click",
            "cursor": None,
            "includePromotedContent": False
            # "withDownvotePerspective": False,
            # "withReactionsMetadata": False,
            # "withReactionsPerspective": False,
        }
        # referer = "https://twitter.com/search?" + urllib.parse.urlencode(
        #     {
        #         "f": "live",
        #         "lang": "en",
        #         "q": query,
        #         "src": "spelling_expansion_revert_click",
        #     }
        # )
        while True:
            param = args.copy()
            if param["cursor"] is None:
                del param["cursor"]

            timeline, global_objects = await self.get_timeline(
                param, self.featureFlags, route[0]
            )
            args["cursor"] = None
            # Get Current run Cursors
            cursor = {"top": None, "bottom": None}
            run_count = 0
            for i in UtilBox.iter_timeline_data(
                timeline, global_objects, limit, cursor
            ):
                run_count += 1
                yield i

            if limit == 0:
                return
            self.logging.debug(f"RunCount: {run_count} Expecting? {run_count > 20}")
            args["cursor"] = cursor["bottom"]["value"]
            if run_count == 0:
                break

    async def get_timeline(self, param: dict, features: dict, graphql_url):
        tries = 5
        adapted = None
        while tries > 0:
            adapted = await self.session.get(
                graphql_url,
                params={
                    "variables": json.dumps(param).replace(" ", ""),
                    "features": json.dumps(features).replace(" ", ""),
                },
            )
            # Twitter may not return a rate limit remaining in the header.
            # In this case, assume that the request was successful and re-get tokens

            if adapted.headers.get("x-rate-limit-remaining", 0) == 0:
                await self.session.ensure_token(retry=True)
                tries -= 1
                continue
            if adapted.status_code == 503:
                tries -= 1
                continue
            if adapted.status_code == 429:
                await self.session.ensure_token(retry=True)
                tries -= 1
                continue
            if adapted.status_code != 200:
                print(adapted.text)
                raise RedGalaxyException(
                    f"Adaptive json returned {adapted.status_code}. Expected 200."
                )
            else:
                break
        if adapted is None:
            raise RedGalaxyException("Gave up Trying.")
        j_data: dict = adapted.json()
        self.logging.debug(f"Response: {j_data}")
        content = (
            j_data.get("data", {})
            .get("search_by_raw_query", {})
            .get("search_timeline", {})
        )
        global_objects = content.get("globalObjects", {})
        timeline = content.get("timeline", {})
        if not timeline:
            print(content)
            raise Exception(f"Expected timeline dict. Got none or invalid data.")
        return timeline, global_objects

    async def stream(
        self,
        query,
        limit=-1,
        mode="top",
        initial_track: bool = False,
        refresh_rate: float = 30.0,
    ):
        """
        Stream a list of tweets from with a query.

        Note: This stream does not backtrack when it reaches a max number of 20 tweets.

        TODO: Allow backtracking eventually. It is possible to backtrack, but it probably needs tweet counting.

        :param query: The query term to be placed in the search
        :param limit: The max number of tweets to be retrieved before exiting.
        :param mode: The type of search to do. Can be: ["live", "top", "user", "image", "video"]
        :param refresh_rate: How often new tweets should be fetched? Defaults to 5 seconds.
        :param initial_track: Do we retrieve the initial first 20 tweets?
        :return:
        """

        raise NotImplementedError("TBD once Search has been reimplemented.")
        count = 20

        args = {
            **self.search_base,
            "q": query,
            "tweet_search_mode": mode,
            "count": count,
            "query_source": "spelling_expansion_revert_click",
            "cursor": None,
            "pc": "1",
            "spelling_corrections": 1,
            "include_ext_edit_control": "true",
            "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,"
            "superFollowMetadata,unmentionInfo,editControl,collab_control,vibe",
        }
        initial_track = not initial_track  # Just invert it lol
        while True:
            param = args.copy()
            if param["cursor"] is None:
                del param["cursor"]

            timeline, global_objects = await self.get_timeline(param)
            args["cursor"] = None
            # Get Current run Cursors
            cursor = {"top": None, "bottom": None}

            for i in timeline.get("instructions"):
                if list(i.keys())[0] == "addEntries":
                    # Bottom to top.
                    reverse = list(reversed(i["addEntries"]["entries"]))
                    for entry in self.iter_entries(reverse, global_objects):
                        if entry.get("type") == "cursor":
                            cursor[entry["direction"]] = entry
                        else:
                            if initial_track:
                                continue
                            yield entry
                            if limit >= 0:
                                limit -= 1
                            if limit == 0:
                                break
                elif list(i.keys())[0] == "replaceEntry":
                    for entry in self.iter_entries(
                        i["addEntries"]["entries"], global_objects
                    ):
                        if entry.get("type") == "cursor":
                            cursor[entry["direction"]] = entry
            if initial_track:
                initial_track = False
            if limit == 0:
                return
            args["cursor"] = cursor["top"]["value"]
            await asyncio.sleep(refresh_rate)
