"""Ensuring layout is cached appropriately: one LRU per process, one build at a time.

This module state is process-global. Do not split apart - would result in half-empty
caches for each copy.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from src.extensions import get_session_factory
from src.services.sessions.layout import Layout

_log = logging.getLogger(__name__)


# Boundaries cost a full ordered pass, so they are cached per filter set and sort
# for any per_page.
# Stale entry is still served (as_of snapshot moment), while background thread
# rebuilds.
_LAYOUT_TTL_S = 60.0
_LAYOUT_CACHE_SIZE = 64

# One pas at a time per process:
# each is a full ordered pass over the table.
# Request that cannot get the slot in time gets the plain list.
_LAYOUT_WAIT_S = 5.0
_build_slot = threading.BoundedSemaphore(1)

# Default 4MB the pass spills. Sort writes about 50MB and both hash joins run 8 batches.
#
# It was measured for 884k session copy and 128MB turned out to be enough to make
# that sort an in-memory quicksort and the hashes single-batch.
# Two concurrent builds peak at about 570MB of memory against containers 1GB cap.
# Page query is still left at default - raising the work_mem flipped the EXIST
# query for the authenticated sessions into a sequential scan over the auth_attempts.
# It made everything slower, even though the deep pages got significantly faster.
_BUILD_WORK_MEM = "128MB"

_layouts: OrderedDict[tuple[Any, ...], Layout] = OrderedDict()
_layouts_lock = threading.Lock()

# set of keys with refresh in flight
_rebuilding: set[tuple[Any, ...]] = set()

# set of keys with build in flight
_building: dict[tuple[Any, ...], threading.Event] = {}


def clear_layout_cache() -> None:
    with _layouts_lock:
        _layouts.clear()


def _store_layout(key: tuple[Any, ...], layout: Layout) -> Layout:
    with _layouts_lock:
        _layouts[key] = layout
        _layouts.move_to_end(key)
        while len(_layouts) > _LAYOUT_CACHE_SIZE:
            _layouts.popitem(last=False)
    return layout


def _set_work_mem(db: DbSession) -> None:
    """Raise work_mem for the layout pass: at the default its sort spills about
    50 MB and both hash joins run 8 batches. The value is a module constant.
    """
    db.execute(text(f"SET LOCAL work_mem = '{_BUILD_WORK_MEM}'"))


def _build_in_slot(
    db: DbSession, build: Callable[[DbSession], Layout], wait: float
) -> Layout | None:
    """Run build in the process's one slot; None if busy past `wait` or failed.

    Parallel workers disabled here. On the 2vCPU this deploys to they cost
    15-20% more CPU for no steady observed gain. Parallel hash join builds its
    table in /dev/shm, which is what ran Postgres out of shared memory once
    work_mem was raised.
    TODO: run more detailed testing on this

    Page queries keep the default parallelism.
    """
    if not _build_slot.acquire(timeout=wait):
        return None
    try:
        db.execute(text("SET LOCAL max_parallel_workers_per_gather = 0"))
        _set_work_mem(db)
        return build(db)
    except OperationalError:
        db.rollback()
        _log.exception("session layout pass failed")
        return None
    finally:
        _build_slot.release()


def _rebuild_layout(
    key: tuple[Any, ...],
    build: Callable[[DbSession], Layout],
    factory: sessionmaker[DbSession],
) -> None:
    try:
        # thread cannot reuse reuest's db session
        # not thread safe + it closes when request ends
        # that's why a factory is set up and session close
        # once with: is done
        with factory() as db:
            # attempt to take the process's single build slot if other build holds
            # it - gives up immediately and returns none
            layout = _build_in_slot(db, build, 0)
        # on success swap the fresh layout into cache under lock
        # needs LRU bump and eviction; on none - slot busy
        # it also might be OperationalError from _build_in_slot
        # keeps stale entry in place
        if layout is not None:
            _store_layout(key, layout)
    except Exception:
        _log.exception("session layout rebuild failed")
    finally:
        # release the key refresh and allow for next one
        with _layouts_lock:
            _rebuilding.discard(key)


def cached_layout(
    db: DbSession, key: tuple[Any, ...], build: Callable[[DbSession], Layout]
) -> Layout | None:
    """The key's layout, or None when it cannot be built now.

    The source of truth for the cached layout build>
    """
    with _layouts_lock:
        hit = _layouts.get(key)

        if hit is not None:
            _layouts.move_to_end(key)  # LRU - mark as recently used

        # stale hit: define and handle a stale layout
        stale = (
            hit is not None
            # older than _LAYOUT_TTL_S
            and time.monotonic() - hit.built_at > _LAYOUT_TTL_S
            # no refresh in flight
            and key not in _rebuilding
        )
        if stale:
            # if stale: claim the refresh - only one thread starts
            _rebuilding.add(key)

        # if cache miss
        # determine whether this follows or leads
        leader = follow = None
        if hit is None:
            follow = _building.get(key)  # is this key already being built?
            if follow is None:  # if not - claim the leader
                # i am the one who builds
                leader = _building[key] = threading.Event()

    # cache miss, and differnet process already is building (this one follows)
    if follow is not None:
        follow.wait(_LAYOUT_WAIT_S * 2)  # leader slot wait + pass
        with _layouts_lock:
            return _layouts.get(key)  # leaders layout or None

    # cache miss, and this process is building (leader)
    if leader is not None:
        try:
            # wait up to 5 seconds for the slot - then pass
            layout = _build_in_slot(db, build, _LAYOUT_WAIT_S)
            return None if layout is None else _store_layout(key, layout)
        finally:
            with _layouts_lock:
                del _building[key]  # next miss elects new leader
            leader.set()  # wake the followers - success or not

    # start a background thread rebuild
    # right before the return - so that still the stale one is returned
    if stale:
        threading.Thread(
            target=_rebuild_layout,
            args=(key, build, get_session_factory()),
            daemon=True,
        ).start()

    return hit
