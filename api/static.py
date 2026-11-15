"""
Static files served by the API:
- /static/exercises/...  exercise images, cached by phones for a week
- /                      the built Mini App (miniapp/dist), if it has been built
"""
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

ONE_WEEK = 7 * 24 * 3600
ONE_YEAR = 365 * 24 * 3600


class CachedStaticFiles(StaticFiles):
    """Static files with a Cache-Control header."""

    def __init__(self, *args, max_age: int = ONE_WEEK, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_control = f"public, max-age={max_age}"

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = self.cache_control
        return response


class MiniAppFiles(StaticFiles):
    """
    The Mini App build. Vite puts content-hashed files in assets/, so those can
    be cached forever; index.html must always be fresh so new builds show up.
    Unknown paths get index.html, so the app's own routes (e.g. /plan) work on reload.
    """

    async def get_response(self, path: str, scope: Scope):
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404)  # never hide API typos behind the app
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as error:
            if error.status_code != 404:
                raise
            response = await super().get_response("index.html", scope)
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        if path.startswith("assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = f"public, max-age={ONE_YEAR}, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response
