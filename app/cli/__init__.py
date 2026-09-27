"""Operations commands `python -m app.cli <command>` (IX §56.3, §56.4).

Common contract (IX §56.3): exit codes `0` success · `1` operation failed · `2` invalid usage or configuration;
readable result on stdout; structured logs on stderr.
"""

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INVALID = 2
