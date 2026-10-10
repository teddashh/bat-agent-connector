"""Bounded subprocess capture with concurrent pipe draining."""

import asyncio
import contextlib


async def capture(proc, limit: int = 1024 * 1024) -> tuple[bytes, bytes]:
    async def read(stream):
        if stream is None:
            return b""
        output = bytearray()
        while chunk := await stream.read(min(65536, limit + 1 - len(output))):
            output.extend(chunk)
            if len(output) > limit:
                raise ValueError("subprocess output exceeds capture limit")
        return bytes(output)

    readers = [asyncio.create_task(read(stream)) for stream in (proc.stdout, proc.stderr)]
    try:
        out, err = await asyncio.gather(*readers)
        await proc.wait()
        return out, err
    except BaseException:
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
        for reader in readers:
            reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
        async def drain(stream):
            if stream is not None:
                while await stream.read(65536):
                    pass

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                asyncio.gather(*(drain(stream) for stream in (proc.stdout, proc.stderr))), 1.0
            )
        await proc.wait()
        raise
