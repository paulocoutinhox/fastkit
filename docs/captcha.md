# Captcha

A public form carries whatever challenge the environment declares. `disabled` is a choice an environment makes, never what a failure falls back to.

## The providers

| Provider | What the page draws | How it is answered |
| --- | --- | --- |
| `image` | a PNG the server drew, plus the field to type it into | the word travels back signed, so nothing is kept between the two requests |
| `recaptcha_v3` | the site key, and a token minted before the form is sent | verified against Google, and refused below the score threshold |
| `disabled` | nothing | everything passes |

Where the page mints the token itself, the form is sent whether or not it could: a challenge nobody was
able to mint is a refusal the server draws on the page with the reason, and holding the form back instead
leaves a visitor pressing a button that does nothing.

That only holds because minting a token can fail. Both places that mint one hand the rejection on rather
than wrapping the call in a promise that can only ever resolve — one that cannot fail leaves whoever waits
on it waiting for good, with no error to catch and nothing to show.

The word of an image challenge is drawn with `secrets` and only the noise around it with `random`: a word out of a general purpose generator is one whose state an attacker rebuilds from a few hundred samples, and from then on the challenge guards nothing.

## Configuration

```python
captcha = CaptchaSettings(provider="recaptcha_v3", site_key="…", secret_key="…", score_threshold=0.5)
```

The `ttl` is how long a drawn challenge stays valid, and `length` is how many characters the image carries.

## Where it is asked

Sign in, sign up, password recovery, contact and the newsletter on the site, and the admin sign in. The same is asked of an application: `POST /api/contact` and `POST /api/newsletter` carry the answer too, because a form anybody can send is a form anybody can flood.

The site draws the challenge into its own HTML. Everything else asks `GET /api/meta/captcha` for one, minted for the attempt about to be made — and the admin asks for another as soon as an attempt is refused, because a spent token would be answered by the same word again.

## What a failure is

Anything that is not a clean pass is a refusal, and that includes a Google that did not answer. A network problem is not a visitor who passed.
