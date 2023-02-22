import asyncio
import typing

from . import global_instance, SessionManager, UtilBox, HighGravity


class TwitterSpaces:
    def __init__(self, session_instance: SessionManager = None):
        """

        :param session_instance:
        """
        if session_instance is None:
            session_instance = global_instance
        self.session = session_instance
        self.gravity = HighGravity(self.session)

    async def GetSpaceById(self):