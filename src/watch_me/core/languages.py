"""Languages the user can pick for the outputs of an instruction template.

The names are English because they go into an English sentence of the template
("all outputs will be written in Czech"). ``ALL_LANGUAGES`` holds one plain name for
every ISO 639-1 language, sorted alphabetically; ``TOP_LANGUAGES`` are offered above
it, ``DEFAULT_LANGUAGE`` is selected when nothing says otherwise.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "English"
TOP_LANGUAGES: tuple[str, ...] = ("English", "Czech")

# fmt: off
ALL_LANGUAGES: tuple[str, ...] = (
    "Abkhazian", "Afar", "Afrikaans", "Akan", "Albanian", "Amharic", "Arabic", "Aragonese",
    "Armenian", "Assamese", "Avaric", "Avestan", "Aymara", "Azerbaijani", "Bambara", "Bashkir",
    "Basque", "Belarusian", "Bengali", "Bislama", "Bosnian", "Breton", "Bulgarian", "Burmese",
    "Catalan", "Chamorro", "Chechen", "Chichewa", "Chinese", "Church Slavonic", "Chuvash",
    "Cornish", "Corsican", "Cree", "Croatian", "Czech", "Danish", "Divehi", "Dutch", "Dzongkha",
    "English", "Esperanto", "Estonian", "Ewe", "Faroese", "Fijian", "Finnish", "French", "Fulah",
    "Galician", "Ganda", "Georgian", "German", "Greek", "Guarani", "Gujarati", "Haitian Creole",
    "Hausa", "Hebrew", "Herero", "Hindi", "Hiri Motu", "Hungarian", "Icelandic", "Ido", "Igbo",
    "Indonesian", "Interlingua", "Interlingue", "Inuktitut", "Inupiaq", "Irish", "Italian",
    "Japanese", "Javanese", "Kalaallisut", "Kannada", "Kanuri", "Kashmiri", "Kazakh", "Khmer",
    "Kikuyu", "Kinyarwanda", "Kirundi", "Komi", "Kongo", "Korean", "Kuanyama", "Kurdish", "Kyrgyz",
    "Lao", "Latin", "Latvian", "Limburgish", "Lingala", "Lithuanian", "Luba-Katanga",
    "Luxembourgish", "Macedonian", "Malagasy", "Malay", "Malayalam", "Maltese", "Manx", "Maori",
    "Marathi", "Marshallese", "Mongolian", "Nauru", "Navajo", "Ndonga", "Nepali", "North Ndebele",
    "Northern Sami", "Norwegian", "Norwegian Bokmål", "Norwegian Nynorsk", "Occitan", "Odia",
    "Ojibwa", "Oromo", "Ossetian", "Pali", "Pashto", "Persian", "Polish", "Portuguese", "Punjabi",
    "Quechua", "Romanian", "Romansh", "Russian", "Samoan", "Sango", "Sanskrit", "Sardinian",
    "Scottish Gaelic", "Serbian", "Shona", "Sichuan Yi", "Sindhi", "Sinhala", "Slovak",
    "Slovenian", "Somali", "South Ndebele", "Southern Sotho", "Spanish", "Sundanese", "Swahili",
    "Swati", "Swedish", "Tagalog", "Tahitian", "Tajik", "Tamil", "Tatar", "Telugu", "Thai",
    "Tibetan", "Tigrinya", "Tongan", "Tsonga", "Tswana", "Turkish", "Turkmen", "Twi", "Ukrainian",
    "Urdu", "Uyghur", "Uzbek", "Venda", "Vietnamese", "Volapük", "Walloon", "Welsh",
    "Western Frisian", "Wolof", "Xhosa", "Yiddish", "Yoruba", "Zhuang", "Zulu",
)
# fmt: on

__all__ = ["ALL_LANGUAGES", "DEFAULT_LANGUAGE", "TOP_LANGUAGES"]
