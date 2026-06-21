"""Unit tests for the auction-price archive models."""

from src.models.auction_prices import AuctionPick, AuctionPrices


class TestAuctionPick:
    def test_defaults(self):
        """keeper and espn_id default for sparse draft-sheet rows."""
        pick = AuctionPick(owner="Greg", player="Josh Allen", price=11)
        assert pick.keeper is False
        assert pick.espn_id is None

    def test_full_record(self):
        pick = AuctionPick(
            owner="Adam", player="Breece Hall", price=13, keeper=True, espn_id=4427366
        )
        assert pick.keeper is True
        assert pick.espn_id == 4427366


class TestAuctionPrices:
    def test_empty_default(self):
        archive = AuctionPrices()
        assert archive.source == ""
        assert archive.seasons == {}

    def test_round_trip(self):
        """JSON round-trips losslessly, keyed by season year."""
        archive = AuctionPrices(
            source="test",
            seasons={
                "2024": [
                    AuctionPick(
                        owner="Adam",
                        player="Breece Hall",
                        price=13,
                        keeper=True,
                        espn_id=4427366,
                    ),
                    AuctionPick(owner="Greg", player="Josh Allen", price=11),
                ]
            },
        )
        restored = AuctionPrices.model_validate_json(archive.model_dump_json())
        assert restored == archive
        assert restored.seasons["2024"][1].espn_id is None

    def test_model_fields(self):
        """Guard against silent field drift in the serialized shape."""
        assert set(AuctionPick.model_fields) == {
            "owner",
            "player",
            "price",
            "keeper",
            "espn_id",
        }
        assert set(AuctionPrices.model_fields) == {"source", "seasons"}
