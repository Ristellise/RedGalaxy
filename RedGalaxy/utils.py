import email.utils
import re
import typing

from . import (
    RedGalaxyException,
    TombTweet,
    User,
    Tweet,
    Media,
    UserCounts,
    ExtendedMedia,
)


class UtilBox:
    @staticmethod
    def make_user(user_data: dict) -> User:
        username = user_data.get("screen_name")
        displayname = user_data.get("name")
        description = user_data.get("description")

        for url in user_data.get("entities", {}).get("description", {}).get("urls", []):
            description = description.replace(url.get("url"), url.get("expanded_url"))
        links = user_data.get("entities", {}).get("url", {}).get("urls", [])
        link_url = None
        if links:
            link_url = links[0].get("expanded_url")
            if link_url is None:
                # some links are short enough that they don't need expanding?
                link_url = links[0].get("url")

        counts = UserCounts(
            followers=user_data.get("followers_count", 0),
            friends=user_data.get("friends_count", 0),
            statuses=user_data.get("statuses_count", 0),
            favourites=user_data.get("favourites_count", 0),
            listed=user_data.get("listed_count", 0),
            media=user_data.get("media_count", 0),
        )
        profile_url = user_data.get("profile_image_url_https", None)
        if profile_url:
            profile_url = profile_url.replace("_normal", "_400x400")
        if isinstance(user_data["id"], str):
            user_data["id"] = int(user_data["id"])
        return User(
            username=username,
            description=description,
            id=user_data["id"],
            link_url=link_url,
            display_name=displayname,
            user_counts=counts,
            verified=user_data.get("verified", False),
            profile_banner_url=user_data.get("profile_banner_url", None),
            profile_image_url=profile_url,
            verified_type=None
            if not user_data["verified"]
            else user_data.get("verified_type", "Legacy"),
            created=email.utils.parsedate_to_datetime(user_data["created_at"]),
            location=user_data.get("location", None),
            protected=False,  # probably lol
        )

    @staticmethod
    def common_tweet(
        true_tweet: dict, entry_globals: typing.Optional[dict], recurse: bool = True
    ):
        if entry_globals:
            user_result = {}
            user_result["legacy"] = entry_globals["users"][str(true_tweet["user_id"])]
            user_result["legacy"]["id"] = str(true_tweet["user_id"])
            base_tweet = true_tweet
        else:
            user_result = true_tweet["core"]["user_results"]["result"]
            user_result["legacy"]["id"] = true_tweet["core"]["user_results"]["result"][
                "rest_id"
            ]
            # print("rest_id:", true_tweet["core"]["user_results"]["result"]["rest_id"])
            base_tweet = true_tweet["legacy"]
        if entry_globals:
            quoted_tweet = entry_globals["tweets"].get(
                str(base_tweet.get("quoted_status_id", "-1")), None
            )
            retweeted_tweet = entry_globals["tweets"].get(
                str(base_tweet.get("retweeted_status_id", "-1")), None
            )
        else:
            quoted_tweet = base_tweet.get("quoted_status_result", {}).get(
                "result", None
            )
            retweeted_tweet = base_tweet.get("retweeted_status_result", {}).get(
                "result", None
            )
        if recurse and quoted_tweet:
            quoted_tweet = UtilBox.common_tweet(
                quoted_tweet, entry_globals, recurse=False
            )
        if recurse and retweeted_tweet:
            retweeted_tweet = UtilBox.common_tweet(
                retweeted_tweet, entry_globals, recurse=False
            )
        user = UtilBox.make_user(user_result["legacy"])

        content = (
            retweeted_tweet.content
            if retweeted_tweet
            else base_tweet.get("full_text", "")
        )

        medias = base_tweet.get("extended_entities", {}).get("media", [])
        urls = base_tweet.get("entities", {}).get("urls", [])
        conversation_id = int(base_tweet.get("conversation_id_str", {}))
        reply_count = base_tweet.get("reply_count")
        retweet_count = base_tweet.get("retweet_count")
        favorite_count = base_tweet.get("favorite_count")
        quote_count = base_tweet.get("quote_count")
        lang = base_tweet.get("lang")

        for link in urls:
            content = content.replace(link["url"], link["expanded_url"])

        spl_content: list[str] = content.split(" ")
        if spl_content[-1].startswith("https://t.co") and len(medias) > 0:
            spl_content.pop(-1)

        wrapped_media_regular = []
        wrapped_media_extended = []

        for media in base_tweet.get("entities", {}).get("media", []):
            set_media = Media(
                display_url=media["display_url"],
                expanded_url=media["expanded_url"],
                features=media.get("features", {}),
                id=int(media["id_str"]),
                media_url=media["media_url_https"],
                type=media["type"],
                original_info=media["original_info"],
            )
            wrapped_media_regular.append(set_media)

        for extended_media in medias:
            set_media = ExtendedMedia(
                display_url=extended_media["display_url"],
                expanded_url=extended_media["expanded_url"],
                ext_media_availability=extended_media["ext_media_availability"],
                ext_media_color=extended_media.get("ext_media_color"),
                features=extended_media.get("features", {}),
                id=int(extended_media["id_str"]),
                media_url=extended_media["media_url_https"],
                type=extended_media["type"],
                original_info=extended_media["original_info"],
            )
            if set_media.type == "video":
                set_media.data_info = extended_media["video_info"]
                set_media.features = extended_media.get("features", None)
            # Animated gifs are just videos. (Thanks twitter)
            elif set_media.type == "animated_gif":
                set_media.data_info = extended_media["video_info"]
                set_media.features = extended_media.get("features", None)
            elif set_media.type != "photo":
                raise Exception(
                    f"Unknown type: {set_media.type}@{int(base_tweet['id_str'])}"
                )
            wrapped_media_extended.append(set_media)

        content = " ".join(spl_content)

        source = base_tweet.get("source", "")
        if source:
            source = source.replace("\\/", "/")
            source = re.sub("<[^<]+?>", "", source)

        return Tweet(
            id=int(base_tweet["id_str"]),
            date=email.utils.parsedate_to_datetime(base_tweet["created_at"]),
            content=content,
            links=urls,
            user=user,
            replies=reply_count,
            retweets=retweet_count,
            favorites=favorite_count,
            quotes=quote_count,
            conversion_id=conversation_id,
            language=lang,
            source=source,
            media=wrapped_media_regular,
            extended_media=wrapped_media_extended,
            retweeted_tweet=retweeted_tweet,
            quoted_tweet=quoted_tweet,
        )

    @staticmethod
    def iter_timeline_data(
        timeline: dict, global_objects: dict, limit: int, cursor: dict, run_count=0
    ):
        for i in timeline.get("instructions", []):
            entryType = list(i.keys())[0]
            if entryType == "type":
                if i[entryType] == "TimelineAddEntries":
                    for entry in UtilBox.iter_timeline_entry(
                        i["entries"], global_objects
                    ):
                        if entry.get("type") == "cursor":
                            cursor[entry["direction"]] = entry
                        else:
                            yield entry
                            run_count += 1
                            if limit > 0:
                                limit -= 1
                            if limit == 0:
                                break
                elif i[entryType] == "TimelineReplaceEntry":
                    for entry in UtilBox.iter_timeline_entry(
                        [i["entry"]], global_objects
                    ):
                        if entry.get("type") == "cursor":
                            cursor[entry["direction"]] = entry
            else:
                if entryType == "addEntries":
                    for entry in UtilBox.iter_timeline_entry(
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
                elif entryType == "replaceEntry":
                    for entry in UtilBox.iter_timeline_entry(
                        i["addEntries"]["entries"], global_objects
                    ):
                        if entry.get("type") == "cursor":
                            cursor[entry["direction"]] = entry

    @staticmethod
    def iter_timeline_entry(entries: list, entry_globals: dict):
        for entry in entries:
            entry_id = entry["entryId"]
            # print(entry_id)
            if entry_id.startswith("tweet-") or entry_id.startswith("sq-I-t-"):
                # print(entry)
                yield {
                    "type": "tweet",
                    **UtilBox.unpack_tweet(entry, entry_globals, entry_id),
                }
            elif entry_id.startswith("cursor") or entry_id.startswith("sq-C"):
                yield {
                    "type": "cursor",
                    **UtilBox.unpack_cursor(entry_id, entry["content"]),
                }

    @staticmethod
    def unpack_tweet(entryData: dict, entry_globals: dict, entry_id: str):
        if entryData.get("__typename") == "TimelineTimelineItem":
            tweet = (
                entryData.get("itemContent", {})
                .get("tweet_results", {})
                .get("result", {})
            )
            if not tweet:
                raise RedGalaxyException("Tweet data missing? [Timeline V2]")
            tweet = UtilBox.common_tweet(tweet, None)
        elif entry_id.startswith("sq-I-t-") or entry_id.startswith("tweet-"):
            tweet_mini = entryData.get("content", {})
            if not tweet_mini:
                raise RedGalaxyException(
                    "Tweet Pointer data missing? [Search Timeline]"
                )
            if tweet_mini.get("item", None) is not None:
                tweet_mini = tweet_mini.get("item", None)
            elif "__typename" in tweet_mini:
                # V2 Search (GraphQL)
                tweet = (
                    tweet_mini.get("itemContent", {})
                    .get("tweet_results", {})
                    .get("result", {})
                )
                if not tweet:
                    tomb_id = int(entry_id.split("-")[-1])
                    if tomb_id:
                        tweet = TombTweet(id=tomb_id)
                        return {"tweet": tweet, "user": tweet.user}
                    print(entryData)
                    raise RedGalaxyException("Tweet data missing? [Timeline V2]")
                tweet = UtilBox.common_tweet(tweet, None)
                return {"tweet": tweet, "user": tweet.user}
            if tweet_mini is None:
                raise RedGalaxyException(
                    "Failed to retrieve tweet_mini [Search Timeline]"
                )
            tweet = entry_globals["tweets"][str(tweet_mini["content"]["tweet"]["id"])]
            tweet = UtilBox.common_tweet(tweet, entry_globals)
        else:
            raise RedGalaxyException(
                f"Unseen Tweet type? [Unknown Timeline]: {entryData}"
            )

        return {"tweet": tweet, "user": tweet.user}

    @staticmethod
    def unpack_cursor(entry_id, cursor: dict):

        content = cursor.get("content", {})
        operation = cursor.get("operation", {})
        v2 = True if cursor.get("__typename") else False

        if not content and not operation and not v2:
            # self.logging.debug(cursor)
            raise Exception("Cursor Content missing?")
        else:
            # self.logging.debug(entry_id, cursor)
            if entry_id.startswith("sq-C"):
                content = operation["cursor"]
                return {
                    "direction": content.get("cursorType").lower(),
                    "value": content.get("value"),
                }
            elif entry_id.startswith("cursor-"):
                if operation.get("cursor"):
                    content = operation["cursor"]
                else:
                    # probably v2
                    content = cursor
                return {
                    "direction": content.get("cursorType", "").lower(),
                    "value": content.get("value"),
                }
            else:
                return {
                    "direction": content.get("cursorType", "").lower(),
                    "value": content.get("value"),
                }
