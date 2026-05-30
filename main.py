"""Phonexi entry point."""

from phonexi.listener import HotkeyListener


def main() -> None:
    listener = HotkeyListener()
    try:
        listener.start()
    except KeyboardInterrupt:
        print("\n[Phonexi] Stopped.")


if __name__ == "__main__":
    main()
