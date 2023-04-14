from . import global_instance, SessionManager, HighGravity


class TwitterSpaces:
    def __init__(self, session_instance: SessionManager = None):
        """

        :param session_instance:
        """
        if session_instance is None:
            session_instance = global_instance
        self.session = session_instance
        self.gravity = HighGravity(self.session)

    async def get_space_by_id(self, space_id):
        pass
