"""
Telnet protocol bytes definitions.
"""


class TelnetBytes:
    """Telnet protocol bytes."""

    # Telnet commands
    IAC = 255  # Interpret As Command
    WILL = 251
    WONT = 252
    DO = 253
    DONT = 254
    SB = 250  # Subnegotiation Begin
    SE = 240  # Subnegotiation End
    NOP = 241  # No Operation - used for keep-alive

    # Telnet options
    ECHO = 1
    SUPPRESS_GA = 3
    TERMINAL_TYPE = 24
    NAWS = 31
    CHARSET = 42
    MCCP1 = 85  # MUD Client Compression Protocol v1
    MCCP2 = 86  # MUD Client Compression Protocol v2
    MSDP = 69  # MUD Server Data Protocol
    GMCP = 201  # Generic MUD Communication Protocol
