# Shared HTTP session

import aiohttp


def create_session(config) -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(
        total=config.timeout
    )

    connector = aiohttp.TCPConnector(
        limit=0,  # unlimited internal pool
        ssl=config.verify_ssl,
    )

    return aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
    )