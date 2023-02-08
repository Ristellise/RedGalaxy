# RedGalaxy
[*A galaxy of children who've only seen red.*](https://www.youtube.com/watch?v=ojnD9WtLmLc)

Unofficial Twitter API's wrapped in a nice present.

## What?

This package wraps around the unofficial "internal" twitter API's to provide a similar as the previous free rate limits.

## How?

Usage is pretty simple.

```py
import asyncio

from RedGalaxy import TwitterUser, SessionManager, Tweet, User, TwitterSearch


async def main():
    sm = SessionManager("__BEARER_TOKEN__")

    # Contains endpoints for specific tweets and users.
    twitUser = TwitterUser()

    # If no SessionManager is provided, it will use a default bearer token.
    # You can access the "default" instance with a `global_instance` import.
    # twitUser = TwitterUser(sm)

    # Returns a dataclass tweet
    tweet: Tweet = await twitUser.get_tweet(1622961462032445440)
    print(tweet.content)
    # print(tweet.user) # To access the user. object.

    # Orr get retrieve a user.
    user: User = await twitUser.get_user("TwitterDev")

    # Wraps around Twitter search api...
    twitSearch = TwitterSearch()

    # Searching is done by an async generator. Search parameters are the same as web UI paramters. 
    async for tweet in twitSearch.search("(from:SYACVG) lol", limit=10, mode="latest"):
        # Same as get_tweet(), returns a tweet dataclass.
        print(tweet)

    # Stream works in a similar way.
    async for tweet in twitSearch.stream("(from:SYACVG) lol", limit=10, mode="latest"):
        # Same as get_tweet(), returns a tweet dataclass.
        print(tweet)


if __name__ == '__main__':
    asyncio.run(main())
```

## Why?

Because blame the "SpaceX" Guy. Yes really. This is mainly out of spite lol.

## Notes?

- Search/Stream notes:
  - Twitter search/stream does have some character limits. Which makes it not ideal for 20+ users filtered streams. You can chunk them into multiple different search/streams.
  - Not to sure if it will catch shadowbanned users. The bearer token I use should alleviate this issue, but Your mileage may vary.

## TODO

- Add API's for uploading and sending tweets.
- Backtracking for streams. If the stream is going too fast, there will be dropped tweets.

## Bugs?

There will be bugs. Mainly some more extreme testing would be nice.