class BaseDevicePlugin:
    """
    Base class for S.A.I. Device Plugins.
    New device types (Smart Plugs, Android, Windows) should subclass this to define 
    their capabilities and validate commands before they hit the network queue.
    """
    @property
    def device_type(self) -> str:
        """Return the lowercase string type of the device (e.g. 'windows', 'android')"""
        raise NotImplementedError

    def get_capabilities(self) -> list:
        """
        Return a list of strings or dicts explaining what this device type can do.
        e.g. ['mouse_move', 'press_key', 'shell', 'open_app']
        """
        return []

    def validate_command(self, command: str, params: dict) -> tuple[bool, str]:
        """
        Validates whether a command and its parameters are supported and safe 
        to route to this device type.
        Returns: (is_valid: bool, error_message: str)
        """
        return True, ""
