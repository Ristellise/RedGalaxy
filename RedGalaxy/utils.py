import email.utils
import re
import typing

from . import User, Tweet, Media, UserCounts, ExtendedMedia


class UtilBox:

    @staticmethod
    def make_user(user_data: dict) -> User:
        username = user_data.get("screen_name")
        displayname = user_data.get("name")
        description = user_data.get("description")

        for url in user_data.get("entities", {}).get("description", {}).get('urls', []):
            description = description.replace(url.get("url"), url.get("expanded_url"))
        links = user_data.get("entities", {}).get("url", {}).get('urls', [])
        link_url = None
        if links:
            link_url = links[0]["expanded_url"]

        counts = UserCounts(
            followers=user_data.get("followers_count", 0),
            friends=user_data.get("friends_count", 0),
            statuses=user_data.get("statuses_count", 0),
            favourites=user_data.get("favourites_count", 0),
            listed=user_data.get("listed_count", 0),
            media=user_data.get("media_count", 0)
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
            verified_type=None if not user_data["verified"] else user_data.get("verified_type", "Legacy"),
            created=email.utils.parsedate_to_datetime(user_data['created_at']),
            location=user_data.get("location", None),
            protected=False  # probably lol
        )

    @staticmethod
    def make_tweet_TimelineTweet(true_tweet: dict) -> Tweet:

        user_results = true_tweet["core"]["user_results"]["result"]
        user_results['legacy']["id"] = true_tweet["core"]["user_results"]["result"]["rest_id"]
        user = UtilBox.make_user(user_results["legacy"])
        legacy = true_tweet["legacy"]

        quoted_tweet = legacy.get("quoted_status_result", {}).get("result", None)
        retweeted_tweet = legacy.get("retweeted_status_result", {}).get("result", None)
        if quoted_tweet:
            quoted_tweet = UtilBox.make_tweet_TimelineTweet(quoted_tweet)
        if retweeted_tweet:
            retweeted_tweet = UtilBox.make_tweet_TimelineTweet(retweeted_tweet)




        content = retweeted_tweet.content if retweeted_tweet else legacy["full_text"]
        tweet_id = int(legacy["id_str"])
        medias = legacy.get("extended_entities", {}).get("media", [])
        urls = legacy.get("entities", {}).get("urls", [])
        conversation_id = int(legacy.get("conversation_id_str", 0))
        reply_count = legacy.get("reply_count")
        retweet_count = legacy.get("retweet_count")
        favorite_count = legacy.get("favorite_count")
        quote_count = legacy.get("quote_count")
        lang = legacy.get("lang")


        for link in urls:
            content = content.replace(link["url"], link["expanded_url"])
        spl_content: list[str] = content.split(" ")
        if spl_content[-1].startswith("https://t.co") and len(medias) > 0:
            spl_content.pop(-1)

        wrapped_media_regular = []
        wrapped_media_extended = []

        for media in legacy.get("entities", {}).get("media", []):
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
                ext_media_color=extended_media["ext_media_color"],
                features=extended_media.get("features", {}),
                id=int(extended_media["id_str"]),
                media_url=extended_media["media_url_https"],
                type=extended_media["type"],
                original_info=extended_media["original_info"],
            )
            if set_media.type == "video":
                set_media.data_info = extended_media["video_info"]
                set_media.features = extended_media["features"],
            elif set_media.type != "photo":
                raise Exception(f"Unknown type: {set_media.type}@{tweet_id}")
            wrapped_media_extended.append(set_media)

        content = " ".join(spl_content)

        source = legacy.get("source", "")
        if source:
            source = source.replace("\\/", "/")
            source = re.sub('<[^<]+?>', '', source)

        return Tweet(
            id=int(tweet_id),
            date=email.utils.parsedate_to_datetime(legacy['created_at']),
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
    def make_tweet(true_tweet: dict, entry_globals: typing.Optional[dict] = None) -> Tweet:

        tweet_id = true_tweet.get("id", -1)
        if tweet_id == -1:
            raise Exception("Invalid TweetID?")

        is_retweeted = True if true_tweet.get("retweeted_status_id") else False
        is_quoted = True if true_tweet.get("quoted_status_id") else False
        retweeted_tweet = None
        quoted_tweet = None
        if is_retweeted:
            if entry_globals is not None:
                retweet_tweet_dict = entry_globals["tweets"][str(true_tweet.get("retweeted_status_id"))]
                retweet_tweet_dict["user"] = entry_globals["users"][str(retweet_tweet_dict['user_id'])]
            else:
                retweet_tweet_dict = true_tweet.get("retweeted_status_result", {}).get("result", {}).get("legacy", {})
                retweet_tweet_dict["user"] = true_tweet.get("retweeted_status_result", {}).get("result", {}).get("core",
                                                                                                                 {}) \
                    .get("user_results", {}).get("result").get("legacy")
            retweeted_tweet = UtilBox.make_tweet(
                retweet_tweet_dict,
                entry_globals)

        if is_quoted:
            if entry_globals is not None:
                quoted_tweet_dict = entry_globals["tweets"][str(true_tweet.get("quoted_status_id"))]
                quoted_tweet_dict["user"] = entry_globals["users"][str(quoted_tweet_dict['user_id'])]
                quoted_tweet = UtilBox.make_tweet(
                    quoted_tweet_dict,
                    entry_globals)
            else:
                quoted_tweet_dict = true_tweet
                if retweeted_tweet:
                    result = true_tweet.get("retweeted_status_result", {}) \
                        .get("result", {})
                    retweet_tweet_dict = result["legacy"]
                    retweet_tweet_dict["user"] = result["legacy"]["core"]["user_results"]
                    retweet_tweet_dict["user"] = retweet_tweet_dict["user"]["result"]["legacy"]
                    retweet_tweet_dict["user"]["id"] = int(result["user"]["result"]["rest_id"])

                result = quoted_tweet_dict.get("quoted_status_result", {}) \
                    .get("result", {})

                quoted_tweet_dict = result["legacy"]
                quoted_tweet_dict["user"] = result["legacy"]["core"]["user_results"]
                quoted_tweet_dict["user"] = quoted_tweet_dict["user"]["result"]["legacy"]
                quoted_tweet_dict["user"]["id"] = int(result["user"]["result"]["rest_id"])

                quoted_tweet = UtilBox.make_tweet(
                    quoted_tweet_dict,
                    entry_globals)

        content = retweeted_tweet.content if is_retweeted else true_tweet.get("full_text")

        medias = true_tweet.get("extended_entities", {}).get("media", [])
        urls = true_tweet.get("entities", {}).get("urls", [])
        conversation_id = int(true_tweet.get("conversation_id_str", {}))
        reply_count = true_tweet.get("reply_count")
        retweet_count = true_tweet.get("retweet_count")
        favorite_count = true_tweet.get("favorite_count")
        quote_count = true_tweet.get("quote_count")
        lang = true_tweet.get("lang")


        for link in urls:
            content = content.replace(link["url"], link["expanded_url"])

        spl_content: list[str] = content.split(" ")
        if spl_content[-1].startswith("https://t.co") and len(medias) > 0:
            spl_content.pop(-1)

        wrapped_media_regular = []
        wrapped_media_extended = []

        for media in true_tweet.get("entities", {}).get("media", []):
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
                ext_media_color=extended_media["ext_media_color"],
                features=extended_media.get("features", {}),
                id=int(extended_media["id_str"]),
                media_url=extended_media["media_url_https"],
                type=extended_media["type"],
                original_info=extended_media["original_info"],
            )
            if set_media.type == "video":
                set_media.data_info = extended_media["video_info"]
                set_media.features = extended_media.get("features",None),
            elif set_media.type != "photo":
                raise Exception(f"Unknown type: {set_media.type}@{tweet_id}")
            wrapped_media_extended.append(set_media)

        content = " ".join(spl_content)
        user = UtilBox.make_user(true_tweet["user"])

        source = true_tweet.get("source", "")
        if source:
            source = source.replace("\\/", "/")
            source = re.sub('<[^<]+?>', '', source)

        return Tweet(
            id=int(tweet_id),
            date=email.utils.parsedate_to_datetime(true_tweet['created_at']),
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
