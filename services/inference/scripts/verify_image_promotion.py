import argparse
import json
import re
from pathlib import Path

_IMAGE_URI = re.compile(
    r"^(?P<registry>[a-z0-9-]+-docker\.pkg\.dev)/"
    r"(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])/"
    r"(?P<repository>nailsize-(?P<environment>staging|production)-inference)/"
    r"(?P<image>inference)@(?P<digest>sha256:[0-9a-f]{64})$"
)


def verify_image_promotion(source_image_uri: str, destination_image_uri: str) -> dict[str, object]:
    source = _parse_image_uri(source_image_uri, "Source")
    destination = _parse_image_uri(destination_image_uri, "Destination")
    if source["environment"] != "staging":
        raise ValueError("Source image must use the staging inference repository")
    if destination["environment"] != "production":
        raise ValueError("Destination image must use the production inference repository")
    if source_image_uri == destination_image_uri:
        raise ValueError("Promotion must copy the image into the production repository")
    if source["digest"] != destination["digest"]:
        raise ValueError("Production image digest does not match the staging-tested digest")

    return {
        "schema_version": "nailsize-image-promotion@1",
        "source_image_uri": source_image_uri,
        "destination_image_uri": destination_image_uri,
        "digest": source["digest"],
        "passed": True,
    }


def _parse_image_uri(value: str, label: str) -> dict[str, str]:
    match = _IMAGE_URI.fullmatch(value)
    if match is None:
        raise ValueError(f"{label} image must be an exact Artifact Registry inference digest URI")
    return match.groupdict()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prove production received the exact staging-tested container digest"
    )
    parser.add_argument("--source-image-uri", required=True)
    parser.add_argument("--destination-image-uri", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        report = verify_image_promotion(arguments.source_image_uri, arguments.destination_image_uri)
    except ValueError as error:
        parser.error(str(error))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
