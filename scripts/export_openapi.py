import json
from pathlib import Path

from apps.fake_blog.main import app


def main() -> None:
    target = Path("openapi.json")
    target.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote {target.resolve()}")


if __name__ == "__main__":
    main()
