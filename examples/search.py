import asyncio
from RedGalaxy import TwitterSearch


async def search_user(screen_name: str):
    """Searches for the tweets by the said user

    Args:
        screen_name (str): The screen name/username of thr user to search.
    """

    # If you have a consumer key that you want to use...
    # current_session = SessionManager(
    #     SessionMode.CONSUMER,
    #     key="<REDACTED>",
    #     secret="<REDACTED>",
    # )
    # await current_session.get_access_token()

    search_instance = TwitterSearch()
    # Or... If you have a session available
    # search_instance = TwitterSearch(session_instance=current_session)
    async for s in search_instance.search(f"(from:{screen_name})", mode="Latest"):
        print(s)


if __name__ == "__main__":
    asyncio.run(search_user("twitter"))
