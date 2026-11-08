# what both installers offer: languages, keyboards, the install steps
import glob


LANGUAGES = [
    ("English (United States)", "en_US"), ("English (United Kingdom)", "en_GB"), ("Français", "fr_FR"),
    ("Deutsch", "de_DE"), ("Español", "es_ES"), ("Español (México)", "es_MX"), ("Italiano", "it_IT"),
    ("Português (Brasil)", "pt_BR"), ("Português", "pt_PT"), ("Nederlands", "nl_NL"), ("Polski", "pl_PL"),
    ("Türkçe", "tr_TR"), ("Русский", "ru_RU"), ("Українська", "uk_UA"), ("العربية", "ar_MA"), ("العربية (مصر)", "ar_EG"),
    ("Svenska", "sv_SE"), ("Norsk bokmål", "nb_NO"), ("Dansk", "da_DK"), ("Suomi", "fi_FI"), ("Čeština", "cs_CZ"),
    ("Magyar", "hu_HU"), ("Română", "ro_RO"), ("Ελληνικά", "el_GR"), ("日本語", "ja_JP"), ("한국어", "ko_KR"),
    ("中文 (简体)", "zh_CN"), ("中文 (繁體)", "zh_TW"), ("हिन्दी", "hi_IN"), ("Bahasa Indonesia", "id_ID"),
    ("Tiếng Việt", "vi_VN"),
]
STEPS = ["Getting the drive ready", "Copying files", "Getting files ready for installation",
         "Installing the boot menu", "Finishing up"]


# the console's keymaps (kbd) aren't named like the xkb layouts: gb is uk, se is sv-latin1, and so on. one that
# doesn't exist leaves the console on us while the desktop gets the real layout, and a password with @ or " typed
# in jiggity doesn't work at the sign-in screen. not by name either: xkb's et is ethiopia, kbd's is estonia
CONSOLE = {"us": "us", "gb": "uk", "fr": "fr", "de": "de", "at": "de", "es": "es", "latam": "la-latin1",
           "it": "it", "br": "br-abnt2", "pt": "pt-latin1", "nl": "nl", "be": "be-latin1", "pl": "pl", "tr": "trq",
           "ru": "ru", "ua": "ua", "by": "by", "se": "sv-latin1", "no": "no-latin1", "dk": "dk-latin1", "fi": "fi",
           "is": "is-latin1", "ie": "ie", "cz": "cz", "sk": "sk-qwertz", "hu": "hu", "ro": "ro", "gr": "gr",
           "bg": "bg_bds-utf8", "mk": "mk", "rs": "sr-cy", "hr": "croat", "si": "slovene", "ee": "et", "lv": "lv",
           "lt": "lt", "il": "il", "ir": "fa", "jp": "jp106", "ch": "sg", "ca": "cf", "kz": "kazakh", "kg": "kyrgyz",
           "ge": "ge", "tj": "tj_alt-UTF8"}
CONSOLE_VARIANTS = {("us", "dvorak"): "dvorak", ("gb", "dvorak"): "dvorak-uk", ("es", "dvorak"): "dvorak-es",
                    ("fr", "dvorak"): "dvorak-fr", ("de", "nodeadkeys"): "de-latin1-nodeadkeys",
                    ("fr", "bepo"): "fr-bepo", ("ch", "fr"): "fr_CH", ("tr", "f"): "trf",
                    ("br", "nodeadkeys"): "br-abnt2", ("ru", "phonetic"): "ru"}


def console_keymap(layout, variant=""):
    # the closest console keymap there is here, us when there's none (arabic, hindi, chinese...)
    for name in (CONSOLE_VARIANTS.get((layout, variant)), CONSOLE.get(layout)):
        if name and any(glob.glob("%s/**/%s.map*" % (d, name), recursive=True)
                        for d in ("/usr/share/kbd/keymaps", "/usr/share/keymaps")):
            return name
    return "us"


def keyboards():
    out, section = [], None
    try:
        lines = open("/usr/share/X11/xkb/rules/base.lst").read().splitlines()
    except OSError:
        return [("English (US)", "us", "")]
    for line in lines:
        if line.startswith("!"):
            section = line[1:].strip()
            continue
        if not line.strip():
            continue
        name, desc = line.split(None, 1)
        if section == "layout":
            out.append((desc.strip(), name, ""))
        elif section == "variant":
            layout, desc = desc.split(":", 1)
            out.append((desc.strip(), layout, name))
    return sorted(out, key=lambda k: k[0].lower())
