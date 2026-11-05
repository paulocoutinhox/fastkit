from enums.social_provider import SocialProvider
from services.apple_login_provider import AppleLoginProvider
from services.discord_login_provider import DiscordLoginProvider
from services.facebook_login_provider import FacebookLoginProvider
from services.git_hub_login_provider import GitHubLoginProvider
from services.google_login_provider import GoogleLoginProvider
from services.instagram_login_provider import InstagramLoginProvider
from services.linked_in_login_provider import LinkedInLoginProvider
from services.microsoft_login_provider import MicrosoftLoginProvider
from services.social_login_provider import SocialLoginProvider

PROVIDERS: dict[SocialProvider, SocialLoginProvider] = {
    SocialProvider.GOOGLE: GoogleLoginProvider(),
    SocialProvider.APPLE: AppleLoginProvider(),
    SocialProvider.FACEBOOK: FacebookLoginProvider(),
    SocialProvider.INSTAGRAM: InstagramLoginProvider(),
    SocialProvider.GITHUB: GitHubLoginProvider(),
    SocialProvider.LINKEDIN: LinkedInLoginProvider(),
    SocialProvider.MICROSOFT: MicrosoftLoginProvider(),
    SocialProvider.DISCORD: DiscordLoginProvider(),
}
