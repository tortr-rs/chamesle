# what both installers offer: languages, keyboards, the install steps


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
