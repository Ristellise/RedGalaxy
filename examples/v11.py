# v11.py
#
# v11.py shows how to use RedGalaxy to interact with v1.1 routes.

from RedGalaxy import SessionManager, SessionMode

CONSUMER_KEY = "<REDACTED>"
CONSUMER_SECRET = "<REDACTED>"


async def list_following_ids(screen_name: str):
    """Gets a list of user ids that the user follows.

    Args:
        screen_name (str): The screen name/username for the user.
    """

    current_session = SessionManager(
        SessionMode.CONSUMER,
        key=CONSUMER_KEY,
        secret=CONSUMER_SECRET,
    )
    # For consumer based sessions, you are required to grab your access token for inital access.
    await current_session.get_access_token()

    base_url = f"https://api.twitter.com/1.1/friends/ids.json?screen_name={screen_name}&count=5000"

    # .get() Takes care of all the parameters, including guest tokens.
    # .get() User-Agent simulates a desktop browser.
    response = await current_session.get(base_url)
    # response returns a httpx response object which you do fun things with.
    if response.status_code != 200:
        print(response.content)
        response.raise_for_status()

    # Grab the ids that the user is following
    ids_content = response.json()
    ids_int = ids_content.get("ids", [])
    counter = 0

    all_ids = []
    while len(ids_int) > 0:
        counter += len(ids_int)
        all_ids.extend(ids_int)

        # Check for next cursor
        nxt = ids_content["next_cursor"]
        cursor_url = base_url + f"&cursor={nxt}"
        if nxt == 0:
            counter += len(ids_int)
            all_ids.extend(ids_int)
            break

        # Read the response
        response = await current_session.get(cursor_url)
        ids_content = response.json()

        # The user's following IDs.
        ids_int = ids_content.get("ids", [])
    print(f"Following: {counter} users.")
    return all_ids
