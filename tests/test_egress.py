"""The way out (ADR-0009): only the allowlist's hosts, over HTTPS, a redirect answered as it came and never
followed. HTTPS is answered here by a handler in place of urllib's own, so nothing leaves the computer."""

import email.message
import io
import urllib.error
import urllib.request
import urllib.response
from typing import ClassVar

import pytest

from iplikci import egress
from iplikci.settings import config

# The real functions, taken before the tests' guard (conftest) puts its refusal in their place.
HTTPS_GET = egress.https_get
HTTPS_POST = egress.https_post
SETTINGS = config.Settings()


class FakeHttps(urllib.request.HTTPSHandler):
    """urllib's HTTPS handler with the network taken out: each request gets the next of `answers` (status, headers,
    body), or `failure` raised; every address asked and every request is kept. Its state is the class's: egress
    makes a handler of its own for each request."""

    answers: ClassVar[list[tuple[int, dict[str, str], bytes]]] = []
    failure: ClassVar[Exception | None] = None
    asked: ClassVar[list[str]] = []
    requests: ClassVar[list[urllib.request.Request]] = []

    def https_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
        FakeHttps.asked.append(req.full_url)
        FakeHttps.requests.append(req)
        if FakeHttps.failure is not None:
            raise FakeHttps.failure
        status, headers, body = FakeHttps.answers[len(FakeHttps.asked) - 1]
        message = email.message.Message()
        for name, value in headers.items():
            message[name] = value
        answer = urllib.response.addinfourl(io.BytesIO(body), message, req.full_url, status)
        answer.msg = "OK" if status < 300 else "Found" if status < 400 else "Error"  # as http.client's responses
        return answer


@pytest.fixture
def https(monkeypatch) -> type[FakeHttps]:
    FakeHttps.answers, FakeHttps.failure, FakeHttps.asked, FakeHttps.requests = [], None, [], []
    monkeypatch.setattr(urllib.request, "HTTPSHandler", FakeHttps)
    return FakeHttps


def test_the_rate_providers_and_evds_are_on_the_allowlist_and_evds_old_address_not():
    hosts = egress.allowed_hosts(SETTINGS)
    assert {egress.TCMB, egress.ECB, egress.FRANKFURTER, egress.EVDS} <= hosts
    assert (egress.TCMB, egress.EVDS) == ("www.tcmb.gov.tr", "evds3.tcmb.gov.tr")
    assert "evds2.tcmb.gov.tr" not in hosts  # it only redirects to evds3, and a redirect is never followed


def test_a_get_brings_the_answer_and_its_status_an_error_status_too(https):
    https.answers = [(200, {}, b"<Tarih_Date/>"), (404, {}, b"yok")]
    assert HTTPS_GET(egress.TCMB, "/kurlar/today.xml", SETTINGS) == (200, b"<Tarih_Date/>")
    assert HTTPS_GET(egress.TCMB, "/kurlar/202611/01112026.xml", SETTINGS) == (404, b"yok")
    assert https.asked == [
        "https://www.tcmb.gov.tr/kurlar/today.xml",
        "https://www.tcmb.gov.tr/kurlar/202611/01112026.xml",
    ]
    assert [r.get_method() for r in https.requests] == ["GET", "GET"]


def test_a_get_carries_the_headers_it_is_given(https):
    https.answers = [(200, {}, b"{}")]
    HTTPS_GET(egress.FRANKFURTER, "/v1/latest", SETTINGS, headers={"Accept": "application/json"})
    assert https.requests[0].get_header("Accept") == "application/json"


def test_a_host_off_the_allowlist_is_refused_before_anything_leaves(https):
    with pytest.raises(egress.Refused):
        HTTPS_GET("kurlar.example", "/today.xml", SETTINGS)
    with pytest.raises(egress.Refused):
        HTTPS_POST("kurlar.example", "/form", {"a": "b"}, SETTINGS)
    assert https.asked == []


def test_a_path_that_would_name_another_host_is_refused(https):
    # https://www.tcmb.gov.tr@kurlar.example/ goes to kurlar.example: the allowed host would only be a user name.
    with pytest.raises(ValueError):
        HTTPS_GET(egress.TCMB, "@kurlar.example/today.xml", SETTINGS)
    assert https.asked == []


def test_a_redirect_is_answered_as_it_came_and_never_followed(https):
    https.answers = [
        (302, {"Location": "https://kurlar.example/today.xml"}, b"tasindi"),
        (200, {}, b"<Tarih_Date/>"),
    ]
    assert HTTPS_GET(egress.TCMB, "/kurlar/today.xml", SETTINGS) == (302, b"tasindi")
    assert https.asked == ["https://www.tcmb.gov.tr/kurlar/today.xml"]  # the other host was never asked


def test_no_answer_is_unreachable_and_the_message_names_the_host_only(https):
    https.failure = urllib.error.URLError("zaman aşımı")
    with pytest.raises(egress.Unreachable) as caught:
        HTTPS_GET(egress.ECB, "/stats/eurofxref/eurofxref-daily.xml", SETTINGS)
    assert "www.ecb.europa.eu" in str(caught.value) and "eurofxref" not in str(caught.value)


def test_the_tests_refuse_every_get_as_they_refuse_posts():
    with pytest.raises(AssertionError, match="network"):
        egress.https_get(egress.TCMB, "/kurlar/today.xml", SETTINGS)
    with pytest.raises(AssertionError, match="network"):
        egress.https_post(egress.TELEGRAM, "/bot1:a/getMe", {}, SETTINGS)
