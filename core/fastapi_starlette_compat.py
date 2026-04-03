from inspect import signature


def patch_starlette_router_for_fastapi() -> None:
    """
    FastAPI<=0.104 passes `on_startup`/`on_shutdown` to Starlette Router.
    Starlette 1.x removed those args. This shim keeps the app bootable
    without changing the user's installed packages.
    """
    from starlette.routing import Router

    init_params = signature(Router.__init__).parameters
    if "on_startup" in init_params:
        return

    original_init = Router.__init__

    def compat_init(
        self,
        routes=None,
        redirect_slashes=True,
        default=None,
        on_startup=None,
        on_shutdown=None,
        lifespan=None,
        *,
        middleware=None,
        **kwargs,
    ):
        # Ignore legacy FastAPI args when running against Starlette 1.x.
        return original_init(
            self,
            routes=routes,
            redirect_slashes=redirect_slashes,
            default=default,
            lifespan=lifespan,
            middleware=middleware,
        )

    Router.__init__ = compat_init

    # FastAPI<=0.104 reads these attributes directly during include_router.
    if not hasattr(Router, "on_startup"):
        Router.on_startup = []
    if not hasattr(Router, "on_shutdown"):
        Router.on_shutdown = []


def patch_fastapi_middleware_unpack_for_starlette() -> None:
    """
    FastAPI<=0.104 expects Starlette Middleware to iterate as (cls, kwargs).
    Starlette 1.x yields (cls, args, kwargs), which breaks unpacking.
    """
    from fastapi.applications import FastAPI
    from fastapi.middleware.asyncexitstack import AsyncExitStackMiddleware
    from starlette.middleware import Middleware
    from starlette.middleware.errors import ServerErrorMiddleware
    from starlette.middleware.exceptions import ExceptionMiddleware

    original_build = FastAPI.build_middleware_stack

    def compat_build_middleware_stack(self):
        debug = self.debug
        error_handler = None
        exception_handlers = {}

        for key, value in self.exception_handlers.items():
            if key in (500, Exception):
                error_handler = value
            else:
                exception_handlers[key] = value

        middleware = (
            [Middleware(ServerErrorMiddleware, handler=error_handler, debug=debug)]
            + self.user_middleware
            + [
                Middleware(ExceptionMiddleware, handlers=exception_handlers, debug=debug),
                Middleware(AsyncExitStackMiddleware),
            ]
        )

        app = self.router
        for entry in reversed(middleware):
            values = tuple(entry)
            if len(values) == 2:
                cls, options = values
                app = cls(app=app, **options)
            elif len(values) == 3:
                cls, args, options = values
                app = cls(app, *args, **options)
            else:
                raise RuntimeError("Unexpected middleware tuple format")
        return app

    FastAPI.build_middleware_stack = compat_build_middleware_stack
