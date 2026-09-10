"""Manual synthesis smoke test; never runs during pytest import/discovery."""

from pipeline.models_client import configured_model, get_model_client


def main() -> None:
    client = get_model_client()
    if client is None:
        raise SystemExit("Set AI_API_KEY or OPENAI_API_KEY to run this manual smoke test")
    response = client.chat.completions.create(
        model=configured_model(),
        messages=[{
            "role": "user",
            "content": "Return one sentence explaining why source-backed AI developer news matters.",
        }],
        max_tokens=100,
        temperature=0.2,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
