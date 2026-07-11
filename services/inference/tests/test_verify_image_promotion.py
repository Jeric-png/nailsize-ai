import pytest

from scripts.verify_image_promotion import verify_image_promotion

DIGEST = "sha256:" + "a" * 64
STAGING = (
    f"us-central1-docker.pkg.dev/nailsize-staging/nailsize-staging-inference/inference@{DIGEST}"
)
PRODUCTION = (
    "us-central1-docker.pkg.dev/nailsize-production/"
    f"nailsize-production-inference/inference@{DIGEST}"
)


def test_accepts_exact_digest_copied_between_environment_repositories() -> None:
    report = verify_image_promotion(STAGING, PRODUCTION)

    assert report == {
        "schema_version": "nailsize-image-promotion@1",
        "source_image_uri": STAGING,
        "destination_image_uri": PRODUCTION,
        "digest": DIGEST,
        "passed": True,
    }


@pytest.mark.parametrize(
    ("source", "destination"),
    [
        (STAGING, PRODUCTION.replace("a" * 64, "b" * 64)),
        (STAGING.replace("@" + DIGEST, ":latest"), PRODUCTION),
        (STAGING, PRODUCTION.replace("@" + DIGEST, ":github-main")),
        (PRODUCTION, STAGING),
        (STAGING, STAGING),
        (STAGING.replace("/inference@", "/worker@"), PRODUCTION),
        (STAGING.replace("nailsize-staging-inference", "shared"), PRODUCTION),
        (STAGING.replace("us-central1-docker.pkg.dev", "docker.io"), PRODUCTION),
    ],
)
def test_rejects_non_identical_or_ambiguous_promotion(source: str, destination: str) -> None:
    with pytest.raises(ValueError):
        verify_image_promotion(source, destination)
