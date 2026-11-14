from design_patterns.behavioural.chain_of_responsibility import (
    Request,
    Response,
    build_chain,
    error_handler,
    make_authenticate,
    make_rate_limit,
    request_id,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def endpoint(request: Request) -> Response:
    if request.path == "/boom":
        raise RuntimeError("bug in the endpoint")
    return Response(200, f"hello {request.user}")


def make_app(clock=None):
    return build_chain(
        [
            error_handler,  # outermost: catches anything below it
            request_id,
            make_authenticate({"secret-token": "ada"}),
            make_rate_limit(limit=2, window_seconds=60, clock=clock or FakeClock()),
        ],
        endpoint,
    )


AUTH = {"Authorization": "Bearer secret-token"}


def test_request_passes_through_every_link():
    response = make_app()(Request("/hello", AUTH))
    assert response.status == 200
    assert response.body == "hello ada"  # authenticate added the user
    assert "X-Request-ID" in response.headers


def test_existing_request_id_is_kept():
    response = make_app()(Request("/hello", {**AUTH, "X-Request-ID": "abc"}))
    assert response.headers["X-Request-ID"] == "abc"


def test_authentication_short_circuits_the_chain():
    response = make_app()(Request("/hello", {"Authorization": "Bearer wrong"}))
    assert response.status == 401
    assert "X-Request-ID" in response.headers  # outer links still wrap the response


def test_rate_limit_per_window():
    clock = FakeClock()
    app = make_app(clock)
    statuses = [app(Request("/hello", AUTH)).status for _ in range(3)]
    assert statuses == [200, 200, 429]
    clock.now = 60  # next window
    assert app(Request("/hello", AUTH)).status == 200


def test_errors_deep_in_the_chain_become_500s():
    assert make_app()(Request("/boom", AUTH)).status == 500


def test_order_matters():
    # With the error handler innermost, it can't catch failures from the outer links.
    def explode(request, call_next):
        raise RuntimeError("middleware bug")

    safe = build_chain([error_handler, explode], endpoint)
    assert safe(Request("/hello")).status == 500

    unsafe = build_chain([explode, error_handler], endpoint)
    try:
        unsafe(Request("/hello"))
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected the error to escape")
