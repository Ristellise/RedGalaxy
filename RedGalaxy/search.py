import asyncio
import urllib.parse

from . import SessionManager, UtilBox, RedGalaxyException, BaseTwitter


class TwitterSearch(BaseTwitter):
    def __init__(self, session_instance: SessionManager = None):
        """
        :param session_instance:
        """
        super().__init__(session_instance)
        self.logging = self.session.logging.getChild("TwitterSearch")

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

    async def search(self, query, limit=-1, mode="top"):
        """
        Search for tweets with the specified query.

        :param query: The query arguments. Anything on Twitter's /search route works.
        :param limit: Limits then umber of tweets returned. 0 to scrape all.
        :param mode: The type of search to do. Can be: ["live", "top", "user", "image", "video"]
        :return: An async generator of tweets.
        """

        count = 20

        args = {
            **self.search_base,
            "q": query,
            "tweet_search_mode": mode,
            "count": count,
            "query_source": "spelling_expansion_revert_click",
            "cursor": None,
            "pc": 1,
            "spelling_corrections": 1,
            "include_ext_edit_control": True,
            "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,"
            "superFollowMetadata,unmentionInfo,editControl,collab_control,vibe",
        }
        referer = "https://twitter.com/search?" + urllib.parse.urlencode(
            {
                "f": "live",
                "lang": "en",
                "q": query,
                "src": "spelling_expansion_revert_click",
            }
        )
        while True:
            param = args.copy()
            if param["cursor"] is None:
                del param["cursor"]

            timeline, global_objects = await self.get_timeline(param, referer)
            args["cursor"] = None
            # Get Current run Cursors
            cursor = {"top": None, "bottom": None}
            run_count = 0

            for i in timeline.get("instructions"):
                if list(i.keys())[0] == "addEntries":
                    for entry in self.iter_entries(
                        i["addEntries"]["entries"], global_objects
                    ):
                        if entry.get("type") == "cursor":
                            cursor[entry["direction"]] = entry
                        else:
                            yield entry
                            run_count += 1
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
            if limit == 0:
                return
            self.logging.debug(f"RunCount: {run_count} Expecting? {run_count > 20}")
            args["cursor"] = cursor["bottom"]["value"]

    async def get_timeline(self, param: dict, referer):
        tries = 5
        adapted = None
        while tries > 0:
            adapted = await self.session.get(
                "https://api.twitter.com/2/search/adaptive.json",
                params=param,
                referer=referer,
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
                print(await adapted.text())
                raise RedGalaxyException(
                    f"Adaptive json returned {adapted.status}. Expected 200."
                )
            else:
                break
        if adapted is None:
            raise RedGalaxyException("Gave up Trying.")
        j_data: dict = adapted.json()

        global_objects = j_data.get("globalObjects", {})
        timeline = j_data.get("timeline", {})
        if not timeline:
            raise Exception("Expected timeline dict. Got none or invalid data.")
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

        referer = "https://twitter.com/search?" + urllib.parse.urlencode(
            {
                "f": "live",
                "lang": "en",
                "q": query,
                "src": "spelling_expansion_revert_click",
            }
        )
        while True:
            param = args.copy()
            if param["cursor"] is None:
                del param["cursor"]

            timeline, global_objects = await self.get_timeline(param, referer)
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

    def iter_entries(self, entries: list, entry_globals: dict):
        for entry in entries:
            entry_id = entry["entryId"]
            # print(entry_id)
            if entry_id.startswith("tweet-") or entry_id.startswith("sq-I-t-"):
                yield {
                    "type": "tweet",
                    **self.unpack_tweet(entry, entry_globals, entry_id),
                }
            elif entry_id.startswith("cursor") or entry_id.startswith("sq-C"):
                yield {
                    "type": "cursor",
                    **self.unpack_cursor(entry_id, entry["content"]),
                }

    def unpack_cursor(self, entry_id, cursor: dict):
        content = cursor.get("content", {})
        operation = cursor.get("operation", {})
        if not content and not operation:
            raise Exception("Cursor Content missing?")
        else:
            print(entry_id, cursor)
            if entry_id.startswith("sq-C"):
                content = operation["cursor"]
                return {
                    "direction": content.get("cursorType").lower(),
                    "value": content.get("value"),
                }
            elif entry_id.startswith("cursor-"):
                content = operation["cursor"]
                return {
                    "direction": content.get("cursorType").lower(),
                    "value": content.get("value"),
                }
            else:
                return {
                    "direction": content.get("cursorType").lower(),
                    "value": content.get("value"),
                }

    def unpack_tweet(self, entry_data: dict, entry_globals: dict, entry_id: str):
        if entry_data.get("__typename") == "TimelineTimelineItem":
            tweet = (
                entry_data.get("itemContent", {})
                .get("tweet_results", {})
                .get("result", {})
            )
            if not tweet:
                raise Exception("Tweet data missing? [Timeline V2]")
            tweet = UtilBox.common_tweet(tweet, None)
        elif entry_id.startswith("sq-I-t-") or entry_id.startswith("tweet-"):
            tweet_mini = entry_data.get("content", {}).get("item", {})
            if not tweet_mini:
                raise Exception("Tweet Pointer data missing? [Search Timeline]")

            tweet = entry_globals["tweets"][str(tweet_mini["content"]["tweet"]["id"])]
            tweet = UtilBox.common_tweet(tweet, entry_globals)
        else:
            raise Exception(f"Unseen Tweet type? [Unknown Timeline]: {entry_data}")

        return {"tweet": tweet, "user": tweet.user}
