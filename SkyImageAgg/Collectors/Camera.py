from abc import ABC, abstractmethod


class Cam(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def login(self, username, pwd):
        """

        Parameters
        ----------
        address
        username
        pwd
        """
        pass

    @abstractmethod
    def cap_pic(self, output):
        """

        Parameters
        ----------
        output
        """
        pass

    @abstractmethod
    def cap_video(self, output):
        """

        Parameters
        ----------
        output
        """
        pass
