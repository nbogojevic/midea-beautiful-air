from __future__ import annotations

from midea_beautiful_dehumidifier.command import base_command



class midea_service:
    """ Base class for cloud and lan service"""
    
    def status(self,
               cmd: base_command,
               id: str | int = None, protocol: int = None) -> list[bytearray]:
        """ Retrieves appliance status """

        return []

    def apply(self,
              cmd: base_command,
              id: str | int = None, protocol: int = None) -> bytearray:
        """ Applies settings to appliance """

        return bytearray()

    def authenticate(self, args) -> bool:
        return False

    def target(self) -> str:
        return "None"
