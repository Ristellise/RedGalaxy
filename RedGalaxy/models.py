import dataclasses
import datetime
import pathlib
import typing


# Adapted from  SNScrape
# (https://github.com/JustAnotherArchivist/snscrape/blob/master/snscrape/modules/twitter.py)


@dataclasses.dataclass
class Media:
    display_url: str
    expanded_url: str
    id: int
    media_url: str
    original_info: dict
    type: str
    features: dict

    @property
    def original_url(self):
        if self.type in ["photo", "gif"]:  # Unsure of gif.
            return f"{self.media_url}:orig"

    @property
    def large_url(self):
        if self.type in ["photo", "gif"]:  # Unsure of gif.
            return f"{self.media_url}:large"

    @property
    def medium_url(self):
        if self.type in ["photo", "gif"]:  # Unsure of gif.
            return f"{self.media_url}:medium"

    @property
    def small_url(self):
        if self.type in ["photo", "gif"]:  # Unsure of gif.
            return f"{self.media_url}:small"


@dataclasses.dataclass
class UploadMedia:
    path: pathlib.Path
    media_type: str
    media_category: str


@dataclasses.dataclass
class VideoVariant:
    bitrate: int
    content_type: str
    url: str


@dataclasses.dataclass
class VideoMeta:
    aspect: typing.List[int]
    duration: float
    variants: typing.List[VideoVariant]


@dataclasses.dataclass
class ExtendedMedia(Media):
    ext_media_availability: dict
    ext_media_color: dict
    data_info: typing.Optional[dict] = None
    # Video Only?
    additional_media_info: typing.Optional[dict] = None
    # features: typing.Optional[dict] = None

    @property
    def video_meta(self) -> typing.Optional[VideoMeta]:
        if self.data_info is not None and self.type == "video":
            meta = VideoMeta(
                self.data_info.get("aspect", [-1, -1]),
                self.data_info.get("duration_millis", 0) / 1000,
                [
                    VideoVariant(
                        variant.get("bitrate", -1),
                        variant.get("content_type", "video/unknown"),
                        variant.get("url", "https://video.twimg.com/"),
                    )
                    for variant in self.data_info.get("variants", [])
                ],
            )
            return meta
        else:
            return None


@dataclasses.dataclass
class Tweet:
    id: int
    date: datetime.datetime

    # Content is a bit special. For retweets it grabs the retweeted tweet
    # as well as strips the trailing t.co for tweets with media.
    content: str
    links: typing.List[str]
    user: "User"
    replies: int
    retweets: int
    favorites: int
    quotes: int
    conversion_id: int
    language: str
    source: str  # May not exist anymore
    media: typing.Optional[typing.List["Media"]] = None
    extended_media: typing.Optional[typing.List["ExtendedMedia"]] = None
    retweeted_tweet: typing.Optional["Tweet"] = None
    quoted_tweet: typing.Optional["Tweet"] = None
    urls: typing.Optional[typing.List] = None

    @property
    def url(self):
        return f"https://twitter.com/{self.user.username}/status/{self.id}"


@dataclasses.dataclass
class UserCounts:
    followers: typing.Optional[int] = None
    friends: typing.Optional[int] = None
    statuses: typing.Optional[int] = None
    favourites: typing.Optional[int] = None
    listed: typing.Optional[int] = None
    media: typing.Optional[int] = None


@dataclasses.dataclass
class User:
    username: str
    description: str
    id: int
    user_counts: UserCounts
    verified: bool  # Includes Verified type
    display_name: typing.Optional[str] = None
    verified_type: typing.Optional[str] = None  # Includes Verified type
    created: typing.Optional[datetime.datetime] = None

    location: typing.Optional[str] = None
    protected: typing.Optional[bool] = False
    link_url: typing.Optional[str] = None
    profile_image_url: typing.Optional[str] = None
    profile_banner_url: typing.Optional[str] = None

    @property
    def url(self):
        return f"https://twitter.com/{self.username}"

    @classmethod
    def create_blank(cls, username, id):
        return cls(username, "", id, UserCounts(), False)
