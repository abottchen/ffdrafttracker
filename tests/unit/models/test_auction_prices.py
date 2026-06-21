"""Unit tests for the auction-price archive models."""

from src.models.auction_prices import AuctionPick, AuctionPrices, SeasonAuction


class TestAuctionPick:
    def test_defaults(self):
        """keeper and espn_id default for sparse draft-sheet rows."""
        pick = AuctionPick(player="Josh Allen", price=11)
        assert pick.keeper is False
        assert pick.espn_id is None

    def test_full_record(self):
        pick = AuctionPick(player="Breece Hall", price=13, keeper=True, espn_id=4427366)
        assert pick.keeper is True
        assert pick.espn_id == 4427366


class TestAuctionPrices:
    def test_empty_default(self):
        archive = AuctionPrices()
        assert archive.seasons == {}

    def test_round_trip(self):
        """JSON round-trips losslessly, grouped by season then owner."""
        archive = AuctionPrices(
            seasons={
                "2024": SeasonAuction(
                    owners={
                        "Adam": [
                            AuctionPick(
                                player="Breece Hall",
                                price=13,
                                keeper=True,
                                espn_id=4427366,
                            )
                        ],
                        "Greg": [AuctionPick(player="Josh Allen", price=11)],
                    }
                )
            },
        )
        restored = AuctionPrices.model_validate_json(archive.model_dump_json())
        assert restored == archive
        assert restored.seasons["2024"].owners["Greg"][0].espn_id is None

    def test_model_fields(self):
        """Guard against silent field drift in the serialized shape."""
        assert set(AuctionPick.model_fields) == {"player", "price", "keeper", "espn_id"}
        assert set(SeasonAuction.model_fields) == {"owners"}
        assert set(AuctionPrices.model_fields) == {"seasons"}
