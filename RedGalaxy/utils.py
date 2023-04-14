import email.utils
import re
import typing

from . import User, Tweet, Media, UserCounts, ExtendedMedia


class UtilBox:
    @staticmethod
    def make_user(user_data: dict) -> User:
        """Creates a user object from a legacy user data.

        There is some transforms performed such as:
         - replacing the profile url with a larger (400x400px variant).
         - Unfurling urls (removing t.co links into full links)

        :param user_data: The dictionary containing user data.
        :return: A "User" dataclass.
        """
        username = user_data.get("screen_name")
        displayname = user_data.get("name")
        description = user_data.get("description")

        for url in user_data.get("entities", {}).get("description", {}).get("urls", []):
            description = description.replace(url.get("url"), url.get("expanded_url"))
        links = user_data.get("entities", {}).get("url", {}).get("urls", [])
        link_url = None
        if links:
            link_url = links[0]["expanded_url"]

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
        """
        Creates a Tweet from GraphQL/Web API's
        :param true_tweet: The "Real" Tweet object
        :param entry_globals: Entry globals from the search api.
        :param recurse: Recurse into quote tweets and retweets. You should not need to touch this.
        :return:
        """
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

        return UtilBox.legacy_tweet(base_tweet, quoted_tweet, retweeted_tweet, user)

    @staticmethod
    def legacy_tweet(
        base_tweet: dict, quoted_tweet: Tweet, retweeted_tweet: Tweet, user: User
    ):
        """
        Creates a Tweet from a base_tweet, quoted and retweeted tweet.
        :param base_tweet: The base Tweet.
        :param quoted_tweet: The quoted Tweet. This needs to be a Tweet object.
        :param retweeted_tweet: The retweeted Tweet. This needs to be a Tweet object as well.
        :param user: The User that made the original/base Tweet. Needs to be a User object.
        :return:
        """
        content = (
            retweeted_tweet.content if retweeted_tweet else base_tweet.get("full_text")
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
                ext_media_color=extended_media["ext_media_color"],
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
    def api_tweet(api_tweet: dict, recurse: bool = True):
        """
        Wraps around
        :param api_tweet:
        :param recurse:
        :return:
        """

        quoted_tweet = api_tweet.get("quoted_status", None)
        retweeted_tweet = api_tweet.get("retweeted_status", None)

        if quoted_tweet:
            if recurse:
                quoted_tweet = UtilBox.api_tweet(quoted_tweet, recurse=False)
            else:
                quoted_tweet = None
        if retweeted_tweet:
            if recurse:
                retweeted_tweet = UtilBox.api_tweet(retweeted_tweet, recurse=False)
            else:
                retweeted_tweet = None

        user = UtilBox.make_user(api_tweet["user"])
        return UtilBox.legacy_tweet(api_tweet, quoted_tweet, retweeted_tweet, user)
