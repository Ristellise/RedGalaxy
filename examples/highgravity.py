# highgravity.py
#
# This examples shows how to use highgravity to retrieve twitter routes.

from RedGalaxy import SessionManager, SessionMode, HighGravity


async def float_gravity():

    # If you have a consumer key that you want to use...
    # HighGravity does not need a consumer key,
    # but in this example it is shown with a consumer key.
    current_session = SessionManager(
        SessionMode.CONSUMER,
        key="<REDACTED>",
        secret="<REDACTED>",
    )
    await current_session.get_access_token()

    high_gravity = HighGravity(sessionInstance=current_session)

    # Retrieve all the routes here.
    routes = await high_gravity.retrieve_routes()
    # Routes returns as a dictionary with the key being the graphQL name.
    # (eg. UserTweetsAndReplies)

    if not routes.get("UserTweetsAndReplies"):
        raise Exception()

    # To get the route data, do the following:
    route = routes.get("UserTweetsAndReplies", [])

    # route returns a url and a list of feature flags for the said route.
    url, feature_flags = route