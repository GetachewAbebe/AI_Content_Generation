import base64
import io

import pytest
import requests
from PIL import Image

from pipeline.core.errors import MissingCredentialError, PermanentError, TransientError
from pipeline.providers import cloudflare, gemini, http


class Reply:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers, self.text = status, body or {}, headers or {}, str(body)

    def json(self):
        return self._body


@pytest.fixture
def post(monkeypatch):
    sent = {}

    def install(reply):
        def fake(url, **kwargs):
            sent.update(url=url, **kwargs)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(http.requests, "post", fake)
        return sent

    for name in ("GEMINI_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        monkeypatch.setenv(name, "test")
    return install


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (Reply(429, headers={"retry-after": "12"}), TransientError),
        (Reply(503), TransientError),
        (Reply(400), PermanentError),
        (Reply(403), PermanentError),
        (requests.Timeout("slow"), TransientError),
    ],
)
def test_http_outcomes_map_to_the_retry_policy(post, reply, error):
    post(reply)
    with pytest.raises(error) as caught:
        http.post_json("https://example.invalid")
    if getattr(reply, "headers", {}) and error is TransientError:
        assert caught.value.retry_after == 12


def steps(kind, **content):
    return {"steps": [{"type": "thought"}, {"type": "model_output", "content": [{"type": kind, **content}]}]}


def test_speech_request_and_audio_price(post):
    wav = b"RIFF" + bytes(40) + bytes(48_000 * 2)
    sent = post(Reply(body=steps("audio", data=base64.b64encode(wav).decode())))
    result = gemini.Gemini().synthesise(
        model="gemini-3.8-flash-tts", voice="Sulafat", style="warm", text="ሰላም"
    )
    content = sent["json"]["input"][0]["content"][0]
    assert content["text"] == "ሰላም"
    assert content["annotations"][0]["style"] == "warm"
    assert sent["json"]["store"] is False
    assert result.units["audio_s"] == 2.0
    assert result.list_price_usd == pytest.approx(2 * 25 * 9e-6)


def test_missing_audio_is_retryable_but_wrong_container_is_not(post):
    post(Reply(body={"steps": []}))
    with pytest.raises(TransientError):
        gemini.Gemini().synthesise(model="m", voice="v", style="s", text="t")
    post(Reply(body=steps("audio", data=base64.b64encode(b"ID3x").decode())))
    with pytest.raises(PermanentError):
        gemini.Gemini().synthesise(model="m", voice="v", style="s", text="t")


def test_text_is_joined(post):
    post(Reply(body=steps("text", text="ready")))
    assert gemini.Gemini().complete(model="gemini-3.8-flash", prompt="x").data == b"ready"


def test_klein_sends_small_references_and_estimates_neurons(post):
    buffer = io.BytesIO()
    Image.new("RGB", (1024, 1024)).save(buffer, "PNG")
    sent = post(Reply(body={"result": {"image": base64.b64encode(b"png").decode()}}))
    result = cloudflare.Cloudflare().generate(
        model="@cf/black-forest-labs/flux-2-klein-4b",
        prompt="p",
        size=(720, 1280),
        steps=4,
        seed=5,
        references=[buffer.getvalue()],
    )
    form = dict(sent["files"])
    assert form["seed"] == (None, "5")
    assert max(Image.open(io.BytesIO(form["input_image_0"][1])).size) < 512
    assert result.units["neurons_est"] == pytest.approx(6 * 26.05 + 5.37, abs=0.1)


def test_schnell_refuses_references(post):
    post(Reply())
    with pytest.raises(PermanentError):
        cloudflare.Cloudflare().generate(
            model="@cf/black-forest-labs/flux-1-schnell",
            prompt="p",
            size=(1, 1),
            steps=4,
            seed=1,
            references=[b"x"],
        )


def test_missing_key_is_named(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingCredentialError, match="GEMINI_API_KEY"):
        gemini.Gemini().complete(model="m", prompt="p")
