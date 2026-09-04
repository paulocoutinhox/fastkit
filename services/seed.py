import pathlib
import secrets
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from sqlalchemy.ext.asyncio import AsyncSession

from enums.banner import BannerPlacement
from enums.commerce import PurchaseStatus
from enums.country import PostalCodeProvider
from enums.integration import Environment, NormalizedAction, Provider, WebhookEventStatus
from enums.subscription import BenefitCadence, BenefitType, IntervalUnit, ResumeDeliveryPolicy, SubscriptionStatus
from enums.upload import UploadPurpose
from enums.user import UserAddressType, UserRole, UserStatus
from helpers import brand
from helpers.brand import Brand
from helpers.dates import now
from helpers.db import AsyncSessionLocal, run_scoped
from helpers.schema import recreate_schema
from helpers.security import encrypt
from helpers.settings import settings
from helpers.storage import storage
from helpers.text import slugify
from models.account import Currency
from models.banner import Banner
from models.commerce import Product, Purchase
from models.content import Content, ContentCategory
from models.country import Country
from models.gallery import Gallery, GalleryPhoto
from models.integration import Integration, WebhookEvent
from models.language import Language
from models.subscription import Benefit, Entitlement, Plan, PlanEntitlement, Subscription
from models.tenant import Tenant
from models.user import User, UserAddress
from services.commerce import commerce_service
from services.delivery import delivery_service
from services.upload import upload_service
from services.user import user_service

ADMIN = {"username": "admin", "email": "admin@admin.com", "password": "admin"}

# The contact addresses are derived from the domain, and the schema that writes a tenant refuses a special use name, so this is the one reserved for examples.
TENANTS = [{"code": "acme", "name": "Acme", "domain": "acme.example"}, {"code": "globex", "name": "Globex", "domain": "globex.example"}]

LANGUAGES = [("Português", "Português", "pt", "pt-BR"), ("English", "English", "en", "en-US"), ("Español", "Español", "es", "es-ES")]

COUNTRIES = [
    ("AF", "Afghanistan"),
    ("AX", "Åland Islands"),
    ("AL", "Albania"),
    ("DZ", "Algeria"),
    ("AS", "American Samoa"),
    ("AD", "Andorra"),
    ("AO", "Angola"),
    ("AI", "Anguilla"),
    ("AQ", "Antarctica"),
    ("AG", "Antigua and Barbuda"),
    ("AR", "Argentina"),
    ("AM", "Armenia"),
    ("AW", "Aruba"),
    ("AU", "Australia"),
    ("AT", "Austria"),
    ("AZ", "Azerbaijan"),
    ("BS", "Bahamas"),
    ("BH", "Bahrain"),
    ("BD", "Bangladesh"),
    ("BB", "Barbados"),
    ("BY", "Belarus"),
    ("BE", "Belgium"),
    ("BZ", "Belize"),
    ("BJ", "Benin"),
    ("BM", "Bermuda"),
    ("BT", "Bhutan"),
    ("BO", "Bolivia"),
    ("BQ", "Bonaire, Sint Eustatius and Saba"),
    ("BA", "Bosnia and Herzegovina"),
    ("BW", "Botswana"),
    ("BV", "Bouvet Island"),
    ("BR", "Brazil"),
    ("IO", "British Indian Ocean Territory"),
    ("BN", "Brunei Darussalam"),
    ("BG", "Bulgaria"),
    ("BF", "Burkina Faso"),
    ("BI", "Burundi"),
    ("CV", "Cabo Verde"),
    ("KH", "Cambodia"),
    ("CM", "Cameroon"),
    ("CA", "Canada"),
    ("KY", "Cayman Islands"),
    ("CF", "Central African Republic"),
    ("TD", "Chad"),
    ("CL", "Chile"),
    ("CN", "China"),
    ("CX", "Christmas Island"),
    ("CC", "Cocos (Keeling) Islands"),
    ("CO", "Colombia"),
    ("KM", "Comoros"),
    ("CG", "Congo"),
    ("CD", "Congo, Democratic Republic of the"),
    ("CK", "Cook Islands"),
    ("CR", "Costa Rica"),
    ("CI", "Côte d'Ivoire"),
    ("HR", "Croatia"),
    ("CU", "Cuba"),
    ("CW", "Curaçao"),
    ("CY", "Cyprus"),
    ("CZ", "Czechia"),
    ("DK", "Denmark"),
    ("DJ", "Djibouti"),
    ("DM", "Dominica"),
    ("DO", "Dominican Republic"),
    ("EC", "Ecuador"),
    ("EG", "Egypt"),
    ("SV", "El Salvador"),
    ("GQ", "Equatorial Guinea"),
    ("ER", "Eritrea"),
    ("EE", "Estonia"),
    ("SZ", "Eswatini"),
    ("ET", "Ethiopia"),
    ("FK", "Falkland Islands"),
    ("FO", "Faroe Islands"),
    ("FJ", "Fiji"),
    ("FI", "Finland"),
    ("FR", "France"),
    ("GF", "French Guiana"),
    ("PF", "French Polynesia"),
    ("TF", "French Southern Territories"),
    ("GA", "Gabon"),
    ("GM", "Gambia"),
    ("GE", "Georgia"),
    ("DE", "Germany"),
    ("GH", "Ghana"),
    ("GI", "Gibraltar"),
    ("GR", "Greece"),
    ("GL", "Greenland"),
    ("GD", "Grenada"),
    ("GP", "Guadeloupe"),
    ("GU", "Guam"),
    ("GT", "Guatemala"),
    ("GG", "Guernsey"),
    ("GN", "Guinea"),
    ("GW", "Guinea-Bissau"),
    ("GY", "Guyana"),
    ("HT", "Haiti"),
    ("HM", "Heard Island and McDonald Islands"),
    ("VA", "Holy See"),
    ("HN", "Honduras"),
    ("HK", "Hong Kong"),
    ("HU", "Hungary"),
    ("IS", "Iceland"),
    ("IN", "India"),
    ("ID", "Indonesia"),
    ("IR", "Iran"),
    ("IQ", "Iraq"),
    ("IE", "Ireland"),
    ("IM", "Isle of Man"),
    ("IL", "Israel"),
    ("IT", "Italy"),
    ("JM", "Jamaica"),
    ("JP", "Japan"),
    ("JE", "Jersey"),
    ("JO", "Jordan"),
    ("KZ", "Kazakhstan"),
    ("KE", "Kenya"),
    ("KI", "Kiribati"),
    ("KP", "Korea, Democratic People's Republic of"),
    ("KR", "Korea, Republic of"),
    ("KW", "Kuwait"),
    ("KG", "Kyrgyzstan"),
    ("LA", "Lao People's Democratic Republic"),
    ("LV", "Latvia"),
    ("LB", "Lebanon"),
    ("LS", "Lesotho"),
    ("LR", "Liberia"),
    ("LY", "Libya"),
    ("LI", "Liechtenstein"),
    ("LT", "Lithuania"),
    ("LU", "Luxembourg"),
    ("MO", "Macao"),
    ("MG", "Madagascar"),
    ("MW", "Malawi"),
    ("MY", "Malaysia"),
    ("MV", "Maldives"),
    ("ML", "Mali"),
    ("MT", "Malta"),
    ("MH", "Marshall Islands"),
    ("MQ", "Martinique"),
    ("MR", "Mauritania"),
    ("MU", "Mauritius"),
    ("YT", "Mayotte"),
    ("MX", "Mexico"),
    ("FM", "Micronesia"),
    ("MD", "Moldova"),
    ("MC", "Monaco"),
    ("MN", "Mongolia"),
    ("ME", "Montenegro"),
    ("MS", "Montserrat"),
    ("MA", "Morocco"),
    ("MZ", "Mozambique"),
    ("MM", "Myanmar"),
    ("NA", "Namibia"),
    ("NR", "Nauru"),
    ("NP", "Nepal"),
    ("NL", "Netherlands"),
    ("NC", "New Caledonia"),
    ("NZ", "New Zealand"),
    ("NI", "Nicaragua"),
    ("NE", "Niger"),
    ("NG", "Nigeria"),
    ("NU", "Niue"),
    ("NF", "Norfolk Island"),
    ("MK", "North Macedonia"),
    ("MP", "Northern Mariana Islands"),
    ("NO", "Norway"),
    ("OM", "Oman"),
    ("PK", "Pakistan"),
    ("PW", "Palau"),
    ("PS", "Palestine, State of"),
    ("PA", "Panama"),
    ("PG", "Papua New Guinea"),
    ("PY", "Paraguay"),
    ("PE", "Peru"),
    ("PH", "Philippines"),
    ("PN", "Pitcairn"),
    ("PL", "Poland"),
    ("PT", "Portugal"),
    ("PR", "Puerto Rico"),
    ("QA", "Qatar"),
    ("RE", "Réunion"),
    ("RO", "Romania"),
    ("RU", "Russian Federation"),
    ("RW", "Rwanda"),
    ("BL", "Saint Barthélemy"),
    ("SH", "Saint Helena, Ascension and Tristan da Cunha"),
    ("KN", "Saint Kitts and Nevis"),
    ("LC", "Saint Lucia"),
    ("MF", "Saint Martin (French part)"),
    ("PM", "Saint Pierre and Miquelon"),
    ("VC", "Saint Vincent and the Grenadines"),
    ("WS", "Samoa"),
    ("SM", "San Marino"),
    ("ST", "Sao Tome and Principe"),
    ("SA", "Saudi Arabia"),
    ("SN", "Senegal"),
    ("RS", "Serbia"),
    ("SC", "Seychelles"),
    ("SL", "Sierra Leone"),
    ("SG", "Singapore"),
    ("SX", "Sint Maarten (Dutch part)"),
    ("SK", "Slovakia"),
    ("SI", "Slovenia"),
    ("SB", "Solomon Islands"),
    ("SO", "Somalia"),
    ("ZA", "South Africa"),
    ("GS", "South Georgia and the South Sandwich Islands"),
    ("SS", "South Sudan"),
    ("ES", "Spain"),
    ("LK", "Sri Lanka"),
    ("SD", "Sudan"),
    ("SR", "Suriname"),
    ("SJ", "Svalbard and Jan Mayen"),
    ("SE", "Sweden"),
    ("CH", "Switzerland"),
    ("SY", "Syrian Arab Republic"),
    ("TW", "Taiwan"),
    ("TJ", "Tajikistan"),
    ("TZ", "Tanzania"),
    ("TH", "Thailand"),
    ("TL", "Timor-Leste"),
    ("TG", "Togo"),
    ("TK", "Tokelau"),
    ("TO", "Tonga"),
    ("TT", "Trinidad and Tobago"),
    ("TN", "Tunisia"),
    ("TR", "Türkiye"),
    ("TM", "Turkmenistan"),
    ("TC", "Turks and Caicos Islands"),
    ("TV", "Tuvalu"),
    ("UG", "Uganda"),
    ("UA", "Ukraine"),
    ("AE", "United Arab Emirates"),
    ("GB", "United Kingdom"),
    ("US", "United States of America"),
    ("UM", "United States Minor Outlying Islands"),
    ("UY", "Uruguay"),
    ("UZ", "Uzbekistan"),
    ("VU", "Vanuatu"),
    ("VE", "Venezuela"),
    ("VN", "Viet Nam"),
    ("VG", "Virgin Islands (British)"),
    ("VI", "Virgin Islands (U.S.)"),
    ("WF", "Wallis and Futuna"),
    ("EH", "Western Sahara"),
    ("YE", "Yemen"),
    ("ZM", "Zambia"),
    ("ZW", "Zimbabwe"),
]

# Only the countries somebody wrote a lookup for, because a country with nobody to ask draws a plain postal code field.
POSTAL_CODE_PROVIDERS = {"BR": PostalCodeProvider.VIACEP}

PHONE_MASKS = {"BR": "(00) 00000-0000"}

CONTENT_CATEGORIES = [("Legal", "legal"), ("Help", "help")]

CONTENTS = [
    {
        "title": "About",
        "tag": "about",
        "language": "en",
        "category": "help",
        "body": "<p>This platform is built on FastKit, a base for products that carry accounts, subscriptions, payments and content.</p><p>Everything a person sees here is rendered by the same process that answers the applications, so what a search engine reads is what a visitor reads.</p><p>Write your own story here from the admin: this text is a content record with the tag <code>about</code>, and editing it is all it takes.</p>",
    },
    {
        "title": "Sobre",
        "tag": "about",
        "language": "pt",
        "category": "help",
        "body": "<p>Esta plataforma é construída sobre o FastKit, uma base para produtos que têm conta, assinatura, pagamento e conteúdo.</p><p>Tudo o que uma pessoa vê aqui é desenhado pelo mesmo processo que responde aos aplicativos, então o que um buscador lê é o que um visitante lê.</p><p>Escreva a sua própria história aqui pelo painel: este texto é um registro de conteúdo com a tag <code>about</code>, e editá-lo é tudo o que é preciso.</p>",
    },
    {
        "title": "Acerca de",
        "tag": "about",
        "language": "es",
        "category": "help",
        "body": "<p>Esta plataforma está construida sobre FastKit, una base para productos que tienen cuenta, suscripción, pago y contenido.</p><p>Todo lo que una persona ve aquí lo dibuja el mismo proceso que responde a las aplicaciones, así que lo que lee un buscador es lo que lee un visitante.</p><p>Escribe tu propia historia aquí desde el panel: este texto es un registro de contenido con la etiqueta <code>about</code>, y editarlo es todo lo que hace falta.</p>",
    },
    {
        "title": "Terms of use",
        "tag": "terms",
        "language": "en",
        "category": "legal",
        "body": "<h2>The account</h2><p>An account is yours and you answer for what is done with it. Keep the password to yourself.</p><h2>What you buy</h2><p>A product you buy is yours for good. A subscription runs for the period it was paid for and renews until you stop it.</p><h2>Refunds</h2><p>A refund gives the money back. What was already delivered stays with you, and the access a subscription opened closes.</p><h2>What is not allowed</h2><p>Reselling what you bought here, and anything that breaks the law where you are.</p><h2>Changes</h2><p>These terms can change, and the version published here is the one that counts.</p><p>Replace this text from the admin: it is a content record with the tag <code>terms</code>.</p>",
    },
    {
        "title": "Termos de uso",
        "tag": "terms",
        "language": "pt",
        "category": "legal",
        "body": "<h2>A conta</h2><p>Uma conta é sua e você responde pelo que é feito com ela. Guarde a senha só com você.</p><h2>O que você compra</h2><p>Um produto que você compra é seu para sempre. Uma assinatura vale pelo período que foi pago e renova até você encerrá-la.</p><h2>Reembolso</h2><p>Um reembolso devolve o dinheiro. O que já foi entregue continua com você, e o acesso que uma assinatura abriu se fecha.</p><h2>O que não é permitido</h2><p>Revender o que você comprou aqui, e qualquer coisa que infrinja a lei do lugar onde você está.</p><h2>Mudanças</h2><p>Estes termos podem mudar, e a versão publicada aqui é a que vale.</p><p>Troque este texto pelo painel: ele é um registro de conteúdo com a tag <code>terms</code>.</p>",
    },
    {
        "title": "Términos de uso",
        "tag": "terms",
        "language": "es",
        "category": "legal",
        "body": "<h2>La cuenta</h2><p>Una cuenta es tuya y respondes por lo que se hace con ella. Guarda la contraseña solo para ti.</p><h2>Lo que compras</h2><p>Un producto que compras es tuyo para siempre. Una suscripción vale por el período que se pagó y se renueva hasta que la termines.</p><h2>Reembolso</h2><p>Un reembolso devuelve el dinero. Lo que ya se entregó sigue siendo tuyo, y el acceso que abrió una suscripción se cierra.</p><h2>Lo que no está permitido</h2><p>Revender lo que compraste aquí, y cualquier cosa que infrinja la ley del lugar donde estás.</p><h2>Cambios</h2><p>Estos términos pueden cambiar, y la versión publicada aquí es la que vale.</p><p>Cambia este texto desde el panel: es un registro de contenido con la etiqueta <code>terms</code>.</p>",
    },
    {
        "title": "Cookie policy",
        "tag": "cookies",
        "language": "en",
        "category": "legal",
        "body": "<h2>What this site keeps</h2><p>A cookie is a small value a site asks your browser to hold on to. This one keeps what it needs to answer you, and asks before keeping anything else.</p><h2>The necessary ones</h2><p><code>fastkit_session</code> is how the site knows you signed in. <code>fastkit_csrf</code> is how a form proves it was drawn here. <code>fastkit_flash</code> carries a notice from one page to the next, and <code>fastkit_consent</code> is the answer you gave on this page. None of them can be turned off, because without them the site cannot answer you at all.</p><h2>Preferences</h2><p><code>fastkit_language</code> keeps the language you chose, so you are not asked again on every page.</p><h2>Analytics and marketing</h2><p>This installation sets none. If it ever does, they are switched on by the choice you make on this page and never before it.</p><h2>Changing your mind</h2><p>Withdrawing is as easy as giving: open this page from the footer and choose again. Your answer is kept for six months, and you are asked again whenever this page changes.</p><p>Replace this text from the admin: it is a content record with the tag <code>cookies</code>.</p>",
    },
    {
        "title": "Política de cookies",
        "tag": "cookies",
        "language": "pt",
        "category": "legal",
        "body": "<h2>O que este site guarda</h2><p>Um cookie é um valor pequeno que um site pede para o seu navegador guardar. Este guarda o que precisa para responder você, e pergunta antes de guardar qualquer outra coisa.</p><h2>Os necessários</h2><p><code>fastkit_session</code> é como o site sabe que você entrou. <code>fastkit_csrf</code> é como um formulário prova que foi desenhado aqui. <code>fastkit_flash</code> leva um aviso de uma página para a seguinte, e <code>fastkit_consent</code> é a resposta que você deu nesta página. Nenhum deles pode ser desligado, porque sem eles o site não tem como responder você.</p><h2>Preferências</h2><p><code>fastkit_language</code> guarda o idioma que você escolheu, para não perguntar de novo a cada página.</p><h2>Análise e publicidade</h2><p>Esta instalação não usa nenhum. Se um dia usar, eles são ligados pela escolha que você faz nesta página e nunca antes dela.</p><h2>Mudar de ideia</h2><p>Retirar é tão fácil quanto dar: abra esta página pelo rodapé e escolha de novo. Sua resposta é guardada por seis meses, e você é perguntado de novo sempre que esta página mudar.</p><p>Troque este texto pelo painel: ele é um registro de conteúdo com a tag <code>cookies</code>.</p>",
    },
    {
        "title": "Política de cookies",
        "tag": "cookies",
        "language": "es",
        "category": "legal",
        "body": "<h2>Lo que guarda este sitio</h2><p>Una cookie es un valor pequeño que un sitio pide a tu navegador que guarde. Este guarda lo que necesita para responderte, y pregunta antes de guardar cualquier otra cosa.</p><h2>Las necesarias</h2><p><code>fastkit_session</code> es como el sitio sabe que entraste. <code>fastkit_csrf</code> es como un formulario prueba que fue dibujado aquí. <code>fastkit_flash</code> lleva un aviso de una página a la siguiente, y <code>fastkit_consent</code> es la respuesta que diste en esta página. Ninguna de ellas se puede apagar, porque sin ellas el sitio no puede responderte.</p><h2>Preferencias</h2><p><code>fastkit_language</code> guarda el idioma que elegiste, para no preguntarte otra vez en cada página.</p><h2>Análisis y publicidad</h2><p>Esta instalación no usa ninguna. Si algún día lo hace, se encienden por la elección que haces en esta página y nunca antes de ella.</p><h2>Cambiar de opinión</h2><p>Retirar es tan fácil como dar: abre esta página desde el pie y elige de nuevo. Tu respuesta se guarda seis meses, y se te pregunta otra vez cuando esta página cambie.</p><p>Cambia este texto desde el panel: es un registro de contenido con la etiqueta <code>cookies</code>.</p>",
    },
    {
        "title": "Privacy policy",
        "tag": "privacy",
        "language": "en",
        "category": "legal",
        "body": "<h2>What is collected</h2><p>The account keeps what you typed into it: a name, the identifiers you sign in with, and the address you gave for your orders.</p><h2>What it is used for</h2><p>Your data is used to run the account, deliver what you bought and answer you. It is not sold.</p><h2>Who else sees it</h2><p>Only the services that make this work: the payment gateway that charges you, and the mail server that writes to you.</p><h2>Your data is yours</h2><p>You can correct it from your account at any time, and you can erase the account itself. Erasing anonymises your personal data and keeps the records of money, which the law requires.</p><p>Replace this text from the admin: it is a content record with the tag <code>privacy</code>.</p>",
    },
    {
        "title": "Política de privacidade",
        "tag": "privacy",
        "language": "pt",
        "category": "legal",
        "body": "<h2>O que é coletado</h2><p>A conta guarda o que você digitou nela: um nome, as identidades com que você entra, e o endereço que você informou para os seus pedidos.</p><h2>Para que isso é usado</h2><p>Seus dados são usados para manter a conta, entregar o que você comprou e responder você. Eles não são vendidos.</p><h2>Quem mais vê</h2><p>Apenas os serviços que fazem isto funcionar: o gateway de pagamento que cobra você, e o servidor de e-mail que escreve para você.</p><h2>Seus dados são seus</h2><p>Você pode corrigi-los pela sua conta a qualquer momento, e pode apagar a própria conta. Apagar anonimiza os seus dados pessoais e mantém os registros de dinheiro, que a lei exige.</p><p>Troque este texto pelo painel: ele é um registro de conteúdo com a tag <code>privacy</code>.</p>",
    },
    {
        "title": "Política de privacidad",
        "tag": "privacy",
        "language": "es",
        "category": "legal",
        "body": "<h2>Qué se recoge</h2><p>La cuenta guarda lo que escribiste en ella: un nombre, las identidades con las que entras, y la dirección que diste para tus pedidos.</p><h2>Para qué se usa</h2><p>Tus datos se usan para mantener la cuenta, entregar lo que compraste y responderte. No se venden.</p><h2>Quién más lo ve</h2><p>Solo los servicios que hacen que esto funcione: la pasarela de pago que te cobra, y el servidor de correo que te escribe.</p><h2>Tus datos son tuyos</h2><p>Puedes corregirlos desde tu cuenta en cualquier momento, y puedes eliminar la cuenta misma. Eliminar anonimiza tus datos personales y conserva los registros de dinero, que la ley exige.</p><p>Cambia este texto desde el panel: es un registro de contenido con la etiqueta <code>privacy</code>.</p>",
    },
]

BANNERS = [{"title": "Welcome", "placement": BannerPlacement.HOME, "position": 0, "url": "/plans", "picture": "banner-welcome.jpg"}, {"title": "What we offer", "placement": BannerPlacement.HOME, "position": 1, "url": "/products", "picture": "banner-offer.jpg"}]

GALLERIES = [
    {"title": "Our office", "tag": "office", "language": "en", "photos": ["Reception", "Meeting room", "The roof"], "pictures": ["gallery-reception.jpg", "gallery-meeting-room.jpg", "gallery-roof.jpg"]},
    {"title": "Nosso escritório", "tag": "office", "language": "pt", "photos": ["Recepção", "Sala de reunião", "O terraço"], "pictures": ["gallery-reception.jpg", "gallery-meeting-room.jpg", "gallery-roof.jpg"]},
    {"title": "Events", "tag": "events", "language": None, "photos": ["Opening night", "The talk", "Closing"], "pictures": ["gallery-opening.jpg", "gallery-talk.jpg", "gallery-closing.jpg"]},
]

CURRENCIES = [{"code": "coin", "name": "Coins", "symbol": "¢"}, {"code": "gem", "name": "Gems", "symbol": "◆"}]

PRODUCTS = [
    {"name": "Starter pack", "price": Decimal("9.90"), "credits": 100, "currency": "coin", "featured": True, "picture": "product-starter-pack.jpg"},
    {"name": "Pro pack", "price": Decimal("29.90"), "credits": 500, "currency": "gem", "featured": True, "picture": "product-pro-pack.jpg"},
    {"name": "Handbook", "price": Decimal("19.90"), "credits": 0, "currency": None, "featured": False, "picture": "product-handbook.jpg"},
]

# The same plan is sold once per market, so each of them is written in the language it is read in and priced in the currency of that market.
PLANS = [
    {
        "code": "monthly",
        "picture": "plan-monthly.jpg",
        "unit": IntervalUnit.MONTH,
        "value": 1,
        "featured": False,
        "markets": [
            {"language": "en", "name": "Monthly", "currency": "USD", "price": Decimal("19.90"), "lead": "Monthly membership"},
            {"language": "pt", "name": "Mensal", "currency": "BRL", "price": Decimal("99.90"), "lead": "Assinatura mensal"},
            {"language": "es", "name": "Mensual", "currency": "EUR", "price": Decimal("18.90"), "lead": "Suscripción mensual"},
        ],
    },
    {
        "code": "yearly",
        "picture": "plan-yearly.jpg",
        "unit": IntervalUnit.YEAR,
        "value": 1,
        "featured": True,
        "markets": [
            {"language": "en", "name": "Yearly", "currency": "USD", "price": Decimal("199.00"), "lead": "Yearly membership"},
            {"language": "pt", "name": "Anual", "currency": "BRL", "price": Decimal("999.00"), "lead": "Assinatura anual"},
            {"language": "es", "name": "Anual", "currency": "EUR", "price": Decimal("189.00"), "lead": "Suscripción anual"},
        ],
    },
]

MEMBERS = [
    {"username": "member", "email": "member@acme.com", "first_name": "Ada", "last_name": "Lovelace", "tenant": "acme", "picture": "avatar-one.jpg"},
    {"username": "reader", "email": "reader@acme.com", "first_name": "Alan", "last_name": "Turing", "tenant": "acme", "picture": "avatar-two.jpg"},
    {"username": "buyer", "email": "buyer@globex.com", "first_name": "Grace", "last_name": "Hopper", "tenant": "globex", "picture": "avatar-three.jpg"},
]

# A picture is kept beside the seed and drawn for the very thing it shows, because a stock photograph picked by number shows an eclipse where an office was asked for.
PICTURES = pathlib.Path(__file__).resolve().parent.parent / "extras" / "seed"


class Picture:
    """The bytes of a picture kept beside the seed, shaped as what the upload service takes, so a seeded file is stored exactly as an operator's upload is."""

    def __init__(self, filename: str, body: bytes):
        self.filename = filename
        self.content_type = "image/jpeg"
        self.stream = BytesIO(body)

    async def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)


class SeedService:
    """The one way to get a local database worth developing against, filled from nothing in a single pass."""

    async def run(self, db: AsyncSession) -> dict:
        brands = await self.seed_brands(db)
        administrator = await self.seed_administrator(db)
        languages = await self.seed_languages(db)
        countries = await self.seed_countries(db)

        currencies = await self.seed_currencies(db)
        contents = await self.seed_contents(db, languages)
        banners = await self.seed_banners(db, brands)
        galleries = await self.seed_galleries(db, languages)
        products = await self.seed_products(db, currencies)

        entitlements = await self.seed_entitlements(db, brands, products, currencies)
        plans = await self.seed_plans(db, entitlements, languages)

        members = await self.seed_members(db, brands, languages)
        purchases = await self.seed_purchases(db, brands, members, products)
        integrations = await self.seed_integrations(db, brands)
        subscriptions = await self.seed_subscriptions(db, brands, plans, members, integrations)

        await self.seed_events(db, subscriptions)
        grants = await self.activate(db, subscriptions)

        return {
            "brands": len(brands),
            "administrator": administrator.username,
            "languages": len(languages),
            "countries": len(countries),
            "contents": len(contents),
            "banners": len(banners),
            "galleries": len(galleries),
            "currencies": len(currencies),
            "products": len(products),
            "plans": len(plans),
            "members": len(members),
            "purchases": len(purchases),
            "subscriptions": len(subscriptions),
            "grants": len(grants),
        }

    async def photograph(self, db: AsyncSession, purpose: UploadPurpose, picture: str, label: str) -> str:
        """A seeded picture walks the very path an operator's upload walks, so the folder, the name, the crop and the webp are the ones the purpose declares."""
        found = PICTURES / picture

        if not found.is_file():
            raise RuntimeError(f"{found} is missing, and a seed draws nothing of its own to hide it")

        stored = await upload_service.store(db, purpose, Picture(f"{slugify(label, 80)}.jpg", found.read_bytes()))

        # The row that names it is written in the same pass, so the picture is spoken for the moment it lands.
        await upload_service.claim(db, [stored["key"]])

        return stored["key"]

    async def seed_brands(self, db: AsyncSession) -> dict[str, Brand]:
        """An instance that serves one brand writes no tenant, and everything seeded into it lands in the scope every reader reaches."""
        if not settings.multi_tenant:
            return {TENANTS[0]["code"]: brand.of(None)}

        brands = {}

        for entry in TENANTS:
            tenant = Tenant(code=entry["code"], name=entry["name"], domain=entry["domain"], email_contact=f"contact@{entry['domain']}", email_administrative=f"admin@{entry['domain']}")
            db.add(tenant)
            await db.commit()
            brands[entry["code"]] = brand.of(tenant)

        return brands

    async def seed_administrator(self, db: AsyncSession) -> User:
        return await user_service.create(db, {**ADMIN, "role": UserRole.ADMINISTRATOR, "status": UserStatus.ACTIVE})

    async def seed_languages(self, db: AsyncSession) -> list[Language]:
        languages = [Language(name=name, native_name=native, code_iso_639_1=code, code_iso_language=locale) for name, native, code, locale in LANGUAGES]

        db.add_all(languages)
        await db.commit()

        return languages

    async def seed_countries(self, db: AsyncSession) -> list[Country]:
        countries = [Country(name=name, code_iso_3166_1=code, postal_code_provider=POSTAL_CODE_PROVIDERS.get(code), phone_mask=PHONE_MASKS.get(code)) for code, name in COUNTRIES]

        db.add_all(countries)
        await db.commit()

        return countries

    def language_of(self, languages: list[Language], code: str | None) -> Language | None:
        return next((language for language in languages if language.code_iso_639_1 == code), None)

    async def seed_contents(self, db: AsyncSession, languages: list[Language]) -> list[Content]:
        categories = {tag: ContentCategory(name=name, tag=tag) for name, tag in CONTENT_CATEGORIES}
        db.add_all(categories.values())
        await db.commit()

        contents = []

        for entry in CONTENTS:
            language = self.language_of(languages, entry["language"])
            content = Content(tenant_id=None, category_id=categories[entry["category"]].id, language_id=language.id, title=entry["title"], tag=entry["tag"], content=entry["body"], published_at=now().date())
            db.add(content)
            contents.append(content)

        await db.commit()

        return contents

    async def seed_banners(self, db: AsyncSession, brands: dict[str, Brand]) -> list[Banner]:
        banners = []

        for entry in BANNERS:
            banner = Banner(tenant_id=brands[TENANTS[0]["code"]].id, placement=entry["placement"], title=entry["title"], url=entry["url"], position=entry["position"], image=await self.photograph(db, UploadPurpose.BANNER, entry["picture"], entry["title"]))
            db.add(banner)
            banners.append(banner)

        await db.commit()

        return banners

    async def seed_galleries(self, db: AsyncSession, languages: list[Language]) -> list[Gallery]:
        galleries = []

        for index, entry in enumerate(GALLERIES):
            language = self.language_of(languages, entry["language"])
            gallery = Gallery(tenant_id=None, language_id=language.id if language else None, title=entry["title"], tag=entry["tag"], description=f"{entry['title']} in pictures", published_at=now().date(), position=index)
            db.add(gallery)
            await db.commit()

            for position, caption in enumerate(entry["photos"]):
                db.add(GalleryPhoto(gallery_id=gallery.id, image=await self.photograph(db, UploadPurpose.GALLERY_PHOTO, entry["pictures"][position], caption), caption=caption, position=position))

            await db.commit()
            galleries.append(gallery)

        return galleries

    async def seed_currencies(self, db: AsyncSession) -> dict[str, Currency]:
        currencies = {}

        for position, entry in enumerate(CURRENCIES):
            currency = Currency(tenant_id=None, code=entry["code"], name=entry["name"], symbol=entry["symbol"], position=position)
            db.add(currency)
            currencies[entry["code"]] = currency

        await db.commit()

        return currencies

    async def seed_products(self, db: AsyncSession, currencies: dict[str, Currency]) -> list[Product]:
        products = []

        for index, entry in enumerate(PRODUCTS):
            product = Product(
                tenant_id=None,
                name=entry["name"],
                slug=entry["name"].lower().replace(" ", "-"),
                description=f"<p>{entry['name']}</p>",
                image=await self.photograph(db, UploadPurpose.PRODUCT_IMAGE, entry["picture"], entry["name"]),
                currency="USD",
                price=entry["price"],
                credits=entry["credits"],
                credits_currency_id=currencies[entry["currency"]].id if entry["currency"] else None,
                featured=entry["featured"],
                position=index,
            )
            db.add(product)
            products.append(product)

        await db.commit()

        return products

    async def seed_entitlements(self, db: AsyncSession, brands: dict[str, Brand], products: list[Product], currencies: dict[str, Currency]) -> list[Entitlement]:
        entitlements = []

        for owner in brands.values():
            entitlement = Entitlement(tenant_id=owner.id, code="member", name="Membership", description="What a subscription of this brand opens")
            db.add(entitlement)
            await db.commit()

            db.add(Benefit(entitlement_id=entitlement.id, type=BenefitType.ACCESS, target="member", quantity=1, cadence=BenefitCadence.ON_ACTIVATION))
            db.add(Benefit(entitlement_id=entitlement.id, type=BenefitType.CREDIT, target="monthly-coins", currency_id=currencies["coin"].id, quantity=50, cadence=BenefitCadence.RECURRING, interval_unit=IntervalUnit.MONTH, interval_value=1))
            db.add(Benefit(entitlement_id=entitlement.id, type=BenefitType.PRODUCT, product_id=products[-1].id, target="handbook", quantity=1, cadence=BenefitCadence.ONCE_PER_USER))

            await db.commit()
            entitlements.append(entitlement)

        return entitlements

    async def seed_plans(self, db: AsyncSession, entitlements: list[Entitlement], languages: list[Language]) -> list[Plan]:
        plans = []

        for entitlement in entitlements:
            for position, entry in enumerate(PLANS):
                for market in entry["markets"]:
                    plan = Plan(
                        tenant_id=entitlement.tenant_id,
                        language_id=self.language_of(languages, market["language"]).id,
                        code=entry["code"],
                        name=market["name"],
                        description=f"<p>{market['lead']}</p>",
                        currency=market["currency"],
                        price=market["price"],
                        billing_interval_unit=entry["unit"],
                        billing_interval_value=entry["value"],
                        resume_delivery_policy=ResumeDeliveryPolicy.SAME_CYCLE,
                        featured=entry["featured"],
                        image=await self.photograph(db, UploadPurpose.PLAN_IMAGE, entry["picture"], market["name"]),
                        position=position,
                    )
                    db.add(plan)
                    await db.commit()

                    db.add(PlanEntitlement(plan_id=plan.id, entitlement_id=entitlement.id))
                    plans.append(plan)

        await db.commit()

        return plans

    async def seed_members(self, db: AsyncSession, brands: dict[str, Brand], languages: list[Language]) -> list[User]:
        english = self.language_of(languages, "en")
        members = []

        for entry in [entry for entry in MEMBERS if entry["tenant"] in brands]:
            member = await user_service.create(db, {"tenant_id": brands[entry["tenant"]].id, "language_id": english.id, "username": entry["username"], "email": entry["email"], "password": "member123", "first_name": entry["first_name"], "last_name": entry["last_name"]})
            member.avatar = await self.photograph(db, UploadPurpose.AVATAR, entry["picture"], entry["username"])
            db.add(UserAddress(user_id=member.id, type=UserAddressType.MAIN, line1="221B Baker Street", street_number="221", city="London", state="London", postal_code="NW16XE", country_code="GB"))
            members.append(member)

        await db.commit()

        return members

    async def seed_purchases(self, db: AsyncSession, brands: dict[str, Brand], members: list[User], products: list[Product]) -> list[Purchase]:
        purchases = []

        for member, product in zip(members, products):
            owner = next(owner for owner in brands.values() if owner.id == member.tenant_id)
            purchase = await commerce_service.open_purchase(db, owner, member, product, None)
            await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID, f"seed-{secrets.token_hex(8)}")
            purchases.append(purchase)

        return purchases

    async def seed_integrations(self, db: AsyncSession, brands: dict[str, Brand]) -> dict[str, Integration]:
        integrations = {}

        for code, owner in brands.items():
            integration = Integration(tenant_id=owner.id, provider=Provider.STRIPE, environment=Environment.SANDBOX, webhook_key=secrets.token_urlsafe(32), stripe_api_key_encrypted=encrypt("sk-local-worth-nothing"), stripe_webhook_secret_encrypted=encrypt("whsec-local-worth-nothing"))
            db.add(integration)
            integrations[code] = integration

        await db.commit()

        return integrations

    async def seed_subscriptions(self, db: AsyncSession, brands: dict[str, Brand], plans: list[Plan], members: list[User], integrations: dict[str, Integration]) -> list[Subscription]:
        moment = now()
        subscriptions = []

        for member in members:
            plan = next(plan for plan in plans if plan.tenant_id == member.tenant_id)
            code = next(code for code, owner in brands.items() if owner.id == member.tenant_id)

            subscription = Subscription(
                tenant_id=member.tenant_id,
                user_id=member.id,
                plan_id=plan.id,
                integration_id=integrations[code].id,
                external_id=f"seed-{secrets.token_hex(8)}",
                status=SubscriptionStatus.ACTIVE,
                environment=Environment.SANDBOX,
                started_at=moment - timedelta(days=30),
                current_period_started_at=moment - timedelta(days=30),
                current_period_ends_at=moment + timedelta(days=1),
                access_until=moment + timedelta(days=1),
            )
            db.add(subscription)
            subscriptions.append(subscription)

        await db.commit()

        return subscriptions

    async def seed_events(self, db: AsyncSession, subscriptions: list[Subscription]) -> None:
        for subscription in subscriptions:
            db.add(
                WebhookEvent(
                    tenant_id=subscription.tenant_id,
                    integration_id=subscription.integration_id,
                    subscription_id=subscription.id,
                    user_id=subscription.user_id,
                    external_event_id=f"seed-{secrets.token_hex(8)}",
                    payload_hash=secrets.token_hex(16),
                    action=NormalizedAction.ACTIVATE,
                    status=WebhookEventStatus.COMPLETED,
                    payload={"seed": True},
                    amount=Decimal("19.90"),
                    currency="USD",
                    occurred_at=now(),
                )
            )

        await db.commit()

    async def activate(self, db: AsyncSession, subscriptions: list[Subscription]) -> list:
        grants = []

        for subscription in subscriptions:
            grants.extend(await delivery_service.activate(db, subscription))

        await db.commit()

        return grants


seed_service = SeedService()


async def discard_media() -> int:
    """A database built from nothing leaves every file the old one pointed at orphaned, so the storage of this machine is emptied with it."""
    discarded = 0

    async for key, _ in storage.walk():
        await storage.delete(key)
        discarded += 1

    return discarded


def run_command(confirmed: bool, database: str) -> int:
    """The seed owns the whole database, so it is refused where the data is not disposable."""
    if settings.environment != "dev":
        print(f"the seed only runs in dev and this is {settings.environment}")

        return 1

    if not confirmed:
        print(f"this would rebuild {database} and fill it from scratch")
        print("run it again with --yes once you are sure")

        return 1

    run_scoped(recreate_schema())
    run_scoped(discard_media())

    async def fill():
        async with AsyncSessionLocal() as session:
            return await seed_service.run(session)

    for name, value in run_scoped(fill()).items():
        print(f"{name}: {value}")

    return 0
