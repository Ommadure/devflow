from app.db.session import engine_options


def test_direct_connection_keeps_prepared_statement_caching() -> None:
    options = engine_options("postgresql+asyncpg://u:p@ep-x.aws.neon.tech/db")
    assert "connect_args" not in options
    assert options["pool_pre_ping"] is True


def test_transaction_pooler_disables_prepared_statement_caching() -> None:
    options = engine_options("postgresql+asyncpg://u:p@ep-x-pooler.aws.neon.tech/db")
    connect_args = options["connect_args"]
    assert connect_args["statement_cache_size"] == 0
    assert connect_args["prepared_statement_cache_size"] == 0
    name_func = connect_args["prepared_statement_name_func"]
    assert name_func() != name_func()  # unique per statement
