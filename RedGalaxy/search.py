import asyncio
import typing

from . import global_instance, SessionManager, UtilBox


class TwitterSearch:

    def __init__(self, session_instance: SessionManager = None):
        """

        :param session_instance:
        """
        if session_instance is None:
            session_instance = global_instance
        self.session = session_instance

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

        args = {**self.search_base,
                "q": query,
                "tweet_search_mode": mode,
                "count": count,
                "query_source": "spelling_suggestion_click",
                "cursor": None,
                "spelling_corrections": 1,
                "include_ext_edit_control": 0,
                "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,"
                       "superFollowMetadata,unmentionInfo,editControl,collab_control,vibe"
                }
        await self.session.guest_token()
        self.session.do_headers("https://twitter.com/", guest_token=True)

        while True:
            param = args.copy()
            if param["cursor"] is None:
                del param["cursor"]

            timeline, global_objects = await self.get_timeline(param)
            args["cursor"] = None
            # Get Current run Cursors
            cursor = {"top": None, "bottom": None}
            run_count = 0

            for i in timeline.get("instructions"):
                if list(i.keys())[0] == "addEntries":
                    for entry in self.iter_entries(
                            i["addEntries"]["entries"],
                            global_objects
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
                            i["addEntries"]["entries"],
                            global_objects
                    ):
                        if entry.get("type") == "cursor":
                            cursor[entry["direction"]] = entry
            if limit == 0:
                return
            args["cursor"] = cursor["bottom"]["value"]

    async def get_timeline(self, param: dict):

        adapted = await self.session.get("https://api.twitter.com/2/search/adaptive.json", params=param)
        if adapted.headers['x-rate-limit-remaining'] == 0:
            await self.session.guest_token()
            self.session.do_headers("https://twitter.com/", guest_token=True)
        if adapted.status != 200:
            print(await adapted.text())
            raise Exception(f"Adaptive json returned {adapted.status}. Expected 200.")
        j_data: dict = await adapted.json()

        global_objects = j_data.get("globalObjects", {})
        timeline = j_data.get("timeline", {})
        if not timeline:
            raise Exception(f"Expected timeline dict. Got none or invalid data.")
        return timeline, global_objects

    async def stream(self, query, limit=-1, mode="top",
                     initial_track: bool = False, refresh_rate: float = 5.0):
        """
        Stream a list of tweets from with a query.

        Note: This stream does not backtrack when it reaches a max number of 20 tweets.

        TODO: Allow backtracking eventually. It is possible to backtrack but it probably needs tweet counting.

        :param query: The query term to be placed in the search
        :param limit: The max number of tweets to be retrieved before exiting.
        :param mode: The type of search to do. Can be: ["live", "top", "user", "image", "video"]
        :param refresh_rate: How often new tweets should be fetched? Defaults to 5 seconds.
        :param initial_track: Do we retrieve the initial first 20 tweets?
        :return:
        """
        count = 20

        args = {**self.search_base,
                "q": query,
                "tweet_search_mode": mode,
                "count": count,
                "query_source": "spelling_suggestion_click",
                "cursor": None,
                "spelling_corrections": 1,
                "include_ext_edit_control": 0,
                "ext": "mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,"
                       "superFollowMetadata,unmentionInfo,editControl,collab_control,vibe"
                }
        self.session.do_headers("https://twitter.com/")
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
                    for entry in self.iter_entries(
                            reverse,
                            global_objects
                    ):
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
                            i["addEntries"]["entries"],
                            global_objects
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
            if entry_id.startswith("tweet-") or \
                    entry_id.startswith("sq-I-t-"):
                yield {"type": "tweet", **self.unpack_tweet(entry, entry_globals, entry_id)}
            elif entry_id.startswith("cursor") or \
                    entry_id.startswith("sq-C"):
                yield {"type": "cursor",
                       **self.unpack_cursor(entry_id, entry["content"])}

    def unpack_cursor(self, entry_id, cursor: dict):
        content = cursor.get("content", {})
        operation = cursor.get("operation", {})
        if not content and not operation:
            raise Exception("Cursor Content missing?")
        else:
            if entry_id.startswith("sq-C"):

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

    def unpack_tweet(self, entryData: dict, entry_globals: dict, entry_id: str):
        if entryData.get("__typename") == "TimelineTimelineItem":
            tweet = entryData.get("itemContent", {}).get("tweet_results", {}).get("result", {}).get("legacy", {})
            if not tweet:
                raise Exception("Tweet data missing? [Timeline V2]")
            tweet["user"] = entryData.get("itemContent", {}).get("tweet_results", {}) \
                .get("result", {}).get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
            if not tweet["user"]:
                raise Exception("Tweet user missing? [Timeline V2]")
        elif entry_id.startswith("sq-I-t-"):
            tweet_mini = entryData.get("content", {}).get("item", {})
            if not tweet_mini:
                raise Exception("Tweet Pointer data missing? [Search Timeline]")

            tweet = entry_globals["tweets"][str(tweet_mini["content"]["tweet"]["id"])]
            tweet["user"] = entry_globals["users"][str(tweet['user_id'])]
            if not tweet["user"]:
                raise Exception("Tweet Pointer data missing? [Search Timeline]")
        else:
            raise Exception("Unseen Tweet type? [Unknown Timeline]")

        tweet = UtilBox.make_tweet(tweet, entry_globals)

        return {"tweet": tweet, "user": tweet.user}
