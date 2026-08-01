"""
tests for feature_store.py -- the core guarantee this module exists to
provide is: as_of(query_time) can NEVER return a value that wasn't
actually knowable at query_time. these tests try hard to break that
guarantee, since a silent violation here is exactly what causes
look-ahead bias in a live backtest.
"""
import pandas as pd
import pytest

from feature_store import PITFeatureStore


@pytest.fixture
def store():
    s = PITFeatureStore(db_path=":memory:")
    yield s
    s.close()


class TestAsOf:
    def test_returns_nothing_before_first_known_value(self, store):
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-02-01"), value=100.0)
        result = store.as_of(["AAPL"], ["revenue"], pd.Timestamp("2023-01-15"))
        assert len(result) == 0

    def test_returns_value_exactly_on_known_at(self, store):
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-02-01"), value=100.0)
        result = store.as_of(["AAPL"], ["revenue"], pd.Timestamp("2023-02-01"))
        assert len(result) == 1
        assert result.iloc[0]["value"] == 100.0

    def test_never_returns_a_future_known_at_value(self, store):
        """The core look-ahead-bias guarantee: querying before a value's
        known_at must never leak that value, even if it's the only row
        in the store."""
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-05-01"), value=999.0)
        result = store.as_of(["AAPL"], ["revenue"], pd.Timestamp("2023-04-30"))
        assert len(result) == 0
        result_one_day_before = store.as_of(["AAPL"], ["revenue"], pd.Timestamp("2023-04-30 23:59:59"))
        assert len(result_one_day_before) == 0

    def test_returns_most_recent_known_value_not_the_latest_period(self, store):
        """This is the trap: a naive implementation might join on period_end
        and grab the 'latest' period's value even if it wasn't known yet.
        Here, Q2's period_end is later than Q1's, but Q2 isn't KNOWN until
        after our query time -- as_of must return Q1's value, not Q2's."""
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-02-01"), value=100.0, period_end=pd.Timestamp("2022-12-31"))
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-05-01"), value=150.0, period_end=pd.Timestamp("2023-03-31"))
        result = store.as_of(["AAPL"], ["revenue"], pd.Timestamp("2023-03-01"))
        assert len(result) == 1
        assert result.iloc[0]["value"] == 100.0  # NOT 150.0, even though Q1 2023 already ended

    def test_returns_updated_value_once_known(self, store):
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-02-01"), value=100.0)
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-05-01"), value=150.0)
        result = store.as_of(["AAPL"], ["revenue"], pd.Timestamp("2023-06-01"))
        assert result.iloc[0]["value"] == 150.0

    def test_multiple_entities_independent(self, store):
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-02-01"), value=100.0)
        store.write("MSFT", "revenue", known_at=pd.Timestamp("2023-03-01"), value=200.0)
        result = store.as_of(["AAPL", "MSFT"], ["revenue"], pd.Timestamp("2023-02-15"))
        assert len(result) == 1
        assert result.iloc[0]["entity_id"] == "AAPL"

    def test_write_batch_matches_individual_writes(self, store):
        df = pd.DataFrame({
            "entity_id": ["AAPL", "MSFT"],
            "feature_name": ["revenue", "revenue"],
            "known_at": [pd.Timestamp("2023-02-01"), pd.Timestamp("2023-02-05")],
            "value": [100.0, 200.0],
        })
        store.write_batch(df)
        result = store.as_of(["AAPL", "MSFT"], ["revenue"], pd.Timestamp("2023-03-01"))
        assert len(result) == 2

    def test_panel_as_of_builds_full_panel_across_query_times(self, store):
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-02-01"), value=100.0)
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-05-01"), value=150.0)
        panel = store.panel_as_of(["AAPL"], ["revenue"], [pd.Timestamp("2023-03-01"), pd.Timestamp("2023-06-01")])
        assert len(panel) == 2
        vals = panel.sort_values("query_time")["value"].tolist()
        assert vals == [100.0, 150.0]

    def test_missing_feature_returns_empty_not_error(self, store):
        store.write("AAPL", "revenue", known_at=pd.Timestamp("2023-02-01"), value=100.0)
        result = store.as_of(["AAPL"], ["nonexistent_feature"], pd.Timestamp("2023-06-01"))
        assert len(result) == 0
