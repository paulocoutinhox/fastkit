from fastkit_core.providers import ProviderRegistry
from fastkit_mail.memory import MemoryEmailProvider

mail_providers = ProviderRegistry("mail")


def build_smtp(settings):
    from fastkit_mail.smtp import SmtpEmailProvider

    mail = settings.mail

    return SmtpEmailProvider(host=mail.host, port=mail.port, username=mail.username, password=mail.password, use_tls=mail.use_tls)


def build_memory(settings):
    return MemoryEmailProvider()


mail_providers.register("smtp", build_smtp)
mail_providers.register("memory", build_memory)
