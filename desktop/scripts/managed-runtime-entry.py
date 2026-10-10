"""Frozen entry point; the central package owns every operation and lifecycle decision."""

from multiprocessing import freeze_support

from bat_agent_connector.managed_runtime import main

if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
