from __future__ import annotations

from datetime import datetime

import httpx

from proton_agent_suite.domain.enums import ErrorCode
from proton_agent_suite.domain.errors import make_error
from proton_agent_suite.domain.value_objects import RadicaleSettings


class RadicaleHttpClient:
    def __init__(self, settings: RadicaleSettings) -> None:
        self.settings = settings

    def _client(self) -> httpx.Client:
        verify = not self.settings.allow_insecure
        return httpx.Client(auth=(self.settings.username or "", self.settings.password or ""), verify=verify, timeout=15.0)

    def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        try:
            with self._client() as client:
                response = client.request(method, url, **kwargs)
        except httpx.ConnectError as exc:
            raise make_error(ErrorCode.CALENDAR_UNREACHABLE, "CalDAV endpoint is unreachable", {"url": url}) from exc
        except httpx.HTTPError as exc:
            raise make_error(ErrorCode.CALENDAR_UNREACHABLE, "CalDAV request failed", {"reason": str(exc)}) from exc
        if response.status_code == 401:
            raise make_error(ErrorCode.CALENDAR_AUTH_FAILED, "CalDAV authentication failed", {"url": url})
        if response.status_code >= 400:
            raise make_error(ErrorCode.CALENDAR_DISCOVERY_FAILED, f"CalDAV request failed with HTTP {response.status_code}", {"url": url, "status_code": response.status_code, "body": response.text[:1000]})
        return response

    def propfind(self, url: str, depth: int = 1, body: str | None = None) -> httpx.Response:
        headers = {"Depth": str(depth), "Content-Type": "application/xml; charset=utf-8"}
        return self._request("PROPFIND", url, headers=headers, content=body or "")

    def report(self, url: str, body: str) -> httpx.Response:
        headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
        return self._request("REPORT", url, headers=headers, content=body)

    def put(self, url: str, body: str, etag: str | None = None) -> httpx.Response:
        headers = {"Content-Type": "text/calendar; charset=utf-8"}
        if etag:
            headers["If-Match"] = etag
        return self._request("PUT", url, headers=headers, content=body)

    def delete(self, url: str, etag: str | None = None) -> httpx.Response:
        headers: dict[str, str] = {}
        if etag:
            headers["If-Match"] = etag
        return self._request("DELETE", url, headers=headers)

    def mkcalendar(self, url: str, name: str) -> httpx.Response:
        body = f"""<?xml version="1.0" encoding="utf-8" ?>
<C:mkcalendar xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
  <D:set>
    <D:prop>
      <D:displayname>{name}</D:displayname>
    </D:prop>
  </D:set>
</C:mkcalendar>
"""
        headers = {"Content-Type": "application/xml; charset=utf-8"}
        return self._request("MKCALENDAR", url, headers=headers, content=body)
