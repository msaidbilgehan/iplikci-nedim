"""What the API's parts share: the workspace, who may come in, and the service's own details."""

import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from fastapi import Request

from ..app.access import LoginKeys
from ..app.bridge import PairingCodes
from ..app.intake import Plan
from ..app.workspace import Workspace

PLANS_KEPT = 8  # plans shown and not yet applied


@dataclass(frozen=True)
class Context:
    ws: Workspace
    token: str  # the API token of the command line and the MCP bridge
    keys: LoginKeys = field(default_factory=LoginKeys)
    pairing: PairingCodes = field(default_factory=PairingCodes)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).replace(microsecond=0).isoformat())
    pid: int = field(default_factory=os.getpid)
    stream_limit: float = 600.0  # an event stream closes after this many seconds; the browser reconnects
    poll: float = 1.0  # how often an event stream looks for new events
    _plans: OrderedDict[str, Plan] = field(default_factory=OrderedDict[str, Plan])
    _plans_lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def port(self) -> int:
        return self.ws.port

    @property
    def hosts(self) -> frozenset[str]:
        """The Host headers the service answers (DNS rebinding sends another name)."""
        return frozenset({f"127.0.0.1:{self.port}", f"localhost:{self.port}"})

    @property
    def origins(self) -> frozenset[str]:
        return frozenset(f"http://{host}" for host in self.hosts)

    @property
    def cookie(self) -> str:
        """The session cookie's name; cookies ignore the port, so it carries the port."""
        return f"iplikci_oturum_{self.port}"

    def login_url(self, key: str) -> str:
        return f"http://127.0.0.1:{self.port}/giris?anahtar={key}"

    def keep(self, plan: Plan) -> None:
        """A plan shown to the user, until it is applied; the oldest go when too many wait."""
        with self._plans_lock:
            self._plans[plan.id] = plan
            while len(self._plans) > PLANS_KEPT:
                self._plans.popitem(last=False)

    def plan(self, plan_id: str) -> Plan | None:
        with self._plans_lock:
            return self._plans.get(plan_id)

    def forget(self, plan_id: str) -> None:
        with self._plans_lock:
            self._plans.pop(plan_id, None)


def context_of(request: Request) -> Context:
    return cast(Context, request.app.state.context)
