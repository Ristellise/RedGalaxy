import io
import logging
import typing

from . import (
    SessionManager,
    HighGravity,
    RedGalaxyException,
    UploadMedia,
    UploadTweet,
    Tweet,
    UtilBox,
    BaseTwitter,
)


class TwitterTweet(BaseTwitter):
    def __init__(self, session_instance: SessionManager):
        """
        Routes relating to posting and/or updating tweets.

        Essentially this uses the legacy v1.1 (Which for some reason has not been deprecated. lol)

        :param session_instance:
        """
        super().__init__(session_instance)
        if session_instance.is_bearer or not session_instance.auth:
            raise RedGalaxyException(
                "Expected a signed in account. Got either a bearer token or an unauthed account."
            )
        self.gravity = HighGravity(self.session)
        self._routes = []
        self.logging = logging.getLogger("TwitterTweet")

    async def upload_media(self, media: UploadMedia):
        """Uploads the tweet media.

        You don't have to call this specifically if you are going to call post_tweet later.
        However, it is exposed for those who want to use it.

        :param media: An UploadMedia dataclass. All non-optional arguments are required.
        :return: A UploadMedia response with media_id and size filled.
        """
        self.logging.info(f"Uploading Media: {media}")
        if isinstance(media.fp, io.BytesIO):
            if not media.fp.seekable():
                raise Exception
            size = media.fp.getbuffer().nbytes
        else:
            pass
        # After upload, set metadata: https://twitter.com/i/api/1.1/media/metadata/create.json
        # {"media_id":"<media_id>","alt_text":{"text":"<alt_text>"},"sensitive_media_warning":["adult_content","graphic_violence","other"]}

    async def post_tweet(
        self,
        tweet_content: UploadTweet,
        reply_to: typing.Optional[typing.Union[Tweet, int]],
    ):
        """Post the... Well Tweet
        :param tweet_content:
        :return:
        """
        uploaded_media: typing.List[UploadMedia] = []
        if tweet_content.media:
            for media in tweet_content.media:
                uploaded_media.append(await self.upload_media(media))
        if reply_to:
            if isinstance(reply_to, Tweet):
                reply_to = reply_to.id
            elif isinstance(reply_to, int):
                pass
            else:
                raise RedGalaxyException(
                    f"reply_to: {reply_to} is not the expected Tweet object or tweet id."
                )
        tweet = {
            "status": tweet_content.status,
            "in_reply_to_status_id": reply_to,
            "" "media_ids": [media.id for media in uploaded_media],
        }

        await self.session.post(
            f"https://api.twitter.com/1.1/statuses/retweet/{tweet_content}"
        )

    async def retweet_tweet(self, tweet_content: typing.Union[int, Tweet]):
        if isinstance(tweet_content, Tweet):
            tweet_content = tweet_content.id
        r = await self.session.post(
            f"https://api.twitter.com/1.1/statuses/retweet/{tweet_content}"
        )
        if r.status_code == 200:
            UtilBox.api_tweet(r.json())
