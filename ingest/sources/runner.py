"""Bound uncooperative third-party fetches in a killable subprocess."""
import multiprocessing as mp
import time
from .base import SourceError, source_error


def create_source(name):
    if name == 'jugaad':
        from .jugaad_source import JugaadSource
        return JugaadSource()
    if name == 'openchart':
        from .openchart_source import OpenChartSource
        return OpenChartSource()
    if name == 'yfinance':
        from .yfinance_source import YFinanceSource
        return YFinanceSource()
    raise ValueError(f'Unknown source: {name}')


def _worker(connection, name, symbol, start, end):
    try:
        connection.send(('ok', create_source(name).fetch_daily(symbol, start, end)))
    except Exception as exc:
        error = exc if isinstance(exc, SourceError) else source_error(exc)
        connection.send(('error', str(error), error.blocked, error.transient))
    finally:
        connection.close()


def fetch_bounded(name, symbol, start, end, timeout=60):
    context = mp.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(writer, name, symbol, start, end))
    process.start()
    writer.close()
    try:
        deadline = time.monotonic() + timeout
        while not reader.poll(min(0.2, max(0, deadline - time.monotonic()))):
            if not process.is_alive():
                raise SourceError('Source worker exited without a result', transient=True)
            if time.monotonic() >= deadline:
                raise SourceError(f'Source timed out after {timeout}s', transient=True)
        try:
            result = reader.recv()
        except EOFError as exc:
            raise SourceError('Source worker disconnected', transient=True) from exc
        if result[0] == 'error':
            raise SourceError(result[1], blocked=result[2], transient=result[3])
        return result[1]
    finally:
        reader.close()
        process.join(timeout=0.2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
