class NonBlockQueue:
    """
    This is regular class, its instance can be passed between classes and threads.

    Usage examples:
    1. Can store current requested domain.
    Since it is passed between classes as an instance, it will be the same instance between classes and threads
    as long as it is used in the same process.
    2. Can store current domain that was set during extended sni.
    Since it is passed between classes as an instance, it will be the same instance between classes and threads
    as long as it is used in the same process.
    """

    def __init__(self):
        self.queue: str = str()
