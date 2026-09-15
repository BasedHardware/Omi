"""Hermetic unit tests for Public Holidays Omi integration.

No third-party runtime dependencies required. Runs deterministically under
both standard library `python3 -S` and `pytest`.
"""

import asyncio
from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


def load_app():
    class DummyState:
        pass

    class DummyFastAPI:
        def __init__(self, **kwargs):
            self.routes = []
            self.lifespan = kwargs.get("lifespan")
            self.state = DummyState()

        def get(self, path, **kwargs):
            return self._route("GET", path, kwargs.get("response_model"))

        def post(self, path, **kwargs):
            return self._route("POST", path, kwargs.get("response_model"))

        def exception_handler(self, exc_class):
            def decorator(func):
                return func

            return decorator

        def _route(self, method, path, response_model):
            def decorator(func):
                self.routes.append({
                    "method": method,
                    "path": path,
                    "func": func,
                    "response_model": response_model,
                })
                return func

            return decorator

    class DummyBaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def Field(default=None, **_kwargs):
        return default

    def field_validator(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    class HTTPError(Exception):
        pass

    class HTTPStatusError(HTTPError):
        def __init__(self, message=None, response=None):
            super().__init__(message)
            self.response = response or types.SimpleNamespace(status_code=500)

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            self.is_closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.is_closed = True

        async def aclose(self):
            self.is_closed = True

        async def get(self, url, params=None):
            raise NotImplementedError

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = DummyFastAPI
    fastapi.Request = object
    fastapi_responses = types.ModuleType("fastapi.responses")
    fastapi_responses.HTMLResponse = str
    fastapi_responses.JSONResponse = dict
    fastapi_exceptions = types.ModuleType("fastapi.exceptions")

    class RequestValidationError(Exception):
        pass

    fastapi_exceptions.RequestValidationError = RequestValidationError

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = DummyBaseModel
    pydantic.Field = Field
    pydantic.field_validator = field_validator

    httpx = types.ModuleType("httpx")
    httpx.HTTPError = HTTPError
    httpx.HTTPStatusError = HTTPStatusError
    httpx.AsyncClient = DummyAsyncClient

    spec = importlib.util.spec_from_file_location("public_holidays_hermetic", Path(__file__).with_name("main.py"))
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "fastapi": fastapi,
            "fastapi.responses": fastapi_responses,
            "fastapi.exceptions": fastapi_exceptions,
            "pydantic": pydantic,
            "httpx": httpx,
        },
    ):
        spec.loader.exec_module(module)
    return module


main = load_app()


class RouteWiringTests(unittest.TestCase):
    def test_routes_registered_with_correct_methods_and_paths(self):
        registered = {(r["method"], r["path"]): r for r in main.app.routes}
        expected_endpoints = {
            ("GET", "/"),
            ("GET", "/health"),
            ("GET", "/.well-known/omi-tools.json"),
            ("POST", "/tools/get_public_holidays"),
            ("POST", "/tools/get_next_public_holidays"),
            ("POST", "/tools/get_long_weekends"),
            ("POST", "/tools/list_supported_countries"),
        }
        for endpoint in expected_endpoints:
            self.assertIn(endpoint, registered)

        self.assertIs(registered[("POST", "/tools/get_public_holidays")]["response_model"], main.ChatToolResponse)
        self.assertIs(registered[("POST", "/tools/get_next_public_holidays")]["response_model"], main.ChatToolResponse)
        self.assertIs(registered[("POST", "/tools/get_long_weekends")]["response_model"], main.ChatToolResponse)
        self.assertIs(registered[("POST", "/tools/list_supported_countries")]["response_model"], main.ChatToolResponse)

    def test_tools_manifest_matches_registered_routes(self):
        manifest = asyncio.run(main.omi_tools())
        tools = manifest["tools"]
        self.assertEqual(len(tools), 4)
        tool_endpoints = {t["endpoint"]: t["method"] for t in tools}
        self.assertEqual(
            tool_endpoints,
            {
                "/tools/get_public_holidays": "POST",
                "/tools/get_next_public_holidays": "POST",
                "/tools/get_long_weekends": "POST",
                "/tools/list_supported_countries": "POST",
            },
        )

    def test_root_and_health_endpoints(self):
        health_resp = asyncio.run(main.health())
        self.assertEqual(health_resp, {"status": "ok"})

        root_resp = asyncio.run(main.root())
        self.assertIn("Omi Public Holidays Integration", root_resp)


class HelperFunctionTests(unittest.TestCase):
    def test_normalize_country_code_valid(self):
        self.assertEqual(main._normalize_country_code("us"), "US")
        self.assertEqual(main._normalize_country_code("  de  "), "DE")
        self.assertEqual(main._normalize_country_code("JP"), "JP")

    def test_normalize_country_code_invalid(self):
        with self.assertRaises(ValueError):
            main._normalize_country_code("USA")
        with self.assertRaises(ValueError):
            main._normalize_country_code("12")
        with self.assertRaises(ValueError):
            main._normalize_country_code("")

    def test_format_list(self):
        self.assertEqual(main._format_list(None), "all regions")
        self.assertEqual(main._format_list([]), "all regions")
        self.assertEqual(main._format_list("not-a-list"), "all regions")
        self.assertEqual(main._format_list(["US-CA", "US-NY"]), "US-CA, US-NY")
        long_list = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]
        self.assertEqual(main._format_list(long_list), "R1, R2, R3, R4, R5 +2 more")

    def test_format_holiday_valid(self):
        holiday = {
            "date": "2026-01-01",
            "name": "New Year's Day",
            "localName": "New Year's Day",
            "global": True,
            "types": ["Public"],
        }
        res = main._format_holiday(holiday)
        self.assertEqual(res, "- 2026-01-01: New Year's Day (global; Public)")

    def test_format_holiday_local_name_difference(self):
        holiday = {
            "date": "2026-10-03",
            "name": "German Unity Day",
            "localName": "Tag der Deutschen Einheit",
            "global": True,
            "types": ["Public"],
        }
        res = main._format_holiday(holiday)
        self.assertIn("German Unity Day / Tag der Deutschen Einheit", res)

    def test_format_holiday_regional(self):
        holiday = {
            "date": "2026-04-20",
            "name": "Patriots' Day",
            "localName": "Patriots' Day",
            "global": False,
            "counties": ["US-MA", "US-ME"],
            "types": None,
        }
        res = main._format_holiday(holiday)
        self.assertIn("US-MA, US-ME", res)

    def test_format_holiday_non_dict(self):
        self.assertEqual(main._format_holiday(None), "- Unknown holiday")
        self.assertEqual(main._format_holiday("string"), "- Unknown holiday")

    def test_format_long_weekend_valid(self):
        weekend = {
            "startDate": "2026-05-22",
            "endDate": "2026-05-25",
            "dayCount": 4,
            "needBridgeDay": False,
            "bridgeDays": [],
        }
        res = main._format_long_weekend(weekend)
        self.assertEqual(res, "- 2026-05-22 to 2026-05-25: 4 days; no bridge day needed")

    def test_format_long_weekend_with_bridge_days(self):
        weekend = {
            "startDate": "2026-05-21",
            "endDate": "2026-05-24",
            "dayCount": 4,
            "needBridgeDay": True,
            "bridgeDays": ["2026-05-22"],
        }
        res = main._format_long_weekend(weekend)
        self.assertIn("bridge day: 2026-05-22", res)

    def test_format_long_weekend_non_dict(self):
        self.assertEqual(main._format_long_weekend(None), "- Unknown long weekend")


class PublicHolidaysToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_public_holidays_success(self):
        mock_data = [
            {"date": "2026-01-01", "name": "New Year's Day", "localName": "New Year's Day", "global": True},
            {"date": "2026-07-04", "name": "Independence Day", "localName": "Independence Day", "global": True},
        ]
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_data
            req = main.HolidayRequest(country_code="US", year=2026, limit=2)
            resp = await main.get_public_holidays(req)
            self.assertIsNone(resp.error)
            self.assertIn("Public holidays for US in 2026:", resp.result)
            self.assertIn("2026-01-01: New Year's Day", resp.result)
            self.assertIn("2026-07-04: Independence Day", resp.result)

    async def test_get_public_holidays_limit_truncation(self):
        mock_data = [
            {"date": f"2026-0{i}-01", "name": f"Holiday {i}", "global": True} for i in range(1, 5)
        ]
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_data
            req = main.HolidayRequest(country_code="US", year=2026, limit=2)
            resp = await main.get_public_holidays(req)
            self.assertIsNone(resp.error)
            self.assertIn("... 2 more", resp.result)

    async def test_get_public_holidays_empty_result(self):
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            req = main.HolidayRequest(country_code="ZZ", year=2026, limit=5)
            resp = await main.get_public_holidays(req)
            self.assertEqual(resp.error, "no holidays returned for ZZ in 2026")

    async def test_get_public_holidays_non_dict_response(self):
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"error": "Invalid country"}
            req = main.HolidayRequest(country_code="ZZ", year=2026, limit=5)
            resp = await main.get_public_holidays(req)
            self.assertEqual(resp.error, "no holidays returned for ZZ in 2026")

    async def test_get_public_holidays_404(self):
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            resp_mock = types.SimpleNamespace(status_code=404)
            mock_req.side_effect = main.httpx.HTTPStatusError("Not Found", response=resp_mock)
            req = main.HolidayRequest(country_code="US", year=2026, limit=5)
            resp = await main.get_public_holidays(req)
            self.assertEqual(resp.error, "no holidays returned for US in 2026")

    async def test_get_next_public_holidays_success(self):
        mock_data = [
            {"date": "2026-11-26", "name": "Thanksgiving Day", "global": True},
        ]
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_data
            req = main.NextHolidayRequest(country_code="US", limit=5)
            resp = await main.get_next_public_holidays(req)
            self.assertIsNone(resp.error)
            self.assertIn("Upcoming public holidays for US:", resp.result)
            self.assertIn("Thanksgiving Day", resp.result)

    async def test_get_next_public_holidays_empty(self):
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            req = main.NextHolidayRequest(country_code="US", limit=5)
            resp = await main.get_next_public_holidays(req)
            self.assertEqual(resp.error, "no upcoming holidays returned for US")

    async def test_get_long_weekends_success(self):
        mock_data = [
            {"startDate": "2026-05-22", "endDate": "2026-05-25", "dayCount": 4, "needBridgeDay": False},
        ]
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_data
            req = main.LongWeekendRequest(country_code="US", year=2026, limit=5)
            resp = await main.get_long_weekends(req)
            self.assertIsNone(resp.error)
            self.assertIn("Long weekends for US in 2026:", resp.result)
            self.assertIn("2026-05-22 to 2026-05-25: 4 days", resp.result)

    async def test_get_long_weekends_empty(self):
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = None
            req = main.LongWeekendRequest(country_code="US", year=2026, limit=5)
            resp = await main.get_long_weekends(req)
            self.assertEqual(resp.error, "no long weekends returned for US in 2026")

    async def test_list_supported_countries_success(self):
        mock_data = [
            {"countryCode": "US", "name": "United States"},
            {"countryCode": "DE", "name": "Germany"},
        ]
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_data
            resp = await main.list_supported_countries()
            self.assertIsNone(resp.error)
            self.assertIn("Supported countries:", resp.result)
            self.assertIn("- US: United States", resp.result)
            self.assertIn("- DE: Germany", resp.result)

    async def test_list_supported_countries_empty_or_malformed(self):
        with patch.object(main, "_request_json", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            resp = await main.list_supported_countries()
            self.assertEqual(resp.error, "country list request returned no countries")

            mock_req.return_value = "invalid-payload"
            resp2 = await main.list_supported_countries()
            self.assertEqual(resp2.error, "country list request returned no countries")


class LifespanAndFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_manages_state_http_client(self):
        async with main.lifespan(main.app):
            self.assertIsNotNone(main.app.state.http_client)
            self.assertFalse(main.app.state.http_client.is_closed)
        self.assertTrue(main.app.state.http_client.is_closed)

    async def test_request_json_fallback_when_unmanaged(self):
        main.app.state.http_client = None
        fake_response = types.SimpleNamespace(status_code=200, content=b'{"status": "ok"}', json=lambda: {"status": "ok"}, raise_for_status=lambda: None)
        with patch.object(main.httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = fake_response
            res = await main._request_json("/test")
            self.assertEqual(res, {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
